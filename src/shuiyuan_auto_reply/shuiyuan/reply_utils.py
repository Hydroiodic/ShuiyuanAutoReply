import random

from ..constants import settings


def generate_random_string(length: int) -> str:
    """
    Generate a random string of a given length.

    :param length: The length of the random string to generate.
    :return: A random string of the specified length.
    """
    return "".join(
        random.choices(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            k=length,
        )
    )


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
