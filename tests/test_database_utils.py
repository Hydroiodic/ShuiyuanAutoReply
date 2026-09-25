import pytest

from shuiyuan_auto_reply.database.utils import (
    env_flag,
    to_psycopg_url,
    to_sqlalchemy_async_url,
)


@pytest.mark.parametrize("value", ["1", "true", "Yes", " ON "])
def test_env_flag_truthy(monkeypatch, value):
    monkeypatch.setenv("TEST_FLAG", value)
    assert env_flag("TEST_FLAG")


def test_env_flag_checks_every_name(monkeypatch):
    monkeypatch.setenv("TEST_FLAG_A", "false")
    monkeypatch.delenv("TEST_FLAG_B", raising=False)
    assert not env_flag("TEST_FLAG_A", "TEST_FLAG_B")
    monkeypatch.setenv("TEST_FLAG_B", "1")
    assert env_flag("TEST_FLAG_A", "TEST_FLAG_B")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite+aiosqlite://", "sqlite+aiosqlite://"),
    ],
)
def test_to_sqlalchemy_async_url(url, expected):
    assert to_sqlalchemy_async_url(url) == expected


def test_to_psycopg_url():
    assert to_psycopg_url("postgresql+psycopg://h/db") == "postgresql://h/db"
    assert to_psycopg_url("postgresql://h/db") == "postgresql://h/db"
