import os
from openai import AsyncOpenAI


class BaseTongyiModel:
    """
    A model for managing Tongyi Qianwen data.
    """

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
