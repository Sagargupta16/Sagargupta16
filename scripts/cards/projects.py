"""The featured project cards: an animated cover scene over each project's date, title, summary and stack."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# One card per ctx["projects"] entry: project-{slug}.svg at 400 wide (all one
# height, they sit two-up) and project-{slug}-mobile.svg at 320. The cover on
# top redraws, flat and in the blue family, the scene the portfolio already
# shows for that project (portfolio-react, src/pages/projects/covers): the
# idea and the beats are the portfolio's, the drawing is kit's. A slug with no
# scene gets a cover built from its tech list, so a new portfolio entry never
# breaks the render.
#
# Every cover runs on the 12 s page clock and is poster-safe: the elements'
# own attributes hold the finished scene, the loop clears it, replays the
# mechanism and rests on the finished scene again. Things that only exist in
# transit (packets, cursors, flashes) rest hidden.
#
# A cover that rebuilds something (GitScope's panel, Ledger Sync's import, the
# predictor's results) opens on the finished frame and holds it: it clears at
# Stage.clear, about 3 s in and later for each card along the grid, rebuilds
# in under 5 s and rests finished for the rest of the loop. So the finished
# frame fills more than half of every loop, and two neighbours never come
# apart at the same moment.
from __future__ import annotations

import math
from urllib.parse import urlparse

import kit

T = kit.T

W55 = "rgba(255,255,255,0.55)"
W30 = "rgba(255,255,255,0.30)"
W07 = "rgba(255,255,255,0.07)"
TINT_STRONG = "rgba(37,99,235,0.28)"
DIM = 0.3  # a plate, row or label that is out of focus for a beat
DESKTOP_LINES, PHONE_LINES = 3, 4  # the most summary lines a card shows
STAR_FLOOR = 10  # a star chip is drawn from this many stars
CHIP_GAP = 6  # between two chips on the tech row
# A build scene clears CLEAR_AT seconds in, CLEAR_STEP later for each card
# along the grid, and starts over every CLEAR_CARDS cards: side by side the
# clears are one step apart, one above the other two steps.
CLEAR_AT, CLEAR_STEP, CLEAR_CARDS = 3.0, 0.9, 4


class Stage:
    """A cover's drawing area: the card's full width, padded like the text under it."""

    def __init__(self, phone: bool, index: int = 0) -> None:
        self.phone = phone
        self.clear = CLEAR_AT + CLEAR_STEP * (index % CLEAR_CARDS)
        self.w = 320 if phone else 400
        self.h = 128 if phone else 120
        self.pad = 16 if phone else 24
        self.micro = kit.MICRO_PHONE if phone else kit.MICRO
        self.x0, self.x1 = self.pad, self.w - self.pad
        self.y0, self.y1 = 16, self.h - 16
        self.cy = (self.y0 + self.y1) / 2

    def label_width(self, label: str) -> float:
        return kit.text_width(label, self.micro, True, kit.TRACK) - kit.TRACK

    def label(
        self,
        x: float,
        y: float,
        label: str,
        fill: str = kit.META,
        anchor: str = "",
    ) -> str:
        """A mono micro-label inside a scene, at the layout's text floor."""
        return kit.text(x, y, label, self.micro, fill, "m", anchor)

    def lit(
        self,
        x: float,
        y: float,
        label: str,
        points: list,
        color: str = kit.BLUE_LIGHT,
        anchor: str = "",
    ) -> str:
        """A label that rests in the caption colour and lights for a beat."""
        return self.label(x, y, label, kit.META, anchor) + (
            f'<g opacity="0">{_fade(points)}{self.label(x, y, label, color, anchor)}</g>'
        )


# ---------------------------------------------------------------- numbers and timing
_n, _rect = kit.num, kit.rect


def _anim(attribute: str, points: list, dur: float = T, kind: str = "") -> str:
    """One repeating animation from [(seconds, value)]; the ends are padded with the first and last value."""
    points = list(points)
    if points[0][0] > 0:
        points.insert(0, (0, points[0][1]))
    if points[-1][0] < dur:
        points.append((dur, points[-1][1]))
    values = ";".join(v if isinstance(v, str) else _n(v) for _, v in points)
    times = ";".join(
        f"{min(1.0, t / dur):.4f}".rstrip("0").rstrip(".") for t, _ in points
    )
    if kind:
        return (
            f'<animateTransform attributeName="transform" type="{kind}" values="{values}" '
            f'keyTimes="{times}" dur="{dur:g}s" repeatCount="indefinite"/>'
        )
    return (
        f'<animate attributeName="{attribute}" values="{values}" keyTimes="{times}" '
        f'dur="{dur:g}s" repeatCount="indefinite"/>'
    )


def _fade(points: list, dur: float = T) -> str:
    return _anim("opacity", points, dur)


def _pairs(points: list) -> list:
    return [(t, f"{_n(x)} {_n(y)}") for t, (x, y) in points]


def _move(points: list, dur: float = T) -> str:
    return _anim("transform", _pairs(points), dur, "translate")


def _scale(points: list, dur: float = T) -> str:
    return _anim("transform", _pairs(points), dur, "scale")


def _window(
    on: float, off: float, ramp: float = 0.3, low: float = 0, high: float = 1
) -> list:
    """Low at rest, high between on and off."""
    return [(on, low), (on + ramp, high), (off, high), (off + ramp, low)]


def _back(clear: float, at: float, ramp: float = 0.4) -> list:
    """Shown at rest, cleared at `clear`, back at `at`: the rest frame is the finished one."""
    return [(clear, 1), (clear + 0.3, 0), (at, 0), (at + ramp, 1)]


# ---------------------------------------------------------------- shapes
def _panel(x: float, y: float, w: float, h: float, r: float = 6) -> str:
    return _rect(x, y, w, h, r, kit.WELL, kit.HAIR_STRONG)


def _bar(x: float, y: float, w: float, h: float, fill: str = W30) -> str:
    return _rect(x, y, w, h, h / 2, fill)


def _wire(
    d: str, stroke: str = kit.HAIR_STRONG, width: float = 1, extra: str = ""
) -> str:
    return f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{_n(width)}"{extra}/>'


def _dot(cx: float, cy: float, r: float, fill: str, extra: str = "") -> str:
    return f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="{fill}"{extra}/>'


def _pivot(cx: float, cy: float, body: str, animation: str, extra: str = "") -> str:
    """Scale `body` (drawn round the origin) about a point."""
    return f'<g transform="translate({_n(cx)} {_n(cy)})"><g{extra}>{animation}{body}</g></g>'


# ---------------------------------------------------------------- curves and travelling lights
def _curve(a: tuple, b: tuple) -> tuple:
    """A cubic with horizontal tangents at both ends: an S between two ports."""
    k = (b[0] - a[0]) / 2
    return (a, (a[0] + k, a[1]), (b[0] - k, b[1]), b)


def _line(a: tuple, b: tuple) -> tuple:
    return (a, a, b, b)


def _at(segment: tuple, t: float) -> tuple:
    a, c1, c2, b = segment
    u = 1 - t
    w0, w1, w2, w3 = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (
        w0 * a[0] + w1 * c1[0] + w2 * c2[0] + w3 * b[0],
        w0 * a[1] + w1 * c1[1] + w2 * c2[1] + w3 * b[1],
    )


def _length(segment: tuple, steps: int = 24) -> float:
    points = [_at(segment, i / steps) for i in range(steps + 1)]
    return sum(math.dist(points[i], points[i + 1]) for i in range(steps))


class Route:
    """A chain of cubics as one path: its d, its length, and where each segment ends as a share of it."""

    def __init__(self, *segments: tuple) -> None:
        self.segments = segments
        a = segments[0][0]
        parts = [f"M{_n(a[0])} {_n(a[1])}"]
        for start, c1, c2, end in segments:
            if c1 == start and c2 == end:
                parts.append(f"L{_n(end[0])} {_n(end[1])}")
            else:
                parts.append(
                    f"C{_n(c1[0])} {_n(c1[1])} {_n(c2[0])} {_n(c2[1])} {_n(end[0])} {_n(end[1])}"
                )
        self.d = "".join(parts)
        lengths = [_length(segment) for segment in segments]
        self.length = sum(lengths) or 1
        run, self.ends = 0.0, []
        for length in lengths:
            run += length
            self.ends.append(run / self.length)

    def back(self) -> Route:
        """The same route walked the other way."""
        return Route(*[(b, c2, c1, a) for a, c1, c2, b in reversed(self.segments)])


def _beam(
    route: Route,
    trips: list,
    color: str = kit.SKY,
    width: float = 2,
    px: float = 9,
    dur: float = T,
) -> str:
    """A short light that rides a route once per trip and rests hidden before its start.

    A trip is [(seconds, share of the route)]: 0 is hidden before the start, 1
    hidden past the end, and a share in between is where the light's middle
    sits, so a repeated share is a hold (under a node drawn over the route).
    The dash pattern repeats past the end of the path, so the offset only ever
    decreases: the light never runs backwards to get home, and after the last
    trip it is back where it rests. kit.beam covers one trip from 0 s; this is
    the same light for trips that leave mid-loop, hold and repeat.
    """
    dash = max(3.0, min(45.0, 100 * px / route.length))
    margin = min(10.0, 100 * 2.5 / route.length)  # keeps the round cap off both ends
    span = 100 + dash + 2 * margin
    period = span + dash
    rest = dash + margin
    points = []
    for index, trip in enumerate(trips):
        base = rest - index * period
        for seconds, share in trip:
            if share <= 0:
                progress = 0.0
            elif share >= 1:
                progress = 1.0
            else:
                progress = (dash / 2 + margin + 100 * share) / span
            points.append((seconds, base - progress * span))
    if points[0][0] > 0:
        points.insert(0, (0, rest))
    points.append((dur, rest - len(trips) * period))
    return (
        f'<path d="{route.d}" fill="none" stroke="{color}" stroke-width="{_n(width)}" stroke-linecap="round" '
        f'pathLength="100" stroke-dasharray="{_n(dash)} {_n(period - dash)}" stroke-dashoffset="{_n(rest)}">'
        f"{_anim('stroke-dashoffset', points, dur)}</path>"
    )


def _trip(start: float, end: float) -> list:
    return [(start, 0), (end, 1)]


def _trace(d: str, points: list, color: str, width: float, extra: str = "") -> str:
    """A stroke that rests drawn; `points` move its dash offset (0 drawn, 1 gone)."""
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{_n(width)}" pathLength="1" '
        f'stroke-dasharray="1" stroke-dashoffset="0"{extra}>{_anim("stroke-dashoffset", points)}</path>'
    )


