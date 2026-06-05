from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(
    size: int,
    *,
    bold: bool = False,
    regular_candidates: list[Path] | tuple[Path, ...],
    bold_candidates: list[Path] | tuple[Path, ...],
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = bold_candidates if bold else regular_candidates
    for font_path in candidates:
        try:
            if font_path.exists():
                return ImageFont.truetype(str(font_path), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    normalized = " ".join((text or "").split())
    if not normalized:
        return [""]

    def split_long_token(token: str) -> list[str]:
        if draw.textlength(token, font=font) <= max_width:
            return [token]

        chunks: list[str] = []
        current = ""
        for char in token:
            candidate = f"{current}{char}"
            if current and draw.textlength(candidate, font=font) > max_width:
                chunks.append(current)
                current = char
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks or [token]

    words = normalized.split(" ")
    lines: list[str] = []
    current = ""

    for word in words:
        fragments = split_long_token(word)
        for index, fragment in enumerate(fragments):
            prefix = " " if current and index == 0 else ""
            candidate = f"{current}{prefix}{fragment}" if current else fragment
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = fragment

    if current:
        lines.append(current)
    return lines


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    x: int,
    y: int,
    width: int,
    font: ImageFont.ImageFont,
    line_spacing: int,
    align: str = "left",
    paragraph_spacing: int = 0,
    first_line_indent: int = 0,
) -> int:
    normalized = " ".join((text or "").split())
    if not normalized:
        return y + paragraph_spacing

    if first_line_indent > 0:
        words = normalized.split(" ")
        first_line_words: list[str] = []
        while words:
            candidate_words = first_line_words + [words[0]]
            candidate = " ".join(candidate_words).strip()
            if draw.textlength(candidate, font=font) <= max(40, width - first_line_indent):
                first_line_words.append(words.pop(0))
            else:
                break

        first_line = " ".join(first_line_words).strip()
        remaining = " ".join(words).strip()
        lines = [first_line] if first_line else []
        if remaining:
            lines.extend(wrap_text(draw, remaining, font, width))
    else:
        lines = wrap_text(draw, normalized, font, width)

    bbox = draw.textbbox((0, 0), "Аг", font=font)
    line_height = (bbox[3] - bbox[1]) + line_spacing

    for index, line in enumerate(lines):
        extra_indent = first_line_indent if index == 0 and align == "left" else 0
        line_width = draw.textlength(line, font=font)
        if align == "center":
            line_x = x + max(0, (width - line_width) / 2)
        elif align == "right":
            line_x = x + max(0, width - line_width)
        else:
            line_x = x + extra_indent

        draw.text((line_x, y), line, fill="#111111", font=font)
        y += line_height

    return y + paragraph_spacing
