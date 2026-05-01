import base64
import os
from typing import Optional

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


@mcp.tool()
async def generate_image(text: str) -> str:
    """
    Generate an image from a text prompt with OpenAI GPT-Image-2.
    NOTE: The user cannot see how you generate the image, so you must add "![](image-url)"
        (Markdown image format) in your final response.

    Args:
        text: The image prompt.

    Returns:
        The generated image URL.
    """

    global shuiyuan_model
    if not shuiyuan_model:
        shuiyuan_model = await ShuiyuanModel.create()

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    try:
        # Use the OpenAI API to generate an image based on the provided text prompt
        response = await client.images.generate(
            prompt=text,
            model="gpt-image-2",
            n=1,
            size="1024x1024",
            quality="high",
            output_format="jpeg",
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
        return f"Error: {exc}"
