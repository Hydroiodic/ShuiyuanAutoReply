"""
Only important information for LLM is kept here.
"""

from typing import Optional

from shuiyuan_auto_reply.shuiyuan.objects import PostDetails, User
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel


class UserShort:
    """
    Represents a short version of a user, with only the most important information.
    """

    id: int
    username: str
    name: Optional[str]

    def __init__(self, user: User):
        self.id = user.id
        self.username = user.username
        self.name = user.name

    def __str__(self):
        return (
            f"ID: 【{self.id}】 Username: 【{self.username}】"
            + f" Name: 【{self.name}】"
            if self.name
            else "" + "\n"
        )

    def __repr__(self):
        return self.__str__()


class PostShort:
    """
    Represents a short version of a post, with only the most important information.
    """

    id: int
    post_number: int
    topic_id: int
    name: Optional[str]
    user_id: int
    username: str
    cooked: str
    raw: Optional[str]
    reply_to_post_number: Optional[int]
    title: str

    def __init__(self, post: PostDetails, title: str):
        self.id = post.id
        self.post_number = post.post_number
        self.topic_id = post.topic_id
        self.name = post.name
        self.user_id = post.user_id
        self.username = post.username
        self.cooked = post.cooked[:384]
        self.raw = post.raw[:384] if post.raw else None
        self.reply_to_post_number = post.reply_to_post_number
        self.title = title

    def __str__(self):
        return (
            f"PostMeta: id={self.id}, post_number={self.post_number}, topic_id={self.topic_id}\n"
            f"FromUser: {UserShort(User(id=self.user_id, username=self.username, name=self.name))}"
            f"TopicTitle: {self.title}\n"
            f"Content: {ShuiyuanModel.remove_shuiyuan_signature(self.raw) if self.raw else self.cooked}\n"
        )

    def __repr__(self):
        return self.__str__()
