import time
import asyncio
import logging
from typing import Optional
from shuiyuan.shuiyuan_model import ShuiyuanModel
from shuiyuan.topic_model import BaseTopicModel
from juhe.juhe_model import JuheModel
from juhe.objects import IndexModel


class StockTopicModel(BaseTopicModel):
    """
    A class to represent a topic model.
    """

    def __init__(self, model: ShuiyuanModel, topic_id: int):
        """
        Initialize the TopicModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param topic_id: The ID of the topic to be managed.
        """
        super().__init__(model, topic_id)
        self.juhe_model = JuheModel()

    async def _new_post_routine(self, _: int) -> None:
        raise NotImplementedError(
            "New post routine is not implemented in TarotTopicModel. "
            "Please implement this method in your subclass."
        )

    async def _daily_routine(self) -> None:
        """
        A routine to handle a daily task.
        NOTE: no exception should be raised in this method.

        :return: None
        """
        # This is the text to reply to the post
        text: Optional[str] = None

        try:
            # Get the two index stock data here
            shanghai_index, shenzhen_index = await asyncio.gather(
                self.juhe_model.get_shanghai_index(),
                self.juhe_model.get_shenzhen_index(),
            )

            def get_details_func(index: IndexModel) -> str:
                formatted_deal_pri = f"{int(float(index.dealPri)):,}".replace(",", " ")
                return (
                    f"**{index.name}**\n"
                    f"当前价格：{index.nowpri}\n"
                    f"涨幅：{index.increPer}%\n"
                    f"最高价：{index.highPri}\n"
                    f"最低价：{index.lowpri}\n"
                    f"成交额：{formatted_deal_pri}\n"
                )

            # Let's arrange the text to reply
            text = (
                f"**当前时间**(GMT+8)：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n\n"
                f"{get_details_func(shanghai_index)}\n"
                f"{get_details_func(shenzhen_index)}\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"---\n[right]来自南瓜Bot自动获取数据[/right]\n"
            )
        except Exception as e:
            # If we failed to get the stock data or any other error occurred
            logging.error(f"Failed to get stock data: {e}")
            # We should reply to the post with an error message
            text = (
                "抱歉，南瓜bot遇到了一个错误，暂时无法获取到大盘数据，请稍后再试。\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
            )
        finally:
            if text is not None:
                await self.model.reply_to_post(text, self.topic_id)
