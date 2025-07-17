import asyncio
import logging
from shuiyuan.objects import TimeInADay
from shuiyuan.shuiyuan_model import ShuiyuanModel
from tarot_topic_model import TarotTopicModel
from stock_topic_model import StockTopicModel

# Setup the logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


async def main():
    """
    Main function to run the ShuiyuanModel.
    This function initializes the model and retrieves the session.
    """

    async with await ShuiyuanModel.create() as model:
        # Let's try to get the post streams
        tarot_topic_model = TarotTopicModel(model, 388001)
        stock_topic_model = StockTopicModel(model, 392286)
        stock_topic_model.add_time_routine(TimeInADay(hour=9, minute=30))
        stock_topic_model.add_time_routine(TimeInADay(hour=11, minute=30))
        stock_topic_model.add_time_routine(TimeInADay(hour=15, minute=0))
        stock_topic_model.start_scheduler()
        await tarot_topic_model.watch_new_post_routine()


if __name__ == "__main__":
    asyncio.run(main())
