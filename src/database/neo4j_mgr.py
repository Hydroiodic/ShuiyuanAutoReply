import os
import asyncio
from datetime import datetime
from neo4j import AsyncGraphDatabase
from pydantic import BaseModel
from typing import List, Optional
from sentence_transformers import SentenceTransformer


class SentenceModel(BaseModel):
    text: str
    embedding: List[float]
    category: Optional[str] = None
    created_at: datetime = datetime.now()


class SentenceResponse(BaseModel):
    text: str
    category: Optional[str]
    score: float


class AsyncNeo4jDatabaseManager:

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.driver = AsyncGraphDatabase.driver(
            uri=os.getenv("NEO4J_DB_URL"),
            auth=eval(os.getenv("NEO4J_DB_AUTH")),
        )
        self.model = SentenceTransformer(model_name)
        self.database_name = "neo4j"

    async def _ensure_database_exists(self) -> None:
        """
        Ensure the target Neo4j database exists, create it if not.
        Must be run against the `system` database.
        """
        async with self.driver.session(database="system") as session:
            await session.run(f"CREATE DATABASE `{self.database_name}` IF NOT EXISTS")

    async def initialize(self):
        """
        Asynchronously initialize the database by creating the vector index.
        """
        # Ensure the database exists
        # NOTE: This is not available in Neo4j Aura Free tier so it's commented out.
        # await self._ensure_database_exists()

        # Create the vector index for sentence embeddings
        async with self.driver.session(database=self.database_name) as session:
            await session.run(
                """
                CREATE VECTOR INDEX sentence_embeddings IF NOT EXISTS
                FOR (n:Sentence) ON n.embedding 
                OPTIONS {indexConfig: {`vector.dimensions`: 384}}
                """
            )

    async def _store_sentence(self, sentence: SentenceModel):
        """
        Asynchronously store a sentence with its embedding into the database.
        """
        async with self.driver.session(database=self.database_name) as session:
            result = await session.run(
                """
                CREATE (s:Sentence {
                    text: $text,
                    embedding: $embedding,
                    category: $category,
                    created_at: datetime()
                })
                RETURN s.text as text
                """,
                text=sentence.text,
                embedding=sentence.embedding,
                category=sentence.category,
            )
            return await result.single()

    async def store_sentences(self, sentences: List[str]):
        """
        Asynchronously compute the embedding and store the sentence.
        """
        # Encode the sentence to get its embedding
        embeddings = self.model.encode(sentences)

        # Create and store SentenceModel instances
        store_routine = []
        for sentence, embedding in zip(sentences, embeddings):
            # Create SentenceModel instance and prepare store routine
            sentence_model = SentenceModel(text=sentence, embedding=embedding.tolist())
            store_routine.append(self._store_sentence(sentence_model))
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

        # Perform the vector similarity search
        async with self.driver.session(database=self.database_name) as session:
            result = await session.run(
                """
                CALL db.index.vector.queryNodes('sentence_embeddings', $top_k, $embedding)
                YIELD node, score
                RETURN node.text AS text, node.category AS category, score
                ORDER BY score DESC
                """,
                embedding=embedding,
                top_k=top_k,
            )

            records = await result.values()
            return [
                SentenceResponse(text=r[0], category=r[1], score=r[2]) for r in records
            ]

    async def close(self):
        """
        Asynchronously close the database connection.
        """
        await self.driver.close()


global_async_neo4j_manager = AsyncNeo4jDatabaseManager()
