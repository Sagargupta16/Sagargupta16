"""The cards' shared design system: palette, type, the page clock and the helpers both layouts draw with."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# Every card module in scripts/cards/ and the phone engine in mobile_cards.py
# draw with these, so one fact has one colour, one type scale and one clock on
# every card and at both widths. Nothing here reads files or the network.
from __future__ import annotations

import math
import re
import unicodedata
from html import escape

# ---------------------------------------------------------------- palette
# Matches the portfolio: warm near-black, one blue family, green only for
# live or ok, amber only for LeetCode and work waiting on review.
BG = "#0b1012"  # every card's surface
CARD = "#0f171c"  # panels and tiles inside a card
RAISED = "#131d24"  # a selected or lifted tile
BLUE = "#2563eb"  # fills, rails, the primary button
BLUE_EDGE = "#3b82f6"  # outlines on a blue tint (4.3:1 and up)
BLUE_LIGHT = "#60a5fa"  # labels, links, the moving highlight
SKY = "#38bdf8"  # packets and second-level accents
BLUE_EITHER = "#4696f9"  # for files shown on both GitHub themes with no background
BLUE_TINT = "rgba(37,99,235,0.14)"  # the fill behind an emphasised tile
GREEN = "#22c55e"
AMBER = "#f59e0b"
INK = "#f3f4f6"  # titles and values
BODY = "rgba(255,255,255,0.78)"  # sentences
META = "rgba(255,255,255,0.62)"  # captions; 4.5:1 and up on BG and CARD
HAIR = "rgba(255,255,255,0.09)"  # a card's border
HAIR_STRONG = "rgba(255,255,255,0.14)"  # a tile's border, tracks, rails at rest
HAIR_FILL = "rgba(255,255,255,0.03)"
# A panel inside a CARD tile: over CARD it lands on BG. It is a tint, not a
# solid, because the panel's edge is its hairline, not its fill.
WELL = "rgba(5,8,10,0.49)"

# ---------------------------------------------------------------- type
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
SANS = "'Segoe UI',Inter,-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"
MICRO = (
    10.5  # the smallest desktop label: 10px once an 840px card fills the README column
)
MICRO_PHONE = 11.5  # the smallest label on a 320px card
TRACK = 1.2  # letter-spacing of a mono micro-label; kickers use 2
RADIUS = 14

# ---------------------------------------------------------------- clock
# One page clock. Every loop lasts 2, 3, 4, 6, 12 or 24 s, so cards that sit
# next to each other realign and nothing drifts. Entrances run once and are
# over within about 1.6 s; a card's loop starts after its entrance.
T = 12.0
ENTER = 0.4
STAGGER = 0.08
EASE = "0.16 1 0.3 1"  # ease-out for entrances; loops that travel stay linear
SVG_CLOSE = "</svg>"

esc = escape


# ---------------------------------------------------------------- text metrics
def _advance(character: str) -> float:
    if unicodedata.combining(character):
        return 0
    if unicodedata.east_asian_width(character) in {"W", "F"}:
        return 1.05
    if character in "W@%M":
        return 1
    if character in "ilI.,:;'!|`":
        return 0.34
    if character in " fjrt()[]":
        return 0.44
    return 0.7 if character.isupper() else 0.58


def text_width(
    text: str, size: float = 15, mono: bool = False, tracking: float = 1
) -> float:
    """Measure text conservatively: sans glyph advances, or monospace plus its tracking."""
    if mono:
        return len(text) * (size * 0.6 + tracking)
    return sum(_advance(character) for character in text) * size


def wrap_text(
    text: str, width: float, size: float = 15, mono: bool = False, tracking: float = 1
) -> list[str]:
    """Wrap words to a pixel width, splitting long tokens without dropping any content."""
    lines, current = [], ""
    for word in str(text).split():
        candidate = f"{current} {word}" if current else word
        if text_width(candidate, size, mono, tracking) <= width:
            current = candidate
            continue
        if current:
            # A token wider than the line splits anyway, so it starts on this
            # line. So does one that would nearly fill the next line and has a
            # "/", "-", "_" or "." to break at, when the words before it would
            # otherwise sit alone on a short line.
            token = text_width(word, size, mono, tracking)
            short_line = text_width(current, size, mono, tracking) < width / 2
            breakable = token > width * 0.75 and re.search("[/_.-].", word)
            if token > width or (short_line and breakable):
                current += " "
            else:
                lines.append(current)
                current = ""
        # a token too long for a line breaks after "/", "-", "_" or "." first,
        # and only splits between letters where no separator fits
        for piece in re.findall(r"[^/\-_.]+[/\-_.]*|[/\-_.]+", word):
            if (
                current.strip()
                and text_width(current + piece, size, mono, tracking) > width
            ):
                lines.append(current.rstrip())
                current = ""
            for character in piece:
                if (
                    current.strip()
                    and text_width(current + character, size, mono, tracking) > width
                ):
                    lines.append(current.rstrip())
                    current = ""
                current += character
    if current:
        lines.append(current)
    return lines


def balance(lines: list[str]) -> list[str]:
    """Move one word down when the last line would hold a single short word."""
    if len(lines) < 2 or " " in lines[-1] or len(lines[-1]) > 12:
        return lines
    head = lines[-2].rsplit(" ", 1)
    if len(head) < 2:
        return lines
    return [*lines[:-2], head[0], f"{head[1]} {lines[-1]}"]


def compact(number: float) -> str:
    """Shorten a count, rounding down so a card never claims more than there is: 941, 1.2K, 24K, 1.3M."""
    for limit, unit in ((1_000_000, "M"), (1_000, "K")):
        if number >= limit:
            if number >= limit * 10:
                return f"{int(number // limit)}{unit}"
            tenths = int(number * 10 // limit)
            return f"{tenths // 10}.{tenths % 10}".removesuffix(".0") + unit
    return f"{int(number):,}"


# ---------------------------------------------------------------- chrome
def svg_open(w: float, h: float, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" viewBox="0 0 {w:g} {h:g}" '
        f'role="img" aria-label="{escape(label)}">'
    )


def style(extra: str = "") -> str:
    """The shared text classes. Sizes and fills are set on each element.

    k kicker, m micro-label, c code or data, t title, s strong, b body, n numeral.
    """
    return (
        "<style>"
        f".k{{font-family:{MONO};font-weight:700;letter-spacing:2px}}"
        f".m{{font-family:{MONO};font-weight:700;letter-spacing:{TRACK}px}}"
        f".c{{font-family:{MONO};font-weight:500}}"
        f".t{{font-family:{SANS};font-weight:800;letter-spacing:-0.2px}}"
        f".s{{font-family:{SANS};font-weight:600}}"
        f".b{{font-family:{SANS};font-weight:500}}"
        f".n{{font-family:{SANS};font-weight:800;font-variant-numeric:tabular-nums}}"
        f"{extra}</style>"
    )


def frame(
    w: float, h: float, r: float = RADIUS, fill: str = BG, stroke: str = HAIR
) -> str:
    """The flat card surface: one fill, one hairline border, no gradient and no glow."""
    return f'<rect x="0.5" y="0.5" width="{w - 1:g}" height="{h - 1:g}" rx="{r:g}" fill="{fill}" stroke="{stroke}"/>'


def card_open(w: float, h: float, label: str, defs: str = "", css: str = "") -> str:
    """Open a card: the svg root, the shared classes, a clip for its rounded corners and the surface."""
    return (
        svg_open(w, h, label)
        + style(css)
        + f'<defs><clipPath id="card"><rect x="1" y="1" width="{w - 2:g}" height="{h - 2:g}" rx="{RADIUS - 1}"/></clipPath>{defs}</defs>'
        + frame(w, h)
    )


def text(
    x: float,
    y: float,
    content: str,
    size: float,
    fill: str = INK,
    cls: str = "b",
    anchor: str = "",
    extra: str = "",
) -> str:
    align = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text class="{cls}" x="{x:g}" y="{y:g}" font-size="{size:g}" fill="{fill}"{align}{extra}>{escape(str(content))}</text>'


def eyebrow(
    x: float, y: float, label: str, fill: str = BLUE_LIGHT, anchor: str = ""
) -> str:
    """The mono micro-label a card opens with; put a line of data here, not the section's title again."""
    return text(x, y, label.upper(), MICRO, fill, "m", anchor)


