"""The three aws-samples cards: each sample's architecture as a looping diagram over its date, title and tags.

sample-agentcore-harness is the lead card, 840 wide on a row of its own: the
REQUEST lane (MCP clients, the gateway's default-deny Cedar policy, the tools
runtime, the harness) over the RELEASE lane (build, a test turn on DEFAULT, the
evaluation, the pinned PROD endpoint). One client asks for a tool the policy
does not list and is refused, then asks for ask_architect and is allowed.
sample-org-governance (the management account writing policies onto the OU
tree) and sample-sagemaker-mlops are 400 wide and sit two-up at one height.
Every card has a 320 wide phone twin that redraws the same diagram on a phone
grid.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# The look is the project cards': a CARD band with a faint dot grid holds the
# diagram, a hairline, then the eyebrow (AWS-SAMPLES and the month), the title
# and the tags as chips, all from ctx["samples"]. Nodes are flat BG tiles with
# mono labels; blue for what is lit, green only for an ok state (an allowed
# call, a passed check, a live endpoint), amber only for the model that waits
# on a person's approval.
#
# Every diagram runs one 12 s loop and is poster-safe: the elements' own
# attributes hold the finished state (the call allowed, the policies attached,
# the model approved and serving), the loop holds it, clears it, plays the
# mechanism beat by beat and ends on the finished state again. Things that only
# exist in transit (packets, flashes, the refused call's mark) rest hidden.
#
# Packets ride the wires only. Each wire runs from one tile's edge to the
# next, every packet sits in a group clipped to the card's wire windows, and
# no window reaches a label, so a packet is never drawn over text: it is seen
# leaving one tile and arriving at the next, and passes behind the tile.
from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise

import kit

T = kit.T
WIDE, HALF, PHONE = 840, 400, 320
SOURCE = "AWS-SAMPLES"
SEPARATOR = "  |  "
MONTHS = {
    name: name[:3].upper()
    for name in (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
}
TITLE_SIZE, TITLE_STEP, TITLE_ROWS = 18, 23, 3  # the 400 and phone titles
LEAD_TITLE = 20  # the lead card's title, on one row with its chips when both fit
CHIP_GAP = 6
REST = 2.0  # the finished frame holds until here, then the scene clears
CLEAR = 0.3  # how long clearing takes
WIRE = "rgba(255,255,255,0.18)"
W30 = "rgba(255,255,255,0.30)"
W07 = "rgba(255,255,255,0.07)"
NAME = kit.BODY  # a node's name at rest

Box = tuple[float, float, float, float]  # x, y, width, height
Point = tuple[float, float]


# ---------------------------------------------------------------- timing
_n, _rect = kit.num, kit.rect


def _anim(attribute: str, points: list) -> str:
    """One loop on the 12 s clock from [(seconds, value)]; the ends are padded with the first and last value."""
    points = list(points)
    if points[0][0] > 0:
        points.insert(0, (0, points[0][1]))
    if points[-1][0] < T:
        points.append((T, points[-1][1]))
    values = ";".join(v if isinstance(v, str) else _n(v) for _, v in points)
    times = ";".join(f"{t / T:.4f}".rstrip("0").rstrip(".") or "0" for t, _ in points)
    return (
        f'<animate attributeName="{attribute}" values="{values}" keyTimes="{times}" '
        f'dur="{T:g}s" repeatCount="indefinite"/>'
    )


def _flash(*spans: tuple[float, float], ramp: float = 0.15) -> list:
    """Hidden at rest, shown during each (on, off) span."""
    points = []
    for on, off in spans:
        points += [(on, 0), (on + ramp, 1), (off, 1), (off + ramp, 0)]
    return points


def _unflash(*spans: tuple[float, float], ramp: float = 0.15) -> list:
    """Shown at rest, hidden during each span: the other state of a _flash mark."""
    return [(t, 1 - v) for t, v in _flash(*spans, ramp=ramp)]


def _swap(on: float, off: float, ramp: float = 0.15) -> tuple[list, list]:
    """Two labels taking turns on one spot, in sequence: (the resting one, the other).

    The resting label fades out over the first ramp and the other fades in over the next;
    on the way back the other one leaves first. They never show at once, so the line
    never reads as two words printed over each other.
    """
    return _unflash((on, off + ramp), ramp=ramp), _flash((on + ramp, off), ramp=ramp)


def _back(at: float, rest: float = REST) -> list:
    """Shown at rest, cleared at `rest`, back from `at`: the rest frame is the finished one."""
    return [(rest, 1), (rest + CLEAR, 0), (at, 0), (at + 0.3, 1)]


def _hidden(body: str, points: list) -> str:
    """A mark that exists only in transit: hidden at rest, its own loop shows it."""
    return f'<g opacity="0">{_anim("opacity", points)}{body}</g>'


def _resting(body: str, points: list) -> str:
    """A mark of the finished state: shown at rest, its own loop clears and restores it."""
    return f"<g>{_anim('opacity', points)}{body}</g>"


# ---------------------------------------------------------------- shapes
def _poly(points: list[Point]) -> str:
    return "M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in points)


def _check(cx: float, cy: float, r: float, color: str = kit.GREEN) -> str:
    """An ok mark: a ring with a tick."""
    k = r / 8
    return (
        f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="none" stroke="{color}" stroke-width="1.4"/>'
        f'<path d="{kit.TICK}" fill="none" stroke="{color}" stroke-width="{_n(1.6 / k)}" stroke-linecap="round" '
        f'stroke-linejoin="round" transform="translate({_n(cx)} {_n(cy)}) scale({_n(k)})"/>'
    )


def _cross(cx: float, cy: float, r: float) -> str:
    """A refused mark: a ring with an X, in ink rather than a status colour."""
    a = r * 0.38
    return (
        f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="none" stroke="{kit.INK}" stroke-width="1.4"/>'
        f'<path d="M{_n(cx - a)} {_n(cy - a)}L{_n(cx + a)} {_n(cy + a)}M{_n(cx + a)} {_n(cy - a)}'
        f'L{_n(cx - a)} {_n(cy + a)}" stroke="{kit.INK}" stroke-width="1.6" stroke-linecap="round"/>'
    )


def _clock(cx: float, cy: float, r: float) -> str:
    """A waiting mark: a clock face, amber because the work waits on a person."""
    return (
        f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="none" stroke="{kit.AMBER}" stroke-width="1.4"/>'
        f'<path d="M{_n(cx)} {_n(cy - r * 0.55)}V{_n(cy)}H{_n(cx + r * 0.45)}" fill="none" '
        f'stroke="{kit.AMBER}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
    )


class Scene:
    """One diagram: its wires and their windows, the packets on them, and the tiles over both."""

    def __init__(self, key: str, w: float, h: float, phone: bool) -> None:
        self.key, self.w, self.h, self.phone = key, w, h, phone
        self.micro = kit.MICRO_PHONE if phone else kit.MICRO
        self.r = 4 if phone else 3.5  # a packet's radius
        self.radius = 7 if phone else 8  # a tile's corner
        self.clip = f"wires-{key}"
        self.wires: list[str] = []
        self.windows: list[Box] = []
        self.packets: list[str] = []
        self.tiles: list[str] = []

    # ------------------------------------------------ text
    def width(self, label: str) -> float:
        return kit.text_width(label, self.micro, True, kit.TRACK) - kit.TRACK

    def baseline(self, middle: float) -> float:
        return middle + self.micro * 0.36

    def label(
        self, x: float, y: float, label: str, fill: str = kit.META, anchor: str = ""
    ) -> str:
        return kit.text(x, y, label, self.micro, fill, "m", anchor)

    def lane(self, x: float, y: float, name: str, note: str) -> None:
        """A lane's mono label: its name in blue, then a line of data, as one text so the gap holds."""
        self.tiles.append(
            f'<text class="m" x="{_n(x)}" y="{_n(y)}" font-size="{self.micro:g}" fill="{kit.META}">'
            f'<tspan fill="{kit.BLUE_LIGHT}">{kit.esc(name)}</tspan>{kit.esc(SEPARATOR + note)}</text>'
        )

    # ------------------------------------------------ tiles
    def node(self, key: str, box: Box, inner: str, r: float = 0) -> None:
        """A tile and everything drawn inside it, tagged so the tests can hold each label to its tile."""
        x, y, w, h = box
        self.tiles.append(
            f'<g data-node="{key}">'
            + _rect(x, y, w, h, r or self.radius, kit.BG, kit.HAIR_STRONG)
            + inner
            + "</g>"
        )

    def lit(self, box: Box, points: list, r: float = 0) -> str:
        """A tile's border and tint lighting for a beat."""
        x, y, w, h = box
        return _hidden(
            _rect(x, y, w, h, r or self.radius, kit.BLUE_TINT, kit.BLUE_EDGE), points
        )

    def chip(
        self,
        x: float,
        y: float,
        label: str,
        h: float,
        color: str = kit.BLUE_LIGHT,
        fill: str = kit.BLUE_TINT,
        stroke: str = kit.BLUE_EDGE,
        dashed: bool = False,
    ) -> tuple[str, float]:
        """A mono pill inside a tile. Returns (svg, width)."""
        width = self.width(label) + 12
        dash = ' stroke-dasharray="3 2"' if dashed else ""
        return (
            _rect(x, y, width, h, h / 2, fill, stroke, dash)
            + self.label(
                x + width / 2, self.baseline(y + h / 2), label, color, "middle"
            ),
            width,
        )

    def two_lines(self, box: Box, name: str, caption: str, code: bool = False) -> str:
        """A tile's name and, under it, a caption (a tool name sets in code type)."""
        x, y, _, h = box
        pad = 12 if self.phone else 14
        first, second = self.lines(box)
        below = (
            kit.text(x + pad, second, caption, self.micro, kit.META, "c")
            if code
            else self.label(x + pad, second, caption)
        )
        return self.label(x + pad, first, name, NAME) + below

    def lines(self, box: Box) -> tuple[float, float]:
        """The two baselines of a two-line tile."""
        _, y, _, h = box
        middle = y + h / 2
        return (middle - 2, middle + 13) if self.phone else (middle - 3, middle + 12)

    def status(self, box: Box, glyph: str, word: str, color: str) -> tuple[str, str]:
        """A state at a tile's right: the mark on the name line, its word under it. Returns (mark, word)."""
        x, _, w, _ = box
        first, second = self.lines(box)
        right = x + w - (12 if self.phone else 14)
        r = 7 if self.phone else 8
        cy = first - self.micro * 0.36
        marks = {"check": _check, "cross": _cross}
        return (
            marks[glyph](right - r, cy, r),
            self.label(right, second, word, color, "end"),
        )

    # ------------------------------------------------ wires and packets
    def wire(self, points: list[Point], dashed: bool = False) -> None:
        """A wire from one tile's edge to another's, and the windows a packet shows through on it.

        Each window covers one segment and the packet's width on either side.
        At a bend it runs on past the corner so the packet turns it whole; at
        the two ends it stops at the tile's edge.
        """
        dash = ' stroke-dasharray="4 4"' if dashed else ""
        self.wires.append(
            f'<path d="{_poly(points)}" fill="none" stroke="{WIRE}" stroke-width="1.2"{dash}/>'
        )
        pad, last = self.r + 1, len(points) - 2
        for index, (a, b) in enumerate(pairwise(points)):
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            edges = [x0 - pad, y0 - pad, x1 + pad, y1 + pad]
            for end, at_tile in ((a, index == 0), (b, index == last)):
                if not at_tile:
                    continue
                if a[1] == b[1]:  # a horizontal segment stops at the tile's side
                    edges[0 if end[0] == x0 else 2] = end[0]
                else:  # a vertical one at its top or bottom
                    edges[1 if end[1] == y0 else 3] = end[1]
            self.windows.append(
                (edges[0], edges[1], edges[2] - edges[0], edges[3] - edges[1])
            )

    def packet(
        self, route: list[Point], stops: list[tuple[float, Point]], fade: float = 0.08
    ) -> None:
        """A packet that rides `route`, at each (seconds, point) in `stops`; hidden before and after."""
        lengths = [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in pairwise(route)]
        total = sum(lengths)

        def share(point: Point) -> float:
            run = 0.0
            for (a, b), length in zip(pairwise(route), lengths):
                on_x = min(a[0], b[0]) - 0.01 <= point[0] <= max(a[0], b[0]) + 0.01
                on_y = min(a[1], b[1]) - 0.01 <= point[1] <= max(a[1], b[1]) + 0.01
                if on_x and on_y:
                    return (run + abs(point[0] - a[0]) + abs(point[1] - a[1])) / total
                run += length
            raise ValueError(f"{point} is not on the route")

        points = [(t, share(p)) for t, p in stops]
        if points[0][0] > 0:
            points.insert(0, (0, points[0][1]))
        if points[-1][0] < T:
            points.append((T, points[-1][1]))
        key_points = ";".join(f"{p:.4f}" for _, p in points)
        key_times = ";".join(
            f"{t / T:.4f}".rstrip("0").rstrip(".") or "0" for t, _ in points
        )
        start, end = stops[0][0], stops[-1][0]
        self.packets.append(
            f'<circle r="{_n(self.r)}" fill="{kit.SKY}" opacity="0">'
            f'<animateMotion dur="{T:g}s" repeatCount="indefinite" calcMode="linear" '
            f'keyPoints="{key_points}" keyTimes="{key_times}" path="{_poly(route)}"/>'
            + _anim(
                "opacity", [(start, 0), (start + 0.05, 1), (end, 1), (end + fade, 0)]
            )
            + "</circle>"
        )

    def svg(self) -> tuple[str, str]:
        """(defs, body): the clip of wire windows, then wires, packets and tiles in that order."""
        windows = "".join(
            f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}"/>'
            for x, y, w, h in self.windows
        )
        defs = f'<clipPath id="{self.clip}">{windows}</clipPath>'
        body = (
            "".join(self.wires)
            + f'<g clip-path="url(#{self.clip})">{"".join(self.packets)}</g>'
            + "".join(self.tiles)
        )
        return defs, body


