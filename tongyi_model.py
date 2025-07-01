import os
from openai import OpenAI
from tarot_group_data import BaseTarotGroup

if not os.getenv("DASHSCOPE_API_KEY"):
    raise ValueError("Please set the DASHSCOPE_API_KEY environment variable.")


class TongyiModel:
    """
    A model for managing Tongyi Qianwen data.
    """

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def consult_tarot_card(self, question: str, tarot_group: BaseTarotGroup) -> str:
        """
        Consult a tarot card with a given question.
        """
        # Let's arrange the tarot results into a string format
        tarot_results_str = str(tarot_group)
        tarot_results_str += (
            "\n\n请根据这些塔罗牌的含义分析我的问题。"
            "注意：需要结合每一张塔罗牌输出综合结果，语义简洁精炼，且必须结合我的问题来回答。\n\n"
        )

        # Create a chat completion request with the tarot results and question
        # TODO: async API
        response = self.client.chat.completions.create(
            model="qwen-max-2025-01-25",
            # extra_body={
            #     "enable_thinking": False,
            # },
            messages=[
                {
                    "role": "system",
                    "content": "You have great knowledge in tarot cards.",
                },
                {
                    "role": "user",
                    "content": f"{tarot_results_str}{question}",
                },
            ],
        )

        # Return the content of the first choice in the response
        return response.choices[0].message.content
