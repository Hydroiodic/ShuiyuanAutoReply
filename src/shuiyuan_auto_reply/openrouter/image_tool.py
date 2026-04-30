import base64
import io
import mimetypes
import re
from pathlib import Path
from typing import Optional
from uuid import uuid4

from openai import BadRequestError
from PIL import Image

from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel

from .openrouter_model import BaseOpenRouterModel, openrouter_model

DEFAULT_OPENROUTER_IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"
_DATA_URL_RE = re.compile(r"^data:(?P<mime>[-\w.]+/[-\w.+]+);base64,(?P<data>.+)$")
_SUPPORTED_ASPECT_RATIOS = {
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
    "1:4",
    "4:1",
    "1:8",
    "8:1",
}
_SUPPORTED_IMAGE_SIZES = {"0.5K", "512", "1K", "2K", "4K"}


class OpenRouterImageTool(BaseOpenRouterModel):
    """
    Generate an image with OpenRouter and upload it to Shuiyuan.
    """

    def __init__(
        self,
        shuiyuan_model: ShuiyuanModel,
        *,
        model: Optional[str] = None,
    ):
        super().__init__()
        self.shuiyuan_model = shuiyuan_model
        self.model = model or openrouter_model(
            "OPENROUTER_IMAGE_MODEL",
            DEFAULT_OPENROUTER_IMAGE_MODEL,
        )

    async def generate_and_upload(
        self,
        prompt: str,
        *,
        output_dir: Optional[str | Path] = None,
        aspect_ratio: Optional[str] = None,
        image_size: Optional[str] = None,
    ) -> str:
        """
        Generate an image, optionally save it locally, upload it to Shuiyuan,
        and return the Shuiyuan short URL.
        """
        data_url = await self._generate_image_data_url(
            prompt, aspect_ratio=aspect_ratio, image_size=image_size
        )
        image_bytes, mime_type = self._decode_data_url(data_url)

        if output_dir is not None:
            self._save_image(image_bytes, mime_type, Path(output_dir))

        upload_bytes = self._to_jpeg_bytes(image_bytes)
        response = await self.shuiyuan_model.upload_image(upload_bytes)
        return response.short_url

    async def _generate_image_data_url(
        self,
        prompt: str,
        *,
        aspect_ratio: Optional[str] = None,
        image_size: Optional[str] = None,
    ) -> str:
        if aspect_ratio is not None and aspect_ratio not in _SUPPORTED_ASPECT_RATIOS:
            raise ValueError(f"Unsupported OpenRouter aspect_ratio: {aspect_ratio}")
        if image_size is not None and image_size not in _SUPPORTED_IMAGE_SIZES:
            raise ValueError(f"Unsupported OpenRouter image_size: {image_size}")

        extra_body = {"modalities": ["image"]}
        image_config = {}
        if aspect_ratio is not None:
            image_config["aspect_ratio"] = aspect_ratio
        if image_size is not None:
            image_config["image_size"] = image_size
        if image_config:
            extra_body["image_config"] = image_config

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                extra_body=extra_body,
            )
        except BadRequestError as exc:
            raise BadRequestError(
                f"OpenRouter image generation request failed. "
                f"model={self.model!r}, aspect_ratio={aspect_ratio!r}, "
                f"image_size={image_size!r}, "
                f"Original error: {exc.message}",
                response=exc.response,
                body=exc.body,
            ) from exc

        message = response.choices[0].message
        images = getattr(message, "images", None)
        if images is None and hasattr(message, "model_extra"):
            images = message.model_extra.get("images")
        if images is None and isinstance(message, dict):
            images = message.get("images")
        if not images:
            raise ValueError("OpenRouter response did not contain generated images.")

        image = images[0]
        image_url = getattr(image, "image_url", None)
        if image_url is None:
            image_url = getattr(image, "imageUrl", None)
        if image_url is None and hasattr(image, "model_extra"):
            image_url = image.model_extra.get("image_url") or image.model_extra.get(
                "imageUrl"
            )
        if image_url is None and isinstance(image, dict):
            image_url = image.get("image_url") or image.get("imageUrl")

        url = getattr(image_url, "url", None)
        if url is None and hasattr(image_url, "model_extra"):
            url = image_url.model_extra.get("url")
        if url is None and isinstance(image_url, dict):
            url = image_url.get("url")
        if not url:
            raise ValueError("OpenRouter generated image did not contain a data URL.")

        return url

    @staticmethod
    def _decode_data_url(data_url: str) -> tuple[bytes, str]:
        match = _DATA_URL_RE.match(data_url)
        if not match:
            raise ValueError("OpenRouter image URL is not a base64 data URL.")

        mime_type = match.group("mime")
        image_bytes = base64.b64decode(match.group("data"))
        return image_bytes, mime_type

    @staticmethod
    def _save_image(image_bytes: bytes, mime_type: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        extension = mimetypes.guess_extension(mime_type) or ".png"
        path = output_dir / f"openrouter-image-{uuid4().hex}{extension}"
        path.write_bytes(image_bytes)
        return path

    @staticmethod
    def _to_jpeg_bytes(image_bytes: bytes) -> bytes:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.mode != "RGB":
                image = image.convert("RGB")

            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=95)
            return buffer.getvalue()
