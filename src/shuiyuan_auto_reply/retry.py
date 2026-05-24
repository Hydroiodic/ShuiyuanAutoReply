import asyncio
import logging
import traceback
from functools import wraps
from typing import Awaitable, Callable, Optional, ParamSpec, TypeVar, cast, overload

P = ParamSpec("P")
_T = TypeVar("_T")


class _NoDefault:
    pass


_NO_DEFAULT = _NoDefault()


@overload
def async_retry(
    *,
    retries: int = 3,
    delay: float = 1.0,
    log_traceback: bool = False,
) -> Callable[[Callable[P, Awaitable[_T]]], Callable[P, Awaitable[_T]]]: ...


@overload
def async_retry(
    *,
    retries: int = 3,
    delay: float = 1.0,
    default: _T | Callable[[], _T],
    log_traceback: bool = False,
) -> Callable[[Callable[P, Awaitable[_T]]], Callable[P, Awaitable[_T]]]: ...


def async_retry(
    *,
    retries: int = 3,
    delay: float = 1.0,
    default: object = _NO_DEFAULT,
    log_traceback: bool = False,
) -> Callable[[Callable[P, Awaitable[_T]]], Callable[P, Awaitable[_T]]]:
    """Retry an async function, optionally returning a default after failures."""
    if retries < 1:
        raise ValueError("retries must be at least 1")

    def decorator(
        func: Callable[P, Awaitable[_T]],
    ) -> Callable[P, Awaitable[_T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> _T:
            last_error: Optional[Exception] = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_error = exc
                    if log_traceback:
                        logging.warning(
                            "%s attempt %d failed with error: %s, "
                            "traceback is as follows:\n%s",
                            func.__name__,
                            attempt + 1,
                            exc,
                            traceback.format_exc(),
                        )
                    else:
                        logging.warning(
                            "%s attempt %d failed: %s",
                            func.__name__,
                            attempt + 1,
                            exc,
                        )
                    if attempt < retries - 1:
                        await asyncio.sleep(delay)

            logging.error(
                "All %d attempts failed for function %s",
                retries,
                func.__name__,
            )
            if default is not _NO_DEFAULT:
                return cast(_T, default() if callable(default) else default)
            if last_error is not None:
                raise last_error
            raise RuntimeError(f"All {retries} attempts failed for {func.__name__}")

        return wrapper

    return decorator
