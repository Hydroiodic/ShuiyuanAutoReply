import os
from typing import Any

import dashscope
from dashscope import MultiModalConversation

from ..instance import mcp

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    raise RuntimeError("DASHSCOPE_API_KEY is not configured.")


def _extract_image_base64(response: Any) -> str:
    if getattr(response, "status_code", 200) != 200:
        message = getattr(response, "message", None) or getattr(response, "code", None)
        raise RuntimeError(f"DashScope request failed: {message or response}")

    output = getattr(response, "output", None)
    if output is None and isinstance(response, dict):
        output = response.get("output")

    choices = getattr(output, "choices", None)
    if choices is None and isinstance(output, dict):
        choices = output.get("choices")
    if not choices:
        raise RuntimeError("DashScope response did not include any image choices.")

    choice = choices[0]
    message = getattr(choice, "message", None)
    if message is None and isinstance(choice, dict):
        message = choice.get("message")

    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if not content:
        raise RuntimeError("DashScope response did not include image content.")

    for item in content:
        image = getattr(item, "image", None)
        if image is None and isinstance(item, dict):
            image = item.get("image")
        if isinstance(image, str) and image:
            return image.split(",", 1)[1] if image.startswith("data:image/") else image

    raise RuntimeError("DashScope response content did not contain a base64 image.")


@mcp.tool()
async def generate_image(text: str) -> str:
    """
    Generate an image from a text prompt with DashScope Qwen Image.

    Args:
        text: The image prompt.

    Returns:
        The generated image as a base64-encoded string.
    """

    messages = [
        {
            "role": "user",
            "content": [{"text": text}],
        }
    ]

    try:
        response = MultiModalConversation.call(
            api_key=api_key,
            model="qwen-image-2.0",
            messages=messages,
            result_format="message",
            stream=False,
            n=1,
            watermark=True,
            negative_prompt="",
        )
        return _extract_image_base64(response)
    except Exception as exc:
        return f"Error: {exc}"
