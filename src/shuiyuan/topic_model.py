import asyncio
import random
import logging
from abc import abstractmethod
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .objects import TimeInADay
from .shuiyuan_model import ShuiyuanModel


class BaseTopicModel:
    """
    A class to represent a topic model.
    """

    def __init__(self, model: ShuiyuanModel, topic_id: int):
        """
        Initialize the TopicModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param topic_id: The ID of the topic to be managed.
        """
        self.model = model
        self.topic_id = topic_id
        self.stream_list = []
        self.scheduler = AsyncIOScheduler()

    def _generate_random_string(self, length: int) -> str:
        """
        Generate a random string of a given length.

        :param length: The length of the random string to generate.
        :return: A random string of the specified length.
        """
        return "".join(
            random.sample(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                k=length,
            )
        )

    @abstractmethod
    async def _new_post_routine(self, post_id: int) -> None:
        """
        A routine to handle a new post in the topic.
        NOTE: no exception should be raised in this method.

        :param post_id: The ID of the new post.
        :return: None
        """
        pass

    @abstractmethod
    async def _daily_routine(self) -> None:
        """
        A routine to perform daily tasks.
        This method can be used to implement daily checks or updates.

        :return: None
        """
        pass

    async def watch_new_post_routine(self) -> None:
        """
        A routine to watch for updates on the topic.
        This method can be extended to implement real-time updates or periodic checks.
        """
        while True:
            # Get the topic details
            try:
                topic_details = await self.model.get_topic_details(self.topic_id)
            except Exception as e:
                logging.error(f"Failed to get topic details for {self.topic_id}: {e}")
                await asyncio.sleep(2)
                continue

            # OK, let's difference the current stream with the new one
            new_stream = topic_details.post_stream.stream

            # Try to find the last element in the previous stream, which is still in the new stream
            last_stream = None
            for post_id in reversed(self.stream_list):
                if post_id in new_stream:
                    last_stream = post_id
                    break

            # If we found the last known post, we can slice the new stream
            if last_stream is not None:
                # Slice the new stream from the last known post
                start_index = new_stream.index(last_stream) + 1
                new_posts = new_stream[start_index:]

                # OK, we have find the new posts, we should do some routine with them
                routines = [self._new_post_routine(post_id) for post_id in new_posts]
                asyncio.gather(*routines)

            # Update the stream list with the new stream
            self.stream_list = new_stream

            # Sleep or wait for a condition to avoid busy waiting
            await asyncio.sleep(2)

    def add_time_routine(
        self,
        activate_time: TimeInADay,
        skip_weekends: bool = False,
    ) -> None:
        """
        A routine to perform actions at a specific time.

        :param activate_time: The time to activate the routine.
        :param skip_weekends: If True, the routine will not run on weekends.
        :return: None
        """
        day_of_week = "mon-fri" if skip_weekends else "*"
        self.scheduler.add_job(
            self._daily_routine,
            "cron",
            day_of_week=day_of_week,
            hour=activate_time.hour,
            minute=activate_time.minute,
            second=activate_time.second,
        )

    def start_scheduler(self) -> None:
        """
        Start the scheduler to run the daily routine at the specified time.

        :return: None
        """
        self.scheduler.start()

    def stop_scheduler(self) -> None:
        """
        Stop the scheduler.

        :return: None
        """
        self.scheduler.shutdown(wait=False)
