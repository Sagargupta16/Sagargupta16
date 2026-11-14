"""The community tool cards: a preview of what the tool does, then its kind and traction, title, summary and stack."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# One card per ctx["tools"] entry: tool-{slug}.svg and tool-{slug}-mobile.svg.
# The profile and COMMUNITY.md show both in rows of 270px images (the README's
# width="270" applies to the desktop source and the phone fallback alike), so
# the phone twin is a 270px card with larger type, not a 320px card that the
# row would scale down to 0.84 and push under the phone text floor.
#
# The strip on top is a small preview motif picked by the tool's kind: a
# workflow run for a GitHub Action, a tool call for an MCP server, a slash
# command for a Claude Code plugin, a check list for a CLI, stacked rows for
# a list or a guide. The run, the call, the command and the check list carry
# the tool's own name, so two tools of one kind never show the same picture.
# Each runs once every 6 s and is poster-safe: the
# elements' own attributes hold the finished frame, the loop clears it,
# replays the mechanism and rests finished again, and what only exists in
# transit (a packet, a highlight) rests hidden. Cards side by side start
# their loops a beat apart, so a row plays as a relay rather than in unison.
#
# Under the strip, the eyebrow row carries the kind on the left and the
# traction chips (stars from ten, monthly npm downloads) on the right, the
# way a project card carries its date and LIVE mark. Every card in a run has
# one height, and the tech chips sit at one height under the lowest summary
# of the run, so no card holds an empty slot for a chip it does not draw. A
# run is a row, except the profile's desktop grid of top tools, which is one
# run so its three rows end level (see runs()).
from __future__ import annotations

import itertools
import math
import re
from typing import NamedTuple

import kit

WIDTH = 270
LOOP = 6  # every motif loop, on the page clock
CLEAR = 0.3  # a motif leaves its finished frame here and replays from the start
STAR_FLOOR = 10  # a card shows its star count only from this many stars
TECH_SHOWN = 3  # at most this many tech chips; fewer when the row is full
CHIP_PAD, BADGE_PAD, CHIP_GAP = 8, 7, 6
KIND_GAP = 10  # between the kind and the traction chips on the eyebrow row
# The star, 20 wide and 19 tall, drawn from its top point.
STAR = "l3.1 6.3 6.9 1 -5 4.9 1.2 6.9 -6.2 -3.3 -6.2 3.3 1.2 -6.9 -5 -4.9 6.9 -1z"
STAR_WIDTH, STAR_HEIGHT, STAR_DRAWN = 20, 19, 11
W30 = "rgba(255,255,255,0.30)"  # a skeleton line: text the motif implies, not states
W12 = "rgba(255,255,255,0.12)"
LIGHT_60 = "rgba(96,165,250,0.6)"
LIGHT_30 = "rgba(96,165,250,0.3)"
LIGHT_45 = "rgba(96,165,250,0.45)"
# The strip and the panels in it (kit.WELL) are tints, not solids: over the
# card's BG the strip lands on kit.CARD and a panel back on BG, and each one's
# edge is its hairline, so a contrast check reads them as surfaces and not as graphics.
STRIP = "rgba(24,39,51,0.3)"


class Layout(NamedTuple):
    """Sizes of one layout. The text's y positions are measured from the strip's foot down."""

    pad: float
    cover: float  # height of the preview strip
    eyebrow: float  # strip foot to the eyebrow baseline
    title_size: float
    title_gap: float  # eyebrow baseline to the first title baseline
    title_pitch: float
    body_size: float
    body_gap: float  # last title baseline to the first summary baseline
    leading: float
    micro: float
    chip_height: float  # the tech chips
    badge_height: float  # the traction chips on the eyebrow row
    drop: float  # last summary baseline to the top of the tech chips
    bottom: float  # under the tech chips
    row: int  # cards side by side at most, so each run of this many shares one height


# Three 270px cards fill the desktop column. The phone file is also what a
# 768 to 1011px window gets, where the README column is 383 to 626px: two a row.
DESKTOP = Layout(18, 72, 26, 16, 26, 20, 13, 22, 18, kit.MICRO, 22, 20, 13, 16, 3)
PHONE = Layout(16, 80, 28, 17, 27, 21, 14, 23, 20, kit.MICRO_PHONE, 24, 22, 14, 16, 2)


def inner(layout: Layout) -> float:
    return WIDTH - 2 * layout.pad


def _mono(content: str, size: float) -> float:
    """The drawn width of a mono micro-label: its tracking counts between letters, not after the last."""
    return kit.text_width(content, size, True, kit.TRACK) - kit.TRACK


# ---------------------------------------------------------------- text
def wrap(text: str, width: float, size: float) -> list[str]:
    """Wrap to a pixel width, and never leave one short word alone on the last line.

    A token wider than the line breaks the way kit.wrap_text breaks it, after a
    "/", "-", "_" or "." where it can, so a repo slug cannot run past the edge.
    """
    lines = kit.wrap_text(str(text), width, size)
    if len(lines) > 1 and " " not in lines[-1] and " " in lines[-2]:
        head, moved = lines[-2].rsplit(" ", 1)
        if kit.text_width(f"{moved} {lines[-1]}", size) <= width:
            lines[-2:] = [head, f"{moved} {lines[-1]}"]
    return lines


def kind(tool: dict) -> str:
    return " ".join(str(tool.get("kind") or "").upper().split())


def eyebrow(tool: dict, layout: Layout) -> str:
    """The tool's kind for the eyebrow, cut to whole words where the traction chips leave too little room."""
    room = inner(layout) - traction_width(tool, layout)
    room -= KIND_GAP if has_traction(tool) else 0
    label = kind(tool)
    if _mono(label, layout.micro) <= room:
        return label
    while " " in label and _mono(label + "...", layout.micro) > room:
        label = label.rsplit(" ", 1)[0]
    while len(label) > 1 and _mono(label + "...", layout.micro) > room:
        label = label[:-1]
    # chips that leave no room for one letter: the strip still shows the kind
    return label + "..." if _mono(label + "...", layout.micro) <= room else ""