# ---------------------------------------------------------------- kalchar: the gallery wall
# Portfolio GalleryScene: a rail of style pills over a wall of museum plates,
# each with an inset line and its tradition in line work. The filter steps
# through the four styles: the active pill fills, its plates lift and the rest
# of the wall dims. The loop opens and closes on the unfiltered wall.
_ZIGZAG = " ".join(["l2,-2 l2,2"] * 8)
_FISH = "M-14,0 Q-2,-8 8,0 Q-2,8 -14,0 Z M8,0 L14,-5 L14,5 Z M-4,-5 Q-1,0 -4,5 M1,-4 Q4,0 1,4"
_LOTUS = (
    "M0,-9 Q5,-2 0,3 Q-5,-2 0,-9 Z M0,3 Q-10,0 -11,-5 Q-4,-5 0,3 Z "
    "M0,3 Q10,0 11,-5 Q4,-5 0,3 Z M-12,4 Q0,10 12,4"
)
_ARCH = "M-16,-12 a4,4 0 0 1 8,0 a4,4 0 0 1 8,0 a4,4 0 0 1 8,0 a4,4 0 0 1 8,0"
_RIPPLE = "M-16,13 q4,-3 8,0 t8,0 t8,0 t8,0"
_LEAF = "M0,-16 Q16,0 0,16 Q-16,0 0,-16 Z"
_LIGHT_70 = "rgba(96,165,250,0.7)"
_LIGHT_45 = "rgba(96,165,250,0.45)"


def _ink(d: str, stroke: str, extra: str = "") -> str:
    return f'<path d="{d}" stroke="{stroke}"{extra}/>'


def _madhubani() -> str:
    fish = _ink(_FISH, kit.BLUE_LIGHT) + _dot(
        -9, -1, 1.2, kit.BLUE_LIGHT, ' stroke="none"'
    )
    return (
        _ink(f"M-16,-18 {_ZIGZAG} M-16,18 {_ZIGZAG}", W30)
        + f'<g transform="translate(0 -7)">{fish}</g>'
        + f'<g transform="translate(0 7) scale(-1 1)">{fish}</g>'
    )


def _pichwai() -> str:
    return _ink(_ARCH, W30) + _ink(_LOTUS, kit.BLUE_LIGHT) + _ink(_RIPPLE, _LIGHT_45)


def _lippan() -> str:
    mirrors = "".join(
        _dot(x, y, 1.6, W55, ' stroke="none"')
        for x, y in ((0, 0), (0, -14), (14, 0), (0, 14), (-14, 0))
    )
    corners = "".join(
        f'<circle cx="{x}" cy="{y}" r="2.6" stroke="{_LIGHT_45}"/>'
        for x, y in ((-15, -15), (15, -15), (15, 15), (-15, 15))
    )
    return (
        _ink("M0,-14 L14,0 L0,14 L-14,0 Z", kit.BLUE_LIGHT)
        + f'<circle r="6" stroke="{_LIGHT_70}"/>'
        + mirrors
        + corners
    )


def _gond() -> str:
    dots = []
    for y in (-9, -4, 1, 6, 11):
        share = (y + 16) / 32
        half = 32 * share * (1 - share)
        for f in (0.3, 0.62):
            dots.append(_dot(half * f, y, 0.9, _LIGHT_70, ' stroke="none"'))
            dots.append(_dot(-half * f, y, 0.9, _LIGHT_70, ' stroke="none"'))
    return (
        _ink(_LEAF, kit.BLUE_LIGHT)
        + _ink("M0,-13 V14", W30, ' stroke-dasharray="1.5 2"')
        + "".join(dots)
    )


_MOTIFS = (_madhubani, _pichwai, _lippan, _gond)


def _plate(x: float, y: float, w: float, h: float, art: int) -> str:
    """A museum plate: hairline frame, inset line, its tradition inside."""
    k = (min(w, h) - 14) / 40
    return (
        _rect(x, y, w, h, 4, kit.WELL, kit.HAIR_STRONG)
        + _rect(x + 3, y + 3, w - 6, h - 6, 2.5, "none", "rgba(96,165,250,0.3)")
        + f'<g transform="translate({_n(x + w / 2)} {_n(y + h / 2)}) scale({_n(k)})" fill="none" '
        f'stroke-width="{_n(1.15 / k)}" stroke-linecap="round" stroke-linejoin="round">{_MOTIFS[art]()}</g>'
    )


def _cover_gallery(stage: Stage, project: dict) -> str:
    styles = ("MADHUBANI", "PICHWAI", "LIPPAN", "GOND")
    slot = 2.0  # all, then each style, then all again: six 2 s beats
    marks = [2 + slot * k for k in range(5)]
    order = [None, 0, 1, 2, 3, None]
    out = []

    pad, gap, x = (7 if stage.phone else 9), 6, stage.x0
    baseline = stage.y0 + 10 + stage.micro * 0.36
    for k, name in enumerate(styles):
        width = stage.label_width(name) + 2 * pad
        middle = x + width / 2
        out.append(
            _rect(x, stage.y0, width, 20, 10, kit.HAIR_FILL, kit.HAIR_STRONG)
            + stage.label(middle, baseline, name, kit.META, "middle")
            + f'<g opacity="0">{_fade(_window(marks[k] - 0.3, marks[k + 1] - 0.3))}'
            + _rect(x, stage.y0, width, 20, 10, TINT_STRONG, kit.BLUE_EDGE)
            + stage.label(middle, baseline, name, kit.INK, "middle")
            + "</g>"
        )
        x += width + gap

    widths = (60, 44, 56, 48, 56) if stage.phone else (60, 44, 56, 48, 60, 44)
    arts = (0, 2, 1, 3, 0, 1)
    gap = 6 if stage.phone else 8
    top = stage.y0 + 28
    height = stage.y1 - top
    plates: dict = {k: [] for k in range(4)}
    x = stage.x0
    for width, art in zip(widths, arts):
        plates[art].append(_plate(x, top, width, height, art))
        x += width + gap
    for k in range(4):
        fade, lift = [(0, 1)], [(0, (0, 0))]
        for i, mark in enumerate(marks):
            before, after = order[i], order[i + 1]
            fade += [
                (mark - 0.3, 1 if before in (None, k) else DIM),
                (mark, 1 if after in (None, k) else DIM),
            ]
            lift += [
                (mark - 0.3, (0, -2 if before == k else 0)),
                (mark, (0, -2 if after == k else 0)),
            ]
        out.append(f"<g>{_fade(fade)}{_move(lift)}{''.join(plates[k])}</g>")
    return "".join(out)


# ---------------------------------------------------------------- any other project: its stack as a pipeline
_STAGES = ("CODE", "BUILD", "SHIP")  # what stands in where the stack gives no node
_NODES = 4  # the most nodes a generic cover draws


def _cover_generic(stage: Stage, project: dict) -> str:
    """No portfolio scene for this slug: its tech names as nodes on one wire, lit as a packet passes.

    Up to four names, in their order. One too long for the band is passed
    over for the shorter names after it, and a stack that yields fewer than
    three nodes is filled out with plain stages, so the cover always reads as
    a pipeline.
    """
    pad, least, room, picked = 9, 14, stage.x1 - stage.x0, []

    def add(name: str) -> None:
        width = stage.label_width(name) + 2 * pad
        used = sum(w for _, w in picked) + least * len(picked)
        if len(picked) < _NODES and used + width <= room:
            picked.append((name, width))

    for name in project.get("tech") or []:
        add(str(name).upper())
    for name in _STAGES[len(picked) :]:
        add(name)
    spare = room - sum(w for _, w in picked)
    gap = spare / (len(picked) - 1) if len(picked) > 1 else 0
    x = stage.x0 if len(picked) > 1 else stage.x0 + spare / 2
    cy, height = stage.cy, 28
    route = Route(_line((stage.x0 - stage.pad, cy), (stage.x1 + stage.pad, cy)))
    travel = 4.0
    nodes = []
    for name, width in picked:
        middle = x + width / 2
        reach = 1.0 + travel * (middle / stage.w)
        baseline = cy + stage.micro * 0.36
        nodes.append(
            _rect(x, cy - height / 2, width, height, 8, kit.BG, kit.HAIR_STRONG)
            + stage.label(middle, baseline, name, kit.META, "middle")
            + f'<g opacity="0">{_fade(_window(reach - 0.2, reach + 1.6))}'
            + _rect(x, cy - height / 2, width, height, 8, kit.BG, kit.BLUE_EDGE)
            + _rect(x, cy - height / 2, width, height, 8, kit.BLUE_TINT)
            + stage.label(middle, baseline, name, kit.INK, "middle")
            + "</g>"
        )
        x += width + gap
    rails = "".join(_wire(f"M0 {_n(cy + dy)}H{stage.w}", W07) for dy in (-30, 30))
    return (
        rails
        + _wire(route.d)
        + _beam(route, [_trip(1.0, 1.0 + travel), _trip(7.0, 7.0 + travel)], px=14)
        + "".join(nodes)
    )


