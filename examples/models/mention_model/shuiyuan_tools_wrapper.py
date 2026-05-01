from typing import List, Optional

from shuiyuan_auto_reply.openrouter.image_tool import OpenRouterImageTool
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel

from .shuiyuan_tools_objects import PostShort, UserShort


class ShuiyuanToolsWrapper:
    """
    A wrapper around the ShuiyuanModel to provide tools for the OpenRouter model.
    """

    def __init__(self, shuiyuan_model: ShuiyuanModel):
        self.shuiyuan_model = shuiyuan_model
        self.image_tool = OpenRouterImageTool(shuiyuan_model)

    async def search_user_by_term(self, term: str) -> List[UserShort]:
        """
        Search for users by a search term.

        :param term: The search term to use for finding users. It has to be NON-EMPTY.
        :return: A list of UserShort instances matching the search term.
        """
        users = await self.shuiyuan_model.search_user_by_term(term)
        return [UserShort(user) for user in users]

    async def search_post_details_by_optional_username_topic(
        self,
        term: str = "",
        latest: bool = False,
        username: Optional[str] = None,
        topic_id: Optional[int] = None,
    ) -> List[PostShort]:
        """
        Search for posts by a search term, an optional username and an optional topic ID, and return detailed information.

        :param term: Optional search term to use for finding posts. Default is empty.
        :param latest: Whether to sort the results by created_at in descending order. Default is False.
        :param username: An optional username to filter posts by. Default is None.
        :param topic_id: An optional topic ID to filter posts by. Default is None.
        :return: A list of PostShort instances matching the search criteria.
        """
        posts_dict = (
            await self.shuiyuan_model.search_post_details_by_optional_username_topic(
                term,
                latest,
                username,
                topic_id,
            )
        )
        return [
            PostShort(post, title)
            for title, post_list in posts_dict.items()
            for post in post_list
        ]

    async def query_recent_posts_by_topic_id(
        self,
        topic_id: int,
        limit: int = 10,
    ) -> List[PostShort]:
        """
        Query recent posts in a topic by its ID.

        :param topic_id: The ID of the topic to query.
        :param limit: The maximum number of recent posts to retrieve. Default is 10.
        :return: A list of PostShort instances for the recent posts in the topic.
        """
        title, posts = await self.shuiyuan_model.query_recent_posts_by_topic_id(
            topic_id, limit
        )
        return [PostShort(post, title) for post in posts]

    async def generate_image_and_upload(self, prompt: str) -> str:
        """
        Generate an image from a prompt and then return the Shuiyuan short URL.
        NOTE: To show this image in your reply, you have to use Markdown format like `![image]({short_url})`.

        :param prompt: The prompt to generate the image from.
        :return: The short URL of the uploaded image on Shuiyuan.
        """
        return await self.image_tool.generate_and_upload(
            prompt,
            output_dir="generated_images",
            image_size="1K",
        )
