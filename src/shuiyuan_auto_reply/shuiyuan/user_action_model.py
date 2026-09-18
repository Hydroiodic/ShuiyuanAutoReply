import asyncio
import logging
import traceback
from abc import ABC, abstractmethod
from typing import List

from .objects import UserActionDetails
from .reply_utils import generate_random_string, make_unique_reply
from .shuiyuan_model import ShuiyuanModel


class BaseUserActionModel(ABC):
    """
    A class to represent a mention model.
    """

    def __init__(self, model: ShuiyuanModel, username: str, action_type: List[int]):
        """
        Initialize the MentionModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param username: The username to be managed.
        :param action_type: The list of action types to monitor.
        """
        self.model = model
        self.username = username
        self.action_type = action_type
        self.stream_list = []
        self._bg_tasks = set()

    # Shared helpers, kept as static methods for backward compatibility
    _generate_random_string = staticmethod(generate_random_string)
    _make_unique_reply = staticmethod(make_unique_reply)

    def _on_bg_task_done(self, task: "asyncio.Task") -> None:
        self._bg_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logging.error(
                "Background action routine failed", exc_info=task.exception()
            )

    @abstractmethod
    async def _new_action_routine(self, action: UserActionDetails) -> None:
        """
        A routine to handle new actions.
        NOTE: no exception should be raised in this method.

        :param action: The details of the action notification.
        :return: None
        """
        pass

    async def watch_new_action_routine(self) -> None:
        """
        A routine to watch for new actions.
        """
        while True:
            # Get the mention details
            try:
                actions = await self.model.get_actions(self.username, self.action_type)
                action_details = actions.user_actions
            except Exception:
                logging.error(
                    f"Failed to get action details for {self.username}, "
                    f"traceback is as follows:\n{traceback.format_exc()}"
                )
                # Back off briefly so a persistent failure cannot busy-loop
                await asyncio.sleep(5.0)
                continue

            # OK, let's difference the current stream with the new one
            new_stream = [detail.post_id for detail in action_details]

            # If the stream list is empty, we should initialize it
            if not self.stream_list:
                self.stream_list = new_stream
                continue

            # Only process actions on posts we haven't seen before. Cutting at
            # the first known post_id would drop genuinely new actions listed
            # after an old one, and reprocess everything when no overlap exists.
            known_post_ids = set(self.stream_list)
            new_actions = [
                detail
                for detail in action_details
                if detail.post_id not in known_post_ids
            ]

            # OK, we have found the new posts, we should do some routine with them
            for mention in new_actions:
                task = asyncio.create_task(self._new_action_routine(mention))
                # keep a reference so tasks aren't garbage-collected
                self._bg_tasks.add(task)
                # remove task from the set (and log any error) when done
                task.add_done_callback(self._on_bg_task_done)

            # Update the stream list with the new stream
            self.stream_list = new_stream
