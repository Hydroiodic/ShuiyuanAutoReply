import re
import random
import logging
import traceback
from typing import Optional
from datetime import datetime
from src.shuiyuan.objects import User
from src.shuiyuan.shuiyuan_model import ShuiyuanModel
from src.shuiyuan.topic_model import BaseTopicModel
from src.constants import auto_reply_tag
from src.database.manager import global_async_db_manager


class RecordTopicModel(BaseTopicModel):
    """
    A class to represent a topic model for managing user records.
    """

    def __init__(self, model: ShuiyuanModel, topic_id: int):
        """
        Initialize the TopicModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param topic_id: The ID of the topic to be managed.
        """
        super().__init__(model, topic_id)
        self.db_manager = global_async_db_manager

    @staticmethod
    def _to_quote_format(text: str) -> str:
        """
        Convert the given text to a quote format.

        :param text: The text to be converted.
        :return: The text in quote format.
        """
        return "> " + text.replace("\n", "\n> ")

    @staticmethod
    def _remove_shuiyuan_signature(text: str) -> str:
        """
        Remove the Shuiyuan signature from the given text.

        :param text: The text from which to remove the signature.
        :return: The text without the signature.
        """
        sig_re = r"<div data-signature>.*?</div>"
        return re.sub(sig_re, "", text, flags=re.DOTALL).strip()

    async def _add_record_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【记录语录】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【记录语录】", we return None
        if "【记录语录】" not in raw:
            return None

        # Remove the keyword itself
        raw = RecordTopicModel._remove_shuiyuan_signature(
            raw.replace("【记录语录】", "")
        ).strip()

        # Get the first line as username/alias, and the rest as the record
        split_result = raw.split("\n", 1)
        if len(split_result) != 2:
            return BaseTopicModel._make_unique_reply(
                "格式错误，请使用：【记录语录】+用户名（需在同一行）+语录内容（需换行）"
            )

        raw_username = split_result[0].strip().lower()
        raw = split_result[1].strip()
        if not raw:
            return BaseTopicModel._make_unique_reply("语录内容不能为空")

        # Get the user_id with alias or username
        db_user = await self.db_manager.get_user_by_alias(raw_username)
        if not db_user:
            # Get the user from the ShuiyuanModel
            sy_user = await self.model.get_user_by_username(raw_username)
            if not sy_user:
                return BaseTopicModel._make_unique_reply(
                    f"找不到用户名或别名为 '{raw_username}' 的用户"
                )
            # OK, now we got the user_id
            db_user = await self.db_manager.get_or_add_user(sy_user.id)

        if not db_user:
            return BaseTopicModel._make_unique_reply("创建用户记录失败，请稍后再试")

        # Check if the user has enabled recording
        if db_user.enable_record != 1:
            return BaseTopicModel._make_unique_reply("该用户未开启或已禁用语录记录功能")

        # Check if the user is allowed to add records
        if user.id != db_user.user_id and db_user.allow_others != 1:
            return BaseTopicModel._make_unique_reply("您没有权限为该用户添加语录")

        # Add the record content to the database
        new_record = await self.db_manager.add_record(db_user.user_id, raw)
        if not new_record:
            return BaseTopicModel._make_unique_reply("添加语录失败，请稍后再试")

        return BaseTopicModel._make_unique_reply(
            f"已将以下语录添加到数据库中，ID为{new_record.record_id}\n\n"
            f"{RecordTopicModel._to_quote_format(raw)}"
        )

    async def _remove_record_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【删除语录】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【删除语录】", we return None
        if "【删除语录】" not in raw:
            return None

        # Remove the keyword itself
        raw = (
            RecordTopicModel._remove_shuiyuan_signature(raw.replace("【删除语录】", ""))
            .strip()
            .lower()
        )

        # Try to parse the ID
        try:
            record_id = int(raw)
        except ValueError:
            return BaseTopicModel._make_unique_reply(
                "无法解析语录ID，请提供一个有效的整数"
            )

        # Get the record with the given ID
        record = await self.db_manager.get_record(record_id)
        if not record:
            return BaseTopicModel._make_unique_reply(f"找不到ID为{record_id}的语录")

        # Check if the current user has permission to delete this record
        if record.user.user_id != user.id and record.user.allow_others != 1:
            return BaseTopicModel._make_unique_reply("您没有权限删除此语录")

        # Remove the record from the database
        success = await self.db_manager.delete_record(record_id)
        if not success:
            return BaseTopicModel._make_unique_reply("删除语录失败，请稍后再试")

        return BaseTopicModel._make_unique_reply(
            f"已将以下语录从数据库中删除：\n\n"
            f"{RecordTopicModel._to_quote_format(record.record_str)}"
        )

    async def _query_record_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【查询语录】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【查询语录】", we return None
        if "【查询语录】" not in raw:
            return None

        # Get the username
        raw = (
            RecordTopicModel._remove_shuiyuan_signature(raw.replace("【查询语录】", ""))
            .strip()
            .lower()
        )

        # Split the content by whitespace and take the first part
        split_result = raw.split()
        if not split_result:
            return BaseTopicModel._make_unique_reply("缺少参数，请添加用户名或别名")

        # Get the user_id with alias or username
        raw = split_result[0]
        db_user = await self.db_manager.get_user_by_alias(raw)
        if not db_user:
            # Get the user from the ShuiyuanModel
            sy_user = await self.model.get_user_by_username(raw)
            if not sy_user:
                return BaseTopicModel._make_unique_reply(
                    f"找不到用户名或别名为 '{raw}' 的用户"
                )
            # OK, now we got the user_id
            db_user = await self.db_manager.get_or_add_user(sy_user.id)

        if not db_user:
            return BaseTopicModel._make_unique_reply(f"数据库错误，请稍后再试")

        # Check if the user has enabled recording
        if db_user.enable_record != 1:
            return BaseTopicModel._make_unique_reply("该用户未开启或已禁用语录记录功能")

        # Get all records for this user
        all_records = await self.db_manager.get_records_by_user(db_user.user_id)
        if not all_records:
            return BaseTopicModel._make_unique_reply("该用户当前没有语录记录")

        # Generate the list of quotes
        text = f"以下是{raw}用户的所有语录记录：\n\n"
        text += "[details]\n"
        for record in all_records:
            text += (
                f"ID {record.record_id}:\n"
                f"{RecordTopicModel._to_quote_format(record.record_str)}\n\n"
            )
        text += "[/details]"

        return BaseTopicModel._make_unique_reply(text.strip())

    async def _get_record_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【获取语录】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【获取语录】", we return None
        if "【获取语录】" not in raw:
            return None

        # Remove the keyword itself
        raw = (
            RecordTopicModel._remove_shuiyuan_signature(raw.replace("【获取语录】", ""))
            .strip()
            .lower()
        )

        # Split the content by whitespace and take the first part
        split_result = raw.split()
        if not split_result:
            return BaseTopicModel._make_unique_reply("缺少参数，请添加用户名")

        # Get the user_id with alias or username
        raw = split_result[0]
        db_user = await self.db_manager.get_user_by_alias(raw)
        if not db_user:
            # Get the user from the ShuiyuanModel
            sy_user = await self.model.get_user_by_username(raw)
            if not sy_user:
                return BaseTopicModel._make_unique_reply(
                    f"找不到用户名或别名为 '{raw}' 的用户"
                )
            # OK, now we got the user_id
            db_user = await self.db_manager.get_or_add_user(sy_user.id)

        if not db_user:
            return BaseTopicModel._make_unique_reply(f"数据库错误，请稍后再试")

        # Check if the user has enabled recording
        if db_user.enable_record != 1:
            return BaseTopicModel._make_unique_reply("该用户未开启或已禁用语录记录功能")

        # Get one random record for this user
        rand_record = await self.db_manager.get_random_record_by_user(db_user.user_id)
        if not rand_record:
            return BaseTopicModel._make_unique_reply("该用户当前没有语录记录")

        return BaseTopicModel._make_unique_reply(
            f"{RecordTopicModel._to_quote_format(rand_record.record_str)}\n\n"
            f"---\n\n[right]这是一条自动回复[/right]"
        )

    async def _set_alias_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【设置别名】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【设置别名】", we return None
        if "【设置别名】" not in raw:
            return None

        # Remove the keyword itself
        raw = (
            RecordTopicModel._remove_shuiyuan_signature(raw.replace("【设置别名】", ""))
            .strip()
            .lower()
        )

        # Parse the alias and username
        parts = raw.split()
        if len(parts) != 2:
            return BaseTopicModel._make_unique_reply(
                "格式错误，请使用：【设置别名】+别名+用户名"
            )

        alias = parts[0]
        username = parts[1]

        # Check if the alias already exists
        existing_alias = await self.db_manager.get_user_by_alias(alias)
        if existing_alias:
            return BaseTopicModel._make_unique_reply(
                f"别名 '{alias}' 已被占用，请选择其他别名"
            )

        # Get the user from the ShuiyuanModel
        sy_user = await self.model.get_user_by_username(username)
        if not sy_user:
            return BaseTopicModel._make_unique_reply(
                f"找不到用户名为 '{username}' 的用户"
            )

        # Get or create the user in the database
        db_user = await self.db_manager.get_or_add_user(sy_user.id)
        if not db_user:
            return BaseTopicModel._make_unique_reply("创建用户记录失败，请稍后再试")

        # Set the alias for the user
        success = await self.db_manager.add_alias(db_user.user_id, alias)
        if not success:
            return BaseTopicModel._make_unique_reply("设置别名失败，请稍后再试")
        return BaseTopicModel._make_unique_reply(
            f"已将别名 '{alias}' 设置为用户 '{username}'"
        )

    async def _enable_record_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【启用语录】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【启用语录】", we return None
        if "【启用语录】" not in raw:
            return None

        # Remove the keyword itself
        raw = (
            RecordTopicModel._remove_shuiyuan_signature(raw.replace("【启用语录】", ""))
            .strip()
            .lower()
        )

        # Split the content by whitespace and take the first part
        split_result = raw.split()
        if not split_result:
            return BaseTopicModel._make_unique_reply("缺少参数，请添加 True 或 False")

        # Determine the value to set
        raw = split_result[0]
        if raw == "true":
            enable_value = 1
            response = "已启用您的语录记录功能"
        elif raw == "false":
            enable_value = 0
            response = "已禁用您的语录记录功能"
        else:
            return BaseTopicModel._make_unique_reply("参数无效，请使用 True 或 False")

        # Get or create the user in the database
        db_user = await self.db_manager.get_or_add_user(user.id)
        if not db_user:
            return BaseTopicModel._make_unique_reply("创建用户记录失败，请稍后再试")

        # Update the user's enable_record setting
        success = await self.db_manager.update_user(user.id, enable_record=enable_value)
        if not success:
            return BaseTopicModel._make_unique_reply("更新设置失败，请稍后再试")
        return BaseTopicModel._make_unique_reply(response)

    async def _allow_others_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【更改权限】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【更改权限】", we return None
        if "【更改权限】" not in raw:
            return None

        # Remove the keyword itself
        raw = (
            RecordTopicModel._remove_shuiyuan_signature(raw.replace("【更改权限】", ""))
            .strip()
            .lower()
        )

        # Split the content by whitespace and take the first part
        split_result = raw.split()
        if not split_result:
            return BaseTopicModel._make_unique_reply("缺少参数，请添加 True 或 False")

        # Determine the value to set
        raw = split_result[0]
        if raw == "true":
            allow_value = 1
            response = "已允许他人记录和删除您的语录"
        elif raw == "false":
            allow_value = 0
            response = "已禁止他人记录和删除您的语录"
        else:
            return BaseTopicModel._make_unique_reply("参数无效，请使用 True 或 False")

        # Get or create the user in the database
        db_user = await self.db_manager.get_or_add_user(user.id)
        if not db_user:
            return BaseTopicModel._make_unique_reply("创建用户记录失败，请稍后再试")

        # Update the user's allow_others setting
        success = await self.db_manager.update_user(user.id, allow_others=allow_value)
        if not success:
            return BaseTopicModel._make_unique_reply("更新设置失败，请稍后再试")
        return BaseTopicModel._make_unique_reply(response)

    def _help_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【帮助】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "帮助", we return None
        if "【帮助】" not in raw:
            return None

        return BaseTopicModel._make_unique_reply(
            "帮助信息如下：\n"
            "1. 输入【获取语录】+用户名，获取用户经典语录 :speech_balloon:\n"
            "2. 输入【记录语录】+用户名（需在同一行）+语录内容（需换行），为用户添加新的语录 :pencil:\n"
            "3. 输入【删除语录】+语录全局唯一ID，删除指定ID的语录 :wastebasket:\n"
            "4. 输入【查询语录】+用户名，查看某位用户的所有语录 :mag_right:\n"
            "5. 输入【启用语录】+True/False，允许/禁止当前用户的语录被记录（默认禁止） :white_check_mark:\n"
            "6. 输入【更改权限】+True/False，允许/禁止当前用户的语录被他人记录/删除 （默认禁止） :lock:\n"
            "7. 输入【设置别名】+别名+用户名，设置某个别名对应的用户名（不会由于昵称更改而被影响） :label:\n"
            "8. 输入【帮助】，查看该帮助信息 :question:"
        )

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

        except Exception:
            logging.error(
                f"Failed to get post details for {post_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            return

        try:
            # If the post is an auto-reply, we should skip it
            if auto_reply_tag in post_details.raw:
                return

            # OK, check the content of the post
            # If the help condition is met, we should not check other conditions
            text = self._help_condition(post_details.raw)
            if text is not None:
                return

            # Check enable_record condition
            text = await self._enable_record_condition(post_details.raw, post_user)
            if text is not None:
                return

            # Check allow_others condition
            text = await self._allow_others_condition(post_details.raw, post_user)
            if text is not None:
                return

            # Check set_alias condition
            text = await self._set_alias_condition(post_details.raw, post_user)
            if text is not None:
                return

            # Check add_record condition
            text = await self._add_record_condition(post_details.raw, post_user)
            if text is not None:
                return

            # Check remove_record condition
            text = await self._remove_record_condition(post_details.raw, post_user)
            if text is not None:
                return

            # Check query_record condition
            text = await self._query_record_condition(post_details.raw)
            if text is not None:
                return

            # Check get_record condition
            text = await self._get_record_condition(post_details.raw, post_user)
            if text is not None:
                return

        except Exception:
            # If we failed to get the post details or any other error occurred
            logging.error(
                f"Failed to process post {post_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            # We should reply to the post with an error message
            text = BaseTopicModel._make_unique_reply(
                "抱歉，南瓜bot遇到了一个错误，暂时无法处理您的请求，请稍后再试"
            )

        finally:
            if text is not None:
                await self.model.reply_to_post(
                    text,
                    self.topic_id,
                    post_details.post_number,
                )

    async def _daily_routine(self) -> None:
        # Get at most 3 random records from the database
        random_records = await self.db_manager.get_random_records(3)
        if not random_records:
            logging.warning("No records found in database for daily routine.")
            return

        # Format the text to reply
        text = f"{datetime.now().strftime('%Y-%m-%d')} 推荐语录：\n\n"
        for record in random_records:
            text += f"{RecordTopicModel._to_quote_format(record.record_str)}\n\n"

        # Try to reply to the topic
        try:
            await self.model.reply_to_post(
                BaseTopicModel._make_unique_reply(text.strip()),
                self.topic_id,
            )
        except Exception:
            logging.error(
                f"Failed to reply to topic {self.topic_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
