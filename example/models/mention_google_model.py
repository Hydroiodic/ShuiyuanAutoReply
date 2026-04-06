import asyncio
import logging
from typing import Dict, List, override
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    HarmBlockThreshold,
    HarmCategory,
)
from google.genai.errors import ServerError
from .mention_chat_model import MentionChatModel
from src.shuiyuan.shuiyuan_model import ShuiyuanModel


class MentionGeminiModel(MentionChatModel):
    """
    A model for managing Google Gemini data with Manual History Management.
    """

    def __init__(self, model: ShuiyuanModel):
        # Initialize the base class first to set up retriever and other components
        super().__init__(model)

        # Then initialize the Gemini model with specific parameters
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-pro-preview",
            temperature=0.8,
            safety_settings={
                # HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                # HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                # HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                # HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            },
            convert_system_message_to_human=False,
            client_args={"proxy": "socks5://127.0.0.1:7890"},
            # max_output_tokens=4096,
            # thinking_budget=2048,
        )

    def parse_model_output(self, raw_output: List[Dict | str]) -> str:
        """
        Parse the raw output from the model to extract the final response text.

        :param raw_output: The raw output from the model, which is expected to be a list of dicts/strings.
        :return: The extracted response text.
        """
        res = ""
        for item in raw_output:
            if isinstance(item, dict) and "text" in item:
                res += item["text"]
            if hasattr(item, "text"):
                res += item.text
            if isinstance(item, str):
                res += item
        return res.strip()

    @override
    async def get_pumpkin_response(self, topic_id, conversation, user):
        # Retry up to 3 times
        for _ in range(3):
            try:
                return await super().get_pumpkin_response(topic_id, conversation, user)
            except ServerError as e:
                logging.warning(f"Error getting response: {e}. Retrying...")
                await asyncio.sleep(1)
        # If all retries fail, raise an exception
        raise RuntimeError("Failed to get response after 3 attempts")
