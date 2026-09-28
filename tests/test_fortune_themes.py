import asyncio
import random
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import skia

from shuiyuan_auto_reply.fortune.fortune_model import FortuneModel
from shuiyuan_auto_reply.fortune.themes import THEMES, resolve_theme, theme_from_command


@pytest.mark.parametrize("name", ["default", "默认", "洛谷", "luogu", " LUOGU "])
def test_default_aliases(name):
    assert resolve_theme(name) is THEMES["luogu"]


def test_explicit_selection_only():
    assert theme_from_command("【今日运势】【pHiGrOs】").key == "phigros"
    assert theme_from_command("【今日运势】今天玩Phigros").key == "luogu"
    with pytest.raises(ValueError, match="未知运势主题"):
        theme_from_command("【今日运势】【不存在】")
    with pytest.raises(TypeError):
        THEMES["new"] = THEMES["luogu"]


@pytest.mark.parametrize("theme", ["default", "洛谷", "Phigros"])
@pytest.mark.parametrize("fortune", ["大吉", "小吉", "大凶"])
def test_render_theme_extremes_and_long_emoji_name(theme, fortune, monkeypatch):
    monkeypatch.setattr(
        "shuiyuan_auto_reply.fortune.fortune_model.random.choice", lambda _: fortune
    )
    model = FortuneModel("很长的中文用户名🌟" * 8, theme)
    image = model.generate_fortune()
    assert (image.width(), image.height()) == model.theme.size
    encoded = image.encodeToData(skia.EncodedImageFormat.kJPEG, 90)
    assert encoded is not None and len(bytes(encoded)) > 1000


def test_theme_does_not_change_random_choices():
    random.seed(42)
    FortuneModel("alice", "default").generate_fortune()
    after_default = random.getstate()
    random.seed(42)
    FortuneModel("alice", "Phigros").generate_fortune()
    assert random.getstate() == after_default


def test_repeated_render_clears_surface():
    model = FortuneModel("alice", "Phigros")
    random.seed(10)
    first = bytes(model.generate_fortune().encodeToData())
    random.seed(10)
    second = bytes(model.generate_fortune().encodeToData())
    assert first == second


def test_handler_uploads_selected_theme(monkeypatch):
    from examples.models.tarot_model.tarot_topic_model import TarotTopicModel

    captured = []
    real = FortuneModel

    def build(username, theme):
        captured.append(theme.key)
        return real(username, theme)

    monkeypatch.setattr(
        "examples.models.tarot_model.tarot_topic_model.FortuneModel", build
    )
    handler = object.__new__(TarotTopicModel)
    handler.model = SimpleNamespace(
        try_upload_image=AsyncMock(
            return_value=SimpleNamespace(data="![img](upload://image.jpg)")
        )
    )
    result = asyncio.run(
        handler._fortune_condition(
            "【今日运势】【Phigros】", SimpleNamespace(display_name="测试用户")
        )
    )
    assert captured == ["phigros"]
    assert "upload://image.jpg" in result
    handler.model.try_upload_image.assert_awaited_once()
