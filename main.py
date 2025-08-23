import asyncio
import dotenv
import logging

# Setup the logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Load all environment variables from the .env file
dotenv.load_dotenv()


from shuiyuan.objects import TimeInADay
from shuiyuan.shuiyuan_model import ShuiyuanModel
from tarot_topic_model import TarotTopicModel
from stock_topic_model import StockTopicModel
from dog_topic_model import DogTopicModel


async def main():
    """
    Main function to run the ShuiyuanModel.
    This function initializes the model and retrieves the session.
    """

    async with await ShuiyuanModel.create() as model:
        # Let's try to get the post streams
        tarot_topic_model = TarotTopicModel(model, 388001)
        stock_topic_model = StockTopicModel(model, 392286)
        dog_topic_model = DogTopicModel(model, 406862)

        stock_topic_model.add_time_routine(TimeInADay(hour=9, minute=30), True)
        stock_topic_model.add_time_routine(TimeInADay(hour=11, minute=30), True)
        stock_topic_model.add_time_routine(TimeInADay(hour=15, minute=0), True)
        dog_topic_model.add_time_routine(TimeInADay(hour=0, minute=0), False)

        stock_topic_model.start_scheduler()
        dog_topic_model.start_scheduler()

        await asyncio.gather(
            tarot_topic_model.watch_new_post_routine(),
            stock_topic_model.watch_new_post_routine(),
            dog_topic_model.watch_new_post_routine(),
        )

        stock_topic_model.stop_scheduler()
        dog_topic_model.stop_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
