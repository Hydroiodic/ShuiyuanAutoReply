import asyncio
import logging
import traceback
from datetime import datetime
from typing import Optional

from shuiyuan_auto_reply.database.postgres_record_mgr import (
    AsyncPostgresRecordDatabaseManager,
    User as RecordUser,
    create_global_async_postgres_record_manager,
)
from shuiyuan_auto_reply.shuiyuan.objects import PostDetails, User
from shuiyuan_auto_reply.shuiyuan.reply_utils import (
    make_unique_reply,
    parse_prompt_text,
)
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel
from shuiyuan_auto_reply.shuiyuan.topic_model import BaseTopicModel

from ..common import handle_post_and_reply


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
        self.record_manager: Optional[AsyncPostgresRecordDatabaseManager] = None

    async def _get_record_manager(self) -> AsyncPostgresRecordDatabaseManager:
        if self.record_manager is None:
            self.record_manager = await create_global_async_postgres_record_manager(
                strict=True
            )
        if self.record_manager is None:
            raise RuntimeError("Postgres record database is not configured")
        return self.record_manager

    @staticmethod
    def _to_quote_format(text: str) -> str:
        """
        Convert the given text to a quote format.

        :param text: The text to be converted.
        :return: The text in quote format.
        """
        return "> " + text.replace("\n", "\n> ")

    async def _find_recording_user(
        self, record_manager: AsyncPostgresRecordDatabaseManager, name: str
    ) -> RecordUser | str:
        """
        Find the record user by alias or Shuiyuan username,
        and make sure that the user has enabled recording.

        :param record_manager: The record database manager.
        :param name: The alias or username of the user.
        :return: The record user, or the text to reply with if it cannot be used.
        """
        # Get the user_id with alias or username
        db_user = await record_manager.get_user_by_alias(name.lower())
        if not db_user:
            # Get the user from the ShuiyuanModel
            sy_user = await self.model.get_user_by_username(name.lower())
            if not sy_user:
                return make_unique_reply(f"找不到用户名或别名为 '{name}' 的用户")
            # OK, now we got the user_id
            db_user = await record_manager.get_or_add_user(sy_user.id)

        if not db_user:
            return make_unique_reply("数据库错误，请稍后再试")

        # Check if the user has enabled recording
        if db_user.enable_record != 1:
            return make_unique_reply("该用户未开启或已禁用语录记录功能")

        return db_user

    async def _add_record_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【记录语录】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【记录语录】", we return None
        raw = parse_prompt_text(raw, "【记录语录】")
        if raw is None:
            return None

        # Get the first line as username/alias, and the rest as the record
        split_result = raw.split("\n", 1)
        if len(split_result) != 2:
            return make_unique_reply(
                "格式错误，请使用：【记录语录】+用户名（需在同一行）+语录内容（需换行）"
            )

        raw_username = split_result[0].strip()
        raw = split_result[1].strip()
        if not raw:
            return make_unique_reply("语录内容不能为空")

        record_manager = await self._get_record_manager()
        db_user = await self._find_recording_user(record_manager, raw_username)
        if isinstance(db_user, str):
            return db_user

        # Check if the user is allowed to add records
        if user.id != db_user.user_id and db_user.allow_others != 1:
            return make_unique_reply("您没有权限为该用户添加语录")

        # Add the record content to the database
        new_record = await record_manager.add_record(db_user.user_id, raw)
        if not new_record:
            return make_unique_reply("添加语录失败，请稍后再试")

        return make_unique_reply(
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
        raw = parse_prompt_text(raw, "【删除语录】")
        if raw is None:
            return None

        # Try to parse the ID
        try:
            record_id = int(raw)
        except ValueError:
            return make_unique_reply("无法解析语录ID，请提供一个有效的整数")

        record_manager = await self._get_record_manager()

        # Get the record with the given ID
        record = await record_manager.get_record(record_id)
        if not record:
            return make_unique_reply(f'找不到ID为 "{record_id}" 的语录')

        # Check if the current user has permission to delete this record
        if record.user.user_id != user.id and record.user.allow_others != 1:
            return make_unique_reply("您没有权限删除此语录")

        # Remove the record from the database
        success = await record_manager.delete_record(record_id)
        if not success:
            return make_unique_reply("删除语录失败，请稍后再试")

        return make_unique_reply(
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
        raw = parse_prompt_text(raw, "【查询语录】")
        if raw is None:
            return None

        # Split the content by whitespace and take the first part
        split_result = raw.split()
        if not split_result:
            return make_unique_reply("缺少参数，请添加用户名或别名")

        record_manager = await self._get_record_manager()
        raw = split_result[0]
        db_user = await self._find_recording_user(record_manager, raw)
        if isinstance(db_user, str):
            return db_user

        # Get all records for this user
        all_records = await record_manager.get_records_by_user(db_user.user_id)
        if not all_records:
            return make_unique_reply("该用户当前没有语录记录")

        # Generate the list of quotes
        text = f"以下是 '{raw}' 用户的所有语录记录：\n\n"
        text += "[details]\n"
        for record in all_records:
            text += (
                f"ID {record.record_id}:\n"
                f"{RecordTopicModel._to_quote_format(record.record_str)}\n\n"
            )
        text += "[/details]"

        return make_unique_reply(text.strip())

    async def _get_record_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【获取语录】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【获取语录】", we return None
        raw = parse_prompt_text(raw, "【获取语录】")
        if raw is None:
            return None

        # Split the content by whitespace and take the first part
        split_result = raw.split()
        if not split_result:
            return make_unique_reply("缺少参数，请添加用户名")

        record_manager = await self._get_record_manager()
        raw = split_result[0]
        db_user = await self._find_recording_user(record_manager, raw)
        if isinstance(db_user, str):
            return db_user

        # Get one random record for this user
        rand_record = await record_manager.get_random_record_by_user(db_user.user_id)
        if not rand_record:
            return make_unique_reply("该用户当前没有语录记录")

        return make_unique_reply(
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
        raw = parse_prompt_text(raw, "【设置别名】")
        if raw is None:
            return None

        # Parse the alias and username
        parts = raw.split()
        if len(parts) != 2:
            return make_unique_reply("格式错误，请使用：【设置别名】+别名+用户名")

        alias = parts[0]
        username = parts[1]

        record_manager = await self._get_record_manager()

        # Check if the alias already exists
        existing_alias = await record_manager.get_user_by_alias(alias.lower())
        if existing_alias:
            return make_unique_reply(f"别名 '{alias}' 已被占用，请选择其他别名")

        # Get the user from the ShuiyuanModel
        sy_user = await self.model.get_user_by_username(username.lower())
        if not sy_user:
            return make_unique_reply(f"找不到用户名为 '{username}' 的用户")

        # Get or create the user in the database
        db_user = await record_manager.get_or_add_user(sy_user.id)
        if not db_user:
            return make_unique_reply("创建用户记录失败，请稍后再试")

        # Only the user themselves, or users who allow others to manage their
        # records, can have aliases bound to their account
        if user.id != db_user.user_id and db_user.allow_others != 1:
            return make_unique_reply("您没有权限为该用户设置别名")

        # Set the alias for the user
        success = await record_manager.add_alias(db_user.user_id, alias.lower())
        if not success:
            return make_unique_reply("设置别名失败，请稍后再试")
        return make_unique_reply(f"已将别名 '{alias}' 设置为用户 '{username}'")

    async def _set_user_flag_condition(
        self,
        raw: str,
        user: User,
        prompt: str,
        field: str,
        enabled_reply: str,
        disabled_reply: str,
    ) -> Optional[str]:
        """
        Set a True/False flag of the posting user if the post contains the prompt.

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :param prompt: The prompt string to look for.
        :param field: The flag of the record user to update.
        :param enabled_reply: The text to reply with when the flag is enabled.
        :param disabled_reply: The text to reply with when the flag is disabled.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        raw = parse_prompt_text(raw, prompt)
        if raw is None:
            return None

        # Split the content by whitespace and take the first part
        split_result = raw.split()
        if not split_result:
            return make_unique_reply("缺少参数，请添加 True 或 False")

        # Determine the value to set
        value = split_result[0].casefold()
        if value == "true":
            flag_value, response = 1, enabled_reply
        elif value == "false":
            flag_value, response = 0, disabled_reply
        else:
            return make_unique_reply("参数无效，请使用 True 或 False")

        record_manager = await self._get_record_manager()

        # Get or create the user in the database
        db_user = await record_manager.get_or_add_user(user.id)
        if not db_user:
            return make_unique_reply("创建用户记录失败，请稍后再试")

        # Update the user's setting
        success = await record_manager.update_user(user.id, **{field: flag_value})
        if not success:
            return make_unique_reply("更新设置失败，请稍后再试")
        return make_unique_reply(response)

    async def _enable_record_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【启用语录】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        return await self._set_user_flag_condition(
            raw,
            user,
            "【启用语录】",
            "enable_record",
            "已启用您的语录记录功能",
            "已禁用您的语录记录功能",
        )

    async def _allow_others_condition(self, raw: str, user: User) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【更改权限】".

        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        return await self._set_user_flag_condition(
            raw,
            user,
            "【更改权限】",
            "allow_others",
            "已允许他人记录和删除您的语录",
            "已禁止他人记录和删除您的语录",
        )

    def _help_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【帮助】".

        :param raw: The raw content of the post.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "帮助", we return None
        if "【帮助】" not in raw:
            return None

        return make_unique_reply(
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
        await handle_post_and_reply(self.model, post_id, self._generate_reply)

    async def _generate_reply(self, post: PostDetails, user: User) -> Optional[str]:
        """
        Build the reply for a post. The first condition that is met wins.

        :param post: The details of the post.
        :param user: The user who posted the message.
        :return: The text to reply with, or None if no condition is met.
        """
        raw = post.raw
        text = self._help_condition(raw)
        if text is not None:
            return text

        conditions = (
            self._enable_record_condition,
            self._allow_others_condition,
            self._set_alias_condition,
            self._add_record_condition,
            self._remove_record_condition,
        )
        for condition in conditions:
            text = await condition(raw, user)
            if text is not None:
                return text

        text = await self._query_record_condition(raw)
        if text is not None:
            return text
        return await self._get_record_condition(raw, user)

    async def _daily_routine(self) -> None:
        record_manager = await self._get_record_manager()

        # Get at most 3 random records from the database
        random_records = await record_manager.get_random_records(3)
        if not random_records:
            logging.warning("No records found in database for daily routine.")
            return

        # Try to get the usernames for these records
        routines = []
        for record in random_records:
            routines.append(self.model.search_user_by_user_id(record.user_id))
        users = await asyncio.gather(*routines, return_exceptions=True)

        # Format the text to reply
        text = f"{datetime.now().strftime('%Y-%m-%d')} 推荐语录：\n\n"
        for record, user in zip(random_records, users, strict=True):
            if isinstance(user, User):
                text += f"{user.username}: \n"
            text += f"{RecordTopicModel._to_quote_format(record.record_str)}\n\n"

        # Try to reply to the topic
        try:
            await self.model.reply_to_post(
                make_unique_reply(text.strip()),
                self.topic_id,
            )
        except Exception:
            logging.error(
                f"Failed to reply to topic {self.topic_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
