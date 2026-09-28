import os

_TRUTHY_VALUES = {"1", "true", "yes", "on"}
_ASYNC_POSTGRES_SCHEME = "postgresql+psycopg://"


def env_flag(*names: str) -> bool:
    """Return True if any of the given environment variables is set to a truthy value."""
    return any(os.getenv(name, "").strip().lower() in _TRUTHY_VALUES for name in names)


def to_sqlalchemy_async_url(db_url: str) -> str:
    """Convert a plain Postgres URL to one that uses the async psycopg driver."""
    for prefix in ("postgresql://", "postgres://"):
        if db_url.startswith(prefix):
            return _ASYNC_POSTGRES_SCHEME + db_url.removeprefix(prefix)
    return db_url


def to_psycopg_url(db_url: str) -> str:
    """Convert a SQLAlchemy psycopg URL back to a plain Postgres URL."""
    if db_url.startswith(_ASYNC_POSTGRES_SCHEME):
        return "postgresql://" + db_url.removeprefix(_ASYNC_POSTGRES_SCHEME)
    return db_url