def _centre(box: Box) -> Point:
    x, y, w, h = box
    return x + w / 2, y + h / 2


# ---------------------------------------------------------------- agentcore: the lead card
# The finished state: the call allowed, ask_architect lit, the harness up, the
# version passed and pinned to PROD. Hold it, clear it, then five 2 s beats.
# 2 s: Claude Code asks for a tool the policy does not list and is refused at
# the gateway. 4 s: it asks for ask_architect, is allowed and reaches the
# tools. 6 s: ask_architect runs the harness (Claude, 3 skills, memory). 8 s: a
# new version is built and given a test turn on DEFAULT. 10 s: the evaluation
# passes it, it is pinned to PROD, and PROD is what ask_architect calls.
_CLIENTS = ("CLAUDE CODE", "CODEX", "KIRO")
_HARNESS = ("CLAUDE", "3 SKILLS", "MEMORY")
_RELEASE = (
    ("BUILD", "ARM64 IMAGE"),
    ("DEFAULT", "TEST TURN"),
    ("EVAL", "SCORED"),
    ("PROD", "PINNED ENDPOINT"),
)
_TOOL = "ask_architect"
_TOOLS = "9 TOOLS"  # 8 tools plus ask_architect, the pips' 3 x 3 grid
_UNLISTED = "UNLISTED TOOL"  # what the refused call asked for
# Both calls leave one client, so the refusal is about the tool, not the client:
# first a tool the policy does not list (refused), then ask_architect (allowed).
_CALLER = 0
_ASKS = ((2.3, 3.0), (4.0, 4.6))
_DENY = (3.0, 3.85)  # the gateway shows DENY and what was asked for
_RELEASE_BEATS = ((8.0, 8.6), (8.65, 9.2), (9.45, 10.05), (10.4, 11.1))


