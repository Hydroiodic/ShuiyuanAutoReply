import asyncio
import logging
import traceback
from abc import ABC, abstractmethod
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .background import BackgroundTaskMixin
from .objects import TimeInADay
from .shuiyuan_model import ShuiyuanModel


class BaseTopicModel(BackgroundTaskMixin, ABC):
    """
    A class to represent a topic model.
    """

    def __init__(self, model: ShuiyuanModel, topic_id: int):
        """
        Initialize the TopicModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param topic_id: The ID of the topic to be managed.
        """
        super().__init__()
        self.model = model
        self.topic_id = topic_id
        self.stream_list: List[int] = []
        self.scheduler = AsyncIOScheduler()

    @abstractmethod
    async def _new_post_routine(self, post_id: int) -> None:
        """
        A routine to handle a new post in the topic.
        NOTE: no exception should be raised in this method.

        :param post_id: The ID of the new post.
        :return: None
        """

    @abstractmethod
    async def _daily_routine(self) -> None:
        """
        A routine to perform daily tasks.
        This method can be used to implement daily checks or updates.

        :return: None
        """

    async def watch_new_post_routine(self) -> None:
        """
        A routine to watch for updates on the topic.
        This method can be extended to implement real-time updates or periodic checks.
        """
        while True:
            # Get the topic details
            try:
                topic_details = await self.model.get_topic_details(self.topic_id)
            except Exception:
                logging.error(
                    f"Failed to get topic details for {self.topic_id}, "
                    f"traceback is as follows:\n{traceback.format_exc()}"
                )
                # Back off briefly so a persistent failure cannot busy-loop
                await asyncio.sleep(5.0)
                continue

            # OK, let's difference the current stream with the new one
            new_stream = topic_details.post_stream.stream

            # Try to find the last element in the previous stream, which is still in the new stream
            new_stream_ids = set(new_stream)
            last_stream = next(
                (
                    post_id
                    for post_id in reversed(self.stream_list)
                    if post_id in new_stream_ids
                ),
                None,
            )

            # If we found the last known post, every post after it is new.
            # Start each routine as a background task so the watcher loop
            # doesn't block waiting for them to finish.
            if last_stream is not None:
                start_index = new_stream.index(last_stream) + 1
                for post_id in new_stream[start_index:]:
                    self._spawn_background_task(self._new_post_routine(post_id))

            # Update the stream list with the new stream
            self.stream_list = new_stream

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
