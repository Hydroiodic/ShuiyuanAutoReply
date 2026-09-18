import asyncio
import logging
import traceback
from abc import ABC, abstractmethod

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .objects import TimeInADay
from .reply_utils import generate_random_string, make_unique_reply
from .shuiyuan_model import ShuiyuanModel


class BaseTopicModel(ABC):
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
        self._bg_tasks = set()

    # Shared helpers, kept as static methods for backward compatibility
    _generate_random_string = staticmethod(generate_random_string)
    _make_unique_reply = staticmethod(make_unique_reply)

    def _on_bg_task_done(self, task: "asyncio.Task") -> None:
        self._bg_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logging.error(
                "Background post routine failed", exc_info=task.exception()
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

                # OK, we have found the new posts — start each routine as a
                # background task so the watcher loop doesn't block waiting
                # for them to finish.
                for post_id in new_posts:
                    task = asyncio.create_task(self._new_post_routine(post_id))
                    # keep a reference so tasks aren't garbage-collected
                    self._bg_tasks.add(task)
                    # remove task from the set (and log any error) when done
                    task.add_done_callback(self._on_bg_task_done)

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
