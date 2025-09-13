import os
import asyncio
import logging
from datetime import datetime
from typing import Callable, List, Optional
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy import (
    func,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    select,
)

# Create base class for ORM models
Base = declarative_base()


class User(Base):
    """User model representing a user in the system"""

    __tablename__ = "user"

    # The class User has columns: user_id, last_update_time, and coin.
    user_id = Column(Integer, primary_key=True)
    last_update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    coin = Column(Integer, default=0)
    enable_record = Column(Integer, default=0)  # 0: disabled, 1: enabled
    allow_others = Column(Integer, default=0)  # 0: disallow, 1: allow

    # Define relationship with Record (one-to-many)
    records = relationship(
        "Record",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User(user_id={self.user_id}, coin={self.coin}, last_update_time={self.last_update_time})>"


class Record(Base):
    """Record model representing a user's record/quote"""

    __tablename__ = "record"

    # The class Record has columns: record_id, record_str, and user_id (foreign key).
    record_id = Column(Integer, primary_key=True, autoincrement=True)
    record_str = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("user.user_id"), nullable=False)

    # Define relationship with User (many-to-one)
    user = relationship("User", back_populates="records")

    def __repr__(self):
        return f"<Record(record_id={self.record_id}, record_str={self.record_str}, user_id={self.user_id})>"


class Alias(Base):
    """Alias model representing a user's alias"""

    __tablename__ = "alias"

    # The class Alias has columns: alias_id, alias_str, and user_id (foreign key).
    alias_id = Column(Integer, primary_key=True, autoincrement=True)
    alias_str = Column(String(255), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("user.user_id"), nullable=False)

    # Define relationship with User (many-to-one)
    user = relationship("User")

    def __repr__(self):
        return f"<Alias(alias_id={self.alias_id}, alias_str={self.alias_str}, user_id={self.user_id})>"


