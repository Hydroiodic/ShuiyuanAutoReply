import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

MemoryPostgresBase = declarative_base()


class MentionMemoryKey(MemoryPostgresBase):
    """ORM metadata for per-user mention memory namespaces."""

    __tablename__ = "mention_memory_key"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_key = Column(String(255), nullable=False, unique=True, index=True)
    first_seen_at = Column(DateTime, default=datetime.now, nullable=False)
    last_seen_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )
    last_query = Column(Text, nullable=True)

    def __repr__(self):
        return (
            "<MentionMemoryKey("
            f"memory_key={self.memory_key}, last_seen_at={self.last_seen_at}"
            ")>"
        )


def _env_flag(*names: str) -> bool:
    return any(
        os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
        for name in names
    )


def _to_sqlalchemy_async_url(conn_string: str) -> str:
    if conn_string.startswith("postgresql+psycopg://"):
        return conn_string
    if conn_string.startswith("postgresql://"):
        return "postgresql+psycopg://" + conn_string.removeprefix("postgresql://")
    if conn_string.startswith("postgres://"):
        return "postgresql+psycopg://" + conn_string.removeprefix("postgres://")
    return conn_string


def _to_psycopg_url(conn_string: str) -> str:
    if conn_string.startswith("postgresql+psycopg://"):
        return "postgresql://" + conn_string.removeprefix("postgresql+psycopg://")
    return conn_string


class AsyncPostgresMemoryDatabaseManager:
    """Postgres manager for LangMem/LangGraph store and memory metadata."""

    def __init__(self, conn_string: Optional[str] = None):
        self.conn_string = conn_string or self._conn_string_from_env()
        if not self.conn_string:
            raise ValueError("Please set POSTGRES_MEMORY_DB_URL or POSTGRES_DB_URL.")

        self.engine = create_async_engine(
            _to_sqlalchemy_async_url(self.conn_string),
            echo=False,
            pool_pre_ping=True,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @staticmethod
    def _conn_string_from_env() -> Optional[str]:
        return os.getenv("POSTGRES_MEMORY_DB_URL") or os.getenv("POSTGRES_DB_URL")

    @staticmethod
    def _strict_from_env() -> bool:
        return _env_flag("POSTGRES_MEMORY_STRICT", "POSTGRES_STRICT")

    async def initialize_schema(self) -> None:
        """Initialize memory metadata tables and the pgvector extension."""
        async with self.engine.begin() as conn:
            await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.run_sync(MemoryPostgresBase.metadata.create_all)

    def create_langgraph_store(
        self,
        *,
        embedding: Any,
        dims: int,
        fields: Optional[list[str]] = None,
    ):
        """Create the LangGraph AsyncPostgresStore used by LangMem."""
        from langgraph.store.postgres.aio import AsyncPostgresStore

        return AsyncPostgresStore.from_conn_string(
            _to_psycopg_url(self.conn_string),
            index={
                "dims": dims,
                "embed": embedding,
                "fields": fields or ["content"],
            },
        )

    async def touch_mention_memory_key(
        self,
        memory_key: str,
        *,
        query: Optional[str] = None,
    ) -> None:
        """Record lightweight ORM metadata for a memory namespace."""
        async with self.async_session() as session:
            result = await session.execute(
                select(MentionMemoryKey).where(
                    MentionMemoryKey.memory_key == memory_key
                )
            )
            row = result.scalar_one_or_none()

            if row is None:
                row = MentionMemoryKey(memory_key=memory_key)
                session.add(row)

            row.last_seen_at = datetime.now()
            row.last_query = self._trim_query(query)
            await session.commit()

    async def close(self) -> None:
        await self.engine.dispose()

    @staticmethod
    def _trim_query(query: Optional[str], limit: int = 512) -> Optional[str]:
        if query is None:
            return None
        return query[:limit]


_global_async_postgres_memory_manager: Optional[AsyncPostgresMemoryDatabaseManager] = (
    None
)
_global_async_postgres_memory_manager_lock: Optional[asyncio.Lock] = None


def _get_global_async_postgres_memory_manager_lock() -> asyncio.Lock:
    global _global_async_postgres_memory_manager_lock
    if _global_async_postgres_memory_manager_lock is None:
        _global_async_postgres_memory_manager_lock = asyncio.Lock()
    return _global_async_postgres_memory_manager_lock


async def create_global_async_postgres_memory_manager(
    *,
    strict: Optional[bool] = None,
) -> Optional[AsyncPostgresMemoryDatabaseManager]:
    """Return the cached Postgres memory manager, or None when unset."""
    global _global_async_postgres_memory_manager

    if _global_async_postgres_memory_manager is not None:
        return _global_async_postgres_memory_manager

    conn_string = AsyncPostgresMemoryDatabaseManager._conn_string_from_env()
    is_strict = (
        AsyncPostgresMemoryDatabaseManager._strict_from_env()
        if strict is None
        else strict
    )
    if not conn_string:
        if is_strict:
            raise ValueError("Please set POSTGRES_MEMORY_DB_URL or POSTGRES_DB_URL.")
        logging.info("Postgres memory connection string is not configured")
        return None

    async with _get_global_async_postgres_memory_manager_lock():
        if _global_async_postgres_memory_manager is None:
            _global_async_postgres_memory_manager = AsyncPostgresMemoryDatabaseManager(
                conn_string
            )
        return _global_async_postgres_memory_manager
