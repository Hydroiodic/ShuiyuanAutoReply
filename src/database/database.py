import os
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey

# Create base class for ORM models
Base = declarative_base()


class User(Base):
    # Define table name
    __tablename__ = "user"

    # The class User has columns: user_id, last_update_time, and coin.
    user_id = Column(Integer, primary_key=True)
    last_update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    coin = Column(Integer, default=0)

    # Define relationship with Record (one-to-many)
    records = relationship(
        "Record",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User(user_id={self.user_id}, coin={self.coin}, last_update_time={self.last_update_time})>"


class Record(Base):
    # Define table name
    __tablename__ = "record"

    # The class Record has columns: record_id, record_str, and user_id (foreign key).
    record_id = Column(Integer, primary_key=True, autoincrement=True)
    record_str = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("user.user_id"), nullable=False)

    # Define relationship with User (many-to-one)
    user = relationship("User", back_populates="records")

    def __repr__(self):
        return f"<Record(record_id={self.record_id}, record_str={self.record_str}, user_id={self.user_id})>"


class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(os.getenv("MYSQL_DB_URL"), echo=False)
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(self.engine)
        logging.info("Tables created successfully")

    def drop_tables(self):
        """Drop all tables (use with caution)"""
        Base.metadata.drop_all(self.engine)
        logging.info("Tables dropped successfully")

    # CRUD operations for User table
    def add_user(self, user_id: int, coin: Optional[int] = None) -> Optional[User]:
        """Add a new user"""
        with self.Session() as session:
            try:
                # Check if user already exists
                existing_user = (
                    session.query(User).filter(User.user_id == user_id).first()
                )
                if existing_user:
                    logging.warning(f"User with ID {user_id} already exists")
                    return existing_user

                # Create new user, add to session, and commit
                user = (
                    User(user_id=user_id, coin=coin)
                    if coin is not None
                    else User(user_id=user_id)
                )
                session.add(user)
                session.commit()
                return user

            except Exception as e:
                # Error occurred, rollback the session
                session.rollback()
                logging.error(f"Error adding user: {e}")
                return None

    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        with self.Session() as session:
            try:
                return session.query(User).filter(User.user_id == user_id).first()
            except Exception as e:
                logging.error(f"Error getting user: {e}")
                return None

    def update_user(self, user_id: int, coin: Optional[int] = None) -> bool:
        """Update user information"""
        with self.Session() as session:
            try:
                # Find the user
                user = session.query(User).filter(User.user_id == user_id).first()
                if not user:
                    logging.warning(f"User with ID {user_id} not found")
                    return False

                # Update coin field if provided
                if coin is not None:
                    user.coin = coin

                # Commit the session (last_update_time will be updated automatically)
                session.commit()
                return True

            except Exception as e:
                # Error occurred, rollback the session
                session.rollback()
                logging.error(f"Error updating user: {e}")
                return False

    def delete_user(self, user_id: int) -> bool:
        """Delete a user and all associated records (cascade delete is configured)"""
        with self.Session() as session:
            try:
                # Find the user
                user = session.query(User).filter(User.user_id == user_id).first()
                if not user:
                    logging.warning(f"User with ID {user_id} not found")
                    return False

                # Delete the user (cascade will handle associated records)
                session.delete(user)
                session.commit()
                return True

            except Exception as e:
                # Error occurred, rollback the session
                session.rollback()
                logging.error(f"Error deleting user: {e}")
                return False

    def get_all_users(self) -> List[User]:
        """Get all users"""
        with self.Session() as session:
            try:
                return session.query(User).all()
            except Exception as e:
                logging.error(f"Error getting users: {e}")
                return []

    # Operations for Record table
    def add_record(self, user_id: int, record_str: str) -> Optional[Record]:
        """Add a record, create user if it doesn't exist"""
        with self.Session() as session:
            try:
                # Find the user
                user = session.query(User).filter(User.user_id == user_id).first()
                if not user:
                    # User doesn't exist, create it first
                    logging.warning(
                        f"User with ID {user_id} not found, creating a new one"
                    )
                    user = User(user_id=user_id)
                    session.add(user)
                    session.flush()  # Flush to get the user ID

                # Create record, add to session, and commit
                record = Record(record_str=record_str, user_id=user.user_id)
                session.add(record)
                session.commit()
                return record

            except Exception as e:
                # Error occurred, rollback the session
                session.rollback()
                logging.error(f"Error adding record: {e}")
                return None

    def get_records_by_user(self, user_id: int) -> List[Record]:
        """Get all records for a specific user"""
        with self.Session() as session:
            try:
                return session.query(Record).filter(Record.user_id == user_id).all()
            except Exception as e:
                logging.error(f"Error getting records: {e}")
                return []

    def get_all_records(self) -> List[Record]:
        """Get all records"""
        with self.Session() as session:
            try:
                return session.query(Record).all()
            except Exception as e:
                logging.error(f"Error getting records: {e}")
                return []

    def delete_record(self, record_id: int) -> bool:
        """Delete a record"""
        with self.Session() as session:
            try:
                # Find the record
                record = (
                    session.query(Record).filter(Record.record_id == record_id).first()
                )
                if not record:
                    logging.warning(f"Record with ID {record_id} not found")
                    return False

                # Delete the record and commit
                session.delete(record)
                session.commit()
                return True

            except Exception as e:
                # Error occurred, rollback the session
                session.rollback()
                logging.error(f"Error deleting record: {e}")
                return False
