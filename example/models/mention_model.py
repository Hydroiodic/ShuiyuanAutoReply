import re
import random
import logging
import traceback
from typing import Optional, Dict, List
from src.shuiyuan.objects import User, UserActionDetails
from src.shuiyuan.shuiyuan_model import ShuiyuanModel
from src.shuiyuan.user_action_model import BaseUserActionModel
from src.constants import auto_reply_tag
from .mention_google_model import MentionGeminiModel


class MentionModel(BaseUserActionModel):
    """
    A class to represent a mention model for robot auto-replies.
    """

    def __init__(self, model: ShuiyuanModel, username: str):
        """
        Initialize the TopicModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param username: The username of the robot account.
        """
        super().__init__(model, username, [5, 7])
        self.mention_google_model = MentionGeminiModel(model)
        self.username = username

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

    async def _pumpkin_condition(
        self, topic_id: int, raw: str, user: User
    ) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【小南瓜】".

        :param topic_id: The ID of the topic where the post is located.
        :param raw: The raw content of the post.
        :param user: The user who posted the message.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "【小南瓜】", we return None
        raw = MentionModel._parse_prompt_text(raw, "【小南瓜】")
        if raw is None:
            return None

        # Let the Gemini model respond based on conversation and similar responses
        reply = await self.mention_google_model.get_pumpkin_response(
            topic_id, raw, user
        )
        reply = f"{reply}\n\n（内容由AI生成，仅供参考）"
        return MentionModel._make_unique_reply(reply)

    async def _clear_condition(self, raw: str, topic_id: int) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【清除历史】".

        :param raw: The raw content of the post.
        :param topic_id: The ID of the topic where the post is located.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "清除历史", we return None
        if "【清除历史】" not in raw:
            return None

        # Clear the session history for the user
        self.mention_google_model.clear_session_history(topic_id)

        return MentionModel._make_unique_reply("已清除当前话题中的对话历史记录")

    def _random_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【投掷】".

        :param raw: The raw content of the post.
        :return: A random number between 1 and max (given in the post).
        """
        # If the raw content does not contain "投掷", we return None
        if "【投掷】" not in raw:
            return None

        # Use regular expression to extract the parameters for the random number generation
        r = re.search(r"【投掷】\s*(\d*)d\s*(\d+)", raw, re.IGNORECASE)
        if r is None:
            return MentionModel._make_unique_reply(
                "请按照格式`【投掷】ndm`来投掷随机数，"
                "例如`【投掷】3d6`表示投掷3个1到6之间的随机数\n"
            )

        n = int(r.group(1)) if r.group(1) else 1
        m = int(r.group(2))

        # Check the validity of n and m
        if n <= 0 or m <= 0:
            return MentionModel._make_unique_reply(
                "n和m必须都是正整数，请检查你的输入\n"
                "例如`【投掷】3d6`表示投掷3个1到6之间的随机数\n"
            )
        if n > 100:
            return MentionModel._make_unique_reply(
                "n太大了，请限制在100以内\n"
                "例如`【投掷】3d6`表示投掷3个1到6之间的随机数\n"
            )

        # Generate n random numbers between 1 and m
        random_numbers = [random.randint(1, m) for _ in range(n)]
        random_numbers_str = ", ".join(str(num) for num in random_numbers)
        return MentionModel._make_unique_reply(
            f"你投掷了 {n} 个 1 到 {m} 之间的随机数，结果是：\n"
            f"> {random_numbers_str}\n"
        )

    async def _poll_condition(
        self, raw: str, topic_id: int, reply_to_post_number: Optional[int]
    ) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "【抽选】".

        :param raw: The raw content of the post.
        :param topic_id: The ID of the topic where the post is located.
        :param reply_to_post_number: The post number of the post to which current post is replying to.
        :return: A string to reply to the post if the condition is met, otherwise None.
        """
        # If the raw content does not contain "抽选", we return None
        if "【抽选】" not in raw:
            return None

        # Now we check if the post is replying to another post
        if reply_to_post_number is None:
            # Flow B, use regular expression to extract the topic_id/post_number
            r = re.search(r"【抽选】\s*(\d+)(?:/(\d+))?", raw, re.IGNORECASE)
            if r is None:
                return MentionModel._make_unique_reply(
                    "请按照格式`【抽选】topic_id/post_number`或`【抽选】post_number`来抽选，"
                    "或者直接回复包含了投票的帖子来进行抽选，"
                    "例如`【抽选】2026/1896`表示选取ID为2026话题的第1896层里的投票进行随机抽选\n"
                )

            if r.group(2):
                topic_id = int(r.group(1))
                reply_to_post_number = int(r.group(2))
            else:
                reply_to_post_number = int(r.group(1))

        # Flow A, let's get the post details
        try:
            post_details = await self.model.get_post_details_by_post_number(
                topic_id, reply_to_post_number
            )
        except Exception:
            logging.error(
                f"Failed to get post details for topic_id {topic_id} and "
                f"post_number {reply_to_post_number}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            return MentionModel._make_unique_reply(
                "无法获取被抽选的帖子详情，请检查你的输入是否正确，或者稍后再试\n"
                "请按照格式`【抽选】topic_id/post_number`或`【抽选】post_number`来抽选，"
                "或者直接回复包含了投票的帖子来进行抽选，"
                "例如`【抽选】2026/1896`表示选取ID为2026话题的第1896层里的投票进行随机抽选\n"
            )

        # Check if the post contains a poll
        if post_details.polls is None:
            return MentionModel._make_unique_reply(
                "被抽选的帖子中不包含投票，无法进行抽选，请检查你的输入或者稍后再试\n"
                "请按照格式`【抽选】topic_id/post_number`或`【抽选】post_number`来抽选，"
                "或者直接回复包含了投票的帖子来进行抽选，"
                "例如`【抽选】2026/1896`表示选取ID为2026话题的第1896层里的投票进行随机抽选\n"
            )

        # Check the visibility of the polls
        visible_polls = [
            poll
            for poll in post_details.polls
            if (poll.type == "regular" or poll.type == "multiple")
            and poll.public
            and (poll.results != "on_close" or poll.status == "closed")
        ]
        visible_poll_ids = {poll.id for poll in visible_polls}
        if not visible_poll_ids:
            return MentionModel._make_unique_reply(
                "被抽选的帖子中的所有投票均不可见或类型不支持，"
                "当前仅支持单选或多选且公开的投票，请检查你的输入或者稍后再试\n"
            )

        # Try to get the full list of voters
        voters = await self.model.get_voters_by_post_id(post_details.id)

        # Now we randomly select one of the options for all polls
        selected_options: Dict[str, User | str] = {}
        for poll_id, users in voters.voters.items():
            # If there are no users who voted for this option, we should skip it
            if not users:
                selected_options[poll_id] = "参与投票人数为0，无法抽选"
                continue

            # Now randomly select one user from the list of users
            selected_user = random.choice(users)
            selected_options[poll_id] = selected_user

        # Now we have to match poll_id with their contents in post_details
        results: Dict[str, Dict[str, User | str] | str] = {}
        for idx, poll in enumerate(post_details.polls):
            current_poll_title = poll.title or f"投票 {idx + 1}"

            # Check whether the poll is visible or not
            if poll.id not in visible_poll_ids:
                results[current_poll_title] = "该投票不可见或类型不支持，无法抽选"
                continue

            current_poll_result: Dict[str, List[User] | str] = {}
            for option in poll.options:
                if option.id in selected_options:
                    current_poll_result[option.html] = selected_options[option.id]

            # Add titles for each poll
            results[current_poll_title] = current_poll_result

        # Finally we format the reply text
        reply_lines = ["抽选结果如下：\n"]
        for poll_title, options in results.items():
            # Poll title line
            reply_lines.append(f"## {poll_title}")
            # Any error reported for this poll
            if isinstance(options, str):
                reply_lines.append(f"错误：{options}")
                continue
            # Now we add the result for each option in the poll
            for option_html, selected_user in options.items():
                # Option content line
                reply_lines.append(f"{option_html}")
                # If any error occurs, we report it here
                if isinstance(selected_user, str):
                    reply_lines.append(f"错误：{selected_user}")
                    continue
                reply_lines.append(f"抽选结果：@{selected_user.username}")
                reply_lines.append("")

        # Join all lines into a single reply text
        return MentionModel._make_unique_reply("\n".join(reply_lines))

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
            "1. 输入【小南瓜】+对话，与南瓜 bot 聊天 :jack_o_lantern:\n"
            "2. 输入【清除历史】，清除当前话题中的对话历史记录 :broom:\n"
            "3. 输入【投掷】+ndm，投掷 n 个 1 到 m 之间的随机数 :game_die:\n"
            "4. 输入【抽选】+topic_id/post_number，随机抽选该帖中的投票结果，或者直接回复包含投票的帖子进行抽选 :ballot_box:\n"
            "5. 输入【帮助】，查看该帮助信息 :question:"
        )

    async def _new_action_routine(self, action: UserActionDetails) -> None:
        """
        A routine to handle new actions for a specific user.
        NOTE: no exception should be raised in this method.

        :param action: The details of the user action (mention).
        :return: None
        """
        # This is the text to reply to the post
        text: Optional[str] = None

        try:
            # First let's try to get the post details
            post_details = await self.model.get_post_details(action.post_id)
            post_user = User(
                post_details.user_id,
                post_details.username,
                post_details.name,
            )

            # If the member "raw" is not present, we should skip it
            if post_details.raw is None:
                logging.warning(
                    f"Post {action.post_id} does not have raw content, skipping."
                )
                return

        except Exception:
            logging.error(
                f"Failed to get post details for {action.post_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            return

        try:
            # If the post is an auto-reply, we should skip it
            if auto_reply_tag in post_details.raw:
                return

            # Check if the mention actually exists
            r = re.search(rf"@{self.username}", post_details.raw, re.IGNORECASE)
            if r is None:
                return

            # Check help condition
            text = self._help_condition(post_details.raw)
            if text is not None:
                return

            # Check clear condition
            text = await self._clear_condition(post_details.raw, post_details.topic_id)
            if text is not None:
                return

            # Check pumpkin condition
            text = await self._pumpkin_condition(
                post_details.topic_id,
                post_details.raw,
                post_user,
            )
            if text is not None:
                return

            # Check random condition
            text = self._random_condition(post_details.raw)
            if text is not None:
                return

            # Check poll condition
            text = await self._poll_condition(
                post_details.raw,
                post_details.topic_id,
                post_details.reply_to_post_number,
            )
            if text is not None:
                return

        except Exception:
            # If we failed to get the post details or any other error occurred
            logging.error(
                f"Failed to process post {action.post_id}, "
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
                    action.topic_id,
                    action.post_number,
                )
