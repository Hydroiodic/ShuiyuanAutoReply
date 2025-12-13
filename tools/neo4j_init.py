import asyncio
import dotenv
import logging
import pandas as pd

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

from src.constants import auto_reply_tag
from src.database.neo4j_mgr import global_async_neo4j_manager


async def init_database():
    """Initialize the Neo4j database"""
    try:
        logging.info("Initializing Neo4j database...")
        # Initialize the Neo4j database
        await global_async_neo4j_manager.initialize()

        # Try to open the CSV file and import data
        file_path = os.path.join(os.path.dirname(__file__), "user_archive.csv")
        if os.path.exists(file_path):
            # Load the CSV data
            logging.info(f"Importing data from {file_path}...")
            df = pd.read_csv(file_path)
            # Some data should not be imported, filter them out
            data_to_import = []
            for idx, raw in enumerate(df["post_raw"]):
                # If NaN, skip
                if pd.isna(raw):
                    continue
                # Auto-reply posts should not be imported
                if auto_reply_tag in str(raw):
                    continue
                # For other posts, import them into the database
                data_to_import.append(str(raw).strip())
            # Make every record unique
            data_to_import = list(set(data_to_import))
            # Log the number of records to be imported
            logging.info(f"Number of records to import: {len(data_to_import)}")
            # Wait for all import routines to complete
            await global_async_neo4j_manager.store_sentences(data_to_import)
            logging.info("Data imported successfully!")
        else:
            logging.warning(f"CSV file {file_path} not found. Skipping data import.")

        await global_async_neo4j_manager.close()
        logging.info("Neo4j database initialized successfully!")
    except Exception as e:
        logging.error(f"Error initializing Neo4j database: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_database())
