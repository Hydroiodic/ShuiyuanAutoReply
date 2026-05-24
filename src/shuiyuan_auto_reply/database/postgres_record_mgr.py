import asyncio
import logging
import os
from datetime import datetime
from functools import wraps
from typing import Any, Callable, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, selectinload

RecordPostgresBase = declarative_base()


class User(RecordPostgresBase):
    """User model representing a user in the record system."""

    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True)
    last_update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    coin = Column(Integer, default=0)
    enable_record = Column(Integer, default=0)  # 0: disabled, 1: enabled
    allow_others = Column(Integer, default=0)  # 0: disallow, 1: allow

    records = relationship(
        "Record",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<User(user_id={self.user_id}, coin={self.coin}, "
            f"last_update_time={self.last_update_time})>"
        )


class Record(RecordPostgresBase):
    """Record model representing a user's record/quote."""

    __tablename__ = "record"

    record_id = Column(Integer, primary_key=True, autoincrement=True)
    record_str = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("user.user_id"), nullable=False)

    user = relationship("User", back_populates="records")

    def __repr__(self):
        return (
            f"<Record(record_id={self.record_id}, "
            f"record_str={self.record_str}, user_id={self.user_id})>"
        )


class Alias(RecordPostgresBase):
    """Alias model representing a user's alias."""

    __tablename__ = "alias"

    alias_id = Column(Integer, primary_key=True, autoincrement=True)
    alias_str = Column(String(255), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("user.user_id"), nullable=False)

    user = relationship("User")

    def __repr__(self):
        return (
            f"<Alias(alias_id={self.alias_id}, alias_str={self.alias_str}, "
            f"user_id={self.user_id})>"
        )


def _default_value(default: Any) -> Any:
    return default() if callable(default) else default


def _env_flag(*names: str) -> bool:
    return any(
        os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
        for name in names
    )


def _to_sqlalchemy_async_url(db_url: str) -> str:
    if db_url.startswith("postgresql+psycopg://"):
        return db_url
    if db_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + db_url.removeprefix("postgresql://")
    if db_url.startswith("postgres://"):
        return "postgresql+psycopg://" + db_url.removeprefix("postgres://")
    return db_url


