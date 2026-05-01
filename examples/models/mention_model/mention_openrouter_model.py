import os
from typing import Any

from langchain_openai import ChatOpenAI

from shuiyuan_auto_reply.openrouter.openrouter_model import (
    DEFAULT_OPENROUTER_MAX_RETRIES,
    OPENROUTER_BASE_URL,
    openrouter_headers,
    openrouter_model,
)
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel

from .mention_chat_model import MentionChatModel


class MentionOpenRouterModel(MentionChatModel):
    """
    A model for managing OpenRouter-backed conversation data.
    """

    def __init__(self, model: ShuiyuanModel):
        # Initialize the base class first to set up retriever and other components
        super().__init__(model)

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("Please set the OPENROUTER_API_KEY environment variable.")

        self.llm = ChatOpenAI(
            model=openrouter_model("OPENROUTER_MENTION_MODEL"),
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            temperature=0.8,
            default_headers=openrouter_headers(),
            max_retries=DEFAULT_OPENROUTER_MAX_RETRIES,
        )

    def parse_model_output(self, raw_output: Any) -> str:
        """
        Parse the raw output from the model to extract the final response text.

        :param raw_output: The raw output from the model.
        :return: The extracted response text.
        """
        if raw_output is None:
            return ""
        if isinstance(raw_output, str):
            return raw_output.strip()

        res = ""
        if isinstance(raw_output, list):
            for item in raw_output:
                if isinstance(item, dict) and "text" in item:
                    res += item["text"]
                if hasattr(item, "text"):
                    res += item.text
                if isinstance(item, str):
                    res += item
        return res.strip()
