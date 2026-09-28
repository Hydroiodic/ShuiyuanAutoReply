import asyncio
import logging
import os

import dotenv
import pandas as pd

# Setup the logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Load all environment variables from the .env file
dotenv.load_dotenv()

from shuiyuan_auto_reply.constants import settings  # noqa: E402
from shuiyuan_auto_reply.database.neo4j_mgr import (  # noqa: E402
    create_global_async_neo4j_manager,
)
from shuiyuan_auto_reply.shuiyuan.reply_utils import (  # noqa: E402
    remove_shuiyuan_signature,
)


async def init_database():
    """Initialize the Neo4j database"""
    try:
        logging.info("Initializing Neo4j database...")
        neo4j_manager = await create_global_async_neo4j_manager(strict=True)
        if neo4j_manager is None:
            raise RuntimeError("NEO4J_DB_URL is not configured")
        # Initialize the Neo4j database
        await neo4j_manager.initialize()

        # Try to open the CSV file and import data
        file_path = os.path.join(os.path.dirname(__file__), "user_archive.csv")
        if os.path.exists(file_path):
            # Load the CSV data
            logging.info(f"Importing data from {file_path}...")
            df = pd.read_csv(file_path)
            # Some data should not be imported, filter them out
            data_to_import = []
            for raw in df["post_raw"]:
                # If NaN, skip
                if pd.isna(raw):
                    continue
                # Auto-reply posts should not be imported
                if settings.auto_reply_tag in str(raw):
                    continue
                # For other posts, import them into the database
                # But signature needs to be removed from the post
                data_to_import.append(remove_shuiyuan_signature(str(raw)))
            # Make every record unique
            data_to_import = list(set(data_to_import))
            # Log the number of records to be imported
            logging.info(f"Number of records to import: {len(data_to_import)}")
            # Wait for all import routines to complete
            await neo4j_manager.store_sentences(data_to_import)
            logging.info("Data imported successfully!")
        else:
            logging.warning(f"CSV file {file_path} not found. Skipping data import.")
        logging.info("Neo4j database initialized successfully!")
    except Exception as e:
        logging.error(f"Error initializing Neo4j database: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(init_database())