def retry_postgres_record_operation(default: Any):
    """Retry a Postgres record operation and return a safe default."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await self._execute_with_retry(
                    lambda: func(self, *args, **kwargs)
                )
            except Exception as exc:
                logging.error(
                    "Failed to %s after retries: %s",
                    func.__name__,
                    exc,
                )
                return _default_value(default)

        return wrapper

    return decorator


class AsyncPostgresRecordDatabaseManager:
    """Asynchronous Postgres manager for record users, quotes, and aliases."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or self._db_url_from_env()
        if not self.db_url:
            raise ValueError(
                "Please set POSTGRES_RECORD_DB_URL, POSTGRES_DB_URL, or POSTGRES_URI."
            )

        self.engine = create_async_engine(
            _to_sqlalchemy_async_url(self.db_url),
            echo=False,
            pool_pre_ping=True,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @staticmethod
    def _db_url_from_env() -> Optional[str]:
        return (
            os.getenv("POSTGRES_RECORD_DB_URL")
            or os.getenv("POSTGRES_DB_URL")
            or os.getenv("POSTGRES_URI")
        )

    @staticmethod
    def _strict_from_env() -> bool:
        return _env_flag("POSTGRES_RECORD_STRICT", "POSTGRES_STRICT")

    @staticmethod
    async def _execute_with_retry(
        coro: Callable,
        retries: int = 3,
        delay: float = 1.0,
    ):
        """Execute a coroutine with retries on transient database failures."""
        last_error: Optional[Exception] = None
        for attempt in range(retries):
            try:
                return await coro()
            except Exception as exc:
                last_error = exc
                logging.warning("Attempt %d failed: %s", attempt + 1, exc)
                if attempt < retries - 1:
                    await asyncio.sleep(delay)

        logging.error("All retry attempts failed")
        if last_error is not None:
            raise last_error
        raise RuntimeError("All retry attempts failed")

    async def create_tables(self) -> None:
        """Create all record tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(RecordPostgresBase.metadata.create_all)
        logging.info("Postgres record tables created successfully")

    async def drop_tables(self) -> None:
        """Drop all record tables (use with caution)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(RecordPostgresBase.metadata.drop_all)
        logging.info("Postgres record tables dropped successfully")

    @retry_postgres_record_operation(default=None)
    async def add_user(self, user_id: int) -> Optional[User]:
        """Add a new user."""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                existing_user = result.scalar_one_or_none()

                if existing_user:
                    logging.warning("User with ID %s already exists", user_id)
                    return existing_user

                user = User(user_id=user_id)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user
            except Exception:
                await session.rollback()
                raise

    @retry_postgres_record_operation(default=None)
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            return result.scalar_one_or_none()

    @retry_postgres_record_operation(default=None)
    async def get_or_add_user(self, user_id: int) -> Optional[User]:
        """Get user by ID, create if it does not exist."""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if user:
                    return user

                user = User(user_id=user_id)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user
            except Exception:
                await session.rollback()
                raise

    @retry_postgres_record_operation(default=False)
    async def update_user(
        self,
        user_id: int,
        coin: Optional[int] = None,
        enable_record: Optional[int] = None,
        allow_others: Optional[int] = None,
    ) -> bool:
        """Update user information."""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    logging.warning("User with ID %s not found", user_id)
                    return False

                if coin is not None:
                    user.coin = coin
                if enable_record is not None:
                    user.enable_record = enable_record
                if allow_others is not None:
                    user.allow_others = allow_others

                await session.commit()
                return True
            except Exception:
                await session.rollback()
                raise

    @retry_postgres_record_operation(default=False)
    async def delete_user(self, user_id: int) -> bool:
        """Delete a user and all associated records."""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    logging.warning("User with ID %s not found", user_id)
                    return False

                await session.delete(user)
                await session.commit()
                return True
            except Exception:
                await session.rollback()
                raise

    @retry_postgres_record_operation(default=list)
    async def get_all_users(self) -> List[User]:
        """Get all users."""
        async with self.async_session() as session:
            result = await session.execute(select(User))
            return list(result.scalars().all())

    @retry_postgres_record_operation(default=None)
    async def add_record(self, user_id: int, record_str: str) -> Optional[Record]:
        """Add a record, creating the user if it does not exist."""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    logging.warning(
                        "User with ID %s not found, creating a new one",
                        user_id,
                    )
                    user = User(user_id=user_id)
                    session.add(user)
                    await session.flush()

                record = Record(record_str=record_str, user_id=user.user_id)
                session.add(record)
                await session.commit()
                await session.refresh(record)
                return record
            except Exception:
                await session.rollback()
                raise

    @retry_postgres_record_operation(default=None)
    async def get_record(self, record_id: int) -> Optional[Record]:
        """Get record by ID with user relationship loaded."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Record)
                .options(selectinload(Record.user))
                .where(Record.record_id == record_id)
            )
            return result.scalar_one_or_none()

    @retry_postgres_record_operation(default=list)
    async def get_all_records(self) -> List[Record]:
        """Get all records."""
        async with self.async_session() as session:
            result = await session.execute(select(Record))
            return list(result.scalars().all())

    @retry_postgres_record_operation(default=list)
    async def get_random_records(self, limit: int = 1) -> List[Record]:
        """Get random records."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Record).order_by(func.random()).limit(limit)
            )
            return list(result.scalars().all())

    @retry_postgres_record_operation(default=list)
    async def get_records_by_user(self, user_id: int) -> List[Record]:
        """Get all records for a specific user."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Record).where(Record.user_id == user_id)
            )
            return list(result.scalars().all())

    @retry_postgres_record_operation(default=None)
    async def get_random_record_by_user(self, user_id: int) -> Optional[Record]:
        """Get a random record for a specific user."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Record)
                .where(Record.user_id == user_id)
                .order_by(func.random())
                .limit(1)
            )
            return result.scalar_one_or_none()

    @retry_postgres_record_operation(default=False)
    async def delete_record(self, record_id: int) -> bool:
        """Delete a record."""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(Record).where(Record.record_id == record_id)
                )
                record = result.scalar_one_or_none()

                if not record:
                    logging.warning("Record with ID %s not found", record_id)
                    return False

                await session.delete(record)
                await session.commit()
                return True
            except Exception:
                await session.rollback()
                raise

    @retry_postgres_record_operation(default=None)
    async def add_alias(self, user_id: int, alias_str: str) -> Optional[Alias]:
        """Add an alias, creating the user if it does not exist."""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    logging.warning(
                        "User with ID %s not found, creating a new one",
                        user_id,
                    )
                    user = User(user_id=user_id)
                    session.add(user)
                    await session.flush()

                alias = Alias(alias_str=alias_str, user_id=user.user_id)
                session.add(alias)
                await session.commit()
                await session.refresh(alias)
                return alias
            except Exception:
                await session.rollback()
                raise

    @retry_postgres_record_operation(default=None)
    async def get_user_by_alias(self, alias_str: str) -> Optional[User]:
        """Get user by alias."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Alias)
                .options(selectinload(Alias.user))
                .where(Alias.alias_str == alias_str)
            )
            alias = result.scalar_one_or_none()
            return alias.user if alias else None

    @retry_postgres_record_operation(default=list)
    async def get_all_aliases(self) -> List[Alias]:
        """Get all aliases."""
        async with self.async_session() as session:
            result = await session.execute(select(Alias))
            return list(result.scalars().all())

    async def close(self) -> None:
        await self.engine.dispose()


_global_async_postgres_record_manager: Optional[AsyncPostgresRecordDatabaseManager] = (
    None
)
_global_async_postgres_record_manager_lock: Optional[asyncio.Lock] = None


def _get_global_async_postgres_record_manager_lock() -> asyncio.Lock:
    global _global_async_postgres_record_manager_lock
    if _global_async_postgres_record_manager_lock is None:
        _global_async_postgres_record_manager_lock = asyncio.Lock()
    return _global_async_postgres_record_manager_lock


async def create_global_async_postgres_record_manager(
    *,
    strict: Optional[bool] = None,
) -> Optional[AsyncPostgresRecordDatabaseManager]:
    """Return the cached Postgres record manager, or None when unset."""
    global _global_async_postgres_record_manager

    if _global_async_postgres_record_manager is not None:
        return _global_async_postgres_record_manager

    db_url = AsyncPostgresRecordDatabaseManager._db_url_from_env()
    is_strict = (
        AsyncPostgresRecordDatabaseManager._strict_from_env()
        if strict is None
        else strict
    )
    if not db_url:
        if is_strict:
            raise ValueError(
                "Please set POSTGRES_RECORD_DB_URL, POSTGRES_DB_URL, or POSTGRES_URI."
            )
        logging.info("Postgres record database URL is not configured")
        return None

    async with _get_global_async_postgres_record_manager_lock():
        if _global_async_postgres_record_manager is None:
            _global_async_postgres_record_manager = AsyncPostgresRecordDatabaseManager(
                db_url
            )
        return _global_async_postgres_record_manager
