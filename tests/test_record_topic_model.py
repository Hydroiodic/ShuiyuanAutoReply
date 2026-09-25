import asyncio
from types import SimpleNamespace

import pytest

from examples.models.record_model.record_topic_model import RecordTopicModel
from shuiyuan_auto_reply.database.postgres_record_mgr import (
    AsyncPostgresRecordDatabaseManager,
)
from shuiyuan_auto_reply.shuiyuan.objects import User

pytest.importorskip("aiosqlite")

ALICE = User(1, "alice", "爱丽丝")
BOB = User(2, "bob", None)


class FakeShuiyuanModel:
    async def get_user_by_username(self, username):
        return {"alice": ALICE, "bob": BOB}.get(username)


def test_record_commands(tmp_path):
    async def run():
        topic_model = RecordTopicModel(FakeShuiyuanModel(), topic_id=1)
        topic_model.record_manager = AsyncPostgresRecordDatabaseManager(
            f"sqlite+aiosqlite:///{tmp_path / 'records.db'}"
        )
        await topic_model.record_manager.create_tables()

        async def reply(raw, user):
            text = await topic_model._generate_reply(SimpleNamespace(raw=raw), user)
            return text.split("\n\n<!-- ")[0] if text is not None else None

        try:
            assert await reply("随便聊聊", ALICE) is None
            assert await reply("【查询语录】carol", ALICE) == (
                "找不到用户名或别名为 'carol' 的用户"
            )
            assert await reply("【记录语录】alice\n名言", ALICE) == (
                "该用户未开启或已禁用语录记录功能"
            )
            assert (
                await reply("【启用语录】maybe", ALICE)
                == "参数无效，请使用 True 或 False"
            )
            assert await reply("【启用语录】True", ALICE) == "已启用您的语录记录功能"
            assert (await reply("【记录语录】Alice\n名言", ALICE)).startswith(
                "已将以下语录添加到数据库中"
            )
            assert await reply("【记录语录】alice\n别的", BOB) == (
                "您没有权限为该用户添加语录"
            )
            assert await reply("【设置别名】ali alice", ALICE) == (
                "已将别名 'ali' 设置为用户 'alice'"
            )
            assert await reply("【获取语录】ALI", BOB) == (
                "> 名言\n\n---\n\n[right]这是一条自动回复[/right]"
            )
            assert "> 名言" in await reply("【查询语录】alice", BOB)
            assert (
                await reply("【更改权限】TRUE", ALICE) == "已允许他人记录和删除您的语录"
            )
            assert (await reply("【记录语录】alice\n别的", BOB)).startswith(
                "已将以下语录添加到数据库中"
            )
        finally:
            await topic_model.record_manager.close()

    asyncio.run(run())
