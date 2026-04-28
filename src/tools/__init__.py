# package tools, decide which tools to enable here

import logging
import os

import dotenv

logger = logging.getLogger(__name__)

dotenv.load_dotenv()


def _tool_enabled(name: str) -> bool:
    return os.getenv(name, "False").lower() in {"1", "true", "yes", "on"}


if _tool_enabled("IMAGE_TOOL_ENABLED"):
    try:
        from . import image_tool
    except Exception as exc:
        logger.warning("Image tool disabled: %s", exc)

if _tool_enabled("COMMAND_TOOL_ENABLED"):
    from . import command_tool
