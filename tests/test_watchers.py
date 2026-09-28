import asyncio
from types import SimpleNamespace

import pytest

from shuiyuan_auto_reply.shuiyuan.topic_model import BaseTopicModel
from shuiyuan_auto_reply.shuiyuan.user_action_model import BaseUserActionModel


class _StopWatching(BaseException):
    """Raised by the fake model to end the infinite watch loop."""


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)

    async def _next(self):
        if not self.responses:
            raise _StopWatching
        return self.responses.pop(0)

    async def get_topic_details(self, topic_id):
        stream = await self._next()
        return SimpleNamespace(post_stream=SimpleNamespace(stream=stream))

    async def get_actions(self, username, action_type):
        post_ids = await self._next()
        return SimpleNamespace(
            user_actions=[SimpleNamespace(post_id=post_id) for post_id in post_ids]
        )


class TopicModel(BaseTopicModel):
    def __init__(self, model):
        super().__init__(model, topic_id=1)
        self.handled = []

    async def _new_post_routine(self, post_id):
        self.handled.append(post_id)

    async def _daily_routine(self):
        pass


class UserActionModel(BaseUserActionModel):
    def __init__(self, model):
        super().__init__(model, "bot", [5, 7])
        self.handled = []

    async def _new_action_routine(self, action):
        self.handled.append(action.post_id)


def _watch(watcher, routine):
    async def run():
        with pytest.raises(_StopWatching):
            await routine()
        # Let the background routines run
        await asyncio.sleep(0)

    asyncio.run(run())
    return watcher.handled


def test_topic_watcher_handles_only_new_posts():
    model = FakeModel([[1, 2, 3], [1, 2, 3, 4, 5], [1, 3, 5, 6]])
    watcher = TopicModel(model)
    assert _watch(watcher, watcher.watch_new_post_routine) == [4, 5, 6]
    assert not watcher._bg_tasks


def test_action_watcher_skips_existing_actions():
    model = FakeModel([[10, 11], [12, 10, 11], [13, 12, 10]])
    watcher = UserActionModel(model)
    assert _watch(watcher, watcher.watch_new_action_routine) == [12, 13]


def test_action_watcher_handles_first_action_of_empty_account():
    model = FakeModel([[], [20]])
    watcher = UserActionModel(model)
    assert _watch(watcher, watcher.watch_new_action_routine) == [20]