# ---------------------------------------------------------------- gitscope: the extension on a profile
# Portfolio ExtensionScene: a browser on a GitHub profile. The content script
# spots the profile (a ring on the avatar), one GraphQL query leaves by the
# toolbar icon, and the GitScope panel is injected beside the avatar: the stat
# grid pops in, the language bar grows, the heatmap lands and the donut draws.
# The loop opens on the injected panel and holds it, then clears it,
# re-injects in under 5 s and holds again.
def _cover_extension(stage: Stage, project: dict) -> str:
    x0, x1 = stage.x0, stage.x1
    top, bottom = 12, stage.h - 12
    bar = 22 if stage.phone else 20
    middle = top + bar / 2
    text_y = middle + stage.micro * 0.36
    c = stage.clear  # the panel leaves here; every beat below is seconds after it
    gone, landed = c + 0.3, c + 2.7  # the slot is empty between these
    url = stage.label_width("GITHUB.COM") + 16
    out = [
        _panel(x0, top, x1 - x0, bottom - top, 8),
        "".join(_dot(x0 + 12 + 8 * i, middle, 2.5, kit.HAIR_STRONG) for i in range(3)),
        _rect(
            x0 + 38,
            top + 3,
            url,
            bar - 6,
            (bar - 6) / 2,
            kit.HAIR_FILL,
            kit.HAIR_STRONG,
        ),
        stage.label(x0 + 46, text_y, "GITHUB.COM"),
        _wire(f"M{x0} {top + bar}H{x1}"),
    ]
    ix = x1 - 16
    icon = (
        _rect(-7, -7, 14, 14, 3.5, TINT_STRONG, kit.BLUE_EDGE)
        + f'<circle cx="-1" cy="-1" r="3" fill="none" stroke="{kit.INK}" stroke-width="1.3"/>'
        + _wire("M1.4 1.4L4 4", kit.INK, 1.3, ' stroke-linecap="round"')
    )
    out.append(
        _pivot(
            ix,
            middle,
            icon,
            _scale([(c + 1.5, (1, 1)), (c + 1.7, (1.35, 1.35)), (c + 2.1, (1, 1))]),
        )
    )
    out.append(
        f'<g opacity="0">{_fade(_window(c + 1.4, c + 2.7))}'
        + stage.label(ix - 14, text_y, "GRAPHQL", kit.SKY, "end")
        + "</g>"
    )

    # the profile: a plain disc for the picture, two lines for the name
    content = top + bar
    ax, ay = x0 + 28, content + 22
    out.append(
        f'<circle cx="{_n(ax)}" cy="{_n(ay)}" r="12" fill="{W07}" stroke="{kit.HAIR_STRONG}"/>'
        + _bar(ax - 14, ay + 19, 28, 4, W30)
        + _bar(ax - 14, ay + 27, 19, 3, kit.HAIR_STRONG)
    )
    ring = f'<circle r="13" fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="1.5"/>'
    out.append(
        _pivot(
            ax,
            ay,
            ring,
            _fade([(c + 0.3, 0), (c + 0.5, 0.95), (c + 1.1, 0)])
            + _scale(
                [(c + 0.4, (0.9, 0.9)), (c + 1.1, (1.5, 1.5)), (c + 1.2, (0.9, 0.9))]
            ),
            ' opacity="0"',
        )
    )

    px, py = x0 + 56, content + 6
    side = 0 if stage.phone else 84
    pw = (x1 - 8 - px) - (side + 8 if side else 0)
    ph = bottom - 6 - py

    # one query out by the toolbar icon, then the answer back along the toolbar
    # and down into the slot, whose outline shows while it is empty. Both
    # lights are long, so the round trip reads at the card's display width.
    under = middle + 7  # just under the toolbar's labels
    drop = (px + pw - 24, py + ph / 2)
    query = Route(_curve((ax + 13, ay - 6), (ix - 8, under)))
    answer = Route(((ix - 8, under), (drop[0] + 10, under), (drop[0], under + 4), drop))
    out.append(
        f'<g opacity="0">{_fade(_window(gone, landed - 0.2, 0.2))}'
        + _rect(px, py, pw, ph, 6, "none", W30, ' stroke-dasharray="3 3"')
        + "</g>"
        + _beam(query, [_trip(c + 0.8, c + 1.6)], width=2.4, px=26)
        + _beam(answer, [_trip(c + 1.9, landed)], width=2.4, px=22)
    )

    reset = gone + 0.15  # the panel's parts reset behind it while it is away
    title = stage.label(px + 8, py + 16, "GITSCOPE", kit.BLUE_LIGHT)
    lx = px + 8 + stage.label_width("GITSCOPE") + 10
    lw = px + pw - 8 - lx
    shares, run, segments = (26, 22, 15, 12, 10, 13), 0.0, []
    for share, alpha in zip(shares, (1, 0.8, 0.62, 0.46, 0.34, 0.24)):
        width = lw * share / sum(shares)
        segments.append(_rect(run, 0, width - 1, 5, 1.5, f"rgba(96,165,250,{alpha})"))
        run += width
    langs = (
        f'<g transform="translate({_n(lx)} {_n(py + 9)})"><g>'
        + _scale(
            [
                (reset, (1, 1)),
                (reset + 0.1, (0, 1)),
                (c + 3.3, (0, 1)),
                (c + 3.9, (1, 1)),
            ]
        )
        + "".join(segments)
        + "</g></g>"
    )
    ry = py + 24
    room = ph - 24 - 8
    tile_h = (room - 4) / 2
    tiles = []
    for row in range(2):
        for col in range(3):
            tx, ty = px + 8 + col * 26, ry + row * (tile_h + 4)
            fill = kit.BLUE_LIGHT if (row, col) == (0, 0) else W55
            tiles.append(
                _rect(tx, ty, 22, tile_h, 3, W07, kit.HAIR_STRONG)
                + _bar(
                    tx + 4, ty + tile_h / 2 - 1.5, 8 + (col * 2 + row * 3) % 7, 3, fill
                )
            )
    stats = f"<g>{_fade([(reset, 1), (reset + 0.1, 0), (c + 3.1, 0), (c + 3.4, 1)])}{''.join(tiles)}</g>"
    hx = px + 8 + 74 + 8
    rows = int(room // 8)
    hy = ry + (room - rows * 8 + 2) / 2
    cols = int((px + pw - 8 - 22 - 8 - hx + 2) // 8)
    cells = []
    for col in range(cols):
        for row in range(rows):
            alpha = (0.16, 0.3, 0.48, 0.85)[(col * 3 + row * 5 + (col * row) % 3) % 4]
            cells.append(
                _rect(
                    hx + col * 8, hy + row * 8, 6, 6, 1.5, f"rgba(59,130,246,{alpha})"
                )
            )
    heat = f"<g>{_fade([(reset, 1), (reset + 0.1, 0), (c + 3.7, 0), (c + 4.0, 1)])}{''.join(cells)}</g>"
    dx, dy, r = px + pw - 8 - 11, ry + room / 2, 9
    donut = (
        f'<circle cx="{_n(dx)}" cy="{_n(dy)}" r="{r}" fill="none" stroke="{kit.HAIR_STRONG}" stroke-width="4"/>'
        f'<path d="M{_n(dx)} {_n(dy - r)}a{r} {r} 0 1 1 0 {2 * r}a{r} {r} 0 1 1 0 {-2 * r}" fill="none" '
        f'stroke="{kit.BLUE_LIGHT}" stroke-width="4" pathLength="1" stroke-dasharray="0.82 1" stroke-dashoffset="0">'
        + _anim(
            "stroke-dashoffset",
            [(reset, 0), (reset + 0.1, 0.82), (c + 3.9, 0.82), (c + 4.5, 0)],
        )
        + "</path>"
    )
    out.append(
        "<g>"
        + _fade(_back(c, landed))
        + _move(
            [(c, (0, 0)), (gone, (0, -6)), (landed, (0, -6)), (landed + 0.4, (0, 0))]
        )
        + _rect(px, py, pw, ph, 6, "rgba(37,99,235,0.10)", kit.BLUE_EDGE)
        + title
        + langs
        + stats
        + heat
        + donut
        + "</g>"
    )
    if side:
        mx = px + pw + 8
        height = (bottom - 6 - py - 6) / 2
        for index in range(2):
            my = py + index * (height + 6)
            out.append(
                _rect(mx, my, side, height, 5, "none", kit.HAIR_STRONG)
                + _bar(mx + 8, my + 8, 34 - index * 8, 4, W30)
                + _bar(mx + 8, my + 16, side - 26, 3, kit.HAIR_STRONG)
                + _dot(mx + 10, my + height - 6, 2, kit.BLUE_EDGE)
            )
    return "".join(out)


# ---------------------------------------------------------------- ledger sync: sheet, hash check, ledger, cash flow
# Portfolio LedgerScene: a messy export is read row by row. Each parsed row
# rides through the SHA-256 transaction ID check into the ledger; the last row
# repeats the one before it, so the check flashes and the duplicate never
# lands. Then the analytics refresh and the cash flow Sankey redraws: income
# into savings, tax and expenses, and expenses into categories. The chart from
# the last import stays up until its refresh, so no panel sits empty.
def _cover_ledger(stage: Stage, project: dict) -> str:
    a, g1, b, g2 = (64, 62, 68, 8) if stage.phone else (88, 72, 92, 12)
    x0, y0, y1 = stage.x0, stage.y0, stage.y1
    t0 = (
        stage.clear
    )  # this run's two rows leave the ledger here; beats are seconds after it
    refresh = t0 + 3.6
    c = stage.x1 - (x0 + a + g1 + b + g2)
    lx, fx = x0 + a + g1, x0 + a + g1 + b + g2
    inset = 5 if stage.phone else 8
    head = y0 + 15
    out = [
        _panel(x0, y0, a, y1 - y0),
        _panel(lx, y0, b, y1 - y0),
        _panel(fx, y0, c, y1 - y0),
        stage.label(x0 + inset, head, "XLSX", kit.BLUE_LIGHT),
        stage.label(lx + inset, head, "LEDGER"),
        stage.label(fx + inset, head, "CASH FLOW"),
    ]

    # the sheet: a merged title row, a blank one, four records; the last repeats the one above it
    rows_top = y0 + 22
    rh = (y1 - 6 - rows_top) / 6
    column = (a - 2 * inset) / 4
    cells = [
        [0],
        [0, 0, 6, 0],
        [10, 8, 9, 7],
        [9, 13, 6, 8],
        [10, 9, 7, 6],
        [10, 9, 7, 6],
    ]
    sheet = [_bar(x0 + inset, rows_top + rh / 2 - 2, (a - 2 * inset) * 0.72, 4, W30)]
    for index, row in enumerate(cells):
        y = rows_top + index * rh
        sheet.append(_wire(f"M{_n(x0 + 2)} {_n(y)}H{_n(x0 + a - 2)}", W07))
        for j, value in enumerate(row):
            if value:
                sheet.append(
                    _bar(
                        x0 + inset + j * column,
                        y + rh / 2 - 1.5,
                        value / 14 * column,
                        3,
                        "rgba(255,255,255,0.24)",
                    )
                )
    out.append("".join(sheet))
    out.append(
        f'<g opacity="0">{_fade([(t0 + 0.1, 0), (t0 + 0.3, 1), (t0 + 3.9, 1), (t0 + 4.1, 0)])}'
        + _move(
            [
                (t0 + 1.4, (0, 0)),
                (t0 + 1.6, (0, 2 * rh)),
                (t0 + 2.7, (0, 2 * rh)),
                (t0 + 2.9, (0, 3 * rh)),
                (t0 + 4.2, (0, 3 * rh)),
                (t0 + 4.4, (0, 0)),
            ]
        )
        + _rect(x0 + 2, rows_top + 2 * rh, a - 4, rh, 2, kit.BLUE_TINT, kit.BLUE_LIGHT)
        + "</g>"
    )

    # the ledger: three saved transactions, then the two this run saves
    step = (y1 - 10 - (y0 + 27)) / 4
    slots = [y0 + 27 + step * i for i in range(5)]
    note = b - 2 * inset - 10 - 20

    def entry(y: float, width: float, amount: float, dot: str) -> str:
        return (
            _dot(lx + inset + 3, y, 2.5, dot)
            + _bar(lx + inset + 10, y - 2, width, 4, W30)
            + _bar(lx + b - inset - amount, y - 2, amount, 4, kit.HAIR_STRONG)
        )

    out.append(
        entry(slots[0], note * 0.8, 12, "rgba(96,165,250,0.85)")
        + entry(slots[1], note * 0.6, 16, "rgba(96,165,250,0.45)")
        + entry(slots[2], note * 0.92, 10, "rgba(96,165,250,0.6)")
    )
    for slot, width, amount, at in ((3, 0.72, 13, t0 + 1.3), (4, 0.86, 11, t0 + 2.6)):
        out.append(
            "<g>"
            + _fade(_back(t0, at, 0.3))
            + _move(
                [(t0, (0, 0)), (t0 + 0.3, (-5, 0)), (at, (-5, 0)), (at + 0.3, (0, 0))]
            )
            + entry(slots[slot], note * width, amount, kit.SKY)
            + "</g>"
        )

    # the hash check between them
    gx, gy, r = x0 + a + g1 / 2, stage.cy + 6, 9
    mids = [rows_top + (i + 0.5) * rh for i in (2, 4, 5)]
    into = [Route(_curve((x0 + a, y), (gx - r, gy))) for y in mids]
    onto = [Route(_curve((gx + r, gy), (lx, slots[i]))) for i in (3, 4)]
    out.append("".join(_wire(route.d) for route in into + onto))
    out.append(
        _beam(into[0], [_trip(t0 + 0.3, t0 + 0.8)])
        + _beam(onto[0], [_trip(t0 + 0.9, t0 + 1.3)])
        + _beam(into[1], [_trip(t0 + 1.6, t0 + 2.1)])
        + _beam(onto[1], [_trip(t0 + 2.2, t0 + 2.6)])
        + _beam(into[2], [_trip(t0 + 2.9, t0 + 3.4)], kit.INK)
    )
    hash_y = gy + stage.micro * 0.36
    out.append(
        f'<circle cx="{_n(gx)}" cy="{_n(gy)}" r="{r}" fill="{kit.BLUE_TINT}" stroke="{kit.BLUE_EDGE}"/>'
        + kit.text(gx, hash_y, "#", stage.micro, kit.BLUE_LIGHT, "m", "middle")
        + stage.label(gx, gy - 17, "SHA256", kit.META, "middle")
        + f'<circle cx="{_n(gx)}" cy="{_n(gy)}" r="{r}" fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="2" opacity="0">'
        + _fade(_window(t0 + 0.7, t0 + 1.0, 0.15) + _window(t0 + 2.0, t0 + 2.3, 0.15))
        + "</circle>"
        + f'<g opacity="0">{_fade(_window(t0 + 3.3, t0 + 4.0, 0.15))}'
        + f'<circle cx="{_n(gx)}" cy="{_n(gy)}" r="{r + 3}" fill="none" stroke="{kit.INK}" stroke-width="1.5"/>'
        + stage.label(gx, gy - 17, "SHA256", kit.INK, "middle")
        + _wire(
            f"M{_n(gx - 4)} {_n(gy + r + 7)}l8 8m0 -8l-8 8",
            kit.INK,
            1.6,
            ' stroke-linecap="round"',
        )
        + "</g>"
    )

    # the cash flow: income fans out into savings, tax and expenses; expenses into two categories
    top = y0 + 24
    tall = y1 - 8 - top
    sx, ox = fx + inset, fx + c - inset - 4
    mx = (sx + ox) / 2
    income = tall * 0.64
    savings, tax, spend = income * 0.5, income * 0.12, income * 0.38
    part, gap = spend / 2, (tall - income) / 3
    source = (
        top + (tall - income) / 2
    )  # the income node is centred; its bands land spread over the full height
    leave = (
        source + savings / 2,
        source + savings + tax / 2,
        source + income - spend / 2,
    )
    reach = (
        top + savings / 2,
        top + savings + gap + tax / 2,
        top + savings + tax + 2 * gap + part / 2,
        top + tall - part / 2,
    )
    middle = (reach[2] + reach[3]) / 2

    def ribbon(
        a_: tuple, b_: tuple, width: float, color: str, on: float, span: float
    ) -> str:
        return _trace(
            Route(_curve(a_, b_)).d,
            [
                (refresh + 0.2, 0),
                (refresh + 0.25, 1),
                (refresh + on, 1),
                (refresh + on + span, 0),
            ],
            color,
            width,
        )

    flow = (
        ribbon(
            (sx + 4, leave[0]),
            (ox, reach[0]),
            savings,
            "rgba(96,165,250,0.38)",
            0.4,
            0.5,
        )
        + ribbon(
            (sx + 4, leave[1]), (ox, reach[1]), tax, "rgba(255,255,255,0.24)", 0.5, 0.4
        )
        + ribbon(
            (sx + 4, leave[2]), (mx, middle), spend, "rgba(37,99,235,0.48)", 0.5, 0.4
        )
        + ribbon(
            (mx + 4, middle - part / 2),
            (ox, reach[2]),
            part,
            "rgba(56,189,248,0.36)",
            0.9,
            0.4,
        )
        + ribbon(
            (mx + 4, middle + part / 2),
            (ox, reach[3]),
            part,
            "rgba(37,99,235,0.42)",
            0.9,
            0.4,
        )
        + _rect(sx, source, 4, income, 2, kit.BLUE_LIGHT)
        + _rect(mx, middle - spend / 2, 4, spend, 2, kit.BLUE_EDGE)
        + _rect(ox, reach[0] - savings / 2, 4, savings, 2, kit.BLUE_LIGHT)
        + _rect(ox, reach[1] - tax / 2, 4, tax, 2, W55)
        + _rect(ox, reach[2] - part / 2, 4, part, 2, kit.SKY)
        + _rect(ox, reach[3] - part / 2, 4, part, 2, kit.BLUE_EDGE)
    )
    # the old chart leaves as the refresh arrives and the new one draws in its place
    out.append(
        f"<g>{_fade([(refresh, 1), (refresh + 0.2, 0), (refresh + 0.3, 0), (refresh + 0.4, 1)])}{flow}</g>"
    )
    out.append(
        _beam(
            Route(_line((lx + b, gy), (sx, gy))),
            [_trip(refresh - 0.3, refresh + 0.1)],
            px=5,
        )
    )
    return "".join(out)


# ---------------------------------------------------------------- rating predictor: form, dense network, deltas
# Portfolio PredictorScene: the form (a weekly and a biweekly contest, each
# ticked) posts to the model. Each contest's row rides through the Dense
# network, the layers fire left to right, and its answer lands as a result
# card whose delta bar grows from a centre axis: right for a gain, left for a
# drop. The second contest follows a beat behind the first. The loop opens on
# both results and holds them before the form is posted again.
def _cover_predictor(stage: Stage, project: dict) -> str:
    fw, cw = (92, 76) if stage.phone else (100, 100)
    x0, x1, y0, y1 = stage.x0, stage.x1, stage.y0, stage.y1
    cx0 = x1 - cw
    c = stage.clear  # the form is posted again here; beats are seconds after it
    out = [_panel(x0, y0, fw, y1 - y0)]

    box, left = 10, (7 if stage.phone else 8)
    tops = (y0 + 7, y0 + 7 + (y1 - y0 - 36) / 2)
    for index, name in enumerate(("WEEKLY", "BIWEEKLY")):
        t = tops[index] + 6
        on = c + 0.3 + 0.2 * index
        out.append(
            _rect(x0 + left, t, box, box, 2.5, W07, kit.HAIR_STRONG)
            + _trace(
                f"M{_n(x0 + left + 2.2)} {_n(t + 5.2)}l2.2 2.3 3.6 -4.6",
                [(c, 0), (c + 0.2, 1), (on, 1), (on + 0.25, 0)],
                kit.BLUE_LIGHT,
                1.7,
                ' stroke-linecap="round" stroke-linejoin="round"',
            )
            + stage.label(x0 + left + box + 6, t + 5 + stage.micro * 0.36, name)
        )
    by = y1 - 8 - 20
    out.append(
        _rect(x0 + 8, by, fw - 16, 20, 6, kit.BLUE)
        + stage.label(
            x0 + fw / 2, by + 10 + stage.micro * 0.36, "PREDICT", kit.INK, "middle"
        )
        + f'<g opacity="0">{_fade(_window(c + 0.75, c + 1.0, 0.12))}'
        + _rect(x0 + 8, by, fw - 16, 20, 6, "rgba(255,255,255,0.32)")
        + "</g>"
    )

    # the network: the neurons drawn per layer stand for 15, 128, 64, 32 and 1
    left_edge, right_edge = x0 + fw + 18, cx0 - 18
    spacing = (right_edge - left_edge) / 4
    xs = [left_edge + spacing * i for i in range(5)]
    counts, pitch = (5, 6, 5, 3, 1), (11 if stage.phone else 10)
    ny = stage.cy + 7
    layers = [[ny + (j - (n - 1) / 2) * pitch for j in range(n)] for n in counts]
    edges = "".join(
        f"M{_n(xs[i])} {_n(ya)}L{_n(xs[i + 1])} {_n(yb)}"
        for i in range(4)
        for ya in layers[i]
        for yb in layers[i + 1]
    )
    out.append(_wire(edges, W07, 0.8))
    out.append(stage.label((xs[0] + xs[4]) / 2, y0 + 9, "DENSE", kit.META, "middle"))

    height = (y1 - y0 - 8) / 2
    card_tops = (y0, y0 + height + 8)
    port_in, port_out = (xs[0] - 7, ny), (xs[4] + 7, ny)
    starts = (c + 1.0, c + 2.2)
    # seconds a contest spends on each leg: into the network, across it, out to its card
    into, across, ride = 0.4, 1.4, 1.8
    beams = []
    for index in range(2):
        feed = _curve((x0 + fw, tops[index] + 11), port_in)
        land = _curve(port_out, (cx0, card_tops[index] + height / 2))
        route = Route(feed, _line(port_in, port_out), land)
        out.append(_wire(Route(feed).d) + _wire(Route(land).d))
        s = starts[index]
        beams.append(
            _beam(
                route,
                [
                    [
                        (s, 0),
                        (s + into, route.ends[0]),
                        (s + across, route.ends[1]),
                        (s + ride, 1),
                    ]
                ],
            )
        )
    travel = xs[4] - xs[0]
    sweep, glow, fire, pop = [], [], [], []
    for s in starts:
        a, b = s + into, s + across
        sweep += [
            (a, (0, 0)),
            (b, (travel, 0)),
            (b + 0.1, (travel, 0)),
            (b + 0.15, (0, 0)),
        ]
        glow += _window(a - 0.1, b, 0.1)
        fire += [(b - 0.1, 0), (b, 1), (b + 0.5, 0)]
        pop += [(b, (1, 1)), (b + 0.5, (2.6, 2.6)), (b + 0.6, (1, 1))]
    tall = (counts[1] - 1) * pitch + 14
    out.append(
        f'<g opacity="0">{_fade(glow)}{_move(sweep)}'
        + _rect(xs[0] - 7, ny - tall / 2, 14, tall, 5, TINT_STRONG)
        + "</g>"
    )
    out.append(
        _pivot(
            xs[4],
            ny,
            f'<circle r="4" fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="1.5"/>',
            _fade(fire) + _scale(pop),
            ' opacity="0"',
        )
    )
    out.append("".join(beams))
    out.append(
        "".join(
            _dot(xs[i], y, 3.2 if i == 4 else 2.4, kit.BLUE_LIGHT if i == 4 else W55)
            for i in range(5)
            for y in layers[i]
        )
    )
    # the result cards: a gain grows right of the axis, a drop left of it
    axis = cx0 + cw / 2
    for index, (reach, color, mark, at) in enumerate(
        (
            (cw * 0.3, kit.BLUE_LIGHT, "M0 6L4 0L8 6Z", starts[0] + ride),
            (-cw * 0.18, W55, "M0 0L4 6L8 0Z", starts[1] + ride),
        )
    ):
        ty = card_tops[index]
        bar_y = ty + height - 19
        out.append(
            _panel(cx0, ty, cw, height)
            + _bar(cx0 + 8, ty + 9, 30, 3, W30)
            + _bar(cx0 + 8, ty + 16, 18, 3, kit.HAIR_STRONG)
            + _wire(f"M{_n(axis)} {_n(bar_y - 4)}V{_n(bar_y + 12)}", W30)
            + f'<g transform="translate({_n(axis)} {_n(bar_y)})"><g>'
            + _scale([(c, (1, 1)), (c + 0.3, (0, 1)), (at, (0, 1)), (at + 0.5, (1, 1))])
            + _rect(min(0, reach), 0, abs(reach), 8, 2, color)
            + "</g></g>"
            + f"<g>{_fade(_back(c, at + 0.3, 0.2))}"
            + f'<path d="{mark}" fill="{color}" transform="translate({_n(cx0 + cw - 17)} {_n(ty + 8)})"/></g>'
        )
    return "".join(out)


# ---------------------------------------------------------------- blue-green: one ALB, two target groups, the pipeline
# Portfolio InfraScene (BlueGreen): two full deployments per loop, because
# CodeDeploy alternates target groups. Each half: the pipeline starts a
# release (its node lights), replacement tasks start in the idle group, a test
# listener probe (white) reaches it, the canary sends one production request
# in two there while CANARY lights, then the pipeline's signal reaches the ALB
# and the listener switches (the knob), every request follows, and the old
# tasks drain. The second half mirrors the first, so the loop closes where it
# opened. The pipeline node is this card's own: the project is shipped by
# CodePipeline, and it shows why the traffic moves.
def _cover_bluegreen(stage: Stage, project: dict) -> str:
    aw, tw = (60, 120) if stage.phone else (76, 140)
    x1, y0, y1 = stage.x1, stage.y0, stage.y1
    # the ALB's left edge; requests reach it from the card's edge
    x0 = stage.x0 + (22 if stage.phone else 36)
    th, tx = 38, x1 - tw
    tops = (y0, y1 - th)
    # the ALB stands level with the first group, the pipeline in the room under it
    ah = 46
    cy = y0 + ah / 2
    ports = ((x0 + aw, cy - 10), (x0 + aw, cy + 10))
    routes = [Route(_curve(ports[i], (tx, tops[i] + th / 2))) for i in (0, 1)]
    inbound = Route(_line((0, cy), (x0, cy)))
    knob = x0 + aw - 9
    name, deep = "CODEPIPELINE", (22 if stage.phone else 20)
    wide, pipe = stage.label_width(name) + 16, y1 - deep
    signal = Route(_line((knob, pipe), (knob, cy + ah / 2)))
    out = [
        _wire(inbound.d) + _wire(signal.d) + "".join(_wire(route.d) for route in routes)
    ]

    half, travel, canary, shift, fade = T / 2, 0.9, 1.4, 3.2, 0.3
    arrivals = []  # every production request crosses the inbound wire just before it leaves the ALB
    steady: dict = {0: [], 1: []}  # production requests that follow the listener
    carrier: dict = {0: [], 1: []}  # the one in two the canary sends to the new group
    probe: dict = {0: [], 1: []}
    for turn in (0, 1):
        old, new = (0, 1) if turn == 0 else (1, 0)
        base = turn * half
        for local in (0.0, 1.5, 3.0, 4.5):
            side = new if local >= shift else old
            steady[side].append(_trip(base + local, base + local + travel))
            arrivals.append((base + local - 0.5) % T)
        for local in (0.5, 2.0, 3.5, 5.0):
            side = new if local >= canary else old
            carrier[side].append(_trip(base + local, base + local + travel))
            arrivals.append(base + local - 0.5)
        probe[new].append(_trip(base + 0.4, base + 1.2))
    out.append(_beam(inbound, [_trip(at, at + 0.45) for at in sorted(arrivals)], px=7))
    for side in (0, 1):
        out.append(
            _beam(routes[side], steady[side])
            + _beam(routes[side], carrier[side])
            + _beam(routes[side], probe[side], kit.INK, 1.6, 6)
        )

    # the pipeline: lit while a release runs; its signal climbs to the listener just before each switch
    release = _window(0.1, shift) + _window(half + 0.1, half + shift)
    text_y = pipe + deep / 2 + stage.micro * 0.36
    out.append(
        _beam(
            signal,
            [_trip(turn * half + shift - 0.7, turn * half + shift) for turn in (0, 1)],
            px=8,
        )
        + _rect(stage.x0, pipe, wide, deep, 6, kit.BG, kit.HAIR_STRONG)
        + stage.label(stage.x0 + 8, text_y, name)
        + f'<g opacity="0">{_fade(release)}'
        + _rect(stage.x0, pipe, wide, deep, 6, kit.BG, kit.BLUE_EDGE)
        + _rect(stage.x0, pipe, wide, deep, 6, kit.BLUE_TINT)
        + stage.label(stage.x0 + 8, text_y, name, kit.BLUE_LIGHT)
        + "</g>"
    )

    switch = [shift, shift + fade, half + shift, half + shift + fade]
    out.append(
        _rect(x0, cy - ah / 2, aw, ah, 8, kit.BLUE_TINT, kit.BLUE_EDGE)
        + stage.label(x0 + 10, cy + stage.micro * 0.36, "ALB", kit.BLUE_LIGHT)
        + _wire(f"M{_n(knob)} {_n(cy - 10)}V{_n(cy + 10)}", W30)
        + f'<circle cx="{_n(knob)}" cy="{_n(cy - 10)}" r="2.5" fill="none" stroke="{W30}"/>'
        + f'<circle cx="{_n(knob)}" cy="{_n(cy + 10)}" r="2.5" fill="none" stroke="{W30}"/>'
        + f'<circle cx="{_n(knob)}" cy="{_n(cy - 10)}" r="4.5" fill="{kit.BLUE_LIGHT}">'
        + _move(list(zip(switch, [(0, 0), (0, 20), (0, 20), (0, 0)])))
        + "</circle>"
    )

    label_x = 8 if stage.phone else 10
    pill = 22 if stage.phone else 28
    first = label_x + stage.label_width("TG 1") + (8 if stage.phone else 10)
    serve = (
        list(zip(switch, [1, 0, 0, 1])),
        list(zip(switch, [0, 1, 1, 0])),
    )
    idle = (
        # group 1 drains after the first switch, then starts the second replacement
        _window(shift, 4.4, fade) + _window(half + 0.3, half + shift, fade),
        # group 2 starts the first replacement, then drains after the second switch
        _window(0.3, shift, fade) + _window(half + shift, half + 4.4, fade),
    )

    def tasks(middle: float, fill: str, edge: str = "") -> str:
        return "".join(
            _rect(tx + first + k * (pill + 6), middle - 5, pill, 10, 5, fill, edge)
            for k in (0, 1)
        )

    for index in (0, 1):
        top = tops[index]
        middle = top + th / 2
        rest = "" if index == 0 else ' opacity="0"'
        out.append(
            _panel(tx, top, tw, th, 8)
            + stage.label(tx + label_x, middle + stage.micro * 0.36, f"TG {index + 1}")
            + tasks(middle, W07)
            + f'<g opacity="0">{_fade(idle[index])}{tasks(middle, "none", W55)}</g>'
            + f"<g{rest}>{_fade(serve[index])}{tasks(middle, kit.BLUE_EDGE)}"
            + _dot(tx + tw - 13, middle, 3.5, kit.GREEN)
            + "</g>"
        )
    out.append(
        stage.lit(
            (x0 + aw + tx) / 2,
            cy + 5 + stage.micro * 0.36,
            "CANARY",
            _window(canary, shift - 0.2) + _window(half + canary, half + shift - 0.2),
            anchor="middle",
        )
    )
    return "".join(out)


# ---------------------------------------------------------------- likes leaderboard: scan, tally, swap
# Portfolio LeaderboardScene: the bundle is pasted into the console, the
# scanner walks the post grid one post at a time, and each post's likers are
# tallied into a ranked board. A heart rides from two scanned posts to the
# runner-up, its bar grows past the leader and the two rows trade places under
# the crown: the leader steps out sideways, the runner-up rises, and the old
# leader comes back in one row down, so the rows never cross. Then the board
# flips to the other tab and back, which resets the swap.
_HEART = (
    "M5 8.6C2 6.4 0 4.6 0 2.7 0 1.2 1.2 0 2.7 0 3.7 0 4.5 0.5 5 1.4 5.5 0.5 6.3 0 7.3 0 "
    "8.8 0 10 1.2 10 2.7 10 4.6 8 6.4 5 8.6Z"
)
_CROWN = "M-5 4V-2l2.5 2.5L0 -4l2.5 4.5L5 -2v6Z"


def _swap(at: float, step: float, width: float, home: float) -> tuple[list, list]:
    """Two rows trade places without crossing: [(seconds, (x, y))] for the leader and for the runner-up.

    The leader slides out of the board sideways, the runner-up rises into its
    slot, and the old leader slides back in one row down. Both step home at
    `home`, while the other tab covers them.
    """
    leader = [
        (at, (0, 0)),
        (at + 0.3, (width, 0)),
        (at + 0.3, (width, step)),
        (at + 0.55, (width, step)),
        (at + 0.85, (0, step)),
        (home, (0, step)),
        (home + 0.1, (0, 0)),
    ]
    runner = [
        (at + 0.25, (0, 0)),
        (at + 0.6, (0, -step)),
        (home, (0, -step)),
        (home + 0.1, (0, 0)),
    ]
    return leader, runner


def _cover_leaderboard(stage: Stage, project: dict) -> str:
    lw = 92 if stage.phone else 108
    x0, x1, y0, y1 = stage.x0, stage.x1, stage.y0, stage.y1
    text_dy = stage.micro * 0.36

    # the console strip and the post grid under it
    start = x0 + 7 + stage.label_width("CONSOLE") + 6
    out = [
        _panel(x0, y0, lw, 20, 5)
        + stage.label(x0 + 7, y0 + 10 + text_dy, "CONSOLE")
        + f'<g transform="translate({_n(start)} {_n(y0 + 8)})"><g>'
        + _scale([(0.2, (1, 1)), (0.3, (0, 1)), (0.5, (0, 1)), (1.1, (1, 1))])
        + _bar(0, 0, x0 + lw - 7 - start, 4, kit.BLUE_LIGHT)
        + "</g></g>"
    ]
    posts_y = y0 + 26 + stage.micro * 0.72
    out.append(stage.label(x0, posts_y, "POSTS"))
    grid_top = posts_y + 6
    tw, th = (lw - 12) / 3, (y1 - grid_top - 6) / 2

    def tile(col: int, row: int) -> tuple:
        return (x0 + col * (tw + 6), grid_top + row * (th + 6))

    for row in range(2):
        for col in range(3):
            tx, ty = tile(col, row)
            out.append(
                _rect(tx, ty, tw, th, 4, kit.WELL, kit.HAIR_STRONG)
                + _wire(
                    f"M{_n(tx + 4)} {_n(ty + th - 5)}l{_n(tw * 0.28)} -9 {_n(tw * 0.2)} 5 {_n(tw * 0.14)} -4 {_n(tw * 0.2)} 8",
                    kit.HAIR_STRONG,
                    1,
                    ' stroke-linejoin="round"',
                )
            )
    walk = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)]
    steps, at = [], 1.0
    for index, (col, row) in enumerate(walk):
        offset = (col * (tw + 6), row * (th + 6))
        if index:
            steps.append((at, offset))
        at += 1.0
        steps.append((at, offset))
        at += 0.2
    steps += [(7.0, steps[-1][1]), (7.2, (0, 0))]
    out.append(
        f'<g opacity="0">{_fade([(1.0, 0), (1.2, 1), (6.5, 1), (6.8, 0)])}{_move(steps)}'
        + _rect(
            x0,
            grid_top,
            tw,
            th,
            4,
            kit.BLUE_TINT,
            kit.BLUE_LIGHT,
            ' stroke-width="1.5"',
        )
        + "</g>"
    )

    # the board: two tabs over three ranked rows
    bx = x0 + lw + 16
    bw = x1 - bx
    out.append(_panel(bx, y0, bw, y1 - y0))
    # both tabs are named; the phone has no room for the portfolio's YOU FOLLOW beside the second
    tabs = ("FANS", "NON-MUTUALS") if stage.phone else ("YOU FOLLOW", "NON-MUTUALS")
    pad = 6 if stage.phone else 8
    tab_x, tab_y = bx + 6, y0 + 5
    flip = (9.0, 10.8)
    active = (
        [(flip[0], 1), (flip[0] + 0.3, 0), (flip[1], 0), (flip[1] + 0.3, 1)],
        _window(flip[0], flip[1]),
    )
    for index, tab in enumerate(tabs):
        width = stage.label_width(tab) + 2 * pad
        middle = tab_x + width / 2
        rest = "" if index == 0 else ' opacity="0"'
        out.append(
            _rect(tab_x, tab_y, width, 18, 9, "none", kit.HAIR_STRONG)
            + stage.label(middle, tab_y + 9 + text_dy, tab, kit.META, "middle")
            + f"<g{rest}>{_fade(active[index])}"
            + _rect(tab_x, tab_y, width, 18, 9, kit.BG, kit.BLUE_EDGE)
            + _rect(tab_x, tab_y, width, 18, 9, TINT_STRONG)
            + stage.label(middle, tab_y + 9 + text_dy, tab, kit.INK, "middle")
            + "</g>"
        )
        tab_x += width + 6
    rows_top = y0 + 28
    step = (y1 - 5 - rows_top) / 3
    ys = [rows_top + step * (i + 0.5) for i in range(3)]
    track_x = bx + bw * 0.52
    track = bx + bw - 10 - track_x
    name = track_x - 12 - (bx + 36)

    def entry(y: float, width: float, bar: str) -> str:
        return (
            _dot(bx + 27, y, 4.5, W30)
            + _bar(bx + 36, y - 2, name * width, 4, W30)
            + _bar(track_x, y - 2.5, track, 5, kit.HAIR_STRONG)
            + bar
        )

    def likes(y: float, share: float, fill: str) -> str:
        return _bar(track_x, y - 2.5, track * share, 5, fill)

    swap = (6.8, 7.65)
    home = 10.0  # the swap resets while the other tab is showing
    leader, runner = _swap(swap[0], step, bw, home)
    grow = (
        f'<g transform="translate({_n(track_x)} {_n(ys[1] - 2.5)})"><g transform="scale(0.55 1)">'
        + _scale(
            [
                (3.5, (0.55, 1)),
                (3.8, (0.7, 1)),
                (5.9, (0.7, 1)),
                (6.2, (0.92, 1)),
                (home, (0.92, 1)),
                (home + 0.1, (0.55, 1)),
            ]
        )
        + _bar(0, 0, track, 5, kit.BLUE_LIGHT)
        + "</g></g>"
    )
    following = (
        f"<g>{_move(leader)}"
        + entry(ys[0], 0.85, likes(ys[0], 0.8, kit.BLUE_EDGE))
        + "</g>"
        + f"<g>{_move(runner)}"
        + entry(ys[1], 0.65, grow)
        + "</g>"
        + entry(ys[2], 0.95, likes(ys[2], 0.42, kit.BLUE_EDGE))
    )
    others = "".join(
        entry(ys[i], width, likes(ys[i], share, W55))
        for i, (width, share) in enumerate(((0.7, 0.7), (0.9, 0.5), (0.6, 0.36)))
    )
    out.append(
        f'<clipPath id="board">{_rect(bx + 1, rows_top - 4, bw - 2, y1 - rows_top + 3)}</clipPath>'
        + '<g clip-path="url(#board)">'
        + f"<g>{_move([(flip[0], (0, 0)), (flip[0] + 0.4, (-bw, 0)), (flip[1], (-bw, 0)), (flip[1] + 0.4, (0, 0))])}{following}</g>"
        + f'<g transform="translate({_n(bw)} 0)">'
        + _move(
            [
                (flip[0], (bw, 0)),
                (flip[0] + 0.4, (0, 0)),
                (flip[1], (0, 0)),
                (flip[1] + 0.4, (bw, 0)),
            ]
        )
        + f"{others}</g></g>"
    )
    out.append(
        _pivot(
            bx + 13,
            ys[0],
            f'<path d="{_CROWN}" fill="{kit.SKY}"/>',
            _scale(
                [
                    (swap[1], (1, 1)),
                    (swap[1] + 0.3, (1.6, 1.6)),
                    (swap[1] + 0.7, (1, 1)),
                ]
            ),
        )
        + "".join(_bar(bx + 10, y - 1.5, 6, 3, kit.HAIR_STRONG) for y in ys[1:])
    )

    # a heart from each of two scanned posts to the runner-up
    for (col, row), leave in (((1, 0), 2.6), ((0, 1), 5.0)):
        tx, ty = tile(col, row)
        curve = _curve((tx + tw / 2, ty + th / 2), (bx + 27, ys[1]))
        path = [(leave + 0.9 * i / 8, _at(curve, i / 8)) for i in range(9)]
        # once it has faded on the avatar it steps back to its post in no time
        path += [(leave + 1.2, path[-1][1]), (leave + 1.2, path[0][1])]
        out.append(
            f'<g opacity="0" transform="translate({_n(path[0][1][0])} {_n(path[0][1][1])})">'
            + _fade([(leave - 0.1, 0), (leave, 1), (leave + 0.9, 1), (leave + 1.05, 0)])
            + _move(path)
            + f'<path d="{_HEART}" fill="{kit.SKY}" transform="translate(-5 -4.3)"/></g>'
        )
    return "".join(out)


