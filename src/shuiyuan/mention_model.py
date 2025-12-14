import asyncio
import random
import logging
import traceback
from abc import abstractmethod
from .objects import MentionNotificationDetails
from .shuiyuan_model import ShuiyuanModel
from ..constants import auto_reply_tag


class BaseMentionModel:
    """
    A class to represent a mention model.
    """

    def __init__(self, model: ShuiyuanModel, username: str):
        """
        Initialize the MentionModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param username: The username to be managed.
        """
        self.model = model
        self.username = username
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
            f"<!-- {BaseMentionModel._generate_random_string(20)} -->\n"
            f"{auto_reply_tag}"
        )

    @abstractmethod
    async def _new_mention_routine(self, mention: MentionNotificationDetails) -> None:
        """
        A routine to handle a new post in the topic.
        NOTE: no exception should be raised in this method.

        :param mention: The mention notification details.
        :return: None
        """
        pass

    async def watch_new_mention_routine(self) -> None:
        """
        A routine to watch for new mentions of the user.
        This method can be extended to implement real-time updates or periodic checks.
        """
        while True:
            # Get the mention details
            try:
                mentions = await self.model.get_mention_notification(self.username)
                mention_details = mentions.user_actions
            except Exception:
                logging.error(
                    f"Failed to get mention details for {self.topic_id}, "
                    f"traceback is as follows:\n{traceback.format_exc()}"
                )
                continue

            # OK, let's difference the current stream with the new one
            new_stream = [mention.post_id for mention in mention_details]

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
                new_mentions = mention_details[:last_index]

                # OK, we have find the new posts, we should do some routine with them
                routines = [
                    self._new_mention_routine(mention) for mention in new_mentions
                ]
                asyncio.gather(*routines)

            # Update the stream list with the new stream
            self.stream_list = new_stream