class Text(NamedTuple):
    titles: list[str]
    lines: list[str]
    title_y: float  # first title baseline
    body_y: float  # first summary baseline
    last: float  # the lowest baseline of the title and summary


def text_block(tool: dict, layout: Layout) -> Text:
    titles = wrap(tool["title"], inner(layout), layout.title_size)
    lines = wrap(tool["summary"], inner(layout), layout.body_size)
    title_y = layout.cover + layout.eyebrow + layout.title_gap
    title_last = title_y + max(len(titles) - 1, 0) * layout.title_pitch
    body_y = title_last + layout.body_gap
    last = body_y + (len(lines) - 1) * layout.leading if lines else title_last
    return Text(titles, lines, title_y, body_y, last)


# ---------------------------------------------------------------- traction and stack
def shows_stars(tool: dict) -> bool:
    return (tool.get("stars") or 0) >= STAR_FLOOR


def npm_label(tool: dict) -> str:
    """The monthly downloads as an exact count, so the chip never rounds past the live figure."""
    monthly = tool.get("npm_monthly")
    return f"{monthly:,}/MO NPM" if monthly else ""


def has_traction(tool: dict) -> bool:
    return shows_stars(tool) or bool(npm_label(tool))


def tech_shown(tool: dict, layout: Layout) -> list[str]:
    """The tech names that fit one row of chips, in their order, three at most.

    A name too wide for what is left is passed over, and the shorter names after
    it still get their turn.
    """
    shown, used = [], 0.0
    for name in map(str, tool.get("tech") or []):
        width = kit.chip_width(name, layout.micro, CHIP_PAD)
        if used + width <= inner(layout):
            shown.append(name)
            used += width + CHIP_GAP
            if len(shown) == TECH_SHOWN:
                break
    return shown


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


def _star_width(stars: int, layout: Layout) -> float:
    return BADGE_PAD + STAR_DRAWN + 4 + _mono(f"{stars:,}", layout.micro) + BADGE_PAD


def traction_width(tool: dict, layout: Layout) -> float:
    """The room the traction chips take on the eyebrow row; 0 when there are none."""
    widths = []
    if shows_stars(tool):
        widths.append(_star_width(tool["stars"], layout))
    if content := npm_label(tool):
        widths.append(kit.chip_width(content, layout.micro, BADGE_PAD))
    return sum(widths) + CHIP_GAP * max(0, len(widths) - 1)