# ---------------------------------------------------------------- the portfolio: data in, page out
# Portfolio PortfolioScene: every section of the site is fed by a JSON file.
# One file is read, passes validation (the green check) and lands in the page,
# drawn as its own hero. The page scrolls, the Projects section lazy-loads its
# cards and their covers run, the command palette opens and its highlight
# steps down the list, then it closes and the page scrolls home.
def _cover_portfolio(stage: Stage, project: dict) -> str:
    dw = 56 if stage.phone else 64
    x0, x1, y0, y1, h = stage.x0, stage.x1, stage.y0, stage.y1, stage.h
    out = [stage.label(x0, y0 + 9, "DATA")]

    files_top = y0 + 18
    gap = (y1 - 18 - files_top) / 2
    files = [files_top + gap * i for i in range(3)]
    for y in files:
        out.append(
            _panel(x0, y, dw, 18, 4)
            + _wire(
                f"M{_n(x0 + 10)} {_n(y + 4)}q-3 0 -3 2.5v1.5q0 1 -2 1q2 0 2 1v1.5q0 2.5 3 2.5",
                W55,
                1.1,
            )
            + _bar(x0 + 15, y + 5.5, dw - 27, 3, W30)
            + _bar(x0 + 15, y + 11, dw - 36, 2.5, kit.HAIR_STRONG)
        )
    out.append(
        f'<g opacity="0">{_fade(_window(0.8, 3.0))}'
        + _rect(x0, files[1], dw, 18, 4, kit.BLUE_TINT, kit.BLUE_LIGHT)
        + "</g>"
    )

    gx, gy = x0 + dw + 20, files[1] + 9
    px = gx + 21
    pw = x1 - px
    feeds = [Route(_curve((x0 + dw, y + 9), (gx - 9, gy))) for y in files]
    land = Route(_line((gx + 9, gy), (px, gy)))
    out.append("".join(_wire(route.d) for route in [*feeds, land]))
    out.append(
        _beam(feeds[1], [_trip(1.1, 1.9)], px=6) + _beam(land, [_trip(2.4, 2.9)], px=5)
    )
    out.append(
        f'<circle cx="{_n(gx)}" cy="{_n(gy)}" r="9" fill="{kit.WELL}" stroke="{kit.HAIR_STRONG}"/>'
        + _pivot(
            gx,
            gy,
            _wire(
                "M-4.2 0.2l3 3 5.4 -6.2",
                kit.GREEN,
                1.8,
                ' stroke-linecap="round" stroke-linejoin="round"',
            ),
            _fade([(0.4, 1), (0.6, 0), (1.9, 0), (2.0, 1)])
            + _scale(
                [
                    (0.6, (1, 1)),
                    (0.7, (0.5, 0.5)),
                    (1.9, (0.5, 0.5)),
                    (2.1, (1.3, 1.3)),
                    (2.4, (1, 1)),
                ]
            ),
        )
    )

    # the page: nav, then a viewport that scrolls from the hero to the Projects section
    view = y0 + 17
    scroll = h - view - 8
    out.append(
        _panel(px, y0, pw, h + 12 - y0, 8)
        + _rect(px + 8, y0 + 5.5, 6, 6, 1.5, kit.BLUE_EDGE)
        + "".join(
            _bar(px + pw - 44 - 16 * k, y0 + 7, 11, 3, kit.HAIR_STRONG)
            for k in (1, 2, 3)
        )
        + _rect(px + pw - 38, y0 + 4.5, 30, 8, 4, kit.INK)
        + _wire(f"M{_n(px)} {_n(view - 1)}H{_n(px + pw)}")
        + f'<rect x="{_n(px)}" y="{_n(y0)}" width="{_n(pw)}" height="{_n(h + 12 - y0)}" rx="8" fill="none" '
        + f'stroke="{kit.BLUE_LIGHT}" stroke-width="1.5" opacity="0">{_fade(_window(2.8, 3.2, 0.2))}</rect>'
    )
    logo = px + pw - 12 - 20
    hero = (
        _rect(px + 12, view + 7, 60, 10, 5, "none", kit.HAIR_STRONG)
        + _dot(px + 18, view + 12, 2, kit.GREEN)
        + _bar(px + 24, view + 10.5, 40, 3, W30)
        + _bar(px + 12, view + 25, pw * 0.5, 7, "rgba(255,255,255,0.86)")
        + _bar(px + 12, view + 37, pw * 0.36, 7, kit.BLUE_LIGHT)
        + _rect(px + 12, view + 52, 40, 11, 5.5, kit.BLUE)
        + _rect(px + 58, view + 52, 40, 11, 5.5, "none", kit.HAIR_STRONG)
        + "".join(
            _rect(px + 12 + k * 38, view + 71, 32, 13, 4, W07, kit.HAIR_STRONG)
            for k in range(3)
        )
        + _rect(logo - 20, view + 12, 40, 40, 9, W07, kit.HAIR_STRONG)
        + _wire(
            f"M{_n(logo - 5)} {_n(view + 26)}l-6 6 6 6M{_n(logo + 5)} {_n(view + 26)}l6 6 -6 6",
            kit.BLUE_LIGHT,
            1.6,
            ' stroke-linecap="round" stroke-linejoin="round"',
        )
    )
    count = 2 if stage.phone else 3
    cw = (pw - 24 - (count - 1) * 8) / count
    top = view + scroll + 24
    cards, runners, ghosts = [], [], []
    for k in range(count):
        cx = px + 12 + k * (cw + 8)
        ghosts.append(
            _rect(
                cx, top, cw, 52, 5, "none", kit.HAIR_STRONG, ' stroke-dasharray="3 3"'
            )
        )
        cards.append(
            _rect(cx, top, cw, 52, 5, W07, kit.HAIR_STRONG)
            + _rect(cx + 4, top + 4, cw - 8, 24, 3, kit.BLUE_TINT)
            + _wire(f"M{_n(cx + 10)} {_n(top + 16)}H{_n(cx + cw - 10)}", W30)
            + _bar(cx + 6, top + 34, cw * 0.55, 4, W30)
            + _bar(cx + 6, top + 42, cw * 0.38, 3, kit.HAIR_STRONG)
        )
        runners.append(_dot(cx + 10, top + 16, 2.5, kit.SKY))
    section = (
        _bar(px + 12, view + scroll + 8, 52, 6, "rgba(255,255,255,0.86)")
        + f"<g>{_fade([(4.5, 1), (4.9, 0), (11.3, 0), (11.5, 1)])}{''.join(ghosts)}</g>"
        + f'<g opacity="0">{_fade([(4.5, 0), (4.9, 1), (11.3, 1), (11.5, 0)])}'
        + "".join(cards)
        + f"<g>{_move([(5.2, (0, 0)), (6.1, (cw - 20, 0)), (7.0, (0, 0))])}{''.join(runners)}</g>"
        + "</g>"
    )
    wide = min(150, pw - 36)
    left, lid = px + (pw - wide) / 2, view + 8
    palette = (
        f'<g opacity="0">{_fade(_window(7.2, 9.5))}'
        + _rect(left, lid, wide, 62, 7, kit.RAISED, kit.BLUE_EDGE)
        + f'<circle cx="{_n(left + 12)}" cy="{_n(lid + 9.5)}" r="3" fill="none" stroke="{W55}" stroke-width="1.2"/>'
        + _wire(f"M{_n(left + 14.3)} {_n(lid + 11.8)}l2.4 2.4", W55, 1.2)
        + _bar(left + 22, lid + 8, 34, 3, W30)
        + stage.label(
            left + wide - 8, lid + 9.5 + stage.micro * 0.36, "CTRL K", kit.META, "end"
        )
        + _wire(f"M{_n(left)} {_n(lid + 19)}H{_n(left + wide)}")
        + f"<g>{_move([(8.0, (0, 0)), (8.2, (0, 13)), (8.7, (0, 13)), (8.9, (0, 26)), (9.9, (0, 26)), (10.0, (0, 0))])}"
        + _rect(left + 4, lid + 22, wide - 8, 11, 3, TINT_STRONG)
        + "</g>"
        + "".join(
            _bar(left + 10, lid + 26 + 13 * k, wide * share, 3, W55)
            for k, share in enumerate((0.5, 0.36, 0.44))
        )
        + "</g>"
    )
    out.append(
        f'<clipPath id="view"><rect x="{_n(px + 1)}" y="{_n(view)}" width="{_n(pw - 2)}" height="{_n(h - view)}"/></clipPath>'
        + '<g clip-path="url(#view)">'
        + f"<g>{_move([(3.6, (0, 0)), (4.6, (0, -scroll)), (10.2, (0, -scroll)), (11.2, (0, 0))])}{hero}{section}</g>"
        + palette
        + "</g>"
    )
    return "".join(out)


