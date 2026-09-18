from typing import List, Optional

from shuiyuan_auto_reply.openrouter.image_tool import OpenRouterImageTool
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel

from .shuiyuan_tools_objects import PostShort, UserShort


class ShuiyuanToolsWrapper:
    """
    A wrapper around the ShuiyuanModel to provide tools for the OpenRouter model.
    Tool methods never raise; failures are returned as strings so the LLM can
    see what went wrong and adapt.
    """

    def __init__(self, shuiyuan_model: ShuiyuanModel):
        self.shuiyuan_model = shuiyuan_model
        self.image_tool = OpenRouterImageTool(shuiyuan_model)

    @staticmethod
    def _format_error(e: Exception) -> str:
        return f"Tool call failed: {type(e).__name__}: {e}"

    async def search_user_by_term(
        self,
        term: str,
        include_avatar: bool = False,
    ) -> List[UserShort] | str:
        """
        Search for users by a search term.

        :param term: The search term to use for finding users. It has to be NON-EMPTY.
        :param include_avatar: Whether to include each user's avatar. Default is False.
            Set to True only if the avatar is needed for image generation or editing.
        :return: A list of UserShort instances matching the search term or error message.
        """
        try:
            users = await self.shuiyuan_model.search_user_by_term(term)
            return [UserShort(user, include_avatar=include_avatar) for user in users]
        except Exception as e:
            return self._format_error(e)

    async def search_user_by_user_id(
        self,
        user_id: int,
        include_avatar: bool = False,
    ) -> UserShort | None | str:
        """
        Search for a user by their user ID.

        :param user_id: The ID of the user to search for.
        :param include_avatar: Whether to include each user's avatar. Default is False.
            Set to True only if the avatar is needed for image generation or editing.
        :return: An instance of UserShort for the user with the given ID or error message.
        """
        try:
            user = await self.shuiyuan_model.search_user_by_user_id(user_id)
            if user and include_avatar and user.avatar_template is None:
                full_user = await self.shuiyuan_model.get_user_by_username(
                    user.username
                )
                if full_user:
                    user = full_user
            return UserShort(user, include_avatar=include_avatar) if user else None
        except Exception as e:
            return self._format_error(e)

    async def search_post_details_by_optional_username_topic(
        self,
        term: str = "",
        latest: bool = False,
        username: Optional[str] = None,
        topic_id: Optional[int] = None,
    ) -> List[PostShort] | str:
        """
        Search for posts by a search term, an optional username and an optional topic ID, and return detailed information.

        :param term: Optional search term to use for finding posts. Default is empty.
        :param latest: Whether to sort the results by created_at in descending order. Default is False.
        :param username: An optional username to filter posts by. Default is None.
        :param topic_id: An optional topic ID to filter posts by. Default is None.
        :return: A list of PostShort instances matching the search criteria or error message.
        """
        try:
            posts_dict = await self.shuiyuan_model.search_post_details_by_optional_username_topic(
                term,
                latest,
                username,
                topic_id,
            )
            return [
                PostShort(post, title)
                for title, post_list in posts_dict.items()
                for post in post_list
            ]
        except Exception as e:
            return self._format_error(e)

    async def query_recent_posts_by_topic_id(
        self,
        topic_id: int,
        limit: int = 10,
    ) -> List[PostShort] | str:
        """
        Query recent posts in a topic by its ID.

        :param topic_id: The ID of the topic to query.
        :param limit: The maximum number of recent posts to retrieve. Default is 10.
        :return: A list of PostShort instances for the recent posts in the topic or error message.
        """
        try:
            title, posts = await self.shuiyuan_model.query_recent_posts_by_topic_id(
                topic_id, limit
            )
            return [PostShort(post, title) for post in posts]
        except Exception as e:
            return self._format_error(e)

    async def get_post_details_by_post_number(
        self, topic_id: int, post_number: int
    ) -> PostShort | str:
        """
        Get the details of a post by its topic ID and post number.
        If a user give you a url like "https://shuiyuan.sjtu.edu.cn/t/topic_id/post_number",
        you can extract the topic_id and post_number from the url and use this function to get the post details.
        Also, for any post you've retrieved using tool, if the `topic_id` and `reply_to_post_number` are both not None,
        you can use this function to get the details of the post being replied to.

        :param topic_id: The ID of the topic the post belongs to.
        :param post_number: The post number within the topic.
        :return: An instance of PostShort containing the post information or error message.
        """
        try:
            title, post = (
                await self.shuiyuan_model.get_post_details_with_title_by_post_number(
                    topic_id,
                    post_number,
                )
            )
            return PostShort(post, title)
        except Exception as e:
            return self._format_error(e)

    async def generate_image_and_upload(self, prompt: str) -> str:
        """
        Generate an image from a prompt and then return the Shuiyuan short URL.
        NOTE: To show this image in your reply, you have to use Markdown format like `![image]({short_url})`.
        NOTE: This tool does NOT accept reference images; describe everything
        needed (style, subject, composition) directly in the prompt text.

        :param prompt: The prompt to generate the image from.
        :return: The short URL of the uploaded image on Shuiyuan or error message.
        """
        try:
            return await self.image_tool.generate_and_upload(
                prompt,
                output_dir="generated_images",
                image_size="1K",
            )
        except Exception as e:
            return self._format_error(e)
