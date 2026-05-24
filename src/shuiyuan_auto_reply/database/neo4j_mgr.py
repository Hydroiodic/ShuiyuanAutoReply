import ast
import asyncio
import logging
import os
from typing import Dict, List, Optional
from urllib.parse import quote

from neomodel import (
    ArrayProperty,
    DateTimeProperty,
    FloatProperty,
    StringProperty,
    StructuredNode,
    config,
    db,
)
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from shuiyuan_auto_reply.constants import settings


class SentenceNode(StructuredNode):
    __label__ = "Sentence"

    text = StringProperty(required=True)
    embedding = ArrayProperty(FloatProperty(), required=True)
    created_at = DateTimeProperty(default_now=True)


class SentenceResponse(BaseModel):
    text: str
    score: float


class AsyncNeo4jDatabaseManager:

    def __init__(
        self,
        model_name: str = "moka-ai/m3e-base",
        database_url: Optional[str] = None,
        database_auth: Optional[str] = None,
    ):
        self.database_url = database_url or self._database_url_from_env()
        if not self.database_url:
            raise ValueError("Please set the NEO4J_DB_URL environment variable.")

        self.database_auth = database_auth
        if self.database_auth is None:
            self.database_auth = os.getenv("NEO4J_DB_AUTH")

        self.model = SentenceTransformer(model_name)
        self.embedding_dims = settings.embedding_dims
        self.database_name = "neo4j"
        self._configured = False

    def _ensure_configured(self) -> None:
        if self._configured:
            return

        config.DATABASE_URL = self._build_database_url()
        self._configured = True

    @staticmethod
    def _database_url_from_env() -> Optional[str]:
        return os.getenv("NEO4J_DB_URL")

    @staticmethod
    def _strict_from_env() -> bool:
        return os.getenv("NEO4J_STRICT", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _build_database_url(self) -> str:
        raw_url = self.database_url.strip()
        raw_auth = (self.database_auth or "").strip()

        if not raw_url:
            raise ValueError("NEO4J_DB_URL is not set")

        if "@" in raw_url or not raw_auth:
            return raw_url

        username, password = ast.literal_eval(raw_auth)

        if "://" in raw_url:
            scheme, rest = raw_url.split("://", 1)
            return f"{scheme}://{quote(str(username))}:{quote(str(password))}@{rest}"

        return f"bolt://{quote(str(username))}:{quote(str(password))}@{raw_url}"

    def _run_cypher(self, query: str, params: Optional[Dict] = None):
        self._ensure_configured()
        return db.cypher_query(query, params=params or {})

    async def initialize(self):
        """
        Asynchronously initialize the database by creating the vector index.
        """
        # Manage vector index explicitly
        # because this is not yet represented by neomodel schema.
        await asyncio.to_thread(
            self._run_cypher,
            """
            DROP INDEX sentence_embeddings IF EXISTS
            """,
        )
        await asyncio.to_thread(
            self._run_cypher,
            f"""
            CREATE VECTOR INDEX sentence_embeddings IF NOT EXISTS
            FOR (n:Sentence) ON n.embedding
            OPTIONS {{indexConfig: {{`vector.dimensions`: {self.embedding_dims}}}}}
            """,
        )

    async def _store_sentence(self, text: str, embedding: List[float]):
        """
        Asynchronously store a sentence with its embedding into the database.
        """
        return await asyncio.to_thread(
            lambda: SentenceNode(text=text, embedding=embedding).save()
        )

    async def store_sentences(self, sentences: List[str]):
        """
        Asynchronously compute the embedding and store the sentence.
        """
        # Encode the sentence to get its embedding
        embeddings = self.model.encode(sentences)

        # Batch writes to avoid creating too many concurrent tasks.
        store_routine = []
        for sentence, embedding in zip(sentences, embeddings):
            store_routine.append(self._store_sentence(sentence, embedding.tolist()))
            # Every 100 sentences, wait for current batch to finish
            if len(store_routine) >= 100:
                await asyncio.gather(*store_routine)
                store_routine = []
        # Wait for any remaining routines to complete
        if store_routine:
            await asyncio.gather(*store_routine)

    async def search_similar(
        self,
        query_text: str,
        top_k: int = 10,
    ) -> List[SentenceResponse]:
        """
        Asynchronously search for similar sentences based on the query text.
        """
        # Calculate embedding for the query text
        embedding = self.model.encode([query_text])[0].tolist()

        # Vector query is done with Cypher, then mapped into typed response objects.
        rows, _ = await asyncio.to_thread(
            self._run_cypher,
            """
            CALL db.index.vector.queryNodes('sentence_embeddings', $top_k, $embedding)
            YIELD node, score
            RETURN node.text AS text, score
            ORDER BY score DESC
            """,
            {
                "embedding": embedding,
                "top_k": top_k,
            },
        )
        return [SentenceResponse(text=r[0], score=r[1]) for r in rows]


_global_async_neo4j_manager: Optional[AsyncNeo4jDatabaseManager] = None
_global_async_neo4j_manager_lock: Optional[asyncio.Lock] = None


def _get_global_async_neo4j_manager_lock() -> asyncio.Lock:
    global _global_async_neo4j_manager_lock
    if _global_async_neo4j_manager_lock is None:
        _global_async_neo4j_manager_lock = asyncio.Lock()
    return _global_async_neo4j_manager_lock


async def create_global_async_neo4j_manager(
    *,
    strict: Optional[bool] = None,
) -> Optional[AsyncNeo4jDatabaseManager]:
    """Return the cached Neo4j manager, or None when NEO4J_DB_URL is unset."""
    global _global_async_neo4j_manager

    if _global_async_neo4j_manager is not None:
        return _global_async_neo4j_manager

    database_url = AsyncNeo4jDatabaseManager._database_url_from_env()
    is_strict = (
        AsyncNeo4jDatabaseManager._strict_from_env() if strict is None else strict
    )
    if not database_url:
        if is_strict:
            raise ValueError("Please set the NEO4J_DB_URL environment variable.")
        logging.info("NEO4J_DB_URL is not configured")
        return None

    async with _get_global_async_neo4j_manager_lock():
        if _global_async_neo4j_manager is None:
            _global_async_neo4j_manager = AsyncNeo4jDatabaseManager(
                database_url=database_url
            )
        return _global_async_neo4j_manager
