"""The community tool cards: one 270px card per tool, and a phone twin that trades width for larger type."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# The profile and COMMUNITY.md show these in rows of 270px images, and that
# width applies to the desktop source and the phone fallback alike. So the
# phone twin is the same 270px card with larger text, drawn by the same
# function, and not a 320px mobile_cards.Card that the row would scale down.
from __future__ import annotations

from typing import NamedTuple

import kit

WIDTH = 270
PAD = 18
INNER = WIDTH - 2 * PAD
MIN_HEIGHT = 220
STAR_FLOOR = 10  # a card shows its star count only from this many stars
TECH_SHOWN = 3  # at most this many tech chips; fewer when the row is full
CHIP_PAD, CHIP_GAP = 8, 6
TITLE_TOP, TITLE_PITCH = 40, 22  # the first title baseline and the step to the next
# The star, 20 wide and 19 tall, drawn from its top point.
STAR = "l3.1 6.3 6.9 1 -5 4.9 1.2 6.9 -6.2 -3.3 -6.2 3.3 1.2 -6.9 -5 -4.9 6.9 -1z"
STAR_WIDTH, STAR_HEIGHT, STAR_DRAWN = 20, 19, 11


class Layout(NamedTuple):
    """Type sizes of one layout; a line holds title_chars or body_chars characters."""

    title_size: float
    title_chars: int
    body_size: float
    body_chars: int
    leading: float
    chip_size: float
    chip_height: float
    row: int  # cards side by side at most, so each run of this many shares one height


# Three 270px cards fill the desktop column. The phone file is also what a
# 768 to 1011px window gets, where the README column is 383 to 626px: two a row.
DESKTOP = Layout(16, 27, 13, 33, 18, kit.MICRO, 20, 3)
PHONE = Layout(18, 24, 15, 28, 21, kit.MICRO_PHONE, 22, 2)


def wrap(text: str, chars: int, size: float) -> list[str]:
    """Wrap to a character count, and never leave one short word alone on the last line.

    A token wider than the card's inner width breaks the way kit.wrap_text breaks it,
    after a "/", "-", "_" or "." where it can, so a repo slug cannot run past the edge.
    """
    lines, current = [], ""
    for word in str(text).split():
        if kit.text_width(word, size) > INNER:
            if current:
                lines.append(current)
            *whole, current = kit.wrap_text(word, INNER, size)
            lines += whole
        elif current and len(current) + 1 + len(word) > chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    if len(lines) > 1 and " " not in lines[-1] and " " in lines[-2]:
        head, moved = lines[-2].rsplit(" ", 1)
        if len(moved) + 1 + len(lines[-1]) <= chars:
            lines[-2:] = [head, f"{moved} {lines[-1]}"]
    return lines


def shows_stars(tool: dict) -> bool:
    return (tool.get("stars") or 0) >= STAR_FLOOR


def npm_label(tool: dict) -> str:
    """The monthly downloads as an exact count, so the chip never rounds past the live figure."""
    monthly = tool.get("npm_monthly")
    return f"{monthly:,}/MO NPM" if monthly else ""


def has_traction(tool: dict) -> bool:
    return shows_stars(tool) or bool(npm_label(tool))


def label(tool: dict) -> str:
    """The card as alt text: what the tool is, what it is built with, and its traction."""
    out = f"{tool['title']}: {tool['summary']}"
    if tech := tool["tech"][:TECH_SHOWN]:
        out += f" Built with {', '.join(tech)}."
    if shows_stars(tool):
        out += f" {tool['stars']:,} stars."
    if tool.get("npm_monthly"):
        out += f" {tool['npm_monthly']:,} npm downloads a month."
    return out


def _pill_width(text: str, layout: Layout) -> float:
    return kit.chip_width(text, layout.chip_size, CHIP_PAD)


def _pill(x: float, y: float, text: str, color: str, layout: Layout) -> str:
    """A chip in its own colour: a faint fill of it and a soft outline."""
    return kit.chip(
        x,
        y,
        text,
        color,
        layout.chip_size,
        layout.chip_height,
        CHIP_PAD,
        f"{color}14",
        f"{color}55",
    )[0]


def _star_pill(x: float, y: float, stars: int, layout: Layout) -> tuple[str, float]:
    """The star count as a chip: the star, then the number. Returns (svg, width)."""
    count = f"{stars:,}"
    height, scale = layout.chip_height, STAR_DRAWN / STAR_WIDTH
    text_x = x + CHIP_PAD + STAR_DRAWN + 5
    width = (
        text_x
        - x
        + kit.text_width(count, layout.chip_size, True, kit.TRACK)
        - kit.TRACK
        + CHIP_PAD
    )
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{width:.1f}" height="{height:g}" rx="{height / 2:g}" '
        f'fill="{kit.SKY}14" stroke="{kit.SKY}55"/>'
        f'<path d="M0 0{STAR}" fill="{kit.SKY}" transform="translate({x + CHIP_PAD + STAR_DRAWN / 2:g} '
        f'{y + (height - STAR_HEIGHT * scale) / 2:.2f}) scale({scale:g})"/>'
        + kit.text(
            text_x,
            y + height / 2 + layout.chip_size * 0.36,
            count,
            layout.chip_size,
            kit.SKY,
            "m",
        ),
        width,
    )


def traction(tool: dict, x: float, y: float, layout: Layout) -> str:
    """The star chip and the npm chip, left to right; a chip that is not drawn takes no room."""
    out = []
    if shows_stars(tool):
        svg, width = _star_pill(x, y, tool["stars"], layout)
        out.append(svg)
        x += width + CHIP_GAP
    if text := npm_label(tool):
        out.append(_pill(x, y, text, kit.SKY, layout))
    return "".join(out)


def tech_shown(tool: dict, layout: Layout) -> list[str]:
    """The leading tech names that fit the card's inner width as one row of chips.

    The row has the whole width on every card: the star is a chip under the summary,
    so no room is held back beside these for a star that may not be drawn.
    """
    shown, used = [], 0.0
    for name in tool["tech"][:TECH_SHOWN]:
        width = _pill_width(name, layout)
        if used + width > INNER:
            break
        shown.append(name)
        used += width + CHIP_GAP
    return shown


def _lines(tool: dict, layout: Layout) -> tuple[list[str], list[str], float]:
    """The wrapped title, the wrapped summary and the summary's first baseline."""
    titles = wrap(tool["title"], layout.title_chars, layout.title_size)
    body_y = TITLE_TOP + 4 + TITLE_PITCH * len(titles)
    return titles, wrap(tool["summary"], layout.body_chars, layout.body_size), body_y