def traction(tool: dict, right: float, y: float, layout: Layout) -> str:
    """The star chip, then the npm chip, ending at `right`; a chip that is not drawn takes no room."""
    x, height, out = right - traction_width(tool, layout), layout.badge_height, []
    fill, stroke = f"{kit.SKY}14", f"{kit.SKY}55"
    baseline = y + height / 2 + layout.micro * 0.36
    if shows_stars(tool):
        width, scale = _star_width(tool["stars"], layout), STAR_DRAWN / STAR_WIDTH
        out.append(
            _rect(x, y, width, height, height / 2, fill, stroke)
            + f'<path d="M0 0{STAR}" fill="{kit.SKY}" transform="translate({_n(x + BADGE_PAD + STAR_DRAWN / 2)} '
            f'{_n(y + (height - STAR_HEIGHT * scale) / 2)}) scale({scale:g})"/>'
            + kit.text(
                x + BADGE_PAD + STAR_DRAWN + 4,
                baseline,
                f"{tool['stars']:,}",
                layout.micro,
                kit.SKY,
                "m",
            )
        )
        x += width + CHIP_GAP
    if content := npm_label(tool):
        out.append(
            kit.chip(
                x, y, content, kit.SKY, layout.micro, height, BADGE_PAD, fill, stroke
            )[0]
        )
    return "".join(out)


def tech_row(tool: dict, x: float, y: float, layout: Layout) -> str:
    out = []
    for name in tech_shown(tool, layout):
        svg, width = kit.chip(
            x, y, name, kit.BLUE_LIGHT, layout.micro, layout.chip_height, CHIP_PAD
        )
        out.append(svg)
        x += width + CHIP_GAP
    return "".join(out)


class Rows(NamedTuple):
    """Where one run of cards puts its tech chips, and the height every card in it shares."""

    tech: float | None  # top of the tech chips, when a card in the run shows any
    height: int


def rows(run: list[dict], layout: Layout) -> Rows:
    """Line up a run of cards: the tech chips go just under the run's lowest summary line."""
    last = max(text_block(tool, layout).last for tool in run)
    if any(tech_shown(tool, layout) for tool in run):
        tech = last + layout.drop
        return Rows(tech, math.ceil(tech + layout.chip_height + layout.bottom))
    return Rows(None, math.ceil(last + layout.body_size * 0.3 + layout.bottom))


# ---------------------------------------------------------------- motion
_n, _rect = kit.num, kit.rect


def _anim(attribute: str, points: list, begin: float = 0, kind: str = "") -> str:
    """One LOOP-second loop from [(seconds, value)], padded at both ends with the first and last value."""
    points = list(points)
    if points[0][0] > 0:
        points.insert(0, (0, points[0][1]))
    if points[-1][0] < LOOP:
        points.append((LOOP, points[-1][1]))
    values = ";".join(v if isinstance(v, str) else _n(v) for _, v in points)
    times = ";".join(
        f"{min(1.0, t / LOOP):.4f}".rstrip("0").rstrip(".") for t, _ in points
    )
    start = f' begin="{_n(begin)}s"' if begin else ""
    if kind:
        return (
            f'<animateTransform attributeName="transform" type="{kind}" values="{values}" '
            f'keyTimes="{times}" dur="{LOOP}s"{start} repeatCount="indefinite"/>'
        )
    return (
        f'<animate attributeName="{attribute}" values="{values}" keyTimes="{times}" '
        f'dur="{LOOP}s"{start} repeatCount="indefinite"/>'
    )


def _window(on: float, off: float, ramp: float = 0.25) -> list:
    """Hidden at rest, shown between on and off."""
    return [(on, 0), (on + ramp, 1), (off, 1), (off + ramp, 0)]


def _back(at: float, ramp: float = 0.2) -> list:
    """Shown at rest, cleared at CLEAR, back at `at`: the rest frame is the finished one."""
    return [(CLEAR, 1), (CLEAR + 0.25, 0), (at, 0), (at + ramp, 1)]


def _bar(x: float, y: float, w: float, h: float = 3.5, fill: str = W30) -> str:
    """A skeleton line centred on y."""
    return _rect(x, y - h / 2, w, h, h / 2, fill)


def _wire(d: str, stroke: str = kit.HAIR_STRONG, width: float = 1) -> str:
    return f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{_n(width)}"/>'


