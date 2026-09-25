import asyncio

import pytest

from shuiyuan_auto_reply.database.postgres_record_mgr import (
    AsyncPostgresRecordDatabaseManager,
)

pytest.importorskip("aiosqlite")


def _run(scenario, tmp_path):
    async def run():
        manager = AsyncPostgresRecordDatabaseManager(
            f"sqlite+aiosqlite:///{tmp_path / 'records.db'}"
        )
        try:
            await manager.create_tables()
            await scenario(manager)
        finally:
            await manager.close()

    asyncio.run(run())


def test_users_are_created_once(tmp_path):
    async def scenario(manager):
        user = await manager.get_or_add_user(1)
        assert user.user_id == 1
        assert (await manager.add_user(1)).user_id == 1
        assert (await manager.get_or_add_user(2)).user_id == 2
        assert sorted(u.user_id for u in await manager.get_all_users()) == [1, 2]

    _run(scenario, tmp_path)


def test_update_and_delete_user(tmp_path):
    async def scenario(manager):
        assert not await manager.update_user(1, enable_record=1)
        await manager.get_or_add_user(1)
        assert await manager.update_user(1, enable_record=1, allow_others=1)
        user = await manager.get_user(1)
        assert (user.enable_record, user.allow_others) == (1, 1)
        assert await manager.delete_user(1)
        assert await manager.get_user(1) is None

    _run(scenario, tmp_path)


def test_records_and_aliases(tmp_path):
    async def scenario(manager):
        # Adding a record or alias creates the user on demand
        record = await manager.add_record(3, "名言")
        assert record.user_id == 3
        assert (await manager.get_record(record.record_id)).user.user_id == 3
        assert [r.record_str for r in await manager.get_records_by_user(3)] == ["名言"]
        assert (await manager.get_random_record_by_user(3)).record_str == "名言"

        await manager.add_alias(4, "nick")
        assert (await manager.get_user_by_alias("nick")).user_id == 4
        assert await manager.get_user_by_alias("missing") is None

        assert await manager.delete_record(record.record_id)
        assert not await manager.delete_record(record.record_id)

    _run(scenario, tmp_path)
