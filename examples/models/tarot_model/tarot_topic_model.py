import asyncio
import io
import math
import os
from typing import Optional

import skia

from shuiyuan_auto_reply.constants import settings
from shuiyuan_auto_reply.fortune.fortune_model import FortuneModel
from shuiyuan_auto_reply.shuiyuan.objects import PostDetails, User
from shuiyuan_auto_reply.shuiyuan.reply_utils import make_unique_reply
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel
from shuiyuan_auto_reply.shuiyuan.topic_model import BaseTopicModel
from shuiyuan_auto_reply.tarot.tarot_group_data import (
    TarotResult,
    get_image_from_cache,
    save_image_to_cache,
)
from shuiyuan_auto_reply.tarot.tarot_model import TarotModel

from ..common import handle_post_and_reply
from .tarot_openrouter_model import TarotOpenRouterModel

# Shuiyuan rejects posts longer than this
_MAX_POST_LENGTH = 65535


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
        self.openrouter_model = TarotOpenRouterModel()
        self.tarot_model = TarotModel(
            tarot_data_path=os.path.join(settings.assets_directory, "tarot_data.json"),
            tarot_img_path=os.path.join(settings.assets_directory, "tarot_img"),
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

        # If the raw content contains "533", we return the text
        if "我要谈恋爱" in raw or "533" in raw:
            return make_unique_reply("鹊\n\n---\n[right]这是一条自动回复[/right]")

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

        # Let OpenRouter tell us the meaning of the tarot cards
        text = '---\n\n[details="分析和建议"]\n'
        text += await self.openrouter_model.consult_tarot_card(
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
        return make_unique_reply(
            f"你好！{user.display_name}，"
            f"欢迎来到南瓜的塔罗牌自助占卜小屋！请注意占卜结果仅供娱乐参考哦！\n\n"
            f"{str(tarot_group)}"
            f"{text}"
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
        username = user.display_name
        fortune_model = FortuneModel(username)

        # Generate an image for the fortune today. The rendering is CPU-bound
        # synchronous work, so run it off the event loop.
        bytes_buffer = io.BytesIO()
        fortune_img = await asyncio.to_thread(fortune_model.generate_fortune)
        fortune_img.save(bytes_buffer, skia.EncodedImageFormat.kJPEG)

        # Upload the image and get the response
        response = await self.model.try_upload_image(bytes_buffer.getvalue(), True)

        # Return the fortune text
        return make_unique_reply(
            f"{username}，你好！请收下你的今日运势：\n\n{response.data}"
        )

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
        return make_unique_reply(
            "帮助信息如下：\n"
            "1. 输入【塔罗牌】+问题，可以进行塔罗牌占卜 :crystal_ball:\n"
            "2. 输入【今日运势】，获取你的今日运势 :dotted_six_pointed_star:\n"
            "3. 输入533或某些变体，可以获得鹊的祝福 :bird:\n"
            "4. 输入【帮助】，可以查看本帮助信息"
        )

    async def _new_post_routine(self, post_id: int) -> None:
        """
        A routine to handle a new post in the topic.
        NOTE: no exception should be raised in this method.

        :param post_id: The ID of the new post.
        :return: None
        """
        await handle_post_and_reply(self.model, post_id, self._generate_reply)

    async def _generate_reply(self, post: PostDetails, user: User) -> Optional[str]:
        """
        Build the reply for a post, checking the conditions in order.

        :param post: The details of the post.
        :param user: The user who posted the content.
        :return: The text to reply with, or None if no condition is met.
        """
        raw = post.raw
        # The help and fortune conditions exclude all later conditions
        text = await self._help_condition(raw)
        if text is None:
            text = await self._fortune_condition(raw, user=user)
        if text is None:
            text = await self._tarot_condition(raw, user=user)
        if text is None:
            text = await self._533_condition(raw)

        # If our reply is too long for Shuiyuan, reply with an error instead
        if text is not None and len(text) > _MAX_POST_LENGTH:
            text = make_unique_reply(
                "抱歉，南瓜bot生成的回复内容过长，无法正常发送，请联系东川路笨蛋小南瓜处理"
            )
        return text

    async def _daily_routine(self) -> None:
        raise NotImplementedError(
            "Daily routine is not implemented in TopicModel. "
            "Please implement this method in your subclass."
        )
