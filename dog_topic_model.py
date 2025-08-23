import os
import re
import json
import random
import logging
import traceback
from datetime import datetime
from typing import Optional
from shuiyuan.shuiyuan_model import ShuiyuanModel
from shuiyuan.topic_model import BaseTopicModel

_auto_reply_tag = "<!-- 来自南瓜的自动回复 -->"


class DogTopicModel(BaseTopicModel):
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

        # The path to the lzyl_data.json file
        assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        self.lzyl_json_path = os.path.join(assets_dir, "lzyl_data.json")

        # Load the lzyl data from the JSON file
        try:
            with open(self.lzyl_json_path, "r", encoding="utf-8") as f:
                self.lzyl_list = json.load(f)
        except FileNotFoundError:
            # If file doesn't exist, create it with an empty list
            self.lzyl_list = []
            with open(self.lzyl_json_path, "w", encoding="utf-8") as f:
                json.dump(self.lzyl_list, f, ensure_ascii=False, indent=4)
            logging.info(f"Created new lzyl_data.json file at {self.lzyl_json_path}")
        except json.JSONDecodeError:
            # If file exists but contains invalid JSON, reset to empty list
            logging.warning(
                f"Invalid JSON in {self.lzyl_json_path}, resetting to empty list"
            )
            self.lzyl_list = []
            with open(self.lzyl_json_path, "w", encoding="utf-8") as f:
                json.dump(self.lzyl_list, f, ensure_ascii=False, indent=4)

    def _to_quote_format(self, text: str) -> str:
        """
        Convert the given text to a quote format.

        :param text: The text to be converted.
        :return: The text in quote format.
        """
        return "> " + text.replace("\n", "\n> ")

    def _lzyl_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【濑总语录】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # At first convert some characters
        raw = raw.replace(" ", "").replace("\n", "")

        # If the raw content does not contain "【濑总语录】", we return None
        if "【濑总语录】" not in raw:
            return None

        # Generate a unique reply text
        random_lzyl = random.choice(self.lzyl_list)
        text = self._to_quote_format(random_lzyl)
        text += "\n\n---\n[right]这是一条自动回复[/right]\n"
        text += f"<!-- {self._generate_random_string(20)} -->\n"
        text += _auto_reply_tag

        return text

    def _add_lzyl_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【濑总说过】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【濑总说过】", we return None
        if "【濑总说过】" not in raw:
            return None

        # Remove the keyword itself
        raw = raw.replace("【濑总说过】", "").strip()

        # Remove the signature if exists
        sig_re = r"<div data-signature>.*?</div>"
        raw = re.sub(sig_re, "", raw, flags=re.DOTALL).strip()

        # If the remaining content is empty, we return None
        if not raw:
            return None

        # OK, now check if it already exists in the list
        if raw in self.lzyl_list:
            return None

        # Save the new quote to the list and update the JSON file
        self.lzyl_list.append(raw)
        with open(self.lzyl_json_path, "w", encoding="utf-8") as f:
            json.dump(self.lzyl_list, f, ensure_ascii=False, indent=4)

        return (
            f"已将以下语录添加到数据库中，ID为{len(self.lzyl_list)}\n\n"
            f"{self._to_quote_format(raw)}\n\n"
            f"<!-- {self._generate_random_string(20)} -->\n"
            f"{_auto_reply_tag}"
        )

    def _remove_lzyl_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【删除语录】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【删除语录】", we return None
        if "【删除语录】" not in raw:
            return None

        # Remove the keyword itself
        raw = raw.replace("【删除语录】", "").strip()

        # Remove the signature if exists
        sig_re = r"<div data-signature>.*?</div>"
        raw = re.sub(sig_re, "", raw, flags=re.DOTALL).strip()

        # If the remaining content is empty, we return None
        if not raw:
            return None

        # Try to parse the ID
        try:
            lzyl_id = int(raw)
        except ValueError:
            return (
                "语录ID无效，请提供一个有效的整数ID。\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"{_auto_reply_tag}"
            )

        # Check if the ID is valid
        if lzyl_id < 1 or lzyl_id > len(self.lzyl_list):
            return (
                f"语录ID无效，请提供一个介于1和{len(self.lzyl_list)}之间的ID。\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"{_auto_reply_tag}"
            )

        # Remove the quote from the list and update the JSON file
        removed_quote = self.lzyl_list.pop(lzyl_id - 1)
        with open(self.lzyl_json_path, "w", encoding="utf-8") as f:
            json.dump(self.lzyl_list, f, ensure_ascii=False, indent=4)

        return (
            "已将以下语录从数据库中删除，注意，这可能导致其他语录ID发生变化\n\n"
            f"{self._to_quote_format(removed_quote)}\n\n"
            f"<!-- {self._generate_random_string(20)} -->\n"
            f"{_auto_reply_tag}"
        )

    def _query_lzyl_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【查询语录】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【查询语录】", we return None
        if "【查询语录】" not in raw:
            return None

        # Generate the list of quotes
        text = "当前数据库中的濑总语录如下：\n\n[details]\n"
        for idx, quote in enumerate(self.lzyl_list, start=1):
            text += f"{idx}. {quote}\n"
        text += "[/details]\n"
        text += f"\n<!-- {self._generate_random_string(20)} -->\n"
        text += _auto_reply_tag

        return text

    def _help_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【帮助】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "帮助", we return None
        if "【帮助】" not in raw:
            return None

        # OK, let's generate a reply
        text = "帮助信息如下：\n"
        text += "1. 输入【濑总语录】，获取濑总经典语录 :speech_balloon:\n"
        text += "2. 输入【濑总说过】+语录内容，添加新的濑总语录 :pencil:\n"
        text += "3. 输入【删除语录】+语录ID，删除指定ID的语录 :wastebasket:\n"
        text += "4. 输入【查询语录】，查看当前所有的濑总语录 :mag_right:\n"
        text += "5. 输入【帮助】，查看该帮助信息 :question:\n"
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

            # If the member "raw" is not present, we should skip it
            if post_details.raw is None:
                logging.warning(f"Post {post_id} does not have raw content, skipping.")
                return

            # If the post is an auto-reply, we should skip it
            if _auto_reply_tag in post_details.raw:
                return

            # OK, check the content of the post
            # If the help condition is met, we should not check other conditions
            text = self._help_condition(post_details.raw)
            if text is not None:
                return

            # Check add_lzyl condition
            text = self._add_lzyl_condition(post_details.raw)
            if text is not None:
                return

            # Check remove_lzyl condition
            text = self._remove_lzyl_condition(post_details.raw)
            if text is not None:
                return

            # Check query_lzyl condition
            text = self._query_lzyl_condition(post_details.raw)
            if text is not None:
                return

            # Check tarot condition
            text = self._lzyl_condition(post_details.raw)
            if text is not None:
                return
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
        # Randomly select at most 3 quotes from the list
        random_quotes = random.sample(self.lzyl_list, min(3, len(self.lzyl_list)))

        # Format the text to reply
        text = f"{datetime.now().strftime("%Y-%m-%d")} 推荐濑总语录：\n\n"
        for quote in random_quotes:
            text += f"{self._to_quote_format(quote)}\n\n"

        # Try to reply to the topic
        try:
            await self.model.reply_to_post(text, self.topic_id)
        except Exception as e:
            logging.error(
                f"Failed to reply to topic {self.topic_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
