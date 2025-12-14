import asyncio
import random
import logging
import traceback
from typing import List
from abc import abstractmethod
from .objects import UserActionDetails
from .shuiyuan_model import ShuiyuanModel
from ..constants import auto_reply_tag


class BaseUserActionModel:
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

    @staticmethod
    def _generate_random_string(length: int) -> str:
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

    @staticmethod
    def _make_unique_reply(base: str) -> str:
        """
        Append a random string to the base reply to make it unique.

        :param base: The base reply string.
        :return: The unique reply string.
        """
        return (
            f"{base}\n\n"
            f"<!-- {BaseUserActionModel._generate_random_string(20)} -->\n"
            f"{auto_reply_tag}"
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
                continue

            # OK, let's difference the current stream with the new one
            new_stream = [detail.post_id for detail in action_details]

            # If the stream list is empty, we should initialize it
            if not self.stream_list:
                self.stream_list = new_stream
                continue

            # Try to find the last known post in the new stream
            last_stream = None
            for post_id in reversed(new_stream):
                if post_id not in self.stream_list:
                    last_stream = post_id
                    break

            # If we found the last known post, slice the new stream
            if last_stream is not None:
                # Slice the new stream to get only the new posts
                last_index = new_stream.index(last_stream) + 1
                new_actions = action_details[:last_index]

                # OK, we have find the new posts, we should do some routine with them
                routines = [
                    self._new_action_routine(mention) for mention in new_actions
                ]
                asyncio.gather(*routines)

            # Update the stream list with the new stream
            self.stream_list = new_stream
