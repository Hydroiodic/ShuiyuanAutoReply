import logging
from typing import Awaitable, Callable, Optional

from shuiyuan_auto_reply.constants import settings
from shuiyuan_auto_reply.shuiyuan.objects import PostDetails, User
from shuiyuan_auto_reply.shuiyuan.reply_utils import make_unique_reply
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel

# Returns the text to reply with, or None if the post needs no reply
PostHandler = Callable[[PostDetails, User], Awaitable[Optional[str]]]

GENERIC_ERROR_REPLY = "抱歉，南瓜bot遇到了一个错误，暂时无法处理您的请求，请稍后再试"


async def handle_post_and_reply(
    model: ShuiyuanModel,
    post_id: int,
    handler: PostHandler,
    error_reply: str = GENERIC_ERROR_REPLY,
) -> None:
    """
    Fetch a post, let the handler build a reply for it and post that reply.
    Posts without raw content and posts made by the bot itself are skipped.
    If the handler raises, an error message is replied instead.
    NOTE: no exception is raised from this function.

    :param model: The ShuiyuanModel used to read and reply to posts.
    :param post_id: The ID of the post to handle.
    :param handler: Builds the reply text for the post, or returns None.
    :param error_reply: The text to reply with if the handler fails.
    """
    # First let's try to get the post details
    try:
        post_details = await model.get_post_details(post_id)
    except Exception:
        logging.exception("Failed to get post details for %s", post_id)
        return

    # If the member "raw" is not present, we should skip it
    if post_details.raw is None:
        logging.warning("Post %s does not have raw content, skipping.", post_id)
        return

    # If the post is an auto-reply, we should skip it
    if settings.auto_reply_tag in post_details.raw:
        return

    post_user = User(post_details.user_id, post_details.username, post_details.name)
    try:
        text = await handler(post_details, post_user)
    except Exception:
        logging.exception("Failed to process post %s", post_id)
        text = make_unique_reply(error_reply)

    if text is None:
        return

    try:
        await model.reply_to_post(text, post_details.topic_id, post_details.post_number)
    except Exception:
        logging.exception("Failed to reply to post %s", post_id)