# ---------------------------------------------------------------- selfhub: one memory, two assistants
# Portfolio McpScene (memory): CLAUDE calls store_memory, the SelfHub server
# writes a new document into the memories collection (newest first), then
# VS CODE calls search_memories, the match on that same row lights up and the
# hit rides back into VS Code. Written by one client, recalled by the other.
def _cover_memory(stage: Stage, project: dict) -> str:
    cw, sw = (84, 112) if stage.phone else (92, 136)
    x0, x1, y0, y1, cy = stage.x0, stage.x1, stage.y0, stage.y1, stage.cy
    box = 40
    tops = (y0, y1 - box)
    out = []
    for top, name in zip(tops, ("CLAUDE", "VS CODE")):
        out.append(
            _panel(x0, top, cw, box)
            + stage.label(x0 + 8, top + 15, name)
            + _dot(x0 + cw - 10, top + 11, 2, kit.BLUE_EDGE)
            + _wire(f"M{_n(x0)} {_n(top + 21)}H{_n(x0 + cw)}", W07)
        )
    out.append(
        _bar(
            x0 + cw - 8 - cw * 0.42, tops[0] + 25, cw * 0.42, 4, "rgba(96,165,250,0.45)"
        )
        + _bar(x0 + 8, tops[0] + 32, cw * 0.55, 4, W30)
        + _bar(x0 + 8, tops[1] + 25, cw * 0.46, 4, W30)
        + f'<g transform="translate({_n(x0 + 8)} {_n(tops[1] + 32)})"><g>'
        + _scale([(0.4, (1, 1)), (0.7, (0, 1)), (10.0, (0, 1)), (10.5, (1, 1))])
        + _bar(0, 0, cw * 0.62, 4, kit.BLUE_LIGHT)
        + "</g></g>"
    )

    sx = x1 - sw
    hx = (x0 + cw + sx) / 2
    rows_top = y0 + 27
    step = (y1 - 6 - rows_top) / 4
    span = sw - 28 - 8 - 18 - 8

    def document(top: float, width: float, chip: str) -> str:
        return (
            _rect(sx + 8, top + 1.5, 14, 7, 2, chip)
            + _bar(sx + 28, top + 2.5, span * width, 5, W30)
            + _bar(sx + sw - 8 - 18, top + 2.5, 18, 5, kit.HAIR_STRONG)
        )

    ports = {
        "claude": (x0 + cw, tops[0] + box / 2),
        "code": (x0 + cw, tops[1] + box / 2),
        "in": (hx - 16, cy),
        "out": (hx + 16, cy),
        "row": (sx, rows_top + 5),
    }
    through = _line(ports["in"], ports["out"])
    last = _curve(ports["out"], ports["row"])
    store = Route(_curve(ports["claude"], ports["in"]), through, last)
    search = Route(_curve(ports["code"], ports["in"]), through, last)
    answer = search.back()

    def hold(route: Route) -> float:
        return (route.ends[0] + route.ends[1]) / 2

    out.append(
        _wire(Route(_curve(ports["claude"], ports["in"])).d)
        + _wire(Route(_curve(ports["code"], ports["in"])).d)
        + _wire(Route(last).d)
        + _beam(store, [[(1.0, 0), (2.0, hold(store)), (2.3, hold(store)), (3.2, 1)]])
        + _beam(
            search, [[(5.0, 0), (6.0, hold(search)), (6.3, hold(search)), (7.2, 1)]]
        )
        + _beam(
            answer, [[(7.8, 0), (8.7, hold(answer)), (9.0, hold(answer)), (10.0, 1)]]
        )
    )
    out.append(
        _rect(hx - 16, cy - 16, 32, 32, 9, kit.BG, kit.BLUE_EDGE)
        + _rect(hx - 16, cy - 16, 32, 32, 9, kit.BLUE_TINT)
        + kit.text(
            hx,
            cy + stage.micro * 0.36,
            ">_",
            stage.micro,
            kit.BLUE_LIGHT,
            "m",
            "middle",
        )
        + f'<rect x="{_n(hx - 16)}" y="{_n(cy - 16)}" width="32" height="32" rx="9" fill="none" '
        + f'stroke="{kit.BLUE_LIGHT}" stroke-width="2" opacity="0">'
        + _fade(
            _window(1.9, 2.3, 0.15) + _window(5.9, 6.3, 0.15) + _window(8.6, 9.0, 0.15)
        )
        + "</rect>"
    )
    calls = ("STORE", "SEARCH") if stage.phone else ("STORE_MEMORY", "SEARCH_MEMORIES")
    out.append(
        f"<g>{_fade([(4.4, 1), (4.7, 0), (10.8, 0), (11.1, 1)])}"
        + stage.label(hx, y0 + 9, calls[0], kit.BLUE_LIGHT, "middle")
        + "</g>"
        + f'<g opacity="0">{_fade(_window(4.8, 10.5))}'
        + stage.label(hx, y0 + 9, calls[1], kit.BLUE_LIGHT, "middle")
        + "</g>"
    )

    out.append(
        _panel(sx, y0, sw, y1 - y0)
        + _wire(
            f"M{_n(sx + 8)} {_n(y0 + 8.5)}a5.5 2.4 0 0 1 11 0v6a5.5 2.4 0 0 1 -11 0zm0 0a5.5 2.4 0 0 0 11 0",
            kit.BLUE_LIGHT,
            1.1,
        )
        + stage.label(sx + 25, y0 + 15, "MEMORIES", kit.BLUE_LIGHT)
        + _wire(f"M{_n(sx)} {_n(y0 + 22)}H{_n(sx + sw)}", W07)
        + f"<g>{_fade([(0.4, 1), (0.7, 0), (7.2, 0), (7.5, 1)])}"
        + _rect(sx + 4, rows_top - 1.5, sw - 8, 13, 3, kit.BLUE_TINT, kit.BLUE_EDGE)
        + "</g>"
        + f"<g>{_fade(_back(0.4, 3.2))}{_move([(0.4, (0, 0)), (0.7, (-8, 0)), (3.2, (-8, 0)), (3.6, (0, 0))])}"
        + document(rows_top, 0.8, kit.BLUE_LIGHT)
        + "</g>"
        + f'<g transform="translate(0 {_n(step)})">'
        + _move([(0.6, (0, step)), (0.9, (0, 0)), (3.2, (0, 0)), (3.6, (0, step))])
        + "".join(
            document(rows_top + step * k, width, W30)
            for k, width in enumerate((0.62, 0.9, 0.5))
        )
        + "</g>"
    )
    return "".join(out)


