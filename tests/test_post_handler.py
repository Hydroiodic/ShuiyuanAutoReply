import asyncio
from types import SimpleNamespace

from examples.models.common import GENERIC_ERROR_REPLY, handle_post_and_reply
from shuiyuan_auto_reply.constants import settings


class FakeModel:
    def __init__(self, raw):
        self.post = SimpleNamespace(
            raw=raw,
            user_id=7,
            username="alice",
            name=None,
            topic_id=100,
            post_number=5,
        )
        self.replies = []

    async def get_post_details(self, post_id):
        return self.post

    async def reply_to_post(self, text, topic_id, reply_to_post_number=None):
        self.replies.append((text, topic_id, reply_to_post_number))


def _handle(model, handler):
    asyncio.run(handle_post_and_reply(model, 1, handler))
    return model.replies


def test_reply_is_posted_to_the_same_post():
    async def handler(post, user):
        assert (user.id, user.display_name) == (7, "alice")
        return f"hi {post.raw}"

    assert _handle(FakeModel("there"), handler) == [("hi there", 100, 5)]


def test_no_reply_when_handler_returns_none():
    async def handler(post, user):
        return None

    assert _handle(FakeModel("there"), handler) == []


def test_auto_replies_and_empty_posts_are_skipped():
    async def handler(post, user):
        raise AssertionError("handler should not be called")

    assert _handle(FakeModel(f"x {settings.auto_reply_tag}"), handler) == []
    assert _handle(FakeModel(None), handler) == []


def test_error_reply_when_handler_fails():
    async def handler(post, user):
        raise RuntimeError("boom")

    [(text, topic_id, post_number)] = _handle(FakeModel("there"), handler)
    assert text.startswith(GENERIC_ERROR_REPLY)
    assert (topic_id, post_number) == (100, 5)
