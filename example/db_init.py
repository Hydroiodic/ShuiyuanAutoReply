import asyncio
import dotenv
import logging

# Setup the logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Load all environment variables from the .env file
dotenv.load_dotenv()

# Add the parent directory to the system path for module resolution
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.manager import global_async_db_manager


async def init_database():
    """Initialize the database"""
    try:
        logging.info("Creating database tables...")
        await global_async_db_manager.create_tables()
        logging.info("Database initialized successfully!")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_database())
