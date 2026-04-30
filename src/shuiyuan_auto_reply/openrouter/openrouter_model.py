import os
from typing import Optional


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
        if value and value.lower().startswith("socks://"):
            os.environ[name] = f"socks5://{value[len('socks://'):]}"


normalize_socks_proxy_env()

from openai import AsyncOpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "google/gemini-3.1-flash-lite-preview"
OPENROUTER_APP_REFERER = "https://github.com/Hydroiodic/ShuiyuanAutoReply"
OPENROUTER_APP_TITLE = "ShuiyuanAutoReply"


def openrouter_headers() -> dict[str, str]:
    return {
        "HTTP-Referer": OPENROUTER_APP_REFERER,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
        "X-Title": OPENROUTER_APP_TITLE,
    }


def openrouter_model(env_name: str, default: str = DEFAULT_OPENROUTER_MODEL) -> str:
    return os.getenv(env_name, os.getenv("OPENROUTER_MODEL", default))


class BaseOpenRouterModel:
    """
    Base OpenRouter client using the OpenAI-compatible Chat Completions API.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("Please set the OPENROUTER_API_KEY environment variable.")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or OPENROUTER_BASE_URL,
            default_headers=openrouter_headers(),
        )