class _Lead:
    """Where everything sits on the lead card, at 840 or 320."""

    def __init__(self, phone: bool) -> None:
        if phone:
            # one column, 16px between the tiles and 8px either side of the bus
            self.x0, self.x1 = 16, 304
            self.lanes = (24, 258)
            self.clients = [(16, 34, 104, 22), (132, 34, 80, 22), (224, 34, 80, 22)]
            self.bus, self.drop = 64, 172
            self.gateway = (16, 72, 288, 42)
            self.tools = (16, 130, 288, 42)
            self.harness = (16, 188, 288, 48)
            gap, top, h = 6, 270, 34
            seg = (288 - 3 * gap) / 4
            self.release = [(16 + i * (seg + gap), top, seg, h) for i in range(4)]
        else:
            self.x0, self.x1 = 24, 816
            self.lanes = (30, 136)
            # three 16px pills 6px apart: 60px, the gateway's height
            self.clients = [(24, 44 + i * 22, 112, 16) for i in range(3)]
            self.gateway = (172, 44, 176, 60)
            self.tools = (384, 44, 172, 60)
            self.harness = (592, 44, 224, 60)
            self.bus = (136 + 172) / 2
            self.release = [
                (x, 150, w, 40)
                for x, _, w, _ in (
                    self.clients[0],
                    self.gateway,
                    self.tools,
                    self.harness,
                )
            ]
        self.prod_x = _centre(self.release[3])[0]


