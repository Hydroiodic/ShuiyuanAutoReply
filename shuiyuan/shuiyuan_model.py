import io
import os
import re
import skia
import base64
import pickle
import aiohttp
import asyncio
import hashlib
import logging
import traceback
import http.cookies
from PIL import Image
from dacite import from_dict
from typing import Optional
from .constants import *
from .objects import *


class CookiesFileNotFoundError(Exception):
    """Custom exception for when the cookies file is not found."""

    pass


class CSRFTokenNotFoundError(Exception):
    """Custom exception for when the CSRF token is not found in the response."""

    pass


class ShuiyuanModel:
    """
    This class is used to interact with the Shuiyuan API.
    We should login to Shuiyuan here.
    """

    def __init__(self):
        """
        Initialize the ShuiyuanModel. Use create() class method for async initialization.
        """
        self.session = None

    @classmethod
    async def create(cls, file_path: str = "cookies"):
        """
        Create and initialize a ShuiyuanModel instance with async operations.

        :param file_path: The path to the cookies file.
        :return: Initialized ShuiyuanModel instance.
        """
        instance = cls()
        await instance._load_persistence_cookie(file_path)
        return instance

    async def _update_cookies(self) -> None:
        # get the cookies
        self.session.headers.update({"User-Agent": default_user_agent})
        response = await self.session.get(get_cookies_url)

        # now let's try to get CSRF Token from response
        format = r'<meta name="csrf-token" content="([^"]+)"[^>]*>'
        match = re.search(format, await response.text())
        if not match:
            raise CSRFTokenNotFoundError(
                "[INITIALIZATION] "
                "Failed to find CSRF token in the response, "
                "please check the cookies file or the website structure"
            )

        # OK, let's update the CSRF token in the session headers
        csrf_token = match.group(1)
        self.session.headers.update({"X-CSRF-Token": csrf_token})

    async def _load_persistence_cookie(self, file_path: str) -> None:
        # check if the cookies file exists
        if not os.path.exists(file_path):
            raise CookiesFileNotFoundError(
                "[FILESYSTEM] "
                "Failed to find persistent cookies, "
                "please run the ipynb file to get them first"
            )

        # load the cookies from the file
        self.session = aiohttp.ClientSession()
        with open(file_path, "rb") as f:
            cookies = pickle.load(f)
            self.session.cookie_jar.update_cookies(cookies)

        # update the cookies in the session
        await self._update_cookies()

    async def reply_to_post(
        self,
        raw: str,
        topic_id: int,
        reply_to_post_number: Optional[int] = None,
    ) -> None:
        """
        Reply to a topic with the given raw content.

        :param raw: The content to reply with.
        :param topic_id: The ID of the topic to reply to.
        :param reply_to_post_number: The post number to reply to.
        """

        # First we construct the form data we need to post
        form_data = aiohttp.FormData()
        form_data.add_field("raw", raw)
        form_data.add_field("topic_id", str(topic_id))
        if reply_to_post_number is not None:
            form_data.add_field("reply_to_post_number", str(reply_to_post_number))

        # OK, let's post it
        while True:
            response = await self.session.post(reply_url, data=form_data)
            if response.status == 200:
                break
            elif response.status == 429:
                logging.warning(f"Failed to reply to post: {await response.text()}")
                await asyncio.sleep(1)
            else:
                raise Exception(f"Failed to reply to post: {await response.text()}")

    async def get_topic_details(self, topic_id: int) -> TopicDetails:
        """
        Get the details of a topic by its ID.

        :param topic_id: The ID of the topic to retrieve.
        :return: An instance of TopicDetails containing the topic information.
        """
        response = await self.session.get(f"{get_topic_url}/{topic_id}.json")
        if response.status != 200:
            raise Exception(f"Failed to get topic details: {await response.text()}")

        data = await response.json()
        return from_dict(TopicDetails, data)

    async def get_post_details(self, post_id: int) -> PostDetails:
        """
        Get the details of a post by its ID.

        :param post_id: The ID of the post to retrieve.
        :return: An instance of PostDetails containing the post information.
        """
        response = await self.session.get(f"{reply_url}/{post_id}.json")
        if response.status != 200:
            raise Exception(f"Failed to get post details: {await response.text()}")

        data = await response.json()
        return from_dict(PostDetails, data)

    async def upload_image(self, image_path: str) -> ImageUploadResponse:
        """
        Upload an image to the Shuiyuan server.

        :param image_path: The path to the image file to upload.
        :return: The URL of the uploaded image.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        with open(image_path, "rb") as image_file:
            # Read the image content
            image_content = image_file.read()

            form_data = aiohttp.FormData()
            form_data.add_field("upload_type", "composer")
            form_data.add_field("relative_path", "null")
            form_data.add_field("type", "image/jpeg")
            # Calculate the SHA1 checksum of the image
            sha1sum = hashlib.sha1(image_content).hexdigest()
            form_data.add_field("sha1sum", sha1sum)
            form_data.add_field(
                "file",
                image_content,
                filename=os.path.basename(image_path),
                content_type="image/jpeg",
            )

            response = await self.session.post(upload_url, data=form_data, timeout=10)
            if response.status != 200:
                raise Exception(f"Failed to upload image: {await response.text()}")

            data = await response.json()
            return from_dict(ImageUploadResponse, data)

    async def try_upload_image(
        self,
        image_path: str,
        try_base64: bool = True,
        try_base64_size_kb: int = 20,
    ) -> ImageURL:
        """
        Try to upload an image and return its URL or base64 HTML code.

        :param image_path: The path to the image file to upload.
        :return: The URL of the uploaded image, or None if the upload failed.
        """
        try:
            # Upload the image and get the response
            response = await self.upload_image(image_path)
            return ImageURL("url", f"![img]({response.short_url})")
        except Exception as e:
            # If try_base64 is False, we will not try to convert later
            if not try_base64:
                logging.error(
                    f"Failed to upload image {image_path} to Shuiyuan server, "
                    f"traceback is as follows:\n{traceback.format_exc()}"
                )
                raise e

            # Log the error and traceback
            logging.warning(
                f"Failed to upload image {image_path} to Shuiyuan server, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            logging.warning("Trying to convert the image to base64 HTML code.")

            try:
                with Image.open(image_path) as pil_image:
                    base64_image = self.compress_image_to_base64(
                        img=pil_image,
                        target_size_kb=try_base64_size_kb,
                    )
                    return ImageURL(
                        "base64",
                        f'<img alt="img" src="data:image/jpeg;base64,{base64_image}" />',
                    )
            except Exception as e:
                logging.error(
                    f"Failed to convert image {image_path} to base64 HTML code, "
                    f"traceback is as follows:\n{traceback.format_exc()}"
                )
                raise e

    @staticmethod
    def skia_to_pil(skia_image: skia.Image) -> Image.Image:
        # Convert Skia Image to bytes
        skia_data = skia_image.encodeToData(skia.EncodedImageFormat.kJPEG)
        if not skia_data:
            raise ValueError("Failed to encode Skia image to data")
        # Convert bytes to PIL Image
        return Image.open(io.BytesIO(bytes(skia_data)))

    @staticmethod
    def compress_image_to_base64(
        img: Image.Image,
        target_size_kb: int = 20,
        quality: int = 85,
        step: int = 5,
    ):
        # Ensure image is in RGB mode
        if img.mode != "RGB":
            img = img.convert("RGB")

        buffer = io.BytesIO()
        current_quality = quality

        while current_quality > 0:
            buffer.seek(0)
            buffer.truncate()

            # Try to save the image with the current quality
            img.save(buffer, format="JPEG", quality=current_quality)
            size_kb = len(buffer.getvalue()) / 1024  # Size in KB

            # Check if the size is within the target
            if size_kb <= target_size_kb:
                break

            # Try to continue reducing quality
            current_quality -= step

        if current_quality <= 0:
            raise ValueError("Cannot compress image to the target size")

        # Convert to base64
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    async def close(self) -> None:
        """
        Close the aiohttp session and clean up resources.
        """
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        """
        Async context manager entry.
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit. Automatically closes the session.
        """
        await self.close()


def _global_ignore_illegal_cookies() -> None:
    # ignore the illegal key error
    http.cookies._is_legal_key = lambda _: True


_global_ignore_illegal_cookies()
