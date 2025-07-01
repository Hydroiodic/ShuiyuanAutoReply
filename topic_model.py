import asyncio
import random
from shuiyuan_model import ShuiyuanModel
from constants import max_random_value


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

        # We use a random empty value to aviod repeating the same post
        self.rand_value = random.randint(0, max_random_value - 1)

    def _533_condition(self, raw: str) -> bool:
        """
        Check if the raw content of a post contains the string "533".

        :param raw: The raw content of the post.
        :return: True if "533" is found, False otherwise.
        """
        # At first convert some characters
        raw = raw.replace(" ", "").replace("\n", "")
        raw = raw.replace("Ⅴ", "5").replace("Ⅲ", "3")
        raw = raw.replace("五", "5").replace("三", "3")
        raw = raw.replace("伍", "5").replace("叁", "3")
        raw = raw.replace("⑤", "5").replace("③", "3")
        return "533" in raw

    async def _new_post_routine(self, post_id: int) -> None:
        # First let's try to get the post details
        post_details = await self.model.get_post_details(post_id)

        # If the member "raw" is not present, we should skip it
        if post_details.raw is None:
            print(f"Post {post_id} does not have raw content, skipping.")
            return

        # OK, check the content of the post
        if self._533_condition(post_details.raw):
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