def _pips(s: Scene) -> tuple[str, str, Point]:
    """The tools as a 3 x 3 grid of pips: eight tools and ask_architect. Returns (grid, lit pip, size)."""
    w, h, gx, gy = (12, 6, 5, 5) if s.phone else (10, 6, 4, 4)
    out = []
    for i in range(9):
        px, py = (i % 3) * (w + gx), (i // 3) * (h + gy)
        # ask_architect's pip is an outline while idle, so its lit fill sits on the tile
        out.append(
            _rect(px, py, w, h, 1.5, W30)
            if i < 8
            else _rect(px + 0.5, py + 0.5, w - 1, h - 1, 1.5, "none", W30)
        )
    lit = _rect(2 * (w + gx), 2 * (h + gy), w, h, 1.5, kit.BLUE_LIGHT)
    return "".join(out), lit, (3 * w + 2 * gx, 3 * h + 2 * gy)


def _agentcore(s: Scene) -> None:
    """The request lane over the release lane."""
    g = _Lead(s.phone)
    pad = 12 if s.phone else 14
    s.lane(
        g.x0,
        g.lanes[0],
        "REQUEST",
        "MCP CALLS, DEFAULT DENY"
        if s.phone
        else "MCP CALLS, DEFAULT-DENY CEDAR POLICY",
    )
    s.lane(
        g.x0,
        g.lanes[1],
        "RELEASE",
        "EVAL BEFORE PROD" if s.phone else "PROD ONLY AFTER AN EVAL PASSES",
    )

    # ------------------------------------------------ the clients, one of which calls twice
    for i, (name, box) in enumerate(zip(_CLIENTS, g.clients)):
        x, y, w, h = box
        tx, anchor = (x + w / 2, "middle") if s.phone else (x + 10, "")
        ty = s.baseline(y + h / 2)
        label = s.label(tx, ty, name, NAME, anchor)
        if i == _CALLER:
            label = (
                s.lit(box, _flash(*_ASKS), 6)
                + label
                + _hidden(s.label(tx, ty, name, kit.BLUE_LIGHT, anchor), _flash(*_ASKS))
            )
        s.node(f"client-{i}", box, label, 6)

    gx, gy, gw, gh = g.gateway
    tx, ty, tw, th = g.tools
    hx, hy, hw, hh = g.harness
    cy = gy + gh / 2  # the desktop request lane's centre line
    for x, y, w, h in g.clients:
        if s.phone:
            c = x + w / 2
            route = [(c, y + h), (c, g.bus), (g.drop, g.bus), (g.drop, gy)]
            s.wire(route if abs(c - g.drop) > 1 else [(c, y + h), (c, gy)])
        else:
            middle = y + h / 2
            route = [(x + w, middle), (g.bus, middle), (g.bus, cy), (gx, cy)]
            s.wire(route if abs(middle - cy) > 1 else [(x + w, middle), (gx, cy)])
    if s.phone:
        s.wire([(g.drop, gy + gh), (g.drop, ty)])
        s.wire([(g.drop, ty + th), (g.drop, hy)])
    else:
        s.wire([(gx + gw, cy), (tx, cy)])
        s.wire([(tx + tw, cy), (hx, cy)])

    # ------------------------------------------------ the gateway: refused, then allowed
    # while it refuses, the caption under GATEWAY says what was asked for; the two
    # captions swap in sequence, and DENY shows exactly while the refused tool does
    allow_mark, allow_word = s.status(g.gateway, "check", "ALLOW", kit.GREEN)
    deny_mark, deny_word = s.status(g.gateway, "cross", "DENY", kit.INK)
    first, second = s.lines(g.gateway)
    policy, refused = _swap(*_DENY)
    s.node(
        "gateway",
        g.gateway,
        s.lit(g.gateway, _flash((3.0, 3.7), (4.65, 5.15)))
        + s.label(gx + pad, first, "GATEWAY", NAME)
        + _resting(s.label(gx + pad, second, "CEDAR POLICY"), policy)
        + _hidden(s.label(gx + pad, second, _UNLISTED, kit.INK), refused)
        + _hidden(deny_mark + deny_word, refused)
        + _resting(allow_mark + allow_word, _back(4.8)),
    )

    # ------------------------------------------------ the tools runtime
    grid, pip, (grid_w, grid_h) = _pips(s)
    offset = f'transform="translate({_n(tx + tw - pad - grid_w)} {_n(ty + (th - grid_h) / 2)})"'
    _, second = s.lines(g.tools)
    s.node(
        "tools",
        g.tools,
        s.lit(g.tools, _flash((5.4, 6.05)))
        + s.two_lines(g.tools, _TOOLS, _TOOL, code=True)
        + f"<g {offset}>{grid}</g>"
        + _resting(
            f"<g {offset}>{pip}</g>"
            + kit.text(tx + pad, second, _TOOL, s.micro, kit.BLUE_LIGHT, "c"),
            _back(5.5),
        ),
    )

    # ------------------------------------------------ the harness: Claude, the skills, memory
    chip_h = 20 if s.phone else 18
    chips_y = hy + hh - chip_h - (6 if s.phone else 8)
    dim, lit, x = [], [], hx + pad
    for i, label in enumerate(_HARNESS):
        svg, width = s.chip(
            x, chips_y, label, chip_h, kit.META, kit.BG, kit.HAIR_STRONG
        )
        dim.append(svg)
        lit.append(_resting(s.chip(x, chips_y, label, chip_h)[0], _back(6.7 + 0.3 * i)))
        x += width + CHIP_GAP
    s.node(
        "harness",
        g.harness,
        s.lit(g.harness, _flash((6.4, 7.2), (11.2, 11.8)))
        + s.label(hx + pad, hy + (16 if s.phone else 20), "HARNESS", NAME)
        + "".join(dim)
        + "".join(lit),
    )

    # ------------------------------------------------ the two calls, both from the caller
    # the refused one stops at the gateway and falls back along its wire
    caller = g.clients[_CALLER]
    gate, tool, hub = _centre(g.gateway), _centre(g.tools), _centre(g.harness)
    if s.phone:
        c, start = _centre(caller)
        d = g.drop
        s.packet(
            [(c, start), (c, g.bus), (d, g.bus), (d, gy)],
            [
                (2.4, (c, start)),
                (2.5, (c, caller[1] + caller[3])),
                (2.6, (c, g.bus)),
                (2.85, (d, g.bus)),
                (3.0, (d, gy)),
                (3.15, (d, gy - 6)),
            ],
            fade=0.3,
        )
        s.packet(
            [(c, start), (c, g.bus), (d, g.bus), (d, hub[1])],
            [
                (4.1, (c, start)),
                (4.2, (c, caller[1] + caller[3])),
                (4.3, (c, g.bus)),
                (4.55, (d, g.bus)),
                (4.65, (d, gy)),
                (4.75, (d, gate[1])),
                (4.95, (d, gate[1])),
                (5.05, (d, gy + gh)),
                (5.35, (d, ty)),
                (5.45, (d, tool[1])),
                (6.0, (d, tool[1])),
                (6.1, (d, ty + th)),
                (6.4, (d, hy)),
                (6.5, (d, hub[1])),
            ],
        )
    else:
        inside = caller[0] + 60
        top = _centre(caller)[1]
        s.packet(
            [(inside, top), (g.bus, top), (g.bus, cy), (gx, cy)],
            [
                (2.4, (inside, top)),
                (2.55, (caller[0] + caller[2], top)),
                (2.7, (g.bus, top)),
                (2.82, (g.bus, cy)),
                (3.0, (gx, cy)),
                (3.15, (gx - 10, cy)),
            ],
            fade=0.3,
        )
        s.packet(
            [(inside, top), (g.bus, top), (g.bus, cy), (hub[0], cy)],
            [
                (4.1, (inside, top)),
                (4.25, (caller[0] + caller[2], top)),
                (4.4, (g.bus, top)),
                (4.5, (g.bus, cy)),
                (4.65, (gx, cy)),
                (4.75, (gate[0], cy)),
                (4.95, (gate[0], cy)),
                (5.05, (gx + gw, cy)),
                (5.35, (tx, cy)),
                (5.45, (tool[0], cy)),
                (6.0, (tool[0], cy)),
                (6.1, (tx + tw, cy)),
                (6.4, (hx, cy)),
                (6.5, (hub[0], cy)),
            ],
        )

    # ------------------------------------------------ the release lane
    for (name, caption), box, beat in zip(_RELEASE, g.release, _RELEASE_BEATS):
        x, y, w, h = box
        middle = y + h / 2
        if s.phone:
            # a stepper: four segments that light in turn, no captions
            mark = ""
            if name == "EVAL":
                mark = _resting(_check(x + w - 13, middle, 6.5), _back(9.7))
            elif name == "PROD":
                mark = kit.live_dot(x + w - 12, middle, r=3)
            label = (
                s.label(x + 9, s.baseline(middle), name, NAME)
                if mark
                else s.label(x + w / 2, s.baseline(middle), name, NAME, "middle")
            )
            s.node(
                f"release-{name.lower()}",
                box,
                s.lit(box, _flash(beat), 6) + label + mark,
                6,
            )
            continue
        mark = ""
        if name == "EVAL":
            check, word = s.status(box, "check", "PASS", kit.GREEN)
            mark = _resting(check + word, _back(9.7))
        elif name == "PROD":
            first, second = s.lines(box)
            right = x + w - pad
            mark = kit.live_dot(right - 4, first - s.micro * 0.36, r=3.5) + s.label(
                right, second, "LIVE", kit.GREEN, "end"
            )
        s.node(
            f"release-{name.lower()}",
            box,
            s.lit(box, _flash(beat)) + s.two_lines(box, name, caption) + mark,
        )
    middle = _centre(g.release[0])[1]
    if not s.phone:
        for a, b in pairwise(g.release):
            s.wire([(a[0] + a[2], middle), (b[0], middle)])
        stages = [_centre(box)[0] for box in g.release]
        edges = [(box[0], box[0] + box[2]) for box in g.release]
        s.packet(
            [(g.x0 + 60, middle), (g.prod_x, middle)],
            [
                (8.1, (g.x0 + 60, middle)),
                (8.2, (edges[0][1], middle)),
                (8.5, (edges[1][0], middle)),
                (8.6, (stages[1], middle)),
                (9.1, (stages[1], middle)),
                (9.2, (edges[1][1], middle)),
                (9.5, (edges[2][0], middle)),
                (9.6, (stages[2], middle)),
                (10.0, (stages[2], middle)),
                (10.1, (edges[2][1], middle)),
                (10.4, (edges[3][0], middle)),
                (10.5, (g.prod_x, middle)),
            ],
        )
    # PROD is the endpoint the harness answers on: the promotion climbs to it
    top = g.release[3][1]
    s.wire([(g.prod_x, top), (g.prod_x, hy + hh)])
    s.packet(
        [(g.prod_x, middle), (g.prod_x, hub[1])],
        [
            (10.7, (g.prod_x, middle)),
            (10.8, (g.prod_x, top)),
            (11.1, (g.prod_x, hy + hh)),
            (11.2, (g.prod_x, hub[1])),
        ],
    )


# ---------------------------------------------------------------- organizations: the OU tree
# The tree as the sample's examples draw it: Control Tower's Security and
# Sandbox OUs, Workloads with Production and Non-Production (examples/standard,
# where the SCP and the RCP both target Workloads). The deployment runs in one
# place, the organization's management account, joined to ROOT: every policy
# and the delegation leave it and travel down the tree. The finished state: SCP
# and RCP attached to Workloads and inherited by the two OUs below it (the
# dashed chips), and the Security OU holding the delegated administrator. Four
# 3 s beats: hold, the SCP leaves the management account, attaches and
# cascades, then the RCP, then delegated administration reaches Security. The
# desktop is a top-down tree with the management account beside ROOT; the
# phone draws the same tree as an outline, one OU to a row, with the
# management account on ROOT's row.
_MGMT = "MGMT ACCOUNT"
_SPEED = 200  # px a second, for a packet's trip down the tree
_OUS = {
    "root": "ROOT",
    "security": "SECURITY",
    "workloads": "WORKLOADS",
    "sandbox": "SANDBOX",
    "production": "PRODUCTION",
    "non-production": "NON-PRODUCTION",
}
_UNDER_ROOT = ("security", "workloads", "sandbox")
_UNDER_WORKLOADS = ("production", "non-production")
_POLICIES = ("SCP", "RCP")
_ADMIN = "DELEGATED ADMIN"
_ORG_BEATS = {"SCP": 3.0, "RCP": 6.0, _ADMIN: 9.0}
_ORG_REST = (
    2.4  # the attached policies hold a little longer than the other cards' frame
)


def _org_tiles(phone: bool) -> dict[str, Box]:
    if phone:
        rows = (
            "root",
            "security",
            "workloads",
            "production",
            "non-production",
            "sandbox",
        )
        level = {"root": 0, "production": 2, "non-production": 2}
        out = {"mgmt": (148, 16, 156, 30)}  # on ROOT's row, right of it
        for i, key in enumerate(rows):
            x = 16 + 24 * level.get(key, 1)
            right = 100 if key == "root" else 304
            out[key] = (x, 16 + 36 * i, right - x, 30)
        return out
    return {
        "mgmt": (24, 14, 144, 26),  # left of ROOT, over Security's column
        "root": (206, 14, 64, 26),
        "security": (24, 64, 144, 50),
        "workloads": (184, 64, 108, 50),
        "sandbox": (308, 64, 68, 50),
        "production": (120, 136, 96, 50),
        "non-production": (232, 136, 124, 50),
    }


def _org_routes(tiles: dict[str, Box], phone: bool) -> dict[str, list[Point]]:
    """The wire from each OU's parent down to it."""
    rx, ry, rw, rh = tiles["root"]
    wx, wy, ww, wh = tiles["workloads"]
    routes = {}
    if phone:
        for key in _UNDER_ROOT:
            x, mid = tiles[key][0], _centre(tiles[key])[1]
            routes[key] = [(28, ry + rh), (28, mid), (x, mid)]
        for key in _UNDER_WORKLOADS:
            x, mid = tiles[key][0], _centre(tiles[key])[1]
            routes[key] = [(52, wy + wh), (52, mid), (x, mid)]
        return routes
    trunk = rx + rw / 2
    for parent, keys, bottom in (
        ("root", _UNDER_ROOT, ry + rh),
        ("workloads", _UNDER_WORKLOADS, wy + wh),
    ):
        bus = bottom + 11
        for key in keys:
            x, top = _centre(tiles[key])[0], tiles[key][1]
            routes[key] = (
                [(trunk, bottom), (trunk, top)]
                if abs(x - trunk) < 1
                else [(trunk, bottom), (trunk, bus), (x, bus), (x, top)]
            )
    return routes


def _org(s: Scene) -> None:
    tiles = _org_tiles(s.phone)
    routes = _org_routes(tiles, s.phone)
    mx, my, mw, mh = tiles["mgmt"]
    rx, ry, rw, rh = tiles["root"]
    level = ry + rh / 2  # the management account and ROOT share a centre line
    # the link from the management account's edge to ROOT's: left of it on the
    # desktop, right of it on the phone
    edge = mx + mw if mx < rx else mx
    link = [(edge, level), (rx if mx < rx else rx + rw, level)]
    s.wire(link)
    for route in routes.values():
        s.wire(route)

    def tail(route: list[Point]) -> Point:
        bx, by = route[-1]
        return (bx + 8, by) if s.phone else (bx, by + 8)

    def from_mgmt(key: str) -> list[Point]:
        """Out of the management account, through ROOT, down the tree into `key`."""
        inside = (edge - 8 if mx < rx else edge + 8, level)
        trunk = (routes[key][0][0], level)
        return [inside, *link, trunk, *routes[key], tail(routes[key])]

    def from_parent(key: str) -> list[Point]:
        """Out of the OU above `key`, down the wire, into `key`."""
        ax, ay = routes[key][0]
        return [(ax, ay - 8), *routes[key], tail(routes[key])]

    def trip(path: list[Point], at: float) -> float:
        """A packet along `path` at one speed from `at`; returns when it is inside the tile."""
        stops, t = [(at, path[0])], at
        for a, b in pairwise(path):
            t += (abs(b[0] - a[0]) + abs(b[1] - a[1])) / _SPEED
            stops.append((t, b))
        s.packet(path, stops)
        return t

    flashes: dict[str, list] = {key: [] for key in tiles}
    returns: dict[tuple[str, str], float] = {}  # (OU, chip) -> when it is back
    for policy in (*_POLICIES, _ADMIN):
        at = _ORG_BEATS[policy]
        flashes["mgmt"].append((at, at + 0.6))
        target = "security" if policy == _ADMIN else "workloads"
        arrive = trip(from_mgmt(target), at + 0.1)
        flashes[target].append((arrive - 0.05, arrive + 0.7))
        returns[target, policy] = arrive
        if policy == _ADMIN:
            continue
        for key in _UNDER_WORKLOADS:
            below = trip(from_parent(key), arrive + 0.3)
            flashes[key].append((below - 0.05, below + 0.65))
            returns[key, policy] = below

    chip_h = 20 if s.phone else 18
    pad = 12 if s.phone else 10
    mgmt_x, anchor = (mx + pad, "") if s.phone else (mx + mw / 2, "middle")
    s.node(
        "mgmt",
        tiles["mgmt"],
        s.lit(tiles["mgmt"], _flash(*flashes["mgmt"]))
        + s.label(mgmt_x, s.baseline(level), _MGMT, NAME, anchor),
    )
    for key, name in _OUS.items():
        box = tiles[key]
        x, y, w, h = box
        marks = ""
        labels = (
            [_ADMIN]
            if key == "security"
            else list(_POLICIES)
            if key in ("workloads", *_UNDER_WORKLOADS)
            else []
        )
        widths = [s.width(label) + 12 for label in labels]
        if s.phone:
            cx = x + w - 8 - (sum(widths) + CHIP_GAP * (len(widths) - 1))
            chip_y = y + (h - chip_h) / 2
        else:
            cx, chip_y = x + pad, y + h - chip_h - 7
        for label, width in zip(labels, widths):
            if key in _UNDER_WORKLOADS:
                # inherited, not attached here: a dashed outline in the caption colour
                svg, _ = s.chip(
                    cx, chip_y, label, chip_h, kit.META, "none", kit.META, dashed=True
                )
            else:
                svg, _ = s.chip(cx, chip_y, label, chip_h)
            # each chip is back as its packet arrives
            marks += _resting(svg, _back(returns[key, label], _ORG_REST))
            cx += width + CHIP_GAP
        one_line = s.phone or not labels
        name_y = s.baseline(y + h / 2) if one_line else y + 19
        if key == "root" and not s.phone:
            text = s.label(x + w / 2, name_y, name, NAME, "middle")
        elif key == "sandbox" and not s.phone:
            text = s.label(x + w / 2, name_y, name, NAME, "middle")
        else:
            text = s.label(x + pad, name_y, name, NAME)
        flash = s.lit(box, _flash(*flashes[key])) if flashes[key] else ""
        s.node(key, box, flash + text + marks)


# ---------------------------------------------------------------- sagemaker: the MLOps loop
# A clockwise loop: DATA into TRAIN (three models in parallel), the quality and
# fairness GATE, APPROVE (the model waits as PendingManualApproval until a
# person approves it), DEPLOY (a 10% canary, then the whole fleet), SERVE,
# MONITOR, and back up to TRAIN when drift is found. Hold, clear, then five 2 s
# beats: a batch trains, the gates pass and the model waits, a person
# approves, the canary rolls out and serves, drift sends it back to train.
_DRIFT = "RETRAIN ON DRIFT"


def _mlops_tiles(phone: bool) -> dict[str, Box]:
    if phone:
        top, bottom, h = 70, 166, 48
        cols = ((16, 80), (120, 80), (224, 80))
        out = {"data": (16, 16, 288, 30)}
    else:
        top, bottom, h = 28, 124, 48
        cols = ((112, 72), (212, 64), (304, 72))
        out = {"data": (24, 28, 60, 144)}
    for (x, w), key in zip(cols, ("train", "gate", "approve")):
        out[key] = (x, top, w, h)
    for (x, w), key in zip(cols, ("monitor", "serve", "deploy")):
        out[key] = (x, bottom, w, h)
    return out


def _mlops(s: Scene) -> None:
    tiles = _mlops_tiles(s.phone)
    pad = 10

    def side(key: str, where: str) -> Point:
        x, y, w, h = tiles[key]
        cx, cy = _centre(tiles[key])
        return {
            "left": (x, cy),
            "right": (x + w, cy),
            "top": (cx, y),
            "bottom": (cx, y + h),
        }[where]

    train_x, top_y = _centre(tiles["train"])
    gate_x = _centre(tiles["gate"])[0]
    approve_x = _centre(tiles["approve"])[0]
    serve_x, bottom_y = _centre(tiles["serve"])
    dx, dy, dw, dh = tiles["data"]
    # DATA hands its batch to TRAIN: down on the phone, across on the desktop
    leave, enter = (
        ((train_x, dy + dh), side("train", "top"))
        if s.phone
        else ((dx + dw, top_y), side("train", "left"))
    )
    start = (train_x, dy + dh / 2) if s.phone else (dx + dw / 2, top_y)

    # ------------------------------------------------ wires
    s.wire([leave, enter])
    s.wire([side("train", "right"), side("gate", "left")])
    s.wire([side("gate", "right"), side("approve", "left")])
    s.wire([side("approve", "bottom"), side("deploy", "top")])
    s.wire([side("deploy", "left"), side("serve", "right")])
    s.wire([side("serve", "left"), side("monitor", "right")])
    s.wire([side("monitor", "top"), side("train", "bottom")], dashed=True)
    middle = s.baseline(
        (tiles["train"][1] + tiles["train"][3] + tiles["monitor"][1]) / 2
    )
    s.tiles.append(
        s.label(train_x + 9, middle, _DRIFT)
        + _hidden(
            s.label(train_x + 9, middle, _DRIFT, kit.BLUE_LIGHT), _flash((10.9, 11.8))
        )
    )

    # ------------------------------------------------ the model's trip round the loop, then drift back up
    route = [start, (approve_x, top_y), (approve_x, bottom_y), (train_x, bottom_y)]
    if s.phone:
        route = [start, (train_x, top_y), *route[1:]]
    s.packet(
        route,
        [
            (2.55, start),
            (2.65, leave),
            (2.95, enter),
            (3.05, (train_x, top_y)),
            (4.0, (train_x, top_y)),
            (4.1, side("train", "right")),
            (4.4, side("gate", "left")),
            (4.5, (gate_x, top_y)),
            (4.95, (gate_x, top_y)),
            (5.05, side("gate", "right")),
            (5.35, side("approve", "left")),
            (5.45, (approve_x, top_y)),
            (7.1, (approve_x, top_y)),
            (7.2, side("approve", "bottom")),
            (7.6, side("deploy", "top")),
            (7.7, (approve_x, bottom_y)),
            (9.2, (approve_x, bottom_y)),
            (9.3, side("deploy", "left")),
            (9.6, side("serve", "right")),
            (9.7, (serve_x, bottom_y)),
            (9.95, (serve_x, bottom_y)),
            (10.05, side("serve", "left")),
            (10.35, side("monitor", "right")),
            (10.45, (train_x, bottom_y)),
        ],
    )
    s.packet(
        [(train_x, bottom_y), (train_x, top_y)],
        [
            (11.0, (train_x, bottom_y)),
            (11.1, side("monitor", "top")),
            (11.5, side("train", "bottom")),
            (11.6, (train_x, top_y)),
        ],
    )

    def head(key: str, name: str) -> str:
        x, y, _, _ = tiles[key]
        return s.label(x + pad, y + (20 if s.phone else 19), name, NAME)

    # ------------------------------------------------ DATA: two classes of images, a batch landing in S3
    images, batch = [], []
    if s.phone:
        (iw, ih), gap, cols, rows = (14, 10), 6, 10, 1
        ix, iy = dx + 78, dy + (dh - 10) / 2
    else:
        (iw, ih), gap, cols, rows = (14, 12), 6, 2, 4
        ix, iy = dx + (dw - 34) / 2, dy + 36
    for row in range(rows):
        for col in range(cols):
            px, py = ix + col * (iw + gap), iy + row * (ih + gap)
            images.append(_rect(px, py, iw, ih, 2, W07, kit.HAIR_STRONG))
            batch.append(_rect(px, py, iw, ih, 2, kit.BLUE_TINT, kit.BLUE_LIGHT))
    if s.phone:
        name = s.label(dx + pad + 2, s.baseline(dy + dh / 2), "DATA", NAME)
    else:
        name = s.label(dx + dw / 2, dy + 22, "DATA", NAME, "middle") + s.label(
            dx + dw / 2, dy + dh - 12, "S3", kit.META, "middle"
        )
    s.node(
        "data",
        tiles["data"],
        name + "".join(images) + _hidden("".join(batch), _flash((2.2, 2.9))),
    )

    # ------------------------------------------------ TRAIN: three models in parallel
    box = tiles["train"]
    x, y, w, h = box
    bars, bw = [], (w - 2 * pad - 8) / 3
    for i in range(3):
        bx = x + pad + i * (bw + 4)
        bars.append(_rect(bx, y + h - 14, bw, 4, 2, W07))
        bars.append(
            _resting(
                _rect(bx, y + h - 14, bw, 4, 2, kit.BLUE_LIGHT), _back(3.3 + 0.25 * i)
            )
        )
    s.node(
        "train",
        box,
        s.lit(box, _flash((3.0, 3.95), (11.55, 11.8)))
        + head("train", "TRAIN")
        + "".join(bars),
    )

    # ------------------------------------------------ GATE: quality, then fairness
    box = tiles["gate"]
    x, y, w, h = box
    checks = "".join(
        _resting(_check(x + pad + 6 + i * 17, y + h - 12, 6), _back(4.55 + 0.2 * i))
        for i in range(2)
    )
    s.node("gate", box, s.lit(box, _flash((4.4, 5.0))) + head("gate", "GATE") + checks)

    # ------------------------------------------------ APPROVE: amber while the model waits, then ok
    box = tiles["approve"]
    x, y, w, h = box
    mx, my = x + pad + 6, y + h - 12
    s.node(
        "approve",
        box,
        s.lit(box, _flash((6.6, 7.2)))
        + head("approve", "APPROVE")
        + _hidden(_clock(mx, my, 6), _flash((5.45, 6.75)))
        + _resting(_check(mx, my, 6), _back(6.75)),
    )

    # ------------------------------------------------ DEPLOY: a 10% canary, then the whole fleet
    box = tiles["deploy"]
    x, y, w, h = box
    track, by = w - 2 * pad, y + h - 14
    s.node(
        "deploy",
        box,
        s.lit(box, _flash((7.7, 9.3)))
        + head("deploy", "DEPLOY")
        + _rect(x + pad, by, track, 4, 2, W07)
        + _hidden(_rect(x + pad, by, track * 0.1, 4, 2, kit.SKY), _flash((8.0, 9.0)))
        + _resting(_rect(x + pad, by, track, 4, 2, kit.BLUE_LIGHT), _back(9.0)),
    )

    # ------------------------------------------------ SERVE: live throughout; the new model takes over in it
    box = tiles["serve"]
    x, y, w, h = box
    s.node(
        "serve",
        box,
        s.lit(box, _flash((9.6, 10.1)))
        + head("serve", "SERVE")
        + kit.live_dot(x + pad + 4, y + h - 12, r=3),
    )

    # ------------------------------------------------ MONITOR: the drift score rises and sends it back
    box = tiles["monitor"]
    x, y, w, h = box
    values = (0.2, 0.25, 0.15, 0.3, 0.2, 0.35, 0.9)
    span, base = w - 2 * pad, y + h - 8
    line = _poly(
        [
            (x + pad + span * i / (len(values) - 1), base - 9 * v)
            for i, v in enumerate(values)
        ]
    )
    s.node(
        "monitor",
        box,
        s.lit(box, _flash((10.35, 11.0)))
        + head("monitor", "MONITOR")
        + f'<path d="{line}" fill="none" stroke="{kit.META}" stroke-width="1.4" stroke-linejoin="round"/>'
        + _hidden(
            f'<path d="{line}" fill="none" stroke="{kit.SKY}" stroke-width="1.6" stroke-linejoin="round"/>',
            _flash((10.5, 11.5)),
        ),
    )


# ---------------------------------------------------------------- the cards
# key -> (diagram, what it shows for the aria-label, desktop width, desktop
# diagram height, phone diagram height)
DIAGRAMS: dict[str, tuple[Callable[[Scene], None], str, int, int, int]] = {
    "agentcore-harness": (
        _agentcore,
        "MCP clients such as Claude Code, Codex and Kiro call AgentCore Gateway, whose default-deny "
        "Cedar policy refuses Claude Code's call for a tool it does not list, then allows its "
        "call for ask_architect, one of 9 tools; ask_architect runs the AgentCore harness with "
        "Claude, 3 skills and memory, and a new version reaches the pinned PROD endpoint only "
        "after an evaluation passes",
        WIDE,
        208,
        318,
    ),
    "org-governance": (
        _org,
        "from the management account, SCP and RCP policies attach to the Workloads OU and are "
        "inherited by Production and Non-Production, and the Security OU gets the delegated "
        "administrator, in an AWS Organizations tree with Root, Security, Workloads and Sandbox",
        HALF,
        200,
        242,
    ),
    "sagemaker-mlops": (
        _mlops,
        "a SageMaker pipeline takes a batch of images, trains three models, passes a quality and "
        "a fairness gate, waits for a person to approve, deploys with a 10% canary, serves, and "
        "retrains when monitoring finds drift",
        HALF,
        200,
        230,
    ),
}


def month(date: str) -> str:
    """'October 2026' as 'OCT 2026'; anything else upper-cased as it is."""
    text = " ".join(str(date or "").split())
    parts = text.split(" ")
    if len(parts) == 2 and parts[0] in MONTHS:
        return f"{MONTHS[parts[0]]} {parts[1]}"
    return text.upper()


def eyebrow(sample: dict) -> str:
    when = month(sample.get("date", ""))
    return f"{SOURCE}{SEPARATOR}{when}" if when else SOURCE


def title_lines(title: str, width: float, size: float = TITLE_SIZE) -> list[str]:
    """The title wrapped to `width`; past TITLE_ROWS lines the last one ends in three dots."""
    lines = kit.wrap_text(str(title), width, size)
    if len(lines) <= TITLE_ROWS:
        return kit.balance(lines)
    kept, last = lines[: TITLE_ROWS - 1], lines[TITLE_ROWS - 1]
    while " " in last and kit.text_width(last + "...", size) > width:
        last = last.rsplit(" ", 1)[0]
    return [*kept, last.rstrip(" ,;:.") + "..."]


def tag_chips(
    tags: list[str],
    x: float,
    y: float,
    room: float,
    size: float,
    height: float,
    right: bool = False,
) -> tuple[str, float]:
    """The tags as chips in their order: the ones that fit and a +N for the rest. Returns (svg, width).

    With right=True the row ends at x instead of starting there.
    """
    labels = [str(tag).upper() for tag in tags if str(tag).strip()]
    if not labels:
        return "", 0.0
    widths = [kit.chip_width(label, size) for label in labels]

    def used(count: int) -> float:
        return sum(widths[:count]) + CHIP_GAP * max(0, count - 1)

    shown = len(labels)
    while shown and used(shown) > room:
        shown -= 1
    more = ""
    if shown < len(labels):
        while (
            shown
            and used(shown) + CHIP_GAP + kit.chip_width(f"+{len(labels) - shown}", size)
            > room
        ):
            shown -= 1
        more = f"+{len(labels) - shown}"
    total = used(shown) + (
        (CHIP_GAP if shown else 0) + kit.chip_width(more, size) if more else 0
    )
    cx = x - total if right else x
    out = []
    for label in labels[:shown]:
        svg, width = kit.chip(cx, y, label, kit.BLUE_LIGHT, size, height)
        out.append(svg)
        cx += width + CHIP_GAP
    if more:
        out.append(kit.chip(cx, y, more, kit.META, size, height)[0])
    return "".join(out), total


def _label(sample: dict, what: str) -> str:
    when = f" ({sample['date']})" if sample.get("date") else ""
    return f"{sample['title']}, published as a solution under aws-samples{when}: {what}"


class Foot:
    """The text under the diagram: where each block sits, and the card's height."""

    def __init__(
        self, sample: dict, w: float, top: float, phone: bool, rows: int = 0
    ) -> None:
        self.x0, self.x1 = (16, w - 16) if phone else (24, w - 24)
        self.micro = kit.MICRO_PHONE if phone else kit.MICRO
        self.chip_h = 24 if phone else 22
        self.tags = list(sample.get("tags") or [])
        self.eyebrow = eyebrow(sample)
        room = self.x1 - self.x0
        wide = w == WIDE and not phone
        title = str(sample["title"])
        self.inline = False
        if wide:
            # the lead card: the title on the left and the chips on the right, when both fit
            self.size, self.step = LEAD_TITLE, 26
            _, chips = tag_chips(self.tags, 0, 0, room, self.micro, self.chip_h)
            self.inline = kit.text_width(title, self.size) <= room - (
                chips + 24 if chips else 0
            )
            self.lines = [title] if self.inline else title_lines(title, room, self.size)
        else:
            self.size, self.step = TITLE_SIZE, TITLE_STEP
            self.lines = title_lines(title, room, self.size)
        self.rows = max(rows, len(self.lines))
        self.eyebrow_y = top + (30 if wide else 28)
        self.title_y = top + (60 if wide else 54)
        last = self.title_y + self.step * (self.rows - 1)
        if self.inline:
            self.chips_y = self.title_y - 15
            self.height = last + 26
        elif self.tags:
            self.chips_y = last + 16
            self.height = self.chips_y + self.chip_h + (20 if phone else 22)
        else:
            self.chips_y = last
            self.height = last + 24

    def svg(self) -> str:
        head = kit.text(
            self.x0, self.eyebrow_y, self.eyebrow, self.micro, kit.BLUE_LIGHT, "m"
        )
        title = "".join(
            kit.text(
                self.x0, self.title_y + self.step * i, line, self.size, kit.INK, "t"
            )
            for i, line in enumerate(self.lines)
        )
        room = self.x1 - self.x0
        x = self.x1 if self.inline else self.x0
        chips, _ = tag_chips(
            self.tags, x, self.chips_y, room, self.micro, self.chip_h, self.inline
        )
        return (
            kit.group(0.1, head)
            + kit.group(0.1 + kit.STAGGER, title)
            + (kit.group(0.1 + 2 * kit.STAGGER, chips) if chips else "")
        )


def card(sample: dict, phone: bool, rows: int = 0, height: float = 0) -> str:
    """One card: the diagram band, the hairline, then the foot. `rows` and `height` level a two-up pair."""
    diagram, what, desktop, cover_desktop, cover_phone = DIAGRAMS[sample["key"]]
    w = PHONE if phone else desktop
    cover = cover_phone if phone else cover_desktop
    scene = Scene(sample["key"], w, cover, phone)
    diagram(scene)
    defs, body = scene.svg()
    foot = Foot(sample, w, cover, phone, rows)
    h = max(height, foot.height)
    band = (
        '<g clip-path="url(#card)">'
        + _rect(0, 0, w, cover, 0, kit.CARD)
        + f'<rect width="{w}" height="{cover}" fill="url(#dots)"/>'
        + body
        + f'<path d="M0 {cover}H{w}" stroke="{kit.HAIR_STRONG}"/>'
        + "</g>"
        + _rect(0.5, 0.5, w - 1, h - 1, kit.RADIUS, "none", kit.HAIR)
    )
    return (
        kit.card_open(
            w, h, _label(sample, what), defs + kit.dot_pattern("dots", 16, 0.05)
        )
        + band
        + foot.svg()
        + kit.SVG_CLOSE
    )


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for every sample in ctx that has a diagram, desktop and -mobile."""
    samples = [s for s in ctx.get("samples") or [] if s.get("key") in DIAGRAMS]
    # the two-up cards share one height: the most title rows, then the tallest foot
    pair = [s for s in samples if DIAGRAMS[s["key"]][2] == HALF]
    rows = max((len(Foot(s, HALF, 0, False).lines) for s in pair), default=0)
    height = max(
        (Foot(s, HALF, DIAGRAMS[s["key"]][3], False, rows).height for s in pair),
        default=0,
    )
    files = {}
    for sample in samples:
        two_up = DIAGRAMS[sample["key"]][2] == HALF
        files[f"sample-{sample['key']}.svg"] = card(
            sample, False, rows if two_up else 0, height if two_up else 0
        )
        files[f"sample-{sample['key']}-mobile.svg"] = card(sample, True)
    return files
