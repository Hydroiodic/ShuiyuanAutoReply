import io
import os
import skia
import math
import asyncio
import logging
import traceback
from PIL import Image
from typing import Optional
from fortune.fortune_model import FortuneModel
from shuiyuan.objects import User
from shuiyuan.shuiyuan_model import ShuiyuanModel
from shuiyuan.topic_model import BaseTopicModel
from tarot_tongyi_model import TarotTongyiModel
from tarot.tarot_model import TarotModel
from tarot.tarot_group_data import (
    TarotResult,
    get_image_from_cache,
    save_image_to_cache,
)

_auto_reply_tag = "<!-- 来自南瓜的自动回复 -->"


class TarotTopicModel(BaseTopicModel):
    """
    A class to represent a topic model.
    """

    def __init__(self, model: ShuiyuanModel, topic_id: int):
        """
        Initialize the TopicModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param topic_id: The ID of the topic to be managed.
        """
        super().__init__(model, topic_id)
        self.tongyi_model = TarotTongyiModel()

        assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        self.tarot_model = TarotModel(
            tarot_data_path=os.path.join(assets_dir, "tarot_data.json"),
            tarot_img_path=os.path.join(assets_dir, "tarot_img"),
        )

    async def _upload_and_get_tarot_image_url(
        self,
        result: TarotResult,
        try_base64: bool = True,
        try_base64_size_kb: int = 40,
    ) -> str:
        """
        Upload an image and return its URL.

        :param result: The TarotResult containing the image path.
        :param try_base64: Whether to try converting the image to base64 if upload fails.
        :param try_base64_size_kb: The maximum size in KB for base64 conversion.
        :return: The URL of the uploaded image.
        """
        # First let's check if the image is already cached
        url = get_image_from_cache(result)
        if url is not None:
            return url

        # Load the image from the tarot image path
        image_path = os.path.join(
            self.tarot_model.tarot_img_path,
            f"{result.index}{'_rev' if result.is_reversed else ''}.jpg",
        )
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Upload the image and get the response
        response = await self.model.try_upload_image(
            image_bytes, try_base64, try_base64_size_kb
        )

        # Return the URL of the uploaded image
        if response.type == "url":
            save_image_to_cache(result, response.data)
        return response.data

    async def _533_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "533".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # At first convert some characters
        raw = raw.replace(" ", "").replace("\n", "")
        raw = raw.replace("Ⅴ", "5").replace("Ⅲ", "3")
        raw = raw.replace("五", "5").replace("三", "3")
        raw = raw.replace("伍", "5").replace("叁", "3")
        raw = raw.replace("⑤", "5").replace("③", "3")

        # Generate a unique reply text
        text = "鹊\n\n---\n[right]这是一条自动回复[/right]\n"
        text += f"<!-- {self._generate_random_string(20)} -->\n"
        text += _auto_reply_tag

        # If the raw content contains "533", we return the text
        if "我要谈恋爱" in raw or "533" in raw:
            return text

        return None

    async def _tarot_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【塔罗牌】".

        :param raw: The raw content of the post.
        :param user: The user who posted the content.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content contains "【塔罗牌】", we reply to the post
        if "【塔罗牌】" not in raw:
            return None

        # OK, let's generate a reply
        tarot_group = await self.tarot_model.choose_tarot_group(
            raw.replace("【塔罗牌】", "")
        )

        # Let GPT tell us the meaning of the tarot cards
        text = '---\n\n[details="分析和建议"]\n'
        text += await self.tongyi_model.consult_tarot_card(
            raw.replace("【塔罗牌】", ""), tarot_group
        )
        text += "\n[/details]\n"

        # Load image for the tarot group
        tarot_result = tarot_group.tarot_results
        urls = await asyncio.gather(
            *[
                self._upload_and_get_tarot_image_url(
                    result, True, math.floor(40.0 / len(tarot_result))
                )
                for result in tarot_result
            ]
        )

        # Now update the tarot results with the image URLs
        for i, result in enumerate(tarot_result):
            result.img_url = urls[i]

        # Prepend the tarot group string
        used_username = (
            user.name if user.name is not None and user.name != "" else user.username
        )
        return (
            f"你好！{used_username}，"
            f"欢迎来到南瓜的塔罗牌自助占卜小屋！请注意占卜结果仅供娱乐参考哦！\n\n"
            + str(tarot_group)
            + text
            + _auto_reply_tag
        )

    async def _fortune_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【今日运势】".

        :param raw: The raw content of the post.
        :param user: The user who posted the content.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【今日运势】", we return None
        if "【今日运势】" not in raw:
            return None

        # OK, let's create the fortune model
        username = (
            user.name if user.name is not None and user.name != "" else user.username
        )
        fortune_model = FortuneModel(username)

        # Generate an image for the fortune today
        bytes_buffer = io.BytesIO()
        fortune_img = fortune_model.generate_fortune()
        fortune_img.save(bytes_buffer, skia.EncodedImageFormat.kJPEG)

        # Upload the image and get the response
        response = await self.model.try_upload_image(bytes_buffer.getvalue(), True)

        # Generate the fortune text
        text = f"{username}，你好！请收下你的今日运势：\n\n"
        text += f"{response.data}\n\n"
        text += f"\n\n<!-- {self._generate_random_string(20)} -->\n"
        text += _auto_reply_tag

        return text

    async def _help_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "帮助".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "帮助", we return None
        if "【帮助】" not in raw:
            return None

        # OK, let's generate a reply
        text = "帮助信息如下：\n"
        text += "1. 输入【塔罗牌】+问题，可以进行塔罗牌占卜 :crystal_ball:\n"
        text += "2. 输入【今日运势】，获取你的今日运势 :dotted_six_pointed_star:\n"
        text += "3. 输入533或某些变体，可以获得鹊的祝福 :bird:\n"
        text += "4. 输入【帮助】，可以查看本帮助信息\n"
        text += f"<!-- {self._generate_random_string(20)} -->\n"
        text += _auto_reply_tag

        return text

    async def _new_post_routine(self, post_id: int) -> None:
        """
        A routine to handle a new post in the topic.
        NOTE: no exception should be raised in this method.

        :param post_id: The ID of the new post.
        :return: None
        """
        # This is the text to reply to the post
        text: Optional[str] = None

        try:
            # First let's try to get the post details
            post_details = await self.model.get_post_details(post_id)
            post_user = User(
                post_details.user_id,
                post_details.username,
                post_details.name,
            )

            # If the member "raw" is not present, we should skip it
            if post_details.raw is None:
                logging.warning(f"Post {post_id} does not have raw content, skipping.")
                return

            # If the post is an auto-reply, we should skip it
            if _auto_reply_tag in post_details.raw:
                return

            # OK, check the content of the post
            # If the help condition is met, we should not check other conditions
            text = await self._help_condition(post_details.raw)
            if text is not None:
                return

            # Check fortune condition
            # If the fortune condition is met, we should not check other conditions
            text = await self._fortune_condition(
                post_details.raw,
                user=post_user,
            )
            if text is not None:
                return

            # Check tarot condition
            text = await self._tarot_condition(
                post_details.raw,
                user=post_user,
            )

            # If the tarot condition is not met, check the 533 condition
            if text is None:
                text = await self._533_condition(post_details.raw)

            # Shuiyuan has a maximum length for a post (65535 characters)
            # If our reply is too long, we should raise an error
            if text is not None and len(text) > 65535:
                text = (
                    "抱歉，南瓜bot生成的回复内容过长，无法正常发送，请联系东川路笨蛋小南瓜处理。\n\n"
                    f"<!-- {self._generate_random_string(20)} -->\n"
                    f"{_auto_reply_tag}"
                )
        except Exception as e:
            # If we failed to get the post details or any other error occurred
            logging.error(
                f"Failed to get post details for {post_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            # We should reply to the post with an error message
            text = (
                "抱歉，南瓜bot遇到了一个错误，暂时无法处理您的请求，请稍后再试。\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"{_auto_reply_tag}"
            )
        finally:
            if text is not None:
                await self.model.reply_to_post(
                    text,
                    self.topic_id,
                    post_details.post_number,
                )

    async def _daily_routine(self) -> None:
        raise NotImplementedError(
            "Daily routine is not implemented in TopicModel. "
            "Please implement this method in your subclass."
        )