def grid_pattern(pattern_id: str = "grid", size: int = 24, alpha: float = 0.035) -> str:
    return (
        f'<pattern id="{pattern_id}" width="{size}" height="{size}" patternUnits="userSpaceOnUse">'
        f'<path d="M{size} 0H0V{size}" fill="none" stroke="rgba(255,255,255,{alpha})" stroke-width="1"/></pattern>'
    )


def dot_pattern(pattern_id: str = "dots", size: int = 16, alpha: float = 0.08) -> str:
    return (
        f'<pattern id="{pattern_id}" width="{size}" height="{size}" patternUnits="userSpaceOnUse">'
        f'<circle cx="1" cy="1" r="1" fill="rgba(255,255,255,{alpha})"/></pattern>'
    )


# ---------------------------------------------------------------- marks
STAR = "M5 0.6 6.4 3.5 9.6 3.9 7.3 6.1 7.9 9.3 5 7.8 2.1 9.3 2.7 6.1 0.4 3.9 3.6 3.5Z"  # 10 x 10, from its top left
TICK = "M-3.4 0.2l2.3 2.3 4.5-4.8"  # an ok tick centred on 0 0, 8 wide


def num(value: float) -> str:
    """A coordinate to two places at most, with no trailing zeros and never "-0"."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def rect(
    x: float,
    y: float,
    w: float,
    h: float,
    r: float = 0,
    fill: str = BG,
    stroke: str = "",
    extra: str = "",
) -> str:
    edge = f' stroke="{stroke}"' if stroke else ""
    return (
        f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" rx="{num(r)}" '
        f'fill="{fill}"{edge}{extra}/>'
    )


# ---------------------------------------------------------------- motion
def keys(points: list[tuple[float, str]], dur: float = T) -> tuple[str, str]:
    """(values, keyTimes) for (seconds, value) points that run from 0 to dur."""
    values = ";".join(value for _, value in points)
    times = ";".join(f"{round(second / dur, 4):g}" for second, _ in points)
    return values, times


def held(begin: float, dur: float, ease: bool = True) -> str:
    """Timing that runs from 0 s and holds the start value until begin.

    The element's own attributes hold the finished frame, so a still render
    (link preview, print, a viewer without SMIL) shows the whole card, and a
    browser never flashes the item before its turn.
    """
    total = begin + dur
    spline = f' calcMode="spline" keySplines="0 0 1 1;{EASE}"' if ease else ""
    return (
        f'keyTimes="0;{begin / total:.3f};1" dur="{total:.2f}s" fill="freeze"{spline}'
    )


def enter(at: float, dur: float = ENTER, shift: str = "", start: str = "0") -> str:
    """A poster-safe entrance for the element it sits in: fade from `start`, and rise from `shift` if given."""
    times = held(at, dur)
    out = f'<animate attributeName="opacity" values="{start};{start};1" {times}/>'
    if shift:
        out += f'<animateTransform attributeName="transform" type="translate" values="{shift};{shift};0 0" {times}/>'
    return out


def group(at: float, body: str, shift: str = "0 8") -> str:
    """Wrap a block so it fades in and rises 8px at `at`."""
    return f"<g>{enter(at, shift=shift)}{body}</g>"


def draw(
    d: str,
    at: float,
    dur: float = 0.8,
    color: str = BLUE,
    width: float = 2,
    extra: str = "",
) -> str:
    """Draw a path in once. pathLength makes the dash its full length; it rests drawn."""
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}" '
        f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="0"{extra}>'
        f'<animate attributeName="stroke-dashoffset" values="1;1;0" {held(at, dur)}/></path>'
    )


def loop(
    attribute: str, values: str, key_times: str, dur: float = T, begin: float = 0
) -> str:
    """A repeating animation on the page clock; dur must be 2, 3, 4, 6, 12 or 24."""
    start = f' begin="{begin:g}s"' if begin else ""
    return (
        f'<animate attributeName="{attribute}" values="{values}" keyTimes="{key_times}" '
        f'dur="{dur:g}s"{start} repeatCount="indefinite"/>'
    )


def beam(
    d: str,
    dur: float = 6,
    begin: float = 0,
    travel: float = 1.0,
    color: str = BLUE_LIGHT,
    width: float = 2,
    dash: float = 10,
    closed: bool = False,
) -> str:
    """A short light that runs along path d once per loop, then rests.

    pathLength normalises the path to 100 units. `travel` is the share of the
    loop the light spends moving (0.33 crosses in 2 s of a 6 s loop). For a
    closed outline pass closed=True and the light circles without a gap.
    """
    start = f' begin="{begin:g}s"' if begin else ""
    if closed:
        return (
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}" stroke-linecap="round" '
            f'pathLength="100" stroke-dasharray="{dash:g} {100 - dash:g}">'
            f'<animate attributeName="stroke-dashoffset" values="0;-100" dur="{dur:g}s"{start} repeatCount="indefinite"/></path>'
        )
    values, times = f"{dash:g};-100", "0;1"
    if travel < 1:
        values, times = f"{dash:g};-100;-100", f"0;{travel:.3f};1"
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}" stroke-linecap="round" '
        f'pathLength="100" stroke-dasharray="{dash:g} {100 + dash:g}" stroke-dashoffset="{dash:g}">'
        f'<animate attributeName="stroke-dashoffset" values="{values}" keyTimes="{times}" dur="{dur:g}s"{start} repeatCount="indefinite"/></path>'
    )


def rounded_rect_path(x: float, y: float, w: float, h: float, r: float) -> str:
    """The outline of a rounded rectangle as a path, for a beam that circles a border."""
    return (
        f"M{x + r:g} {y:g}H{x + w - r:g}A{r:g} {r:g} 0 0 1 {x + w:g} {y + r:g}V{y + h - r:g}"
        f"A{r:g} {r:g} 0 0 1 {x + w - r:g} {y + h:g}H{x + r:g}A{r:g} {r:g} 0 0 1 {x:g} {y + h - r:g}"
        f"V{y + r:g}A{r:g} {r:g} 0 0 1 {x + r:g} {y:g}Z"
    )


def live_dot(cx: float, cy: float, color: str = GREEN, r: float = 4) -> str:
    """A status point: a ring that widens and fades every 2 s under a steady dot."""
    return (
        f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" stroke="{color}" stroke-width="1.5">'
        f'<animate attributeName="r" values="{r:g};{r + 7:g}" dur="2s" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values="0.9;0" dur="2s" repeatCount="indefinite"/></circle>'
        f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{color}"/>'
    )


def rotating(
    lines: list[str],
    x: float,
    y: float,
    cls: str,
    size: float,
    color: str,
    slot: float = 3.0,
    anchor: str = "",
) -> str:
    """Lines that take turns in one place: each holds for `slot` seconds; the first shows at rest."""
    count = len(lines)
    if count == 1:
        return text(x, y, lines[0], size, color, cls, anchor)
    dur, out = slot * count, []
    align = f' text-anchor="{anchor}"' if anchor else ""
    for index, line in enumerate(lines):
        rest = "" if index == 0 else ' opacity="0"'
        a = index / count
        b, c, d = a + 0.04, a + 1 / count - 0.04, a + 1 / count
        times = sorted({0.0, round(a, 3), round(b, 3), round(c, 3), round(d, 3), 1.0})
        values = ["1" if round(b, 3) <= t <= round(c, 3) else "0" for t in times]
        out.append(
            f'<text class="{cls}" x="{x:g}" y="{y:g}" fill="{color}" font-size="{size:g}"{align}{rest}>{escape(line)}'
            f'<animate attributeName="opacity" values="{";".join(values)}" keyTimes="{";".join(f"{t:g}" for t in times)}" '
            f'dur="{dur:g}s" repeatCount="indefinite"/></text>'
        )
    return "".join(out)


# ---------------------------------------------------------------- data marks
def sparkline(
    values: list[float],
    x: float,
    y: float,
    w: float,
    h: float,
    color: str = BLUE_LIGHT,
    at: float = 0.4,
    dur: float = 1.0,
    width: float = 1.6,
) -> str:
    """A word-sized line of a series, drawn in once, ending on a dot. No frame and no axis."""
    if len(values) < 2:
        return ""
    low, high = min(values), max(values)
    span = (high - low) or 1
    step = w / (len(values) - 1)
    points = [
        (x + i * step, y + h - (v - low) / span * h) for i, v in enumerate(values)
    ]
    d = "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in points)
    end_x, end_y = points[-1]
    return draw(
        d, at, dur, color, width, ' stroke-linejoin="round" stroke-linecap="round"'
    ) + (
        f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="2.6" fill="{color}">{enter(at + dur, 0.3)}</circle>'
    )


def ring(
    cx: float,
    cy: float,
    r: float,
    share: float,
    color: str = BLUE_LIGHT,
    at: float = 0.4,
    dur: float = 0.9,
    width: float = 5,
) -> str:
    """A radial gauge: a full track and an arc for `share` (0 to 1) that draws in from 12 o'clock."""
    around = 2 * math.pi * r
    arc = max(0.0, min(1.0, share)) * around
    return (
        f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" stroke="{HAIR_STRONG}" stroke-width="{width:g}"/>'
        f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" stroke="{color}" stroke-width="{width:g}" stroke-linecap="round" '
        f'stroke-dasharray="{arc:.1f} {around:.1f}" stroke-dashoffset="0" transform="rotate(-90 {cx:g} {cy:g})">'
        f'<animate attributeName="stroke-dashoffset" values="{arc:.1f};{arc:.1f};0" {held(at, dur)}/></circle>'
    )


