import os
import asyncio
import ast
from urllib.parse import quote
from neomodel import (
    StructuredNode,
    StringProperty,
    DateTimeProperty,
    ArrayProperty,
    FloatProperty,
    config,
    db,
)
from pydantic import BaseModel
from typing import List, Optional
from sentence_transformers import SentenceTransformer


class SentenceNode(StructuredNode):
    text = StringProperty(required=True)
    embedding = ArrayProperty(FloatProperty(), required=True)
    category = StringProperty(default=None)
    created_at = DateTimeProperty(default_now=True)


class SentenceResponse(BaseModel):
    text: str
    category: Optional[str]
    score: float


class AsyncNeo4jDatabaseManager:

    def __init__(self, model_name: str = "moka-ai/m3e-base"):
        config.DATABASE_URL = self._build_database_url()
        self.model = SentenceTransformer(model_name)
        self.database_name = "neo4j"

    def _build_database_url(self) -> str:
        raw_url = os.getenv("NEO4J_DB_URL", "").strip()
        raw_auth = os.getenv("NEO4J_DB_AUTH", "").strip()

        if not raw_url:
            raise ValueError("NEO4J_DB_URL is not set")

        if "@" in raw_url or not raw_auth:
            return raw_url

        username, password = ast.literal_eval(raw_auth)

        if "://" in raw_url:
            scheme, rest = raw_url.split("://", 1)
            return f"{scheme}://{quote(str(username))}:{quote(str(password))}@{rest}"

        return f"bolt://{quote(str(username))}:{quote(str(password))}@{raw_url}"

    def _run_cypher(self, query: str, params: Optional[dict] = None):
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
            """
            CREATE VECTOR INDEX sentence_embeddings IF NOT EXISTS
            FOR (n:SentenceNode) ON n.embedding
            OPTIONS {indexConfig: {`vector.dimensions`: 768}}
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
            RETURN node.text AS text, node.category AS category, score
            ORDER BY score DESC
            """,
            {
                "embedding": embedding,
                "top_k": top_k,
            },
        )
        return [SentenceResponse(text=r[0], category=r[1], score=r[2]) for r in rows]


global_async_neo4j_manager = AsyncNeo4jDatabaseManager()