def last_baseline(tool: dict, layout: Layout) -> float:
    """The baseline of the card's last summary line, which the traction row sits under."""
    _, lines, body_y = _lines(tool, layout)
    return body_y + (len(lines) - 1) * layout.leading


def needed_height(tool: dict, layout: Layout) -> int:
    """The height this card needs on its own; a row then takes the tallest of its cards."""
    _, lines, body_y = _lines(tool, layout)
    below = body_y + len(lines) * layout.leading  # where one more line would sit
    chips = layout.chip_height + 12  # the tech row and the margin under it
    if has_traction(tool):
        last = below - layout.leading
        return int(max(MIN_HEIGHT, last + 14 + layout.chip_height + 10 + chips))
    return int(max(MIN_HEIGHT, below + 12 + chips))


def draw(
    tool: dict, index: int, layout: Layout, height: int, last: float | None = None
) -> str:
    """One tool card at the given height: title, summary, traction chips, then the tech row.

    last is the baseline the traction row hangs under; a row of cards passes the
    lowest one so the chips of every card in it sit at one height.
    """
    titles, lines, body_y = _lines(tool, layout)
    if last is None:
        last = last_baseline(tool, layout)
    tech_y = height - 12 - layout.chip_height
    parts = [
        kit.svg_open(WIDTH, height, label(tool)),
        kit.style(),
        kit.frame(WIDTH, height, fill=kit.CARD),
        f'<rect x="0" y="20" width="3" height="24" rx="1.5" fill="{kit.SKY}">'
        + kit.loop("opacity", "1;0.4;1", "0;0.5;1", 3, index * 0.25)
        + "</rect>",
    ]
    parts += [
        kit.text(
            PAD, TITLE_TOP + TITLE_PITCH * j, title, layout.title_size, kit.INK, "t"
        )
        for j, title in enumerate(titles)
    ]
    parts += [
        kit.text(
            PAD, body_y + j * layout.leading, line, layout.body_size, kit.BODY, "b"
        )
        for j, line in enumerate(lines)
    ]
    if has_traction(tool):
        parts.append(traction(tool, PAD, last + 14, layout))
    x = float(PAD)
    for name in tech_shown(tool, layout):
        parts.append(_pill(x, tech_y, name, kit.BLUE_LIGHT, layout))
        x += _pill_width(name, layout) + CHIP_GAP
    parts.append(kit.SVG_CLOSE)
    return "".join(parts)


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for every tool card, desktop and -mobile.

    Both pages lay the cards out in ctx["tools"] order from the first one (the
    profile shows the leading top tools, COMMUNITY.md all of them), so the rows
    are runs of that list and every card in a run is drawn at the tallest height.
    """
    tools = ctx["tools"]
    files = {}
    for layout, suffix in ((DESKTOP, ""), (PHONE, "-mobile")):
        heights = [needed_height(tool, layout) for tool in tools]
        for index, tool in enumerate(tools):
            start = index - index % layout.row
            run = slice(start, start + layout.row)
            last = max(
                (last_baseline(t, layout) for t in tools[run] if has_traction(t)),
                default=None,
            )
            files[f"tool-{tool['slug']}{suffix}.svg"] = draw(
                tool, index, layout, max(heights[run]), last
            )
    return files
