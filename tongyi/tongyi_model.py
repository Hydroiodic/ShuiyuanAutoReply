import os
from openai import OpenAI

if not os.getenv("DASHSCOPE_API_KEY"):
    raise ValueError("Please set the DASHSCOPE_API_KEY environment variable.")


class BaseTongyiModel:
    """
    A model for managing Tongyi Qianwen data.
    """

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
