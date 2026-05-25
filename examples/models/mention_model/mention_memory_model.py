import json
import logging
import os
import uuid
from contextlib import AbstractAsyncContextManager
from typing import Dict, List, Literal, Optional, Tuple

from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.store.base import BaseStore, SearchItem
from pydantic import BaseModel, Field

from shuiyuan_auto_reply.constants import settings
from shuiyuan_auto_reply.database.postgres_memory_mgr import (
    AsyncPostgresMemoryDatabaseManager,
    create_global_async_postgres_memory_manager,
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class SearchMentionMemoryInput(BaseModel):
    target_user_id: Optional[int] = Field(
        default=None,
        description=(
            "Stable Shuiyuan forum user.id whose mention memories should be searched. "
            "Use the current prompt user_id for the current user; omit this field "
            "to search all mention memory namespaces when the target user is unknown."
        ),
    )
    query: Optional[str] = Field(
        default=None,
        description=(
            "Semantic search query. Use a concise query about the relevant stable "
            "fact or preference; omit only when listing memories without a specific query."
        ),
    )
    limit: int = Field(
        default=5,
        description="Maximum number of memories to return. Values are clamped to 1..20.",
    )
    offset: int = Field(
        default=0,
        description="Number of matching memories to skip before returning results.",
    )


class ManageMentionMemoryInput(BaseModel):
    target_user_id: int = Field(
        description=(
            "Stable Shuiyuan forum user.id whose mention memory namespace should be "
            "modified. Do not use username as the key."
        )
    )
    action: Literal["create", "update", "delete"] = Field(
        default="create",
        description=(
            "Memory operation. create needs content and no memory_id; update needs "
            "memory_id and content; delete needs memory_id."
        ),
    )
    content: Optional[str] = Field(
        default=None,
        description=(
            "Short stable memory content to create or replace. Keep it reusable and "
            "third-person. Required for create/update and ignored for delete."
        ),
    )
    memory_id: Optional[str] = Field(
        default=None,
        description=(
            "Exact memory id returned by search_mention_memory. Required for "
            "update/delete and omitted for create."
        ),
    )


class MentionMemoryModel:
    """
    LangMem-backed long-term memory for mention replies.

    This class keeps LangMem/Postgres wiring out of the chat model so the graph
    only needs to ask for tools, a store, and formatted search results.
    """

    def __init__(self, embedding: Embeddings):
        self.embedding = embedding
        self.postgres: Optional[AsyncPostgresMemoryDatabaseManager] = None

        self.search_limit = int(os.getenv("LANGMEM_SEARCH_LIMIT", "5"))
        self.max_context_chars = int(os.getenv("LANGMEM_CONTEXT_MAX_CHARS", "1600"))
        self.strict = _env_flag("POSTGRES_MEMORY_STRICT", False) or _env_flag(
            "POSTGRES_STRICT", False
        )

        self.embedding_dims = settings.embedding_dims
        self.memory_config_key = "mention_memory_key"
        self.memory_namespace = "mention_memories"

        self.store: Optional[BaseStore] = None
        self.tools: List[BaseTool] = []
        self._store_context: Optional[AbstractAsyncContextManager[BaseStore]] = None
        self._initialized = False

    @property
    def enabled(self) -> bool:
        return self.store is not None

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self.postgres = await create_global_async_postgres_memory_manager(
            strict=self.strict
        )
        if self.postgres is None:
            logging.info(
                "Postgres memory database is not configured; skipping persistent mention memory"
            )
            return

        try:
            await self.postgres.initialize_schema()

            self._store_context = self.postgres.create_langgraph_store(
                embedding=self.embedding,
                dims=self.embedding_dims,
                fields=["content"],
            )
            self.store = await self._store_context.__aenter__()
            await self.store.setup()

            self.tools = self._create_tools()
            logging.info(
                "Initialized persistent mention memory with namespace=%s",
                self.namespace_template,
            )
        except Exception as exc:
            await self._close_store_context()
            self.store = None
            self.tools = []
            self._handle_init_error(
                "Failed to initialize persistent mention memory", exc
            )

    async def aclose(self) -> None:
        await self._close_store_context()
        self.store = None
        self.tools = []

    @property
    def namespace_template(self) -> Tuple[str, str]:
        return (self.memory_namespace, f"{{{self.memory_config_key}}}")

    def graph_config(self, memory_key: str) -> Dict[str, Dict[str, str]]:
        return {"configurable": {self.memory_config_key: memory_key}}

    @staticmethod
    def memory_key(user_id: int) -> str:
        if user_id is None:
            raise ValueError("user.id is required for mention memory")
        return str(user_id)

    def namespace_for_user(self, memory_key: str) -> Tuple[str, str]:
        return (self.memory_namespace, memory_key)

    def _create_tools(self) -> List[BaseTool]:
        return [
            StructuredTool.from_function(
                coroutine=self.search_mention_memory,
                name="search_mention_memory",
                args_schema=SearchMentionMemoryInput,
                description=(
                    "Search mention long-term memories. Use stable target_user_id "
                    "when known; omit target_user_id to search all mention memory "
                    "namespaces when the relevant user is unknown."
                ),
            ),
            StructuredTool.from_function(
                coroutine=self.manage_mention_memory,
                name="manage_mention_memory",
                args_schema=ManageMentionMemoryInput,
                description=(
                    "Create, update, or delete mention long-term memory by stable "
                    "target_user_id. Only store stable reusable facts or preferences. "
                    "Search first to get memory_id before update/delete."
                ),
            ),
        ]

    async def search_mention_memory(
        self,
        *,
        target_user_id: Optional[int] = None,
        query: Optional[str] = None,
        limit: int = 5,
        offset: int = 0,
    ) -> str:
        """
        Search mention long-term memories for a target forum user.

        Use the stable forum user.id as target_user_id. For the current user, use
        the current user_id from the prompt. Omit target_user_id to search all mention
        memory namespaces when the relevant user is unknown.

        :param target_user_id: Stable Shuiyuan forum user.id to search, or None to search globally.
        :param query: Semantic search query for stable facts or preferences.
        :param limit: Maximum number of memories to return; clamped to 1..20.
        :param offset: Number of matching memories to skip.
        :return: Formatted memory search results for the target user.
        """
        if not self.store:
            return "长期记忆未启用"

        query_text = query.strip() if query else None
        limit = self._normalize_limit(limit)
        offset = max(0, offset)
        namespace_prefix: Tuple[str, ...]
        memory_key: Optional[str] = None

        if target_user_id is None:
            namespace_prefix = (self.memory_namespace,)
        else:
            try:
                memory_key = self.memory_key(target_user_id)
            except ValueError as exc:
                return str(exc)
            namespace_prefix = self.namespace_for_user(memory_key)

        try:
            if memory_key is not None:
                await self._touch_memory_key(memory_key, query=query_text)
            items = await self.store.asearch(
                namespace_prefix,
                query=query_text,
                limit=limit,
                offset=offset,
            )
        except Exception:
            logging.exception(
                "Failed to search mention memories for target_user_id=%s",
                target_user_id,
            )
            return "长期记忆检索失败"

        if target_user_id is None:
            if not items:
                return "全局无相关长期记忆"
            return "全局长期记忆：\n" + self._format_memory_items(
                items,
                include_user_id=True,
            )

        if not items:
            return f"user_id={target_user_id} 无相关长期记忆"

        return (
            f"user_id={target_user_id} 长期记忆：\n{self._format_memory_items(items)}"
        )

    async def manage_mention_memory(
        self,
        *,
        target_user_id: int,
        action: Literal["create", "update", "delete"] = "create",
        content: Optional[str] = None,
        memory_id: Optional[str] = None,
    ) -> str:
        """
        Create, update, or delete mention long-term memory for a target user.

        Use target_user_id to choose the user's memory namespace. Create needs
        content and no memory_id. Update needs memory_id and content. Delete needs
        memory_id. Search first when updating or deleting so the memory_id is exact.

        :param target_user_id: Stable Shuiyuan forum user.id to modify.
        :param action: One of create, update, or delete.
        :param content: Short stable memory content for create/update.
        :param memory_id: Exact memory uuid for update/delete.
        :return: Operation result text.
        """
        if not self.store:
            return "长期记忆未启用"

        try:
            memory_key = self.memory_key(target_user_id)
        except ValueError as exc:
            return str(exc)

        if action not in {"create", "update", "delete"}:
            return "无效的长期记忆操作，只能是 create、update 或 delete"

        normalized_id = memory_id.strip() if memory_id else None
        normalized_content = content.strip() if content else None
        namespace = self.namespace_for_user(memory_key)

        try:
            if action == "create":
                if normalized_id:
                    return f"{action} 长期记忆时不要提供 memory_id"
                if not normalized_content:
                    return f"{action} 长期记忆需要提供 content"
                new_id = str(uuid.uuid4())
                await self.store.aput(
                    namespace,
                    key=new_id,
                    value={"content": normalized_content},
                )
                await self._touch_memory_key(memory_key, query=normalized_content)
                return f"created memory {new_id} for user_id={target_user_id}"

            if not normalized_id:
                return f"{action} 长期记忆需要提供 memory_id"

            existing = await self.store.aget(namespace, normalized_id)
            if existing is None:
                return f"user_id={target_user_id} 中没有找到 memory_id={normalized_id}"

            if action == "delete":
                await self.store.adelete(namespace, normalized_id)
                await self._touch_memory_key(
                    memory_key, query=f"delete:{normalized_id}"
                )
                return f"deleted memory {normalized_id} for user_id={target_user_id}"

            if not normalized_content:
                return f"{action} 长期记忆需要提供 content"

            await self.store.aput(
                namespace,
                key=normalized_id,
                value={"content": normalized_content},
            )
            await self._touch_memory_key(memory_key, query=normalized_content)
            return f"updated memory {normalized_id} for user_id={target_user_id}"
        except Exception:
            logging.exception(
                "Failed to %s mention memory for target_user_id=%s memory_id=%s",
                action,
                target_user_id,
                normalized_id,
            )
            return "长期记忆操作失败"

    async def _touch_memory_key(
        self,
        memory_key: str,
        *,
        query: Optional[str] = None,
    ) -> None:
        try:
            if self.postgres is not None:
                await self.postgres.touch_mention_memory_key(
                    memory_key,
                    query=query,
                )
        except Exception:
            logging.exception(
                "Failed to update mention memory metadata for user=%s",
                memory_key,
            )

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        return max(1, min(limit, 20))

    async def _close_store_context(self) -> None:
        if not self._store_context:
            return
        try:
            await self._store_context.__aexit__(None, None, None)
        finally:
            self._store_context = None

    def _handle_init_error(self, message: str, exc: Exception) -> None:
        if self.strict:
            raise RuntimeError(message) from exc
        logging.exception("%s; persistent mention memory disabled", message)

    def _format_memory_items(
        self,
        items: List[SearchItem],
        *,
        include_user_id: bool = False,
    ) -> str:
        lines = []
        used_chars = 0

        for index, item in enumerate(items, start=1):
            memory_id = getattr(item, "key", "<unknown>")
            content = self._extract_memory_content(item)
            if include_user_id:
                user_id = self._extract_user_id_from_item(item)
                line = f"{index}. user_id={user_id} id={memory_id}: {content}"
            else:
                line = f"{index}. id={memory_id}: {content}"
            line_chars = len(line) + (1 if lines else 0)

            if used_chars + line_chars > self.max_context_chars:
                break

            lines.append(line)
            used_chars += line_chars

        return "\n".join(lines) if lines else "无相关长期记忆"

    def _extract_user_id_from_item(self, item: SearchItem) -> str:
        namespace = getattr(item, "namespace", ())
        if (
            isinstance(namespace, (list, tuple))
            and len(namespace) >= 2
            and namespace[0] == self.memory_namespace
        ):
            return str(namespace[1])
        return "<unknown>"

    @staticmethod
    def _extract_memory_content(item: SearchItem) -> str:
        value = getattr(item, "value", item)

        if isinstance(value, dict):
            content = value.get("content", value.get("data", value))
        else:
            content = value

        if isinstance(content, str):
            return content.strip()

        try:
            return json.dumps(content, ensure_ascii=False, default=str)
        except TypeError:
            return str(content)
