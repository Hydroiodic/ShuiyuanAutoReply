import os
from typing import Any

import langchain_core.utils.function_calling as function_calling
from langchain_openai import ChatOpenAI

from shuiyuan_auto_reply.openrouter.openrouter_model import (
    DEFAULT_OPENROUTER_MAX_RETRIES,
    OPENROUTER_BASE_URL,
    openrouter_headers,
    openrouter_model,
)
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel

from .mention_chat_model import MentionChatModel


def _register_openrouter_tool_types(tools: list[dict[str, Any]]) -> None:
    for tool in tools:
        tool_type = tool.get("type")
        if tool_type and tool_type not in function_calling._WellKnownOpenAITools:
            function_calling._WellKnownOpenAITools = (
                *function_calling._WellKnownOpenAITools,
                tool_type,
            )


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

        self.openai_tools = [
            {
                "type": "openrouter:web_search",
                "parameters": {
                    "engine": "exa",
                    "max_results": 2,
                    "max_total_results": 4,
                },
            },
        ]
        _register_openrouter_tool_types(self.openai_tools)

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
