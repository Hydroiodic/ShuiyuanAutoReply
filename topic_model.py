import asyncio
import random
from typing import Optional
from shuiyuan_model import ShuiyuanModel
from constants import max_random_value
from tarot_group_data import TarotResult, get_image_from_cache
from tarot_model import TarotModel
from tongyi_model import TongyiModel


class TopicModel:
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

        self.tarot_model = TarotModel()
        self.tongyi_model = TongyiModel()

        # We use a random empty value to aviod repeating the same post
        self.rand_value = random.randint(0, max_random_value - 1)

    async def _upload_and_get_image_url(self, result: TarotResult) -> str:
        """
        Upload an image and return its URL.

        :param result: The TarotResult containing the image path.
        :return: The URL of the uploaded image.
        """
        # First let's check if the image is already cached
        url = get_image_from_cache(result)
        if url is not None:
            return url

        # Upload the image and get the response
        response = await self.model.upload_image(
            "tarot_img/"
            + str(result.index)
            + ("_rev" if result.is_reversed else "")
            + ".jpg"
        )

        # Return the URL of the uploaded image
        return response.short_url

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

        # If the raw content does not contain "533", we return None
        if "533" not in raw:
            return None

        # To avoid repeating the same post, we use a random value
        self.rand_value = (self.rand_value + 1) % max_random_value
        insert_pos = random.randint(0, self.rand_value)

        text = ""
        for _ in range(insert_pos):
            text += "<!-- 鹊 -->\n"
        text += "鹊\n"
        for _ in range(insert_pos, self.rand_value + 1):
            text += "<!-- 鹊 -->\n"
        text += "---\n"
        text += "[right]这是一条自动回复[/right]\n"
        return text

    async def _tarot_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【塔罗牌】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content contains "【塔罗牌】", we reply to the post
        if "【塔罗牌】" not in raw:
            return None

        # OK, let's generate a reply
        tarot_group = self.tarot_model.choose_tarot_group(raw.replace("【塔罗牌】", ""))

        # Let GPT tell us the meaning of the tarot cards
        text = '---\n\n[details="分析和建议"]\n'
        text += self.tongyi_model.consult_tarot_card(
            raw.replace("【塔罗牌】", ""), tarot_group
        ).replace("【塔罗牌】", "")
        text += "\n[/details]\n"

        # Load image for the tarot group
        tarot_result = tarot_group.tarot_results
        urls = await asyncio.gather(
            *[self._upload_and_get_image_url(result) for result in tarot_result]
        )

        # Now update the tarot results with the image URLs
        for i, result in enumerate(tarot_result):
            result.img_url = urls[i]

        # Prepend the tarot group string
        text = str(tarot_group) + text
        return text

    async def _help_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "帮助".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "帮助", we return None
        if "【帮助】" not in raw or "自动回复" in raw:
            return None

        # OK, let's generate a reply
        text = "这是一个自动回复，帮助信息如下：\n"
        text += "1. 输入【塔罗牌】+问题，可以进行塔罗牌占卜 :crystal_ball:\n"
        text += "2. 输入533或某些变体，可以获得鹊的祝福 :bird:\n"
        text += "3. 输入【帮助】，可以查看本帮助信息\n"
        text += f"<!-- {random.sample('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', 20)} -->\n"

        return text

    async def _new_post_routine(self, post_id: int) -> None:
        # First let's try to get the post details
        post_details = await self.model.get_post_details(post_id)

        # If the member "raw" is not present, we should skip it
        if post_details.raw is None:
            print(f"Post {post_id} does not have raw content, skipping.")
            return

        # OK, check the content of the post
        # If the help condition is met, we should not check other conditions
        text = await self._help_condition(post_details.raw)
        if text is not None:
            await self.model.reply_to_post(
                text,
                self.topic_id,
                post_details.post_number,
            )
            return

        text = await self._533_condition(post_details.raw)
        if text is not None:
            await self.model.reply_to_post(
                text,
                self.topic_id,
                post_details.post_number,
            )

        text = await self._tarot_condition(post_details.raw)
        if text is not None:
            await self.model.reply_to_post(
                text,
                self.topic_id,
                post_details.post_number,
            )

    async def watch_routine(self) -> None:
        """
        A routine to watch for updates on the topic.
        This method can be extended to implement real-time updates or periodic checks.
        """
        while True:
            # Get the topic details
            topic_details = await self.model.get_topic_details(self.topic_id)

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