def _tick(cx: float, cy: float, r: float, square: bool = False) -> str:
    """A done mark: a blue disc (or box) with a light tick."""
    if square:
        mark = _rect(cx - r, cy - r, 2 * r, 2 * r, 2.5, kit.BLUE)
    else:
        mark = f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="{kit.BLUE}"/>'
    return mark + (
        f'<path d="M{_n(cx - r * 0.45)} {_n(cy + r * 0.02)}l{_n(r * 0.3)} {_n(r * 0.32)} '
        f'{_n(r * 0.58)} {_n(-r * 0.64)}" fill="none" stroke="{kit.INK}" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _code(content: str, size: float) -> float:
    """The drawn width of a code label (class c): mono, with no tracking."""
    return len(content) * size * 0.6


def _fit(content: str, room: float, size: float) -> str:
    """A code label cut to `room` with "..." when it is longer; the motifs' names rarely are."""
    if _code(content, size) <= room:
        return content
    while content and _code(content + "...", size) > room:
        content = content[:-1]
    return content + "..."


def _name_lines(name: str, room: float, size: float, most: int = 3) -> list[str]:
    """A name in the fewest lines that fit `room`, broken only after a "-", its longest
    line as short as the breaks allow; cut to one line when no break makes it fit."""
    pieces = re.findall(r"[^-]+-*|-+", name) or [name]
    for count in range(1, min(most, len(pieces)) + 1):
        best = None
        for cuts in itertools.combinations(range(1, len(pieces)), count - 1):
            bounds = (0, *cuts, len(pieces))
            lines = ["".join(pieces[a:b]) for a, b in itertools.pairwise(bounds)]
            widest = max(_code(line, size) for line in lines)
            if widest <= room and (best is None or widest < best[0]):
                best = (widest, lines)
        if best:
            return best[1]
    return [_fit(name, room, size)]


def _chevron(x: float, y: float, right: bool, color: str = kit.HAIR_STRONG) -> str:
    """An arrowhead whose point is at (x, y)."""
    k = -1 if right else 1
    return (
        f'<path d="M{_n(x + 4 * k)} {_n(y - 3)}L{_n(x)} {_n(y)}L{_n(x + 4 * k)} {_n(y + 3)}" '
        f'fill="none" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )


class Strip:
    """The preview strip: the card's width, padded like the text under it, with its loop's start."""

    def __init__(self, layout: Layout, begin: float) -> None:
        self.phone = layout is PHONE or layout.micro > kit.MICRO
        self.h = layout.cover
        self.x0, self.x1 = layout.pad, WIDTH - layout.pad
        self.w = self.x1 - self.x0
        self.cy = self.h / 2
        self.micro = layout.micro
        self.begin = begin
        self.pitch = 18 if self.phone else 16  # between stacked rows
        self.defs: list[str] = []  # clip paths a motif needs

    def anim(self, attribute: str, points: list, kind: str = "") -> str:
        return _anim(attribute, points, self.begin, kind)

    def fade(self, points: list) -> str:
        return self.anim("opacity", points)

    def label(
        self,
        x: float,
        y: float,
        content: str,
        fill: str = kit.META,
        anchor: str = "",
        cls: str = "m",
    ) -> str:
        """A mono label at the layout's text floor, set so y is its middle."""
        return kit.text(
            x, y + self.micro * 0.36, content, self.micro, fill, cls, anchor
        )

    def flash(self, body: str, on: float, off: float) -> str:
        """A highlight over something already drawn: hidden at rest, shown between on and off."""
        return f'<g opacity="0">{self.fade(_window(on, off))}{body}</g>'

    def back(self, body: str, at: float) -> str:
        """Part of the finished frame: shown at rest, cleared at CLEAR, back at `at`."""
        return f"<g>{self.fade(_back(at))}{body}</g>"

    def packet(
        self,
        a: tuple,
        b: tuple,
        start: float,
        end: float,
        color: str = kit.SKY,
        width: float = 2,
        px: float = 9,
    ) -> str:
        """A short light that runs the straight wire a to b once per loop and rests hidden off its ends."""
        length = math.dist(a, b) or 1
        dash = 100 * px / length
        margin = 100 * width / length  # keeps the round cap off both ends
        rest, gone = dash + margin, -(100 + margin)
        return (
            f'<path d="M{_n(a[0])} {_n(a[1])}L{_n(b[0])} {_n(b[1])}" fill="none" stroke="{color}" '
            f'stroke-width="{_n(width)}" stroke-linecap="round" pathLength="100" '
            f'stroke-dasharray="{_n(dash)} {_n(100 + dash + 2 * margin)}" stroke-dashoffset="{_n(rest)}">'
            + self.anim("stroke-dashoffset", [(start, rest), (end, gone)])
            + "</path>"
        )

    def stroke(
        self,
        x: float,
        y: float,
        w: float,
        at: float,
        dur: float = 0.35,
        color: str = W30,
        width: float = 3.5,
    ) -> str:
        """A line that rests drawn, clears at CLEAR and draws in from the left at `at`."""
        hidden = 1 + 2 * width / max(
            w, 1
        )  # the round cap stays off the start while hidden
        return (
            f'<path d="M{_n(x)} {_n(y)}H{_n(x + w)}" fill="none" stroke="{color}" stroke-width="{_n(width)}" '
            f'stroke-linecap="round" pathLength="1" stroke-dasharray="1 3" stroke-dashoffset="0">'
            + self.anim(
                "stroke-dashoffset",
                [(CLEAR, 0), (CLEAR + 0.2, hidden), (at, hidden), (at + dur, 0)],
            )
            + "</path>"
        )


# ---------------------------------------------------------------- motifs
def _run(s: Strip, tool: dict) -> str:
    """A GitHub Action: a run of the tool's workflow, three jobs that turn done in turn, and its progress bar."""
    jobs, bw, bh = 3, (60 if s.phone else 56), (28 if s.phone else 24)
    gap = (s.w - jobs * bw) / (jobs - 1)
    # the run is named after the tool on the line above its jobs, as a run is listed
    name = _fit(str(tool.get("slug") or ""), s.w, s.micro)
    cy = s.cy + (2 if name else -4) + (1 if s.phone else 0)
    top, r = cy - bh / 2, (5.5 if s.phone else 5)
    track = s.h - (11 if s.phone else 10)
    out = [
        _wire(f"M{_n(s.x0 + bw / 2)} {_n(cy)}H{_n(s.x1 - bw / 2)}"),
        _wire(f"M{_n(s.x0)} {_n(track)}H{_n(s.x1)}", kit.HAIR_STRONG, 2),
        s.stroke(s.x0, track, s.w, 0.8, 2.6, LIGHT_60, 2),
    ]
    if name:
        out.append(s.label(s.x0, top - (10 if s.phone else 9), name, kit.META, cls="c"))
    for k in range(jobs):
        x = s.x0 + k * (bw + gap)
        turn = 0.8 + 0.9 * k  # job k runs from here for 0.7 s
        cx = x + r + 6
        line_x = cx + r + 6
        line = x + bw - 8 - line_x
        out.append(
            _rect(x, top, bw, bh, 6, kit.WELL, kit.HAIR_STRONG)
            + s.flash(
                _rect(x, top, bw, bh, 6, kit.BLUE_TINT, kit.BLUE_EDGE),
                turn - 0.1,
                turn + 0.7,
            )
            + f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="none" stroke="{kit.HAIR_STRONG}" stroke-width="1.5"/>'
            + _bar(line_x, cy - 3, line)
            + _bar(line_x, cy + 3, line * 0.6, 3, W12)
            + s.back(_tick(cx, cy, r), turn + 0.55)
        )
        if k < jobs - 1:
            out.append(
                s.packet((x + bw, cy), (x + bw + gap, cy), turn + 0.55, turn + 0.9)
            )
    return "".join(out)


def _call(s: Strip, tool: dict) -> str:
    """An MCP server: an agent sends tools/call to the server, named on its box, and the result comes back."""
    pad, bh = 8, (32 if s.phone else 28)
    left_w = _mono("AGENT", s.micro) + 2 * pad
    # the server box says which server this is (the eyebrow already says MCP SERVER),
    # broken after a "-" where the wires and their labels need the room
    span = _code("tools/call", s.micro) + 12
    room = s.w - left_w - span - 2 * 8
    name = str(tool.get("slug") or "") or "server"
    lines = _name_lines(name, room, s.micro)
    pitch = s.micro + 3
    right_w = max(_code(line, s.micro) for line in lines) + 2 * 8
    bh = max(bh, (len(lines) - 1) * pitch + s.micro + 16)
    a, b = s.x0 + left_w, s.x1 - right_w  # the wires run between the boxes
    up, down, top = s.cy - 5, s.cy + 5, s.cy - bh / 2
    mid = (a + b) / 2
    ask = up - 8 - s.micro * 0.36  # the middle of each wire's label
    answer = down + 7 + s.micro * 0.36
    agent = _rect(s.x0, top, left_w, bh, 7, kit.WELL, kit.HAIR_STRONG) + s.label(
        s.x0 + left_w / 2, s.cy, "AGENT", kit.META, "middle"
    )
    first = s.cy - (len(lines) - 1) * pitch / 2
    server = _rect(b, top, right_w, bh, 7, kit.BLUE_TINT, kit.BLUE_EDGE) + "".join(
        s.label(b + right_w / 2, first + k * pitch, line, kit.INK, "middle", "c")
        for k, line in enumerate(lines)
    )
    return (
        _wire(f"M{_n(a)} {_n(up)}H{_n(b - 1)}")
        + _chevron(b - 1, up, True)
        + _wire(f"M{_n(b)} {_n(down)}H{_n(a + 1)}")
        + _chevron(a + 1, down, False)
        + s.label(mid, ask, "tools/call", kit.META, "middle", "c")
        + s.flash(
            s.label(mid, ask, "tools/call", kit.BLUE_LIGHT, "middle", "c"), 0.6, 1.8
        )
        + s.label(mid, answer, "result", kit.META, "middle", "c")
        + s.flash(
            s.label(mid, answer, "result", kit.BLUE_LIGHT, "middle", "c"), 2.0, 3.2
        )
        + s.packet((a, up), (b - 1, up), 0.8, 1.6)
        + s.packet((b, down), (a + 1, down), 2.2, 3.0)
        + agent
        + s.flash(
            _rect(s.x0, top, left_w, bh, 7, kit.BLUE_TINT, kit.BLUE_EDGE), 2.9, 3.7
        )
        + server
        + s.flash(_rect(b, top, right_w, bh, 7, "none", kit.BLUE_LIGHT), 1.5, 2.3)
    )


def _slash(s: Strip, tool: dict) -> str:
    """A Claude Code plugin: its slash command goes in, and the output writes out under it, line by line."""
    pill_h = 26 if s.phone else 24
    key = pill_h - 8
    size = 14 if s.phone else 13
    key_x = s.x0 + 4
    text_x = key_x + key + 7
    # the command is the plugin's own name, the way Claude Code namespaces its commands
    command = _fit(str(tool.get("slug") or ""), s.x1 - 11 - text_x, s.micro) or "plugin"
    pill_w = text_x + _code(command, s.micro) + 11 - s.x0
    pill_top = 9
    pill_cy = pill_top + pill_h / 2
    # the output panel hangs under the command, reached by an elbow from the key
    elbow_x = key_x + key / 2
    panel_x = elbow_x + 24
    panel_top = pill_top + pill_h + 7
    panel_w, panel_h = s.x1 - panel_x, s.h - 7 - panel_top
    panel_cy = panel_top + panel_h / 2
    room = panel_w - 22
    step = panel_h / 3
    rows = [panel_cy - step / 2, panel_cy + step / 2]
    return (
        _wire(
            f"M{_n(elbow_x)} {_n(pill_top + pill_h)}V{_n(panel_cy)}H{_n(panel_x - 1)}"
        )
        + _chevron(panel_x - 1, panel_cy, True)
        + _rect(s.x0, pill_top, pill_w, pill_h, pill_h / 2, kit.WELL, kit.HAIR_STRONG)
        + s.flash(
            _rect(
                s.x0,
                pill_top,
                pill_w,
                pill_h,
                pill_h / 2,
                kit.BLUE_TINT,
                kit.BLUE_LIGHT,
            ),
            0.5,
            1.4,
        )
        + _rect(key_x, pill_cy - key / 2, key, key, key / 2, kit.BLUE)
        + kit.text(
            key_x + key / 2, pill_cy + size * 0.36, "/", size, kit.INK, "c", "middle"
        )
        + s.label(text_x, pill_cy, command, kit.INK, cls="c")
        + s.packet((elbow_x, panel_cy), (panel_x - 1, panel_cy), 1.15, 1.6)
        + _rect(panel_x, panel_top, panel_w, panel_h, 6, kit.WELL, kit.HAIR_STRONG)
        + s.stroke(panel_x + 11, rows[0], room * 0.8, 1.7, color=LIGHT_60)
        + s.stroke(panel_x + 11, rows[1], room * 0.56, 2.05)
    )


def _checks(s: Strip, tool: dict) -> str:
    """A CLI: a check list, run by the tool named on its first line, ticks row by row, then the run passes."""
    pass_w = _mono("PASS", s.micro) + 20
    pass_h = 26 if s.phone else 24
    pass_x = s.x1 - pass_w
    box = 6 if s.phone else 5.5  # half the check box
    line_x = s.x0 + 2 * box + 10
    room = pass_x - 18 - line_x
    name = _fit(str(tool.get("slug") or ""), room, s.micro)
    out = []
    for k, share in enumerate((1.0, 0.7, 0.86)):
        y = s.cy + (k - 1) * s.pitch
        line = (
            s.label(line_x, y, name, kit.INK, cls="c")
            if k == 0 and name
            else _bar(line_x, y, room * share)
        )
        out.append(
            _rect(s.x0, y - box, 2 * box, 2 * box, 2.5, "none", kit.HAIR_STRONG)
            + line
            + s.back(_tick(s.x0 + box, y, box, True), 1.0 + 0.5 * k)
        )
    top = s.cy - pass_h / 2
    lit = _rect(
        pass_x, top, pass_w, pass_h, pass_h / 2, kit.BLUE_TINT, kit.BLUE_EDGE
    ) + s.label(pass_x + pass_w / 2, s.cy, "PASS", kit.INK, "middle")
    return (
        "".join(out)
        + _rect(pass_x, top, pass_w, pass_h, pass_h / 2, kit.HAIR_FILL, kit.HAIR_STRONG)
        + s.label(pass_x + pass_w / 2, s.cy, "PASS", kit.META, "middle")
        + s.back(lit, 2.6)
    )


def _list(s: Strip, tool: dict) -> str:
    """A curated list: entries step up through a focus band, one every 2 s; the one in the band lights."""
    p, shares = s.pitch, (0.62, 0.44, 0.7)
    tag = 26 if s.phone else 22
    room = s.w - 12 - tag - 14
    steps = [(0, "0 0")]
    for k in range(3):
        at = 1.7 + 2 * k
        steps += [(at, f"0 {_n(-k * p)}"), (at + 0.3, f"0 {_n(-(k + 1) * p)}")]
    steps.append((LOOP, "0 0"))  # three rows up is the opening view again

    # The scrolling paints stay under half opacity: they reach below the strip
    # under its clip, and a contrast check that cannot see the clip reads only
    # solid shapes as graphics or as the background of the text under them.
    def scroller(dot: str, line: str, end: str) -> str:
        entries = "".join(  # three in view, three to step through; the list repeats every three
            f'<circle cx="{_n(s.x0 + 2.5)}" cy="{_n(s.cy + (k - 1) * p)}" r="2.2" fill="{dot}"/>'
            + _bar(s.x0 + 12, s.cy + (k - 1) * p, room * shares[k % 3], fill=line)
            + _bar(s.x1 - tag, s.cy + (k - 1) * p, tag, 3, end)
            for k in range(6)
        )
        return f"<g>{s.anim('transform', steps, 'translate')}{entries}</g>"

    band = s.cy - p / 2
    s.defs.append(
        f'<clipPath id="rows">{_rect(s.x0 - 8, s.cy - 1.5 * p, s.w + 16, 3 * p)}</clipPath>'
        f'<clipPath id="focus">{_rect(s.x0 - 6, band, s.w + 12, p)}</clipPath>'
    )
    return (
        _rect(s.x0 - 6, band, s.w + 12, p, 4, kit.BLUE_TINT)
        + _rect(s.x0 - 6, band + 2, 2, p - 4, 1, kit.BLUE_LIGHT)
        + f'<g clip-path="url(#rows)">{scroller(W30, W30, W12)}</g>'
        + f'<g clip-path="url(#focus)">{scroller(LIGHT_45, LIGHT_45, LIGHT_30)}</g>'
    )


def _guide(s: Strip, tool: dict) -> str:
    """A guide: numbered steps, the current one highlighted, each ticked as it is done."""
    p, out = s.pitch, []
    line_x = s.x0 + _mono("00", s.micro) + 12
    room = s.x1 - 18 - line_x
    for k, share in enumerate((0.78, 0.6, 0.7)):
        y = s.cy + (k - 1) * p
        out.append(
            s.label(s.x0, y, f"{k + 1:02d}", kit.BLUE_LIGHT)
            + _bar(line_x, y, room * share)
            + s.back(
                f'<path d="M{_n(s.x1 - 9)} {_n(y)}l3 3 6 -6" fill="none" stroke="{kit.BLUE_LIGHT}" '
                'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
                1.6 + k,
            )
        )
    moves = [
        (0, "0 0"),
        (1.8, "0 0"),
        (2.0, f"0 {_n(p)}"),
        (2.8, f"0 {_n(p)}"),
        (3.0, f"0 {_n(2 * p)}"),
        (4.4, f"0 {_n(2 * p)}"),
        (4.6, "0 0"),
    ]
    band = _rect(s.x0 - 6, s.cy - 1.5 * p, s.w + 12, p, 4, kit.BLUE_TINT, kit.BLUE_EDGE)
    return (
        f'<g opacity="0">{s.fade(_window(0.8, 3.9))}<g>{s.anim("transform", moves, "translate")}{band}</g></g>'
        + "".join(out)
    )


# kind -> (motif name, drawing); a kind not listed gets the list
MOTIFS = {
    "GITHUB ACTION": ("run", _run),
    "WORKFLOWS": ("run", _run),
    "MCP SERVER": ("call", _call),
    "CLAUDE CODE PLUGIN": ("slash", _slash),
    "AGENT SKILLS": ("slash", _slash),
    "CLI": ("checks", _checks),
    "CURATED LIST": ("list", _list),
    "GUIDE": ("guide", _guide),
}
FALLBACK = ("list", _list)


def motif(tool: dict) -> tuple:
    return MOTIFS.get(kind(tool), FALLBACK)


# ---------------------------------------------------------------- the card
def draw(tool: dict, index: int, layout: Layout, row: Rows) -> str:
    """One tool card: the preview strip, the kind and traction, the title, the summary and the tech chips.

    `row` holds where its run of cards puts the tech chips and the height they
    share; `index` is the card's place in the list, which sets when its motif
    starts so neighbours take turns.
    """
    block = text_block(tool, layout)
    height, pad, cover = row.height, layout.pad, layout.cover
    strip = Strip(layout, (index % layout.row) * LOOP / layout.row)
    name, scene = motif(tool)
    picture = scene(strip, tool)
    baseline = cover + layout.eyebrow
    head = ""
    if shown := eyebrow(tool, layout):
        head += kit.text(pad, baseline, shown, layout.micro, kit.BLUE_LIGHT, "m")
    if has_traction(tool):
        top = baseline - layout.micro * 0.36 - layout.badge_height / 2
        head += traction(tool, WIDTH - pad, top, layout)
    head += "".join(
        kit.text(
            pad,
            block.title_y + j * layout.title_pitch,
            title,
            layout.title_size,
            kit.INK,
            "t",
        )
        for j, title in enumerate(block.titles)
    )
    body = "".join(
        kit.text(
            pad,
            block.body_y + j * layout.leading,
            line,
            layout.body_size,
            kit.BODY,
            "b",
        )
        for j, line in enumerate(block.lines)
    )
    chips = tech_row(tool, pad, row.tech, layout) if row.tech is not None else ""
    return (
        kit.card_open(
            WIDTH,
            height,
            label(tool),
            "".join(strip.defs) + kit.dot_pattern("dots", 16, 0.05),
        )
        + '<g clip-path="url(#card)">'
        + _rect(0, 0, WIDTH, cover, 0, STRIP)
        + f'<rect width="{WIDTH}" height="{_n(cover)}" fill="url(#dots)"/>'
        + f'<g id="motif-{name}">{picture}</g>'
        + _wire(f"M0 {_n(cover)}H{WIDTH}")
        + "</g>"
        + _rect(0.5, 0.5, WIDTH - 1, height - 1, kit.RADIUS, "none", kit.HAIR)
        + kit.group(0.1, head)
        + kit.group(0.1 + kit.STAGGER, body)
        + (kit.group(0.1 + 2 * kit.STAGGER, chips) if chips else "")
        + kit.SVG_CLOSE
    )


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for every tool card, desktop and -mobile.

    Both pages lay the cards out in ctx["tools"] order from the first one (the
    profile shows the leading top tools, COMMUNITY.md all of them), so the rows
    are runs of that list and every card in a run is drawn at one height with
    its tech chips at one height.
    """
    tools = ctx["tools"]
    files = {}
    for layout, suffix in ((DESKTOP, ""), (PHONE, "-mobile")):
        for start, run in runs(tools, layout):
            row = rows(run, layout)
            for offset, tool in enumerate(run):
                files[f"tool-{tool['slug']}{suffix}.svg"] = draw(
                    tool, start + offset, layout, row
                )
    return files


def runs(tools: list[dict], layout: Layout) -> list[tuple[int, list[dict]]]:
    """The runs of cards drawn at one height, as (first index, cards).

    On desktop the profile's grid, the leading top tools in whole rows, is one run, so
    its three rows are one height and its chips one line; the rest go a row at a time.
    The phone's two-up rows stay runs of their own.
    """
    lead = 0
    if layout is DESKTOP:
        top = next(
            (i for i, tool in enumerate(tools) if not tool.get("top")), len(tools)
        )
        lead = min(len(tools), math.ceil(top / layout.row) * layout.row)
    out = [(0, tools[:lead])] if lead else []
    out += [
        (start, tools[start : start + layout.row])
        for start in range(lead, len(tools), layout.row)
    ]
    return out
