import re
import logging
import traceback
from typing import Optional
from src.shuiyuan.objects import User, MentionNotificationDetails
from src.shuiyuan.shuiyuan_model import ShuiyuanModel
from src.shuiyuan.mention_model import BaseMentionModel
from src.constants import auto_reply_tag
from .mention_tongyi_model import MentionTongyiModel


class MentionModel(BaseMentionModel):
    """
    A class to represent a mention model for robot auto-replies.
    """

    def __init__(self, model: ShuiyuanModel, username: str):
        """
        Initialize the TopicModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param username: The username of the robot account.
        """
        super().__init__(model, username)
        self.mention_tongyi_model = MentionTongyiModel()

    @staticmethod
    def _remove_shuiyuan_signature(text: str) -> str:
        """
        Remove the Shuiyuan signature from the given text.

        :param text: The text from which to remove the signature.
        :return: The text without the signature.
        """
        sig_re = r"<div data-signature>.*?</div>"
        return re.sub(sig_re, "", text, flags=re.DOTALL).strip()

    @staticmethod
    def _parse_prompt_text(raw: str, prompt: str) -> Optional[str]:
        """
        Return text after the first occurrence of the prompt in raw.
        And remove the prompt itself and Shuiyuan signature.

        :param raw: The raw content of the post.
        :param prompt: The prompt string to look for.
        :return: The parsed text after the prompt or None if prompt not found.
        """
        # Get the text after the first occurrence of the prompt
        irst_occurrence = raw.find(prompt)
        if irst_occurrence == -1:
            return None
        raw = raw[irst_occurrence:]

        # Remove the keyword itself
        raw = MentionModel._remove_shuiyuan_signature(raw.replace(prompt, "")).strip()
        return raw

    async def _pumpkin_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【小南瓜】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【小南瓜】", we return None
        raw = MentionModel._parse_prompt_text(raw, "【小南瓜】")
        if raw is None:
            return None

        # Let the Tongyi model respond based on conversation and similar responses
        reply = await self.record_tongyi_model.get_pumpkin_response(raw, user)
        return MentionModel._make_unique_reply(reply)

    def _help_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【帮助】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "帮助", we return None
        if "【帮助】" not in raw:
            return None

        return MentionModel._make_unique_reply(
            "帮助信息如下：\n"
            "1. 输入【小南瓜】+对话，与南瓜bot聊天 :jack_o_lantern:\n"
            "2. 输入【帮助】，查看该帮助信息 :question:"
        )

    async def _new_post_routine(self, mention: MentionNotificationDetails) -> None:
        """
        A routine to handle a new post in the topic.
        NOTE: no exception should be raised in this method.

        :param mention: The details of the mention notification.
        :return: None
        """
        # This is the text to reply to the post
        text: Optional[str] = None

        try:
            # First let's try to get the post details
            post_details = await self.model.get_post_details(mention.post_id)
            post_user = User(
                post_details.user_id,
                post_details.username,
                post_details.name,
            )

            # If the member "raw" is not present, we should skip it
            if post_details.raw is None:
                logging.warning(
                    f"Post {mention.post_id} does not have raw content, skipping."
                )
                return

        except Exception:
            logging.error(
                f"Failed to get post details for {mention.post_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            return

        try:
            # If the post is an auto-reply, we should skip it
            if auto_reply_tag in post_details.raw:
                return

            # Check help condition
            text = self._help_condition(post_details.raw)
            if text is not None:
                return

            # Check pumpkin condition
            text = await self._pumpkin_condition(post_details.raw, post_user)
            if text is not None:
                return

        except Exception:
            # If we failed to get the post details or any other error occurred
            logging.error(
                f"Failed to process post {mention.post_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            # We should reply to the post with an error message
            text = MentionModel._make_unique_reply(
                "抱歉，南瓜bot遇到了一个错误，暂时无法处理您的请求，请稍后再试"
            )

        finally:
            if text is not None:
                await self.model.reply_to_post(
                    text,
                    mention.topic_id,
                    mention.post_number,
                )