def tile(
    x: float,
    y: float,
    w: float,
    h: float,
    value: str,
    label: str,
    at: float = 0,
    color: str = INK,
    size: float = 26,
) -> str:
    """A stat tile: one large numeral over a mono micro-label."""
    body = (
        f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="10" fill="{CARD}" stroke="{HAIR_STRONG}"/>'
        + text(x + 16, y + h / 2 + 2, value, size, color, "n")
        + text(x + 16, y + h - 14, label.upper(), MICRO, META, "m")
    )
    return group(at, body)


def chip_width(
    label: str, size: float = MICRO, pad: float = 10, tracking: float = TRACK
) -> float:
    return text_width(label, size, True, tracking) + pad * 2 - tracking


def chip(
    x: float,
    y: float,
    label: str,
    color: str = BLUE_LIGHT,
    size: float = MICRO,
    height: float = 22,
    pad: float = 10,
    fill: str = HAIR_FILL,
    stroke: str = HAIR_STRONG,
) -> tuple[str, float]:
    """A mono pill, its label centred so a measuring error shows as even padding. Returns (svg, width)."""
    width = chip_width(label, size, pad)
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{width:.1f}" height="{height:g}" rx="{height / 2:g}" fill="{fill}" stroke="{stroke}"/>'
        + text(
            x + width / 2,
            y + height / 2 + size * 0.36,
            label,
            size,
            color,
            "m",
            "middle",
        ),
        width,
    )


def chips(
    labels: list[str],
    x: float,
    y: float,
    max_width: float,
    color: str = BLUE_LIGHT,
    gap: float = 6,
    row_gap: float = 6,
    max_rows: int = 0,
    size: float = MICRO,
    height: float = 22,
) -> tuple[str, float, int]:
    """Flow pills into rows no wider than max_width. Returns (svg, height used, labels shown)."""
    out, cx, cy, rows, shown = [], x, y, 1, 0
    for label in labels:
        width = chip_width(label, size)
        if cx > x and cx + width > x + max_width:
            if max_rows and rows >= max_rows:
                break
            cx, cy, rows = x, cy + height + row_gap, rows + 1
        svg, width = chip(cx, cy, label, color, size, height)
        out.append(svg)
        cx += width + gap
        shown += 1
    return "".join(out), cy + height - y, shown
