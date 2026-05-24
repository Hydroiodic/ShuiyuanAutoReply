import asyncio
import logging

import dotenv
from sqlalchemy import select, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

dotenv.load_dotenv()

from shuiyuan_auto_reply.database.mysql_mgr import (  # noqa: E402
    create_global_async_mysql_manager,
)
from shuiyuan_auto_reply.database.postgres_record_mgr import (  # noqa: E402
    Alias as PostgresAlias,
)
from shuiyuan_auto_reply.database.postgres_record_mgr import (  # noqa: E402
    Record as PostgresRecord,
)
from shuiyuan_auto_reply.database.postgres_record_mgr import (  # noqa: E402
    User as PostgresUser,
)
from shuiyuan_auto_reply.database.postgres_record_mgr import (  # noqa: E402
    create_global_async_postgres_record_manager,
)


async def _reset_serial_sequence(session, table_name: str, column_name: str) -> None:
    if table_name not in {"record", "alias"}:
        raise ValueError(f"Unsupported table name: {table_name}")
    if column_name not in {"record_id", "alias_id"}:
        raise ValueError(f"Unsupported column name: {column_name}")

    await session.execute(text(f"""
            SELECT setval(
                pg_get_serial_sequence('"{table_name}"', '{column_name}'),
                COALESCE((SELECT MAX({column_name}) FROM "{table_name}"), 1),
                (SELECT MAX({column_name}) IS NOT NULL FROM "{table_name}")
            )
            """))


async def migrate_database() -> None:
    """Copy legacy MySQL record data into Postgres, preserving IDs."""
    mysql_manager = None
    postgres_manager = None
    try:
        mysql_manager = await create_global_async_mysql_manager(strict=True)
        if mysql_manager is None:
            raise RuntimeError("MYSQL_DB_URL is not configured")

        postgres_manager = await create_global_async_postgres_record_manager(
            strict=True
        )
        if postgres_manager is None:
            raise RuntimeError("Postgres record database is not configured")

        await postgres_manager.create_tables()

        users = await mysql_manager.get_all_users()
        records = await mysql_manager.get_all_records()
        aliases = await mysql_manager.get_all_aliases()
        logging.info(
            "Loaded %d users, %d records, %d aliases from MySQL",
            len(users),
            len(records),
            len(aliases),
        )

        async with postgres_manager.async_session() as session:
            try:
                for source_user in users:
                    target_user = await session.get(PostgresUser, source_user.user_id)
                    if target_user is None:
                        target_user = PostgresUser(user_id=source_user.user_id)
                        session.add(target_user)

                    target_user.last_update_time = source_user.last_update_time
                    target_user.coin = source_user.coin
                    target_user.enable_record = source_user.enable_record
                    target_user.allow_others = source_user.allow_others

                await session.flush()

                for source_record in records:
                    target_record = await session.get(
                        PostgresRecord,
                        source_record.record_id,
                    )
                    if target_record is None:
                        target_record = PostgresRecord(
                            record_id=source_record.record_id
                        )
                        session.add(target_record)

                    target_record.record_str = source_record.record_str
                    target_record.user_id = source_record.user_id

                await session.flush()

                for source_alias in aliases:
                    target_alias = await session.get(
                        PostgresAlias,
                        source_alias.alias_id,
                    )
                    if target_alias is None:
                        result = await session.execute(
                            select(PostgresAlias).where(
                                PostgresAlias.alias_str == source_alias.alias_str
                            )
                        )
                        target_alias = result.scalar_one_or_none()

                    if target_alias is None:
                        target_alias = PostgresAlias(alias_id=source_alias.alias_id)
                        session.add(target_alias)

                    target_alias.alias_str = source_alias.alias_str
                    target_alias.user_id = source_alias.user_id

                await _reset_serial_sequence(session, "record", "record_id")
                await _reset_serial_sequence(session, "alias", "alias_id")
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        logging.info("MySQL to Postgres migration completed successfully")
    finally:
        if mysql_manager is not None:
            await mysql_manager.engine.dispose()
        if postgres_manager is not None:
            await postgres_manager.close()


if __name__ == "__main__":
    asyncio.run(migrate_database())