class AsyncDatabaseManager:
    """Asynchronous database manager for handling database operations"""

    def __init__(self):
        async_db_url = os.getenv("MYSQL_DB_URL")
        self.engine = create_async_engine(async_db_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    @staticmethod
    async def _execute_with_retry(
        coro: Callable,
        retries: int = 3,
        delay: float = 1.0,
    ):
        """Execute a coroutine with retries on failure"""
        for attempt in range(retries):
            try:
                return await coro()
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)

        # If all attempts fail, raise the last exception
        logging.error("All retry attempts failed")
        raise Exception("All retry attempts failed")

    async def create_tables(self):
        """Create all tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logging.info("Tables created successfully")

    async def drop_tables(self):
        """Drop all tables (use with caution)"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logging.info("Tables dropped successfully")

    # CRUD operations for User table
    async def _add_user(self, user_id: int) -> Optional[User]:
        """Add a new user"""
        async with self.async_session() as session:
            try:
                # Check if user already exists
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                existing_user = result.scalar_one_or_none()

                if existing_user:
                    logging.warning(f"User with ID {user_id} already exists")
                    return existing_user

                # Create new user
                user = User(user_id=user_id)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user

            except Exception as e:
                await session.rollback()
                raise e

    async def add_user(self, user_id: int) -> Optional[User]:
        """Add a new user with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._add_user(user_id)
            )
        except Exception as e:
            logging.error(f"Failed to add user after retries: {e}")
            return None

    async def _get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                return result.scalar_one_or_none()
            except Exception as e:
                raise e

    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._get_user(user_id)
            )
        except Exception as e:
            logging.error(f"Failed to get user after retries: {e}")
            return None

    async def _get_or_add_user(self, user_id: int) -> Optional[User]:
        """Get user by ID, create if not exists"""
        async with self.async_session() as session:
            try:
                # Try to get the user
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if user:
                    return user

                # User doesn't exist, create it
                user = User(user_id=user_id)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user

            except Exception as e:
                await session.rollback()
                raise e

    async def get_or_add_user(self, user_id: int) -> Optional[User]:
        """Get user by ID, create if not exists, with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._get_or_add_user(user_id)
            )
        except Exception as e:
            logging.error(f"Failed to get or add user after retries: {e}")
            return None

    async def _update_user(
        self,
        user_id: int,
        coin: Optional[int] = None,
        enable_record: Optional[int] = None,
        allow_others: Optional[int] = None,
    ) -> bool:
        """Update user information"""
        async with self.async_session() as session:
            try:
                # Find the user
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    logging.warning(f"User with ID {user_id} not found")
                    return False

                # Update fields if provided
                if coin is not None:
                    user.coin = coin
                if enable_record is not None:
                    user.enable_record = enable_record
                if allow_others is not None:
                    user.allow_others = allow_others

                # Commit the session (last_update_time will be updated automatically)
                await session.commit()
                return True

            except Exception as e:
                await session.rollback()
                raise e

    async def update_user(
        self,
        user_id: int,
        coin: Optional[int] = None,
        enable_record: Optional[int] = None,
        allow_others: Optional[int] = None,
    ) -> bool:
        """Update user information with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._update_user(user_id, coin, enable_record, allow_others)
            )
        except Exception as e:
            logging.error(f"Failed to update user after retries: {e}")
            return False

    async def _delete_user(self, user_id: int) -> bool:
        """Delete a user and all associated records (cascade delete is configured)"""
        async with self.async_session() as session:
            try:
                # Find the user
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    logging.warning(f"User with ID {user_id} not found")
                    return False

                # Delete the user (cascade will handle associated records)
                await session.delete(user)
                await session.commit()
                return True

            except Exception as e:
                await session.rollback()
                raise e

    async def delete_user(self, user_id: int) -> bool:
        """Delete a user and all associated records with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._delete_user(user_id)
            )
        except Exception as e:
            logging.error(f"Failed to delete user after retries: {e}")
            return False

    async def _get_all_users(self) -> List[User]:
        """Get all users"""
        async with self.async_session() as session:
            try:
                result = await session.execute(select(User))
                return list(result.scalars().all())
            except Exception as e:
                raise e

    async def get_all_users(self) -> List[User]:
        """Get all users with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(self._get_all_users)
        except Exception as e:
            logging.error(f"Failed to get all users after retries: {e}")
            return []

    # Operations for Record table
    async def _add_record(self, user_id: int, record_str: str) -> Optional[Record]:
        """Add a record, create user if it doesn't exist"""
        async with self.async_session() as session:
            try:
                # Find the user
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    # User doesn't exist, create it first
                    logging.warning(
                        f"User with ID {user_id} not found, creating a new one"
                    )
                    user = User(user_id=user_id)
                    session.add(user)
                    await session.flush()  # Flush to get the user ID

                # Create record, add to session, and commit
                record = Record(record_str=record_str, user_id=user.user_id)
                session.add(record)
                await session.commit()
                await session.refresh(record)
                return record

            except Exception as e:
                await session.rollback()
                raise e

    async def add_record(self, user_id: int, record_str: str) -> Optional[Record]:
        """Add a record, create user if it doesn't exist, with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._add_record(user_id, record_str)
            )
        except Exception as e:
            logging.error(f"Failed to add record after retries: {e}")
            return None

    async def _get_record(self, record_id: int) -> Optional[Record]:
        """Get record by ID with user relationship loaded"""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(Record)
                    .options(selectinload(Record.user))  # Async version of joinedload
                    .where(Record.record_id == record_id)
                )
                return result.scalar_one_or_none()
            except Exception as e:
                raise e

    async def get_record(self, record_id: int) -> Optional[Record]:
        """Get record by ID with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._get_record(record_id)
            )
        except Exception as e:
            logging.error(f"Failed to get record after retries: {e}")
            return None

    async def _get_all_records(self) -> List[Record]:
        """Get all records"""
        async with self.async_session() as session:
            try:
                result = await session.execute(select(Record))
                return list(result.scalars().all())
            except Exception as e:
                raise e

    async def get_all_records(self) -> List[Record]:
        """Get all records with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(self._get_all_records)
        except Exception as e:
            logging.error(f"Failed to get all records after retries: {e}")
            return []

    async def _get_random_records(self, limit: int = 1) -> List[Record]:
        """Get random records"""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(Record).order_by(func.random()).limit(limit)
                )
                return list(result.scalars().all())
            except Exception as e:
                raise e

    async def get_random_records(self, limit: int = 1) -> List[Record]:
        """Get random records with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._get_random_records(limit)
            )
        except Exception as e:
            logging.error(f"Failed to get random records after retries: {e}")
            return []

    async def _get_records_by_user(self, user_id: int) -> List[Record]:
        """Get all records for a specific user"""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(Record).where(Record.user_id == user_id)
                )
                return list(result.scalars().all())
            except Exception as e:
                raise e

    async def get_records_by_user(self, user_id: int) -> List[Record]:
        """Get all records for a specific user with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._get_records_by_user(user_id)
            )
        except Exception as e:
            logging.error(f"Failed to get records by user after retries: {e}")
            return []

    async def _get_random_record_by_user(self, user_id: int) -> Optional[Record]:
        """Get a random record for a specific user"""
        async with self.async_session() as session:
            try:
                result = await session.execute(
                    select(Record)
                    .where(Record.user_id == user_id)
                    .order_by(func.random())
                    .limit(1)
                )
                return result.scalar_one_or_none()
            except Exception as e:
                raise e

    async def get_random_record_by_user(self, user_id: int) -> Optional[Record]:
        """Get a random record for a specific user with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._get_random_record_by_user(user_id)
            )
        except Exception as e:
            logging.error(f"Failed to get random record by user after retries: {e}")
            return None

    async def _delete_record(self, record_id: int) -> bool:
        """Delete a record"""
        async with self.async_session() as session:
            try:
                # Find the record
                result = await session.execute(
                    select(Record).where(Record.record_id == record_id)
                )
                record = result.scalar_one_or_none()

                if not record:
                    logging.warning(f"Record with ID {record_id} not found")
                    return False

                # Delete the record and commit
                await session.delete(record)
                await session.commit()
                return True

            except Exception as e:
                await session.rollback()
                raise e

    async def delete_record(self, record_id: int) -> bool:
        """Delete a record with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._delete_record(record_id)
            )
        except Exception as e:
            logging.error(f"Failed to delete record after retries: {e}")
            return False

    # Operations for Alias table
    async def _add_alias(self, user_id: int, alias_str: str) -> Optional[Alias]:
        """Add an alias, create user if it doesn't exist"""
        async with self.async_session() as session:
            try:
                # Find the user
                result = await session.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    # User doesn't exist, create it first
                    logging.warning(
                        f"User with ID {user_id} not found, creating a new one"
                    )
                    user = User(user_id=user_id)
                    session.add(user)
                    await session.flush()  # Flush to get the user ID

                # Create alias, add to session, and commit
                alias = Alias(alias_str=alias_str, user_id=user.user_id)
                session.add(alias)
                await session.commit()
                await session.refresh(alias)
                return alias

            except Exception as e:
                await session.rollback()
                raise e

    async def add_alias(self, user_id: int, alias_str: str) -> Optional[Alias]:
        """Add an alias, create user if it doesn't exist, with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._add_alias(user_id, alias_str)
            )
        except Exception as e:
            logging.error(f"Failed to add alias after retries: {e}")
            return None

    async def _get_user_by_alias(self, alias_str: str) -> Optional[User]:
        """Get user by alias"""
        async with self.async_session() as session:
            try:
                # Find the alias
                result = await session.execute(
                    select(Alias)
                    .options(selectinload(Alias.user))
                    .where(Alias.alias_str == alias_str)
                )
                alias = result.scalar_one_or_none()
                # Return the associated user
                return alias.user if alias else None
            except Exception as e:
                raise e

    async def get_user_by_alias(self, alias_str: str) -> Optional[User]:
        """Get user by alias with retries"""
        try:
            return await AsyncDatabaseManager._execute_with_retry(
                lambda: self._get_user_by_alias(alias_str)
            )
        except Exception as e:
            logging.error(f"Failed to get user by alias after retries: {e}")
            return None


# Global async database manager instance
global_async_db_manager = AsyncDatabaseManager()
