import random
import re
import string
from typing import Optional

from ..constants import settings

_SIGNATURE_RE = re.compile(r"<div data-signature>.*?</div>", flags=re.DOTALL)


def generate_random_string(length: int) -> str:
    """
    Generate a random string of a given length.

    :param length: The length of the random string to generate.
    :return: A random string of the specified length.
    """
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def make_unique_reply(base: str) -> str:
    """
    Append a random string to the base reply to make it unique.

    :param base: The base reply string.
    :return: The unique reply string.
    """
    return (
        f"{base}\n\n"
        f"<!-- {generate_random_string(20)} -->\n"
        f"{settings.auto_reply_tag}"
    )


def remove_shuiyuan_signature(text: str) -> str:
    """
    Remove the Shuiyuan signature from the given text.

    :param text: The text from which to remove the signature.
    :return: The text without the signature.
    """
    return _SIGNATURE_RE.sub("", text).strip()


def parse_prompt_text(raw: str, prompt: str) -> Optional[str]:
    """
    Return the text after the first occurrence of the prompt in raw,
    with the prompt itself and the Shuiyuan signature removed.

    :param raw: The raw content of the post.
    :param prompt: The prompt string to look for.
    :return: The parsed text after the prompt or None if prompt not found.
    """
    # Keep any later occurrences of the same keyword intact
    first_occurrence = raw.find(prompt)
    if first_occurrence == -1:
        return None
    return remove_shuiyuan_signature(raw[first_occurrence + len(prompt) :])
