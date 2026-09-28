import asyncio
import logging
import traceback
from abc import ABC, abstractmethod
from typing import List, Optional

from .background import BackgroundTaskMixin
from .objects import UserActionDetails
from .shuiyuan_model import ShuiyuanModel


class BaseUserActionModel(BackgroundTaskMixin, ABC):
    """
    A class to represent a user action model.
    """

    def __init__(self, model: ShuiyuanModel, username: str, action_type: List[int]):
        """
        Initialize the UserActionModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param username: The username to be managed.
        :param action_type: The list of action types to monitor.
        """
        super().__init__()
        self.model = model
        self.username = username
        self.action_type = action_type
        # None until the first successful poll, so that actions which already
        # existed at startup are not replayed
        self.stream_list: Optional[List[int]] = None

    @abstractmethod
    async def _new_action_routine(self, action: UserActionDetails) -> None:
        """
        A routine to handle new actions.
        NOTE: no exception should be raised in this method.

        :param action: The details of the action notification.
        :return: None
        """

    async def watch_new_action_routine(self) -> None:
        """
        A routine to watch for new actions.
        """
        while True:
            # Get the action details
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

            # On the first poll we only record what already exists. Checking
            # for None rather than an empty list means that the very first
            # action of an account with no history is still handled.
            if self.stream_list is None:
                self.stream_list = new_stream
                continue

            # Only process actions on posts we haven't seen before. Cutting at
            # the first known post_id would drop genuinely new actions listed
            # after an old one, and reprocess everything when no overlap exists.
            known_post_ids = set(self.stream_list)
            for detail in action_details:
                if detail.post_id not in known_post_ids:
                    self._spawn_background_task(self._new_action_routine(detail))

            # Update the stream list with the new stream
            self.stream_list = new_stream
