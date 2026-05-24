import json
import logging
import os
from typing import Any, Optional

from langmem import create_manage_memory_tool, create_search_memory_tool

from shuiyuan_auto_reply.constants import settings
from shuiyuan_auto_reply.database.postgres_memory_mgr import (
    AsyncPostgresMemoryDatabaseManager,
    create_global_async_postgres_memory_manager,
)

MENTION_MEMORY_CONFIG_KEY = "mention_memory_key"
MENTION_MEMORY_NAMESPACE = ("mention_memories", f"{{{MENTION_MEMORY_CONFIG_KEY}}}")


MANAGE_MEMORY_INSTRUCTIONS = (
    "你可以管理当前论坛用户的长期记忆。仅在信息稳定、明确、以后会反复有用时调用："
    "用户明确要求记住/忘记某件事；用户表达了稳定偏好；已有记忆明显过期或错误。"
    "不要保存当前帖子全文、临时楼层上下文、工具输出原文、一次性的情绪反应、"
    "敏感政治/历史/暴力内容，或任何不需要长期保留的隐私信息。"
    "记忆应简短、可复用，并用第三人称描述用户偏好或稳定事实。"
)


SEARCH_MEMORY_INSTRUCTIONS = (
    "搜索当前论坛用户的长期记忆。通常系统已经会主动检索相关记忆；"
    "只有在需要更多用户偏好、历史要求或稳定事实时再调用。"
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class MentionMemoryModel:
    """
    LangMem-backed long-term memory for mention replies.

    This class keeps LangMem/Postgres wiring out of the chat model so the graph
    only needs to ask for tools, a store, and formatted search results.
    """

    def __init__(self, embedding: Any):
        self.embedding = embedding
        self.postgres: Optional[AsyncPostgresMemoryDatabaseManager] = None
        self.embedding_dims = settings.embedding_dims
        self.search_limit = int(os.getenv("LANGMEM_SEARCH_LIMIT", "5"))
        self.max_context_chars = int(os.getenv("LANGMEM_CONTEXT_MAX_CHARS", "1600"))
        self.strict = _env_flag("POSTGRES_MEMORY_STRICT", False) or _env_flag(
            "POSTGRES_STRICT", False
        )

        self.store: Optional[Any] = None
        self.tools: list[Any] = []
        self._store_context: Optional[Any] = None
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

            self.tools = [
                create_manage_memory_tool(
                    namespace=MENTION_MEMORY_NAMESPACE,
                    instructions=MANAGE_MEMORY_INSTRUCTIONS,
                    name="manage_mention_memory",
                ),
                create_search_memory_tool(
                    namespace=MENTION_MEMORY_NAMESPACE,
                    instructions=SEARCH_MEMORY_INSTRUCTIONS,
                    name="search_mention_memory",
                ),
            ]
            logging.info(
                "Initialized persistent mention memory with namespace=%s",
                MENTION_MEMORY_NAMESPACE,
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

    async def search_relevant_memories(
        self,
        memory_key: str,
        query: str,
    ) -> str:
        if not self.store:
            return "长期记忆未启用"

        try:
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

            items = await self.store.asearch(
                self.namespace_for_user(memory_key),
                query=query,
                limit=self.search_limit,
            )
        except Exception:
            logging.exception(
                "Failed to search mention memories for user=%s",
                memory_key,
            )
            return "长期记忆检索失败"

        if not items:
            return "无相关长期记忆"

        return self._format_memory_items(items)

    def graph_config(self, memory_key: str) -> dict[str, dict[str, str]]:
        return {"configurable": {MENTION_MEMORY_CONFIG_KEY: memory_key}}

    @staticmethod
    def memory_key(user_id: Any) -> str:
        if user_id is None:
            raise ValueError("user.id is required for mention memory")
        return str(user_id)

    @staticmethod
    def namespace_for_user(memory_key: str) -> tuple[str, str]:
        return ("mention_memories", memory_key)

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

    def _format_memory_items(self, items: list[Any]) -> str:
        lines = []
        used_chars = 0

        for index, item in enumerate(items, start=1):
            memory_id = getattr(item, "key", "<unknown>")
            content = self._extract_memory_content(item)
            line = f"{index}. id={memory_id}: {content}"
            line_chars = len(line) + (1 if lines else 0)

            if used_chars + line_chars > self.max_context_chars:
                break

            lines.append(line)
            used_chars += line_chars

        return "\n".join(lines) if lines else "无相关长期记忆"

    @staticmethod
    def _extract_memory_content(item: Any) -> str:
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
