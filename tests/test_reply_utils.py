import string

from shuiyuan_auto_reply.constants import settings
from shuiyuan_auto_reply.shuiyuan.reply_utils import (
    generate_random_string,
    make_unique_reply,
    parse_prompt_text,
    remove_shuiyuan_signature,
)
from shuiyuan_auto_reply.shuiyuan.shuiyuan_model import ShuiyuanModel


def test_generate_random_string():
    value = generate_random_string(32)
    assert len(value) == 32
    assert set(value) <= set(string.ascii_letters + string.digits)


def test_make_unique_reply_is_tagged_and_unique():
    first = make_unique_reply("hello")
    second = make_unique_reply("hello")
    assert first.startswith("hello\n\n<!-- ")
    assert first.endswith(settings.auto_reply_tag)
    assert first != second


def test_remove_shuiyuan_signature():
    text = "正文\n<div data-signature>\n签名\n</div>\n"
    assert remove_shuiyuan_signature(text) == "正文"
    assert ShuiyuanModel.remove_shuiyuan_signature(text) == "正文"


def test_parse_prompt_text():
    raw = "前缀【记录语录】alice\n内容【记录语录】保留<div data-signature>签名</div>"
    assert parse_prompt_text(raw, "【记录语录】") == "alice\n内容【记录语录】保留"
    assert parse_prompt_text(raw, "【删除语录】") is None
