import random
from typing import Iterator, List, Literal, Optional, Tuple

import skia

from .constants import (
    ToDoData,
    bg_size,
    detail_font,
    detail_size,
    emoji_font,
    emoji_pattern,
    fortune_font,
    fortune_list,
    fortune_size,
    lucky,
    title_font,
    title_size,
    to_do_font,
    to_do_font_bold,
    to_do_list,
    to_do_size,
    too_lucky,
    too_lucky_not_to_do,
    too_unlucky,
    too_unlucky_to_do,
)


class FortuneModel:

    def __init__(self, username: str):
        # Create the Skia surface (equivalent to PIL Image)
        self.surface = skia.Surface(bg_size[0], bg_size[1])
        self.canvas = self.surface.getCanvas()
        self.username = username

        # Create Skia paint objects
        self.white_paint = skia.Paint(Color=skia.ColorWHITE)
        self.red_paint = skia.Paint(Color=skia.ColorRED)
        self.black_paint = skia.Paint(Color=skia.ColorBLACK)
        self.gray_paint = skia.Paint(Color=skia.ColorSetRGB(0x7F, 0x7F, 0x7F))
        self.dark_gray_paint = skia.Paint(Color=skia.ColorSetRGB(0x3F, 0x3F, 0x3F))

        # Fill background with white
        self.canvas.drawRect(skia.Rect.MakeWH(bg_size[0], bg_size[1]), self.white_paint)

    @staticmethod
    def _sample_to_do(fortune: str) -> List[Optional[ToDoData]]:
        # [to_do, to_do, not_to_do, not_to_do]

        # If fortune is too unlucky, return a default to-do
        if fortune in too_unlucky:
            result = [too_unlucky_to_do, None]
            result.extend(random.sample(to_do_list, 2))
            return result
        # If fortune is too lucky, return a default not-to-do
        elif fortune in too_lucky:
            result = random.sample(to_do_list, 2)
            result.extend([too_lucky_not_to_do, None])
            return result

        return random.sample(to_do_list, 4)

    @staticmethod
    def _calculate_to_do_width(to_do: ToDoData, is_true: bool) -> Tuple[float, float]:
        # Calculate the width of the to-do text and its detail
        detail_text = to_do.detail_true if is_true else to_do.detail_false
        to_do_text = to_do.to_do
        if (
            to_do.to_do != too_unlucky_to_do.to_do
            and to_do.to_do != too_lucky_not_to_do.to_do
        ):
            to_do_text = " " * 6 + to_do_text

        # Get text bounds in Skia
        return to_do_font.measureText(to_do_text), detail_font.measureText(detail_text)

    def _draw_to_do(
        self,
        fortune: str,
        to_do: Optional[ToDoData],
        is_true: bool,
        center_x: float,
        begin_pos_y: float,
    ) -> None:
        # Nothing to draw in this cell
        if to_do is None:
            return

        # "宜" is drawn in red on the left, "忌" in black on the right. For the
        # extreme fortunes the whole cell reads "诸事不宜" or "诸事皆宜" instead.
        if is_true:
            is_extreme = fortune in too_unlucky
            label = "诸事不宜" if is_extreme else "宜:"
            detail = to_do.detail_true
            paint = self.red_paint
        else:
            is_extreme = fortune in too_lucky
            label = "诸事皆宜" if is_extreme else "忌:"
            detail = to_do.detail_false
            paint = self.black_paint

        to_do_w, detail_w = self._calculate_to_do_width(to_do, is_true)
        x = center_x - to_do_w / 2

        # Draw the label and the detail text
        self.canvas.drawString(label, x, begin_pos_y, to_do_font_bold, paint)
        self.canvas.drawString(
            detail,
            center_x - detail_w / 2,
            begin_pos_y + 40,
            detail_font,
            self.gray_paint,
        )

        # Draw the to-do itself right after the label
        if not is_extreme:
            self.canvas.drawString(
                " " * 6 + to_do.to_do, x, begin_pos_y, to_do_font, paint
            )

    def _draw_one_to_do_and_not_to_do(
        self,
        fortune: str,
        to_do: Optional[ToDoData],
        not_to_do: Optional[ToDoData],
        begin_pos_y: float,
    ) -> None:
        self._draw_to_do(fortune, to_do, True, bg_size[0] / 4, begin_pos_y)
        self._draw_to_do(fortune, not_to_do, False, bg_size[0] / 4 * 3, begin_pos_y)

    def _draw_title_for_fortune(self, fortune: str):
        # Prepare text for the title
        title = self.username + "的运势"
        fortune_text = "§ " + fortune + " §"

        # Layout arrangement
        title_width = FortuneModel._get_emoji_text_width(title, title_font, emoji_font)
        fortune_width = fortune_font.measureText(fortune_text)

        # Draw the title using Skia
        self._draw_emoji_text(
            (bg_size[0] / 2 - title_width / 2, 50.0 + title_size),
            title,
            title_font,
            emoji_font,
        )

        # Choose color based on fortune type
        fortune_color = self.red_paint if fortune in lucky else self.dark_gray_paint
        self.canvas.drawString(
            fortune_text,
            bg_size[0] / 2 - fortune_width / 2,
            125.0 + fortune_size,
            fortune_font,
            fortune_color,
        )

    @staticmethod
    def _split_text_by_emoji(text: str) -> List[Tuple[Literal["text", "emoji"], str]]:
        parts: List[Tuple[Literal["text", "emoji"], str]] = []
        last_end = 0

        # Iterate through all matches of the emoji pattern
        for match in emoji_pattern.finditer(text):
            if match.start() > last_end:
                parts.append(("text", text[last_end : match.start()]))
            parts.append(("emoji", match.group()))
            last_end = match.end()

        # The last part of the text after the last emoji
        if last_end < len(text):
            parts.append(("text", text[last_end:]))

        return parts

    @staticmethod
    def _iter_font_runs(
        text: str,
        primary_font: skia.Font,
        emoji_font: skia.Font,
    ) -> Iterator[Tuple[str, skia.Font]]:
        # Emojis are rendered with the emoji font, everything else with the primary font
        for part_type, content in FortuneModel._split_text_by_emoji(text):
            if content:
                yield content, emoji_font if part_type == "emoji" else primary_font

    @staticmethod
    def _get_emoji_text_width(
        text: str,
        primary_font: skia.Font,
        emoji_font: skia.Font,
    ) -> float:
        # Calculate the width of mixed text with emojis
        return sum(
            font.measureText(content)
            for content, font in FortuneModel._iter_font_runs(
                text, primary_font, emoji_font
            )
        )

    def _draw_emoji_text(
        self,
        xy: Tuple[float, float],
        text: str,
        primary_font: skia.Font,
        emoji_font: skia.Font,
    ) -> None:
        # Draw each run with its own font, advancing x by the run's width
        x, y = xy
        for content, font in self._iter_font_runs(text, primary_font, emoji_font):
            self.canvas.drawString(content, x, y, font, self.black_paint)
            x += font.measureText(content)

    def generate_fortune(self) -> skia.Image:
        # Generate a random fortune
        fortune = random.choice(fortune_list)
        to_do_and_not_to_do = self._sample_to_do(fortune)

        # Draw the title and fortune text
        self._draw_title_for_fortune(fortune)

        # ToDos and their details
        self._draw_one_to_do_and_not_to_do(
            fortune,
            to_do_and_not_to_do[0],
            to_do_and_not_to_do[2],
            275.0 + to_do_size + detail_size,
        )
        self._draw_one_to_do_and_not_to_do(
            fortune,
            to_do_and_not_to_do[1],
            to_do_and_not_to_do[3],
            375.0 + to_do_size + detail_size,
        )

        # Return the Skia image
        return self.surface.makeImageSnapshot()
