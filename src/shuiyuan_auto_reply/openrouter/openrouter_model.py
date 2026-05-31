import os
from typing import Dict, Optional

import httpx


def _normalize_socks_proxy_url(value: str) -> str:
    if value.lower().startswith("socks://"):
        return f"socks5://{value[len('socks://'):]}"
    return value


def normalize_socks_proxy_env() -> None:
    """
    httpx expects SOCKS proxy URLs to use socks5:// instead of socks://.
    """
    proxy_env_names = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    )

    for name in proxy_env_names:
        value = os.getenv(name)
        if value:
            os.environ[name] = _normalize_socks_proxy_url(value)


normalize_socks_proxy_env()

from openai import AsyncOpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "google/gemini-3.1-flash-lite-preview"
DEFAULT_OPENROUTER_MAX_RETRIES = 5
OPENROUTER_APP_REFERER = "https://github.com/Hydroiodic/ShuiyuanAutoReply"
OPENROUTER_APP_TITLE = "ShuiyuanAutoReply"
OPENROUTER_PROXY_ENV = "OPENROUTER_PROXY"


def openrouter_headers() -> Dict[str, str]:
    return {
        "HTTP-Referer": OPENROUTER_APP_REFERER,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
        "X-Title": OPENROUTER_APP_TITLE,
    }


def openrouter_model(env_name: str, default: str = DEFAULT_OPENROUTER_MODEL) -> str:
    return os.getenv(env_name, os.getenv("OPENROUTER_MODEL", default))


def openrouter_proxy_from_env() -> Optional[str]:
    proxy = os.getenv(OPENROUTER_PROXY_ENV)
    if not proxy:
        return None
    return _normalize_socks_proxy_url(proxy)


def openrouter_http_client(
    *,
    proxy: Optional[str] = None,
    trust_env: bool = True,
) -> httpx.Client:
    if proxy:
        proxy = _normalize_socks_proxy_url(proxy)
    return httpx.Client(proxy=proxy, trust_env=trust_env)


def openrouter_async_http_client(
    *,
    proxy: Optional[str] = None,
    trust_env: bool = True,
) -> httpx.AsyncClient:
    if proxy:
        proxy = _normalize_socks_proxy_url(proxy)
    return httpx.AsyncClient(proxy=proxy, trust_env=trust_env)


class BaseOpenRouterModel:
    """
    Base OpenRouter client using the OpenAI-compatible Chat Completions API.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = DEFAULT_OPENROUTER_MAX_RETRIES,
        proxy: Optional[str] = None,
        trust_env: bool = True,
    ):
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("Please set the OPENROUTER_API_KEY environment variable.")

        proxy = proxy or openrouter_proxy_from_env()
        http_client = None
        if proxy:
            http_client = openrouter_async_http_client(proxy=proxy, trust_env=False)
        elif not trust_env:
            http_client = openrouter_async_http_client(trust_env=False)

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or OPENROUTER_BASE_URL,
            default_headers=openrouter_headers(),
            http_client=http_client,
            max_retries=max_retries,
        )
