import re
import random
import skia
from typing import List, Literal, Optional
from .constants import *


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
    def _calculate_to_do_width(
        to_do: Optional[ToDoData],
        is_true: bool,
        to_do_font: skia.Font,
        detail_font: skia.Font,
    ) -> tuple[float, float]:
        # If to_do is None, return 0 width
        if to_do is None:
            return 0.0, 0.0

        # Else, calculate the width of the to-do text
        detail_text = to_do.detail_true if is_true else to_do.detail_false
        to_do_text = to_do.to_do
        if (
            to_do.to_do != too_unlucky_to_do.to_do
            and to_do.to_do != too_lucky_not_to_do.to_do
        ):
            to_do_text = " " * 6 + to_do_text

        # Get text bounds in Skia
        to_do_bounds = to_do_font.measureText(to_do_text)
        detail_bounds = detail_font.measureText(detail_text)

        return to_do_bounds, detail_bounds

    def _draw_one_to_do_and_not_to_do(
        self,
        fortune: str,
        to_do: Optional[ToDoData],
        not_to_do: Optional[ToDoData],
        begin_pos_y: float,
        to_do_font: skia.Font,
        to_do_font_bold: skia.Font,
        detail_font: skia.Font,
    ):
        # Calculate text width for to_do and not_to_do
        ttd_w, ttd_det_w = FortuneModel._calculate_to_do_width(
            to_do, True, to_do_font, detail_font
        )
        tntd_w, tntd_det_w = FortuneModel._calculate_to_do_width(
            not_to_do, False, to_do_font, detail_font
        )

        if to_do is not None:
            # Draw "诸事不宜" or "宜:"
            self.canvas.drawString(
                "诸事不宜" if fortune in too_unlucky else "宜:",
                bg_size[0] / 4 - ttd_w / 2,
                begin_pos_y,
                to_do_font_bold,
                self.red_paint,
            )

            # Draw detail text
            self.canvas.drawString(
                to_do.detail_true,
                bg_size[0] / 4 - ttd_det_w / 2,
                begin_pos_y + 40,
                detail_font,
                self.gray_paint,
            )

            if fortune not in too_unlucky:
                self.canvas.drawString(
                    " " * 6 + to_do.to_do,
                    bg_size[0] / 4 - ttd_w / 2,
                    begin_pos_y,
                    to_do_font,
                    self.red_paint,
                )

        if not_to_do is not None:
            # Draw "诸事皆宜" or "忌:"
            self.canvas.drawString(
                "诸事皆宜" if fortune in too_lucky else "忌:",
                bg_size[0] / 4 * 3 - tntd_w / 2,
                begin_pos_y,
                to_do_font_bold,
                self.black_paint,
            )

            # Draw detail text
            self.canvas.drawString(
                not_to_do.detail_false,
                bg_size[0] / 4 * 3 - tntd_det_w / 2,
                begin_pos_y + 40,
                detail_font,
                self.gray_paint,
            )

            if fortune not in too_lucky:
                self.canvas.drawString(
                    " " * 6 + not_to_do.to_do,
                    bg_size[0] / 4 * 3 - tntd_w / 2,
                    begin_pos_y,
                    to_do_font,
                    self.black_paint,
                )

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
    def _split_text_by_emoji(text: str) -> List[tuple[Literal["text", "emoji"], str]]:
        # Find all emojis in the text
        emoji_pattern = re.compile(emoji_format, flags=re.UNICODE)

        parts: List[tuple[Literal["text", "emoji"], str]] = []
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
    def _get_emoji_text_width(
        text: str,
        primary_font: skia.Font,
        emoji_font: skia.Font,
    ) -> float:
        # Calculate the width of mixed text with emojis
        total_width = 0
        parts = FortuneModel._split_text_by_emoji(text)

        # Iterate through each part of the text
        for part_type, content in parts:
            # Skip empty content
            if not content:
                continue

            # If part is emoji, use emoji font; otherwise, use primary font
            if part_type == "emoji":
                total_width += emoji_font.measureText(content)
            elif part_type == "text":
                total_width += primary_font.measureText(content)
            else:
                raise ValueError(f"Unknown part type: {part_type}")

        return total_width

    def _draw_emoji_text(
        self,
        xy: tuple[float, float],
        text: str,
        primary_font: skia.Font,
        emoji_font: skia.Font,
    ) -> None:
        # Parse the location of the text
        x, y = xy

        # Split the text into parts (text and emojis)
        parts = FortuneModel._split_text_by_emoji(text)
        for part_type, content in parts:
            # Skip empty content
            if not content:
                continue

            # If part is emoji, draw it with the emoji font; otherwise, draw text with the primary font
            if part_type == "emoji":
                self.canvas.drawString(
                    content,
                    x,
                    y,
                    emoji_font,
                    self.black_paint,
                )
                x += emoji_font.measureText(content)
            elif part_type == "text":
                self.canvas.drawString(
                    content,
                    x,
                    y,
                    primary_font,
                    self.black_paint,
                )
                x += primary_font.measureText(content)
            else:
                raise ValueError(f"Unknown part type: {part_type}")

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
            to_do_font,
            to_do_font_bold,
            detail_font,
        )
        self._draw_one_to_do_and_not_to_do(
            fortune,
            to_do_and_not_to_do[1],
            to_do_and_not_to_do[3],
            375.0 + to_do_size + detail_size,
            to_do_font,
            to_do_font_bold,
            detail_font,
        )

        # Return the Skia image
        return self.surface.makeImageSnapshot()
