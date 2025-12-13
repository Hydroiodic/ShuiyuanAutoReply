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

from src.constants import auto_reply_tag
from src.database.neo4j_mgr import global_async_neo4j_manager


async def main():
    # Try to search for similar sentences
    try:
        logging.info("Searching for similar sentences...")
        query = "533"
        results = await global_async_neo4j_manager.search_similar(query, top_k=10)
        for res in results:
            logging.info(
                f"Text: {res.text}, Category: {res.category}, Score: {res.score}"
            )
        logging.info("Search completed successfully!")
    except Exception as e:
        logging.error(f"Error during search: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
