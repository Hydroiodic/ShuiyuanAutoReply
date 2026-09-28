"""Immutable theme registry; default is the original Luogu-style fortune card."""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable

from .constants import bg_size, detail_size, to_do_size

if TYPE_CHECKING:
    from .constants import ToDoData
    from .fortune_model import FortuneModel


@dataclass(frozen=True)
class FortuneTheme:
    key: str
    name: str
    size: tuple[int, int]
    draw: Callable[["FortuneModel", str, list["ToDoData | None"]], None]


def _draw_luogu(
    model: FortuneModel, fortune: str, activities: list[ToDoData | None]
) -> None:
    model._draw_title_for_fortune(fortune)
    model._draw_one_to_do_and_not_to_do(
        fortune, activities[0], activities[2], 275.0 + to_do_size + detail_size
    )
    model._draw_one_to_do_and_not_to_do(
        fortune, activities[1], activities[3], 375.0 + to_do_size + detail_size
    )


def _draw_phigros(
    model: FortuneModel, fortune: str, activities: list[ToDoData | None]
) -> None:
    from .phigros import draw_phigros

    draw_phigros(model, fortune, activities)


THEMES = MappingProxyType(
    {
        "luogu": FortuneTheme("luogu", "洛谷", bg_size, _draw_luogu),
        "phigros": FortuneTheme("phigros", "Phigros", (1200, 760), _draw_phigros),
    }
)
_ALIASES = {"默认": "luogu", "default": "luogu", "洛谷": "luogu"}


def resolve_theme(name: str = "default") -> FortuneTheme:
    key = name.strip().casefold()
    key = _ALIASES.get(key, key)
    if key not in THEMES:
        raise ValueError(f"未知运势主题：{name}；可选：默认、洛谷、Phigros")
    return THEMES[key]


def theme_from_command(raw: str) -> FortuneTheme:
    """Only an explicit adjacent 【主题】 selects a style; ordinary text is ignored."""
    match = re.search(r"【今日运势】\s*【([^】]+)】", raw)
    return resolve_theme(match.group(1) if match else "default")
