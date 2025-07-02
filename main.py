import asyncio
from shuiyuan_model import ShuiyuanModel
from topic_model import TopicModel


async def main():
    """
    Main function to run the ShuiyuanModel.
    This function initializes the model and retrieves the session.
    """

    async with await ShuiyuanModel.create() as model:
        # Let's try to get the post streams
        topic_model = TopicModel(model, 388001)
        await topic_model.watch_routine()


if __name__ == "__main__":
    asyncio.run(main())