# ---------------------------------------------------------------- the card
COVERS = {
    "kalchar": _cover_gallery,
    "gitscope": _cover_extension,
    "ledger-sync": _cover_ledger,
    "leetcode-rating-predictor": _cover_predictor,
    "blue-green-aws-terraform": _cover_bluegreen,
    "instagram-likes-leaderboard": _cover_leaderboard,
    "personal-portfolio": _cover_portfolio,
    "selfhub": _cover_memory,
}


def _summary(project: dict, phone: bool) -> list[str]:
    """The summary wrapped to the card's column; past the cap the last line ends in three dots."""
    width = (320 - 32) if phone else (400 - 48)
    size = 13.5 if phone else 13
    cap = PHONE_LINES if phone else DESKTOP_LINES
    lines = kit.wrap_text(project["summary"], width, size)
    if len(lines) <= cap:
        return kit.balance(lines)
    kept, last = lines[: cap - 1], lines[cap - 1]
    while " " in last and kit.text_width(last + "...", size) > width:
        last = last.rsplit(" ", 1)[0]
    return [*kept, last.rstrip(" ,;:.") + "..."]


def _star_chip(
    right: float, y: float, stars: int, size: float, height: float
) -> tuple[str, float]:
    """The star count as a pill that ends at `right`. Returns (svg, width)."""
    count = kit.compact(stars)
    width = 10 + 10 + 5 + kit.text_width(count, size, True, kit.TRACK) - kit.TRACK + 10
    x = right - width
    return (
        _rect(x, y, width, height, height / 2, kit.HAIR_FILL, kit.HAIR_STRONG)
        + f'<path d="{kit.STAR}" fill="{kit.SKY}" transform="translate({_n(x + 10)} {_n(y + height / 2 - 5)})"/>'
        + kit.text(x + 25, y + height / 2 + size * 0.36, count, size, kit.INK, "m"),
        width,
    )


