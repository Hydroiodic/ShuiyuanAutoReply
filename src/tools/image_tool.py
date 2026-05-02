import asyncio
import base64
import logging
import os
import traceback
from typing import List, Optional

import aiohttp
import shuiyuan_auto_reply.openrouter.openrouter_model
from openai import AsyncOpenAI
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel

from ..instance import mcp

api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_COMPATIBLE_API_KEY is not configured.")

base_url = os.getenv("OPENAI_COMPATIBLE_URL")
if not base_url:
    raise RuntimeError("OPENAI_COMPATIBLE_URL is not configured.")

image_local_save_path = os.getenv("IMAGE_LOCAL_SAVE_PATH", "./generated_images")
os.makedirs(image_local_save_path, exist_ok=True)


shuiyuan_model: Optional[ShuiyuanModel] = None


async def _ensure_shuiyuan_model() -> ShuiyuanModel:
    """
    Ensure that the ShuiyuanModel instance is created and available for use.
    This function checks if the global variable `shuiyuan_model` is already initialized.

    :return: The initialized ShuiyuanModel instance.
    """
    global shuiyuan_model
    if not shuiyuan_model:
        shuiyuan_model = await ShuiyuanModel.create()

    return shuiyuan_model


async def _try_download_shuiyuan_image(url: str, retries: int = 3) -> bytes | None:
    """
    Try to download an image from a Shuiyuan upload URL.

    Args:
        url: The Shuiyuan upload URL, which starts with "upload://".
        retries: The number of retry attempts in case of failure.

    Returns:
        The byte data of the downloaded image if successful, or None if any error occurs.
    """
    shuiyuan_model = await _ensure_shuiyuan_model()

    # Retry for a specified number of attempts in case of transient errors
    for attempt in range(retries):
        try:
            return await shuiyuan_model.download_image(url)
        except Exception as exc:
            logging.warning(
                f"Attempt {attempt + 1} to download image from {url} failed: {exc}"
            )
            await asyncio.sleep(1)

    raise RuntimeError(f"Failed to download image from {url} after {retries} attempts.")


async def _try_download_http_image(url: str, retries: int = 3) -> bytes | None:
    """
    Try to download an image from a regular HTTP/HTTPS URL.

    Args:
        url: The HTTP/HTTPS URL of the image.
        retries: The number of retry attempts in case of failure.

    Returns:
        The byte data of the downloaded image if successful, or None if any error occurs.
    """
    # Use aiohttp to download the image with retries and error handling
    async with aiohttp.ClientSession() as session:
        # Retry for a specified number of attempts in case of transient errors
        for attempt in range(retries):
            try:
                response = await session.get(url)
                bytes = await response.read()
            except Exception as exc:
                logging.warning(
                    f"Attempt {attempt + 1} to download image from {url} failed: {exc}"
                )
                await asyncio.sleep(1)
                continue

            # Validate that the downloaded content is an image by checking the Content-Type header
            content_type = response.headers.get("Content-Type", "")
            if content_type.startswith("image/"):
                return bytes
            else:
                raise ValueError(
                    f"URL {url} did not return an image. Content-Type: {content_type}"
                )

    raise RuntimeError(f"Failed to download image from {url} after {retries} attempts.")


async def _urls_to_bytes(image_urls: List[str]) -> List[bytes] | str:
    """
    Convert a list of image URLs to a list of byte data.

    Args:
        image_urls: A list of image URLs. The URLs can start with "upload://" or "http(s)://".

    Returns:
        A list of byte data corresponding to the images at the provided URLs.
        Or an error message if any error occurs during the conversion process.
    """

    # OpenAI constaint
    if len(image_urls) > 16:
        return "Error: The number of reference images cannot exceed 16."

    byte_data_list = []
    for url in image_urls:
        if url.startswith("upload://"):
            # Handle Shuiyuan upload URL
            try:
                byte_data = await _try_download_shuiyuan_image(url)
                byte_data_list.append(byte_data)
            except Exception as exc:
                logging.error(f"Error downloading image from {url}: {exc}")
        elif url.startswith("http://") or url.startswith("https://"):
            # Handle regular HTTP/HTTPS URL
            try:
                byte_data = await _try_download_http_image(url)
                byte_data_list.append(byte_data)
            except Exception as exc:
                logging.error(f"Error downloading image from {url}: {exc}")
        else:
            logging.warning(f"Unsupported URL format: {url}")

    # If no valid images were downloaded, return an error message
    if not byte_data_list:
        return "Error: No valid images could be downloaded from the provided URLs."

    return byte_data_list


@mcp.tool()
async def generate_image(text: str, image_urls: Optional[List[str]] = None) -> str:
    """
    Generate an image from a text prompt with OpenAI GPT-Image-2.
    NOTE: The user cannot see how you generate the image, so you must add "![](image-url)"
        (Markdown image format) in your final response. ALWAYS use this function for image generation,
        and NEVER generate from some other website or tool like "pollinations.ai".
    STYLE PREFERENCE: If the user does not specify a style, you should generate an image in a comic style.

    Args:
        text: The image prompt.
        image_urls: An optional LIST of image URLs that can be used as references for generating the new image.
            NOTE: You have to retrieve urls from the Markdown style post like "![](image-url)" in the user input.
            Normally, the urls are started with "upload://", which means the images are uploaded to Shuiyuan.
            You can only pass those urls beginning with "upload://" or "http(s)://" here.

    Returns:
        The generated image URL. Started with "upload://". Or error message if the image generation fails.
    """

    # Initialize the ShuiyuanModel instance if it hasn't been created yet
    shuiyuan_model = await _ensure_shuiyuan_model()
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=5,
    )

    try:
        # Use the OpenAI API to generate an image based on the provided text prompt
        if image_urls:
            # Download the reference images and convert them to byte data
            image_bytes_list = await _urls_to_bytes(image_urls)

            # If the result is a string, it means an error occurred during image downloading
            if isinstance(image_bytes_list, str):
                return image_bytes_list

            # Edit the image with the provided reference images and the text prompt
            response = await client.images.edit(
                prompt=text,
                image=image_bytes_list,
                model="gpt-image-2",
                output_format="jpeg",
                n=1,
            )
        else:
            # Generate a new image with the provided text prompt without any reference images
            response = await client.images.generate(
                prompt=text,
                model="gpt-image-2",
                output_format="jpeg",
                moderation="low",
                n=1,
            )
        base64_image = response.data[0].b64_json
        decoded_image = base64.b64decode(base64_image)

        # Save the image to a local file
        file_path = os.path.join(image_local_save_path, f"{response.created}.jpeg")
        with open(file_path, "wb") as f:
            f.write(decoded_image)

        # Upload the image to Shuiyuan and get the URL
        return (await shuiyuan_model.upload_image(decoded_image)).short_url

    except Exception as exc:
        logging.error(f"Error generating image: {traceback.format_exc()}")
        return f"Error: {exc}"
