from dataclasses import dataclass
from typing import List, Optional, Literal


@dataclass
class User:
    """
    Represents a user in the system.
    """

    id: int
    username: str
    name: Optional[str]


@dataclass
class PostDetails:
    """
    Represents the details of a post in a topic.
    """

    id: int
    name: Optional[str]
    user_id: int
    username: str
    user_cakedate: Optional[str]
    created_at: str
    cooked: str
    raw: Optional[str]
    post_number: int
    post_type: int
    updated_at: str
    reply_count: int
    reply_to_post_number: Optional[int]
    reply_to_user: Optional[User]
    yours: bool
    topic_id: int
    can_edit: bool
    can_delete: bool
    can_recover: bool
    can_wiki: bool
    can_retort: bool
    can_remove_retort: bool
    can_accept_answer: bool
    can_unaccept_answer: bool
    can_see_hidden_post: bool
    can_view_edit_history: bool


@dataclass
class PostStream:
    """
    Represents a stream of posts in a topic.
    """

    posts: List[PostDetails]
    stream: List[int]


@dataclass
class TopicDetails:
    """
    Represents the details of a topic.
    """

    post_stream: PostStream
    id: int
    title: str
    fancy_title: str
    posts_count: int
    created_at: str
    views: int
    reply_count: int
    like_count: int
    last_posted_at: str
    visible: bool
    closed: bool
    archived: bool
    has_summary: bool
    archetype: str
    slug: str
    category_id: int
    word_count: int
    deleted_at: Optional[str]
    user_id: int
    image_url: Optional[str]
    slow_mode_seconds: int
    draft_key: Optional[str]
    draft_sequence: Optional[int]
    posted: bool
    current_post_number: int
    highest_post_number: int
    last_read_post_number: int
    last_read_post_id: int
    chunk_size: int
    bookmarked: bool
    message_bus_last_id: int
    participant_count: int
    show_read_indicator: bool
    slow_mode_enabled_until: Optional[str]
    summarizable: bool


@dataclass
class ImageUploadPayload:
    """
    Represents the payload for an image upload.
    """

    upload_type: str
    relativePath: str
    name: str
    type: str
    sha1_checksum: str
    file: bytes


@dataclass
class ImageUploadResponse:
    """
    Represents the response from an image upload.
    """

    id: int
    url: str
    original_filename: str
    short_url: str
    short_path: str


@dataclass
class TimeInADay:
    """
    Represents a time in a day.
    """

    hour: int
    minute: int
    second: int = 0


@dataclass
class ImageURL:
    """
    Represents an image URL.
    """

    type: Literal["url", "base64"]
    data: str
