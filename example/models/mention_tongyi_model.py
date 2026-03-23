import os
from typing import Optional
from langchain_community.chat_models.tongyi import ChatTongyi
from .mention_chat_model import MentionChatModel
from src.shuiyuan.objects import User
from src.shuiyuan.shuiyuan_model import ShuiyuanModel


class MentionTongyiModel(MentionChatModel):
    """
    A model for managing Tongyi Qianwen data.
    """

    def __init__(self, model: ShuiyuanModel):
        """
        Initialize the Tongyi Qianwen model.
        """
        # Initialize the base class first to set up retriever and other components
        super().__init__(model)

        # Define the ChatTongyi model
        self.llm = ChatTongyi(
            model_name="qwen3-max-2026-01-23",
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
            model_kwargs={
                "temperature": 1.5,
                "enable_thinking": True,
                "incremental_output": True,
            },
        )

    def parse_model_output(self, raw_output: str) -> str:
        """
        Parse the raw output from the model to extract the final response text.

        :param raw_output: The raw output from the model, which is expected to be a string.
        :return: The extracted response text.
        """
        return raw_output.strip()
