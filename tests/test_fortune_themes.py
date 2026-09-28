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


@pytest.mark.parametrize("display", [False, True])
def test_phigros_uses_bundled_fonts_with_chinese_and_emoji_fallback(display):
    from pathlib import Path

    from shuiyuan_auto_reply.constants import settings
    from shuiyuan_auto_reply.fortune.constants import emoji_typeface
    from shuiyuan_auto_reply.fortune.phigros import _font_runs, _load_typeface

    model = FortuneModel("测试", "phigros")
    runs = _font_runs(model, "ABC运势🌟", 32, display)
    assert "".join(content for content, _ in runs) == "ABC运势🌟"
    assets = Path(settings.assets_directory) / "themes/phigros"
    phi = _load_typeface(str(assets / "phi.ttf"))
    for content, font in runs:
        face = font.getTypeface()
        assert font.getSize() == 32
        if content == "🌟":
            assert face.uniqueID() == emoji_typeface.uniqueID()
        else:
            expected = (
                "Aldrich" if display and content.isascii() else phi.getFamilyName()
            )
            assert face.getFamilyName() == expected
            assert all(face.unicharToGlyph(ord(char)) for char in content)
    # Rendering at a different size must not mutate already constructed runs.
    _font_runs(model, "ABC运势", 18, display)
    assert all(font.getSize() == 32 for _, font in runs)


def test_phigros_chinese_glyphs_use_phi_file_not_noto():
    from pathlib import Path

    from shuiyuan_auto_reply.constants import settings
    from shuiyuan_auto_reply.fortune.constants import to_do_typeface
    from shuiyuan_auto_reply.fortune.phigros import _font_runs, _load_typeface

    phi = _load_typeface(
        str(Path(settings.assets_directory) / "themes/phigros/phi.ttf")
    )
    model = FortuneModel("测试", "phigros")
    for display in (False, True):
        for _, font in _font_runs(model, "今日运势宜忌学习大吉", 32, display):
            assert font.getTypeface().uniqueID() == phi.uniqueID()
            assert font.getTypeface().uniqueID() != to_do_typeface.uniqueID()


def test_phigros_header_stays_inside_shared_slanted_outline():
    from shuiyuan_auto_reply.fortune.phigros import _panel, _panel_path

    surface = skia.Surface(180, 140)
    surface.getCanvas().clear(skia.ColorTRANSPARENT)
    _panel(surface.getCanvas(), 10, 10, 150, 100, header_color=skia.ColorCYAN)
    pixels = surface.makeImageSnapshot().toarray()
    path = _panel_path(10, 10, 150, 100)
    for y in range(10, 110):
        left = 10 + (110 - y) * 0.3
        right = 160 - (y - 10) * 0.3
        # Both the title stripe and body follow the same edge; avoid AA pixels.
        assert pixels[y, int(left) - 2, 3] == 0
        assert pixels[y, int(right) + 2, 3] == 0
        assert pixels[y, int(left) + 3, 3] > 0
        assert path.contains(left + 3, y + 0.5)
