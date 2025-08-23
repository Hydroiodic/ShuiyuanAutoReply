import os

if not os.getenv("DASHSCOPE_API_KEY"):
    raise ValueError("Please set the DASHSCOPE_API_KEY environment variable.")
