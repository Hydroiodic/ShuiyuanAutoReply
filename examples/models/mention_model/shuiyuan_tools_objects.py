"""
Only important information for LLM is kept here.
"""

from typing import Optional

from shuiyuan_auto_reply.shuiyuan.objects import PostDetails, User


class UserShort:
    """
    Represents a short version of a user, with only the most important information.
    """

    username: str
    name: Optional[str]

    def __init__(self, user: User):
        self.username = user.username
        self.name = user.name


class PostShort:
    """
    Represents a short version of a post, with only the most important information.
    """

    id: int
    post_number: int
    topic_id: int
    name: Optional[str]
    username: str
    cooked: str
    raw: Optional[str]
    reply_to_post_number: Optional[int]

    def __init__(self, post: PostDetails):
        self.id = post.id
        self.post_number = post.post_number
        self.topic_id = post.topic_id
        self.name = post.name
        self.username = post.username
        self.cooked = post.cooked[:192]
        self.raw = post.raw[:192] if post.raw else None
        self.reply_to_post_number = post.reply_to_post_number

    def __str__(self):
        return (
            f"PostMeta: id={self.id}, post_number={self.post_number}, topic_id={self.topic_id}\n"
            f"FromUser: {self.username}{f' ({self.name})' if self.name else ''}\n"
            f"Content: {self.raw if self.raw else self.cooked}\n"
        )

    def __repr__(self):
        return self.__str__()