def _fit(labels: list[str], room: float, size: float, reserve: float = 0) -> list[str]:
    """The names that fit one row, in their order, with `reserve` kept free after the last.

    A name too wide for what is left is passed over, and the shorter names
    after it still get their turn.
    """
    picked, used = [], 0.0
    for label in labels:
        width = kit.chip_width(label, size)
        if used + width + reserve <= room:
            picked.append(label)
            used += width + CHIP_GAP
    return picked


def _chip_row(project: dict, stage: Stage, y: float) -> str:
    """One row: the tech chips that fit, a +N for the rest, and the star chip on the right.

    The +N chip is drawn whenever names are left out, unless its room would
    cost the row its second name: then the names win and the count is dropped.
    """
    size, height = stage.micro, (24 if stage.phone else 22)
    limit, out = stage.x1, []
    stars = project.get("stars") or 0
    if stars >= STAR_FLOOR:
        svg, width = _star_chip(stage.x1, y, stars, size, height)
        out.append(svg)
        limit -= width + 8
    labels = [str(label) for label in project.get("tech") or []]
    room = limit - stage.x0
    shown, count = _fit(labels, room, size), False
    if len(shown) < len(labels):
        more = kit.chip_width(f"+{len(labels)}", size) + CHIP_GAP
        counted = _fit(labels, room, size, more)
        if len(counted) >= min(2, len(shown)):
            shown, count = counted, True
    x = stage.x0
    for label in shown:
        svg, width = kit.chip(x, y, label, kit.BLUE_LIGHT, size, height)
        out.append(svg)
        x += width + CHIP_GAP
    if count:
        svg, _ = kit.chip(x, y, f"+{len(labels) - len(shown)}", kit.META, size, height)
        out.append(svg)
    return "".join(out)


