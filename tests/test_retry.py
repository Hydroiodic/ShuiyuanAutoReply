import asyncio

import pytest

from shuiyuan_auto_reply.retry import async_retry


def test_retry_until_success():
    calls = []

    @async_retry(retries=3, delay=0)
    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("boom")
        return "ok"

    assert asyncio.run(flaky()) == "ok"
    assert len(calls) == 3


def test_retry_returns_default_after_failures():
    @async_retry(retries=2, delay=0, default=list)
    async def always_fails():
        raise RuntimeError("boom")

    assert asyncio.run(always_fails()) == []


def test_retry_raises_last_error_without_default():
    @async_retry(retries=2, delay=0)
    async def always_fails():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(always_fails())


def test_retry_rejects_non_positive_retries():
    with pytest.raises(ValueError):
        async_retry(retries=0)
