import asyncio
import logging

import dotenv

# Setup the logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Load all environment variables from the .env file
dotenv.load_dotenv()

from shuiyuan_auto_reply.shuiyuan.objects import TimeInADay
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel

from .models.mention_model.mention_model import MentionModel
from .models.record_model.record_topic_model import RecordTopicModel
from .models.stock_model.stock_topic_model import StockTopicModel
from .models.tarot_model.tarot_topic_model import TarotTopicModel


async def main():
    """
    Main function to run the ShuiyuanModel.
    This function initializes the model and retrieves the session.
    """

    async with await ShuiyuanModel.create() as model:
        # Let's try to get the post streams
        mention_model = MentionModel(model, "MonkeysPumpkin")
        tarot_topic_model = TarotTopicModel(model, 456849)
        # stock_topic_model = StockTopicModel(model, 392286)
        record_topic_model = RecordTopicModel(model, 441566)

        # stock_topic_model.add_time_routine(TimeInADay(hour=9, minute=30), True)
        # stock_topic_model.add_time_routine(TimeInADay(hour=11, minute=30), True)
        # stock_topic_model.add_time_routine(TimeInADay(hour=15, minute=0), True)
        record_topic_model.add_time_routine(TimeInADay(hour=0, minute=0), False)

        # stock_topic_model.start_scheduler()
        record_topic_model.start_scheduler()

        await asyncio.gather(
            mention_model.watch_new_action_routine(),
            tarot_topic_model.watch_new_post_routine(),
            # stock_topic_model.watch_new_post_routine(),
            record_topic_model.watch_new_post_routine(),
        )

        # stock_topic_model.stop_scheduler()
        record_topic_model.stop_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
