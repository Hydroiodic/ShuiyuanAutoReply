"""Skia adaptation of phi-plugin's default palette and slanted glass panels.

Sources: resources/html/common/common.css and resources/html/sign/sign.css
in Hydroiodic/phi-plugin-openclaw. No runtime dependency on that checkout.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import skia

from ..constants import settings
from .constants import ToDoData, emoji_typeface, lucky, to_do_typeface

if TYPE_CHECKING:
    from .fortune_model import FortuneModel

CYAN = 0xFF00B0F0
GOLD = 0xFFFFF700
TEXT = 0xFFEDF6FF
MUTED = 0xFFA8DEFF
PINK = 0xFFFFB6C1
PANEL = 0xD9041428
SLOPE = 0.3


def _panel(
    canvas: skia.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    color: int = PANEL,
) -> None:
    cut = min(height * SLOPE, 46)
    path = skia.Path()
    path.moveTo(x + cut, y)
    path.lineTo(x + width, y)
    path.lineTo(x + width - cut, y + height)
    path.lineTo(x, y + height)
    path.close()
    canvas.drawPath(path, skia.Paint(Color=color, AntiAlias=True))


@lru_cache(maxsize=4)
def _load_typeface(path: str) -> skia.Typeface:
    face = skia.Typeface.MakeFromFile(path)
    if face is None:
        raise RuntimeError(f"Unable to load Phigros theme font: {path}")
    return face


def _font_runs(
    model: FortuneModel, value: str, size: float, display: bool = False
) -> list[tuple[str, skia.Font]]:
    """Match the plugin's PHI body and Aldrich/PHI display font stacks."""
    assets = Path(settings.assets_directory) / "themes/phigros"
    phi = _load_typeface(str(assets / "phi.ttf"))
    faces = [phi, to_do_typeface]
    if display:
        faces.insert(0, _load_typeface(str(assets / "Aldrich-Regular.ttf")))
    fonts = [skia.Font(face, size) for face in faces]
    emoji = skia.Font(emoji_typeface, size)
    runs: list[tuple[str, skia.Font]] = []
    for kind, content in model._split_text_by_emoji(value):
        if kind == "emoji":
            runs.append((content, emoji))
            continue
        for char in content:
            index = next(
                (i for i, face in enumerate(faces) if face.unicharToGlyph(ord(char))),
                len(faces) - 1,
            )
            font = fonts[index]
            if runs and runs[-1][1] is font:
                runs[-1] = (runs[-1][0] + char, font)
            else:
                runs.append((char, font))
    return runs


def _text(
    model: FortuneModel,
    value: str,
    x: float,
    y: float,
    size: float,
    width: float,
    color: int = TEXT,
    display: bool = False,
) -> None:
    """Fit and draw using identical per-glyph font fallback and emoji runs."""
    current_size = size

    def measure(value: str) -> float:
        return sum(
            font.measureText(content)
            for content, font in _font_runs(model, value, current_size, display)
        )

    while measure(value) > width and current_size > size * 0.72:
        current_size = max(size * 0.72, current_size - 1)
    if measure(value) > width:
        while value and measure(value + "…") > width:
            value = value[:-1]
        value += "…"
    paint = skia.Paint(Color=color, AntiAlias=True)
    for content, run_font in _font_runs(model, value, current_size, display):
        model.canvas.drawString(content, x, y, run_font, paint)
        x += run_font.measureText(content)


@lru_cache(maxsize=2)
def _load_background(path: str) -> skia.Image:
    image = skia.Image.open(path)
    if image is None:
        raise RuntimeError(f"Unable to decode Phigros theme background: {path}")
    return image


def draw_phigros(
    model: FortuneModel, fortune: str, activities: list[ToDoData | None]
) -> None:
    canvas = model.canvas
    canvas.clear(0xFF081423)
    background = _load_background(
        str(Path(settings.assets_directory) / "themes/phigros/background.png")
    )
    canvas.drawImageRect(background, skia.Rect.MakeWH(1200, 760))
    canvas.drawRect(skia.Rect.MakeWH(1200, 760), skia.Paint(Color=0xB0081423))
    for index, color in enumerate((0xFF92D050, CYAN, 0xFFFF0000, 0xFF6E6E6E)):
        _panel(canvas, 42 + index * 16, 53, 13, 654, color)
    _panel(canvas, 137, 45, 1015, 80)
    _text(model, model.username + "的运势", 171, 97, 32, 650)
    _text(model, "PHIGROS", 945, 95, 23, 170, CYAN, True)
    _panel(canvas, 137, 145, 1015, 195)
    _panel(canvas, 137, 145, 1015, 5, CYAN)
    _text(model, "TODAY / 今日运势", 179, 187, 21, 350, MUTED, True)
    _text(model, fortune, 185, 299, 92, 530, GOLD if fortune in lucky else PINK, True)
    _text(model, "DAILY FORTUNE", 819, 241, 21, 270, MUTED, True)
    _text(model, "把握当下 · 自由选择", 810, 283, 22, 290)
    for side, heading, accent in ((0, "宜 / GOOD", CYAN), (1, "忌 / AVOID", PINK)):
        x = 137 + side * 520
        _panel(canvas, x, 360, 495, 310)
        _panel(canvas, x, 360, 495, 49, 0xB000B0F0 if side == 0 else 0x994D375D)
        _text(model, heading, x + 35, 394, 25, 395, TEXT, True)
        for row in range(2):
            activity = activities[side * 2 + row]
            if activity is None:
                continue
            y = 459 + row * 116
            _text(model, activity.to_do, x + 35, y, 29, 389, accent)
            detail = activity.detail_true if side == 0 else activity.detail_false
            _text(model, detail, x + 35, y + 40, 22, 389, MUTED)
    _text(model, "SHUIYUAN  /  仅供娱乐参考", 171, 716, 19, 640, MUTED)