def _title(project: dict, stage: Stage, y: float) -> str:
    """The title at 18; a long one steps down to 15, and past that loses its last words to three dots."""
    title, size, room = str(project["title"]), 18.0, stage.x1 - stage.x0
    while size > 15 and kit.text_width(title, size) > room:
        size -= 0.5
    if kit.text_width(title, size) > room:
        while " " in title and kit.text_width(title + "...", size) > room:
            title = title.rsplit(" ", 1)[0]
        title = title.rstrip(" ,;:.") + "..."
    return kit.text(stage.x0, y, title, size, kit.INK, "t")


def _label(project: dict) -> str:
    state = ", live" if project.get("live") else ""
    return f"{project['title']} ({project['date']}{state}): {project['summary']}"


def _source(project: dict) -> bool:
    """True when the card's link is the project's repository rather than a running site."""
    host = urlparse(str(project.get("url") or "")).hostname or ""
    return host in ("github.com", "www.github.com")


def _card(project: dict, phone: bool, rows: int = 0, index: int = 0) -> str:
    """One project card.

    `rows` reserves that many summary lines so the desktop cards share a
    height; `index` is the card's place in the grid, which sets when its
    cover clears.
    """
    stage = Stage(phone, index)
    w, top = stage.w, stage.h
    lines = _summary(project, phone)
    rows = max(rows, len(lines))
    size, leading = (13.5, 19) if phone else (13, 18)
    eyebrow_y, title_y, first = top + 28, top + 52, top + 74
    chips_y = first + (rows - 1) * leading + 14
    height = chips_y + (24 if phone else 22) + (20 if phone else 22)

    scene = COVERS.get(project["slug"], _cover_generic)
    cover = (
        '<g clip-path="url(#card)"><g clip-path="url(#cover)">'
        + _rect(0, 0, w, top, 0, kit.CARD)
        + f'<rect width="{w}" height="{top}" fill="url(#dots)"/>'
        + scene(stage, project)
        + "</g>"
        + _wire(f"M0 {top}H{w}", kit.HAIR_STRONG)
        + "</g>"
        + _rect(0.5, 0.5, w - 1, height - 1, kit.RADIUS, "none", kit.HAIR)
    )

    head = stage.label(
        stage.x0, eyebrow_y, str(project["date"]).upper(), kit.BLUE_LIGHT
    )
    if project.get("live"):
        mark = stage.label_width("LIVE")
        head += kit.live_dot(
            stage.x1 - mark - 12, eyebrow_y - stage.micro * 0.36, r=3.5
        )
        head += stage.label(stage.x1, eyebrow_y, "LIVE", kit.GREEN, "end")
    elif _source(project):
        # no running site to point at: the right of the row says the link is the code
        head += stage.label(stage.x1, eyebrow_y, "SOURCE", kit.META, "end")
    head += _title(project, stage, title_y)
    body = "".join(
        kit.text(stage.x0, first + index * leading, line, size, kit.BODY, "b")
        for index, line in enumerate(lines)
    )
    defs = (
        f'<clipPath id="cover"><rect width="{w}" height="{top}"/></clipPath>'
        + kit.dot_pattern("dots", 16, 0.05)
    )
    return (
        kit.card_open(w, height, _label(project), defs)
        + cover
        + kit.group(0.1, head)
        + kit.group(0.1 + kit.STAGGER, body)
        + kit.group(0.1 + 2 * kit.STAGGER, _chip_row(project, stage, chips_y))
        + kit.SVG_CLOSE
    )


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text}: project-{slug}.svg and project-{slug}-mobile.svg for every featured project."""
    projects = ctx["projects"]
    rows = max((len(_summary(project, False)) for project in projects), default=1)
    files = {}
    for index, project in enumerate(projects):
        slug = project["slug"]
        files[f"project-{slug}.svg"] = _card(project, False, rows, index)
        files[f"project-{slug}-mobile.svg"] = _card(project, True, 0, index)
    return files
