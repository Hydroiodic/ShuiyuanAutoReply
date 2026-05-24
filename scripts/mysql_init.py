import asyncio
import logging

import dotenv

# Setup the logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Load all environment variables from the .env file
dotenv.load_dotenv()

from shuiyuan_auto_reply.database.mysql_mgr import create_global_async_mysql_manager


async def init_database():
    """Initialize the database"""
    try:
        logging.info("Creating database tables...")
        mysql_manager = await create_global_async_mysql_manager(strict=True)
        if mysql_manager is None:
            raise RuntimeError("MYSQL_DB_URL is not configured")
        await mysql_manager.create_tables()
        logging.info("Database initialized successfully!")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_database())
