import asyncio
import logging

import dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

dotenv.load_dotenv()

from shuiyuan_auto_reply.database.postgres_memory_mgr import (  # noqa: E402
    create_global_async_postgres_memory_manager,
)
from shuiyuan_auto_reply.database.postgres_record_mgr import (  # noqa: E402
    create_global_async_postgres_record_manager,
)


async def init_database() -> None:
    """Initialize Postgres tables for records and mention memory."""
    record_manager = None
    memory_manager = None
    try:
        logging.info("Creating Postgres record tables...")
        record_manager = await create_global_async_postgres_record_manager(strict=True)
        if record_manager is None:
            raise RuntimeError("Postgres record database is not configured")
        await record_manager.create_tables()

        logging.info("Creating Postgres memory metadata tables...")
        memory_manager = await create_global_async_postgres_memory_manager(strict=True)
        if memory_manager is None:
            raise RuntimeError("Postgres memory database is not configured")
        await memory_manager.initialize_schema()

        logging.info("Postgres database initialized successfully")
    except Exception as exc:
        logging.error("Error initializing Postgres database: %s", exc)
        raise
    finally:
        if record_manager is not None:
            await record_manager.close()
        if memory_manager is not None:
            await memory_manager.close()


if __name__ == "__main__":
    asyncio.run(init_database())
