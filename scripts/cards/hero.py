"""The hero: the first screen of the profile, with a platform hub as its scene.

Left: the greeting, the name, the role, one tagline at a time, the availability pill and the
intro sentence. Right: a cloud platform at the centre and six capabilities round it, each on
its own spoke. While the core reads BUILDING, a signal runs out along each spoke in turn, down
the left side and then down the right, and the capability it reaches lights; once all six are
up the core is marked live. Below both: the proof row. The scene keeps one 12 s clock, and
every element rests on the finished, live state, so a still render shows the whole card.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
from __future__ import annotations

import math
from itertools import pairwise

import kit

T = kit.T
NAME = "Sagar Gupta"

# ---------------------------------------------------------------- the clock
# Seconds on the 12 s loop. The hub comes up a side at a time: the left side's signals leave
# the core PITCH apart from FIRST, the right side's SIDE later, and each capability is up RUN
# after its signal leaves. The tagline turns on 0, 3, 6 and 9. The proof row's light moves at
# 5 and 11, in the pause between the two sides and while the finished hub holds.
REST = 2.0  # the finished frame holds until here, then the hub powers down
CLEAR = 0.3  # how long powering down takes
FIRST = 2.5  # the first signal leaves the core
PITCH = 0.75  # the next one on the same side this much later
SIDE = 3.0  # the right side starts this long after the left
RUN = 0.5  # a signal's time along its spoke
LEAVES = tuple(
    FIRST + side * SIDE + step * PITCH for side in (0, 1) for step in (0, 1, 2)
)
DONE = 8.25  # every capability is up: the core is marked live
ROLL = 0.3  # how long a reel takes to turn to its next row
PROOF_AT = 5.0  # the proof light's first move; the rest follow a whole slot apart
PROOF_SLOT = 6.0  # how long the light rests on a cell when there are four

TITLE = "WHAT I BUILD AND RUN"
CORE, BUILDING, LIVE = "PLATFORM", "BUILDING", "LIVE"
# The capabilities round the core, in the order the signals reach them: down the left side,
# then down the right. Each is (label, as the alt text says it, side, row): side -1 is the
# left, row -1 the top row. The two widest sit on the top row, where the cloud is narrowest.
NODES = (
    ("AUTOMATION", "automation", -1, -1),
    ("CI/CD", "CI/CD", -1, 0),
    ("SECURITY", "security", -1, 1),
    ("MONITORING", "monitoring", 1, -1),
    ("MLOPS", "MLOps", 1, 0),
    ("AI AGENTS", "AI agents", 1, 1),
)
# A flat cloud in a 90 by 52 box: four lobes (cx, cy, r) on a flat base (x, y, w, h), filled
# as one shape, and the ellipse inside it (cx, cy, rx, ry) that the spokes start from.
LOBES = ((18, 34, 18), (40, 22, 22), (66, 28, 18), (74, 36, 16))
BASE = (18, 34, 56, 18)
HUB = (45, 32, 38, 18)

TICK = "M-3.4 0.2l2.3 2.3 4.5-4.8"
PIN = "M0 -5.5a3.6 3.6 0 0 1 3.6 3.6c0 2.7-3.6 6.4-3.6 6.4s-3.6-3.7-3.6-6.4a3.6 3.6 0 0 1 3.6-3.6z"
SMOOTH = "0.4 0 0.2 1"  # ease in and out, for a move that travels and stops
JOIN = chr(0x2060)  # holds a keyword phrase together while the intro wraps
FILL = (
    0.6  # a keyword phrase may break across lines sooner than leave a line this short
)
SANS_FIT = 0.9  # kit measures sans text wide on purpose; a 600-weight line sets at about this share

# The scene's measures at each width. margin is where the tiles' outer edges sit; tile and
# pitch are a tile's height and the row spacing, hub the middle row's y; cloud is the core's
# width and cloud_y its top; port is the radius of the dot where a spoke meets its tile, head
# the signal's length and ring the radius of the core's live mark; status is how far below
# the cloud's foot the core's status sits, and high is the panel height the hub is placed for.
DESKTOP = {
    "margin": 18, "pad": 10, "tile": 28, "pitch": 54, "hub": 130,
    "cloud": 100, "cloud_y": 88, "port": 3.5, "head": 10, "ring": 7, "status": 18,
    "title": 31, "size": kit.MICRO, "track": kit.TRACK, "high": 216,
}  # fmt: skip
PHONE = {
    "margin": 8, "pad": 5, "tile": 20, "pitch": 36, "hub": 53,
    "cloud": 84, "cloud_y": 25, "port": 3, "head": 8, "ring": 6, "status": 15,
    "title": 0, "size": kit.MICRO_PHONE, "track": 0.8, "high": 106,
}  # fmt: skip


# ---------------------------------------------------------------- timing helpers
def _keys(points: list[tuple[float, str]], dur: float = T) -> tuple[str, str]:
    """(values, keyTimes) for (seconds, value) points that run from 0 to dur."""
    values = ";".join(value for _, value in points)
    times = ";".join(f"{round(second / dur, 4):g}" for second, _ in points)
    return values, times


def _anim(attribute: str, points: list[tuple[float, str]], dur: float = T) -> str:
    values, times = _keys(points, dur)
    return kit.loop(attribute, values, times, dur)


def _travel(points: list[tuple[float, float]], axis: str = "x", dur: float = T) -> str:
    """Move the element it sits in through (seconds, offset) points; a move eases, a wait holds.

    kit has no transform loop, so this is the module's own.
    """
    shape = "{:g} 0" if axis == "x" else "0 {:g}"
    values, times = _keys([(second, shape.format(at)) for second, at in points], dur)
    splines = ";".join(
        SMOOTH if a[1] != b[1] else "0 0 1 1" for a, b in pairwise(points)
    )
    return (
        f'<animateTransform attributeName="transform" type="translate" values="{values}" '
        f'keyTimes="{times}" calcMode="spline" keySplines="{splines}" dur="{dur:g}s" repeatCount="indefinite"/>'
    )


def _on(start: float, end: float, fade: float = 0.2, dur: float = T) -> str:
    """An opacity loop that is 1 from start+fade to end and 0 otherwise; the span may wrap past dur."""
    length = (end - start) % dur

    def level(second: float) -> float:
        since = (second - start) % dur
        if since <= fade:
            return since / fade
        if since <= length:
            return 1.0
        if since <= length + fade:
            return 1 - (since - length) / fade
        return 0.0

    marks = sorted(
        {0.0, dur, start % dur, (start + fade) % dur, end % dur, (end + fade) % dur}
    )
    return _anim(
        "opacity",
        [(mark, f"{max(0.0, round(level(mark), 3)):g}") for mark in marks],
        dur,
    )


def _reel(rows: str, pitch: float, turns: list[float], clip: str) -> str:
    """Rows that take turns in one window: the stack steps up a row at each turn.

    `rows` holds one row per turn plus the first row again, `pitch` apart, so the window is
    never empty and the loop closes on the frame it opens with. The module's own helper:
    kit.rotating crossfades through an empty slot.
    """
    points = [(0.0, 0.0)]
    for index, turn in enumerate(turns):
        points += [(turn - ROLL, -index * pitch), (turn, -(index + 1) * pitch)]
    if turns[-1] < T:
        points.append((T, -len(turns) * pitch))
    return f'<g clip-path="url(#{clip})"><g>{_travel(points, "y")}{rows}</g></g>'


def _window(clip: str, x: float, y: float, w: float, h: float) -> str:
    return f'<clipPath id="{clip}"><rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"/></clipPath>'


def _proof_clock(count: int) -> tuple[float, float]:
    """(loop, slot) for the proof light: four cells get 6 s each on a 24 s loop."""
    loop = 2 * T if count > 2 else T
    return loop, loop / count


# ---------------------------------------------------------------- scene parts
def _badge(cx: float, cy: float, r: float, fill: str, ink: str = kit.INK) -> str:
    """A done mark: a filled disc with a tick drawn to its size."""
    scale = r / 8
    return (
        f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{fill}"/>'
        f'<path transform="translate({cx:g} {cy:g}) scale({scale:g})" d="{TICK}" fill="none" '
        f'stroke="{ink}" stroke-width="{1.7 / scale:.2f}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _micro(x: float, y: float, label: str, fill: str, g: dict, anchor: str = "") -> str:
    """A scene label: the mono micro-label, set a little tighter where the phone measures ask."""
    tight = ""
    if g["track"] != kit.TRACK:
        tight = f' style="letter-spacing:{g["track"]:g}px"'
    return kit.text(x, y, label, g["size"], fill, "m", anchor, tight)


def _micro_width(label: str, g: dict) -> float:
    return kit.text_width(label, g["size"], True, g["track"]) - g["track"]


def _cloud(x: float, y: float, scale: float) -> str:
    """The core: the flat cloud, its top left corner at x, y.

    One path of clockwise lobes and base, so the nonzero fill paints their union as one shape.
    """

    def at(value: float) -> str:
        return f"{round(value * scale, 2):g}"

    parts = [
        f"M{at(cx - r)} {at(cy)}A{at(r)} {at(r)} 0 1 1 {at(cx + r)} {at(cy)}"
        f"A{at(r)} {at(r)} 0 1 1 {at(cx - r)} {at(cy)}Z"
        for cx, cy, r in LOBES
    ]
    bx, by, bw, bh = BASE
    parts.append(f"M{at(bx)} {at(by)}H{at(bx + bw)}V{at(by + bh)}H{at(bx)}Z")
    return f'<path transform="translate({x:g} {y:g})" d="{"".join(parts)}" fill="{kit.BLUE}"/>'


def _tiles(
    w: float, drop: float, g: dict
) -> list[tuple[tuple[float, ...], tuple[float, float]]]:
    """Each capability's tile (x, y, width, height) and the point on its inner edge its spoke meets.

    A tile is wider by its port's radius, which sits on its inner edge, so the word keeps
    its padding clear of the port.
    """
    out = []
    for word, _, side, row in NODES:
        wide = round(_micro_width(word, g) + 2 * g["pad"] + g["port"])
        tall = g["tile"]
        y = drop + g["hub"] + row * g["pitch"] - tall / 2
        x = g["margin"] if side < 0 else w - g["margin"] - wide
        out.append(((x, y, wide, tall), (x + wide if side < 0 else x, y + tall / 2)))
    return out


def _spoke(hub: tuple[float, ...], port: tuple[float, float]) -> tuple[float, float]:
    """Where the spoke to a port leaves the hub ellipse (cx, cy, rx, ry), towards the port."""
    hx, hy, rx, ry = hub
    dx, dy = port[0] - hx, port[1] - hy
    reach = 1 / math.hypot(dx / rx, dy / ry)
    return round(hx + dx * reach, 1), round(hy + dy * reach, 1)


def _between(lower: list[tuple[float, ...]], y: float) -> float:
    """The middle, at height y, of the two spokes (x0, y0, x1, y1) to the bottom row."""
    across = [x0 + (x1 - x0) * (y - y0) / (y1 - y0) for x0, y0, x1, y1 in lower]
    return (min(across) + max(across)) / 2


def _scene(w: float, h: float, phone: bool) -> str:
    """The platform hub, drawn from 0,0 in a w by h panel."""
    g = PHONE if phone else DESKTOP
    size, port, ring = g["size"], g["port"], g["ring"]
    drop = max(0.0, h - g["high"]) / 2  # a taller panel centres the hub
    scale = g["cloud"] / 90
    ox, oy = w / 2 - 45 * scale, drop + g["cloud_y"]
    hub = (ox + HUB[0] * scale, oy + HUB[1] * scale, HUB[2] * scale, HUB[3] * scale)

    out = [
        f'<rect x="0.5" y="0.5" width="{w - 1:g}" height="{h - 1:g}" rx="10" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>',
        f'<rect x="1" y="1" width="{w - 2:g}" height="{h - 2:g}" rx="9" fill="url(#dots)"/>',
    ]
    if g["title"]:
        out.append(_micro(g["margin"], g["title"], TITLE, kit.BLUE_LIGHT, g))

    # each spoke runs from inside the cloud to its tile's port. At rest it is a hairline; a
    # signal lights it from the core outwards, and it stays lit until the hub powers down.
    spokes, nodes, lower = [], [], []
    for index, ((x, y, wide, tall), (px, py)) in enumerate(_tiles(w, drop, g)):
        word, _, side, row = NODES[index]
        sx, sy = _spoke(hub, (px, py))
        if row > 0:
            lower.append((sx, sy, px, py))
        d = f"M{sx:g} {sy:g}L{px:g} {py:g}"
        # the signal's length as a share of its spoke, so it is as long on a short spoke
        head = round(100 * g["head"] / math.hypot(px - sx, py - sy), 1)
        leave = LEAVES[index]
        up = leave + RUN
        lit = [
            (0.0, "0"),
            (REST, "0"),
            (REST + CLEAR, "100"),
            (leave, "100"),
            (up, "0"),
            (T, "0"),
        ]
        # the signal: a short bright head on the lit length's front, out of sight off either
        # end of the spoke (it starts inside the cloud) except while it runs
        run = [
            (0.0, f"{head + 8:g}"),
            (leave, f"{head:g}"),
            (up, f"{head - 100:g}"),
            (up + RUN * head / 100, "-100"),
            (T, "-100"),
        ]
        spokes.append(
            f'<path d="{d}" fill="none" stroke="{kit.HAIR_STRONG}" stroke-width="1.5"/>'
            f'<path d="{d}" fill="none" stroke="{kit.BLUE_EDGE}" stroke-width="1.5" '
            'pathLength="100" stroke-dasharray="100 100" stroke-dashoffset="0">'
            + _anim("stroke-dashoffset", lit)
            + "</path>"
            f'<path d="{d}" fill="none" stroke="{kit.SKY}" stroke-width="3" stroke-linecap="round" '
            f'pathLength="100" stroke-dasharray="{head:g} 300" stroke-dashoffset="{head + 8:g}">'
            + _anim("stroke-dashoffset", run)
            + "</path>"
        )
        # the tile waits dark, its word in grey; it lights as the signal lands, and a dot
        # marks the port where its spoke plugs in
        mid, base = x + wide / 2 + side * port / 2, y + tall / 2 + size * 0.36
        nodes.append(
            f'<rect x="{x:g}" y="{y:g}" width="{wide:g}" height="{tall:g}" rx="7" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
            + _micro(mid, base, word, kit.META, g, "middle")
            + "<g>"
            + _on(up - 0.1, REST)
            + f'<rect x="{x:g}" y="{y:g}" width="{wide:g}" height="{tall:g}" rx="7" fill="{kit.BLUE_TINT}" stroke="{kit.BLUE_EDGE}" stroke-width="1.2"/>'
            + _micro(mid, base, word, kit.INK, g, "middle")
            + f'<circle cx="{px:g}" cy="{py:g}" r="{port:g}" fill="{kit.BLUE_LIGHT}"/>'
            + "</g>"
        )
    out += spokes
    out.append(_cloud(ox, oy, scale))
    out.append(_micro(w / 2, oy + 33 * scale + size * 0.36, CORE, kit.INK, g, "middle"))
    out += nodes

    # the core's status under the cloud, centred between the two lower spokes: BUILDING while
    # the capabilities come up, then the green ok and LIVE once all six are
    cy = oy + 52 * scale + g["status"]
    cx, base = _between(lower, cy), cy + size * 0.36
    gap = ring - 1
    start = cx - (2 * ring + gap + _micro_width(LIVE, g)) / 2
    out.append(
        '<g opacity="0">'
        + _on(REST + CLEAR, DONE - 0.45)
        + _micro(cx, base, BUILDING, kit.BLUE_LIGHT, g, "middle")
        + "</g><g>"
        + _on(DONE - 0.2, REST)
        + _badge(start + ring, cy, ring, kit.GREEN, kit.BG)
        + _micro(start + 2 * ring + gap, base, LIVE, kit.INK, g)
        + "</g>"
    )
    return "".join(out)


def _scene_defs(w: float, h: float, phone: bool) -> str:
    return (
        f'<clipPath id="scene"><rect x="1" y="1" width="{w - 2:g}" height="{h - 2:g}" rx="9"/></clipPath>'
        + kit.dot_pattern("dots", 16, 0.06)
    )


def _scene_block(x: float, y: float, w: float, h: float, phone: bool) -> str:
    return (
        f'<g transform="translate({x:g} {y:g})"><g clip-path="url(#scene)">'
        f"{kit.enter(kit.STAGGER)}{_scene(w, h, phone)}</g></g>"
    )


# ---------------------------------------------------------------- text blocks
def _role_lines(role: str, width: float, size: float) -> list[str]:
    """Wrap the role; a line never starts with the hyphen."""
    lines = kit.wrap_text(role, width, size)
    for index in range(1, len(lines)):
        if lines[index] == "-" or lines[index].startswith("- "):
            lines[index - 1] += " -"
            lines[index] = lines[index][2:]
    return [line for line in lines if line]


def _wrap_units(text: str, keywords: list[str], width: float, size: float) -> list[str]:
    """Wrap like kit.wrap_text, keeping each keyword phrase on one line.

    A phrase goes to the next line whole when it does not fit, unless that would leave
    the line it left less than FILL full; then it breaks at its spaces like any words.
    """
    for keyword in keywords:
        if keyword:
            text = text.replace(keyword, keyword.replace(" ", JOIN))

    def wide(line: str) -> float:
        return kit.text_width(line.replace(JOIN, " "), size)

    lines, current = [], ""
    for unit in text.split():
        candidate = f"{current} {unit}" if current else unit
        if wide(candidate) <= width:
            current = candidate
            continue
        if current and wide(current) >= width * FILL and wide(unit) <= width:
            lines.append(current)
            current = unit
            continue
        for word in unit.split(JOIN):
            candidate = f"{current} {word}" if current else word
            if current and wide(candidate) > width:
                lines.append(current)
                candidate = word
            current = candidate
    if current:
        lines.append(current)
    # a single word wider than the column still splits the way kit splits it
    return [
        piece
        for line in lines
        for piece in kit.wrap_text(line.replace(JOIN, " "), width, size)
    ]


def _intro(
    intro: str,
    keywords: list[str],
    x: float,
    y: float,
    width: float,
    size: float,
    leading: float,
) -> tuple[str, int]:
    """The intro sentence, wrapped, with its keyword phrases in the light blue. Returns (svg, lines)."""
    marked = [False] * len(intro)
    for keyword in keywords:
        at = intro.find(keyword) if keyword else -1
        while at >= 0:
            marked[at : at + len(keyword)] = [True] * len(keyword)
            at = intro.find(keyword, at + len(keyword))
    lines, cursor, rows = _wrap_units(intro, keywords, width, size), 0, []
    for index, line in enumerate(lines):
        at = intro.find(line, cursor)
        flags = marked[at : at + len(line)] if at >= 0 else [False] * len(line)
        cursor = at + len(line) if at >= 0 else cursor
        runs: list[tuple[bool, str]] = []
        for character, flag in zip(line, flags):
            if runs and runs[-1][0] == flag:
                runs[-1] = (flag, runs[-1][1] + character)
            else:
                runs.append((flag, character))
        row = "".join(
            f'<tspan fill="{kit.BLUE_LIGHT}" font-weight="600">{kit.esc(part)}</tspan>'
            if flag
            else kit.esc(part)
            for flag, part in runs
        )
        rows.append(f'<tspan x="{x:g}" y="{y + index * leading:g}">{row}</tspan>')
    return (
        f'<text class="b" font-size="{size:g}" fill="{kit.BODY}">{"".join(rows)}</text>',
        len(lines),
    )


def _kicker(ctx: dict, x: float, edge: float, y: float, size: float) -> str:
    """The top line: the greeting, a hairline, and the place behind its pin."""
    greeting, place = ctx["greeting"].upper(), ctx["location"].upper()
    place_w = kit.text_width(place, size, True, kit.TRACK) - kit.TRACK
    pin = edge - place_w - 12
    rule_from = x + kit.text_width(greeting, size, True, 2) + 8
    out = [
        kit.text(x, y, greeting, size, kit.BLUE_LIGHT, "k"),
        f'<path transform="translate({pin:g} {y - 3.5:g})" d="{PIN}" fill="none" stroke="{kit.META}" stroke-width="1.2"/>',
        f'<circle cx="{pin:g}" cy="{y - 5.4:g}" r="1.1" fill="{kit.META}"/>',
        kit.text(edge, y, place, size, kit.META, "m", "end"),
    ]
    if pin - 14 - rule_from >= 16:
        out.append(
            f'<path d="M{rule_from:g} {y - 3.5:g}H{pin - 14:g}" stroke="{kit.HAIR_STRONG}"/>'
        )
    return "".join(out)


def _fit_line(line: str, size: float, floor: float, room: float) -> tuple[str, float]:
    """A tagline at the largest size from `size` down to `floor` that fits `room`.

    One still too long at the floor ends on its last whole word that fits, so the window
    never cuts a word. Returns (line, size).
    """
    while size > floor and kit.text_width(line, size) > room:
        size = max(floor, size - 0.5)
    if kit.text_width(line, size) > room:
        words = line.split()
        while len(words) > 1 and kit.text_width(" ".join(words), size) > room:
            words.pop()
        line = " ".join(words).rstrip(",;:")
    return line, size


def _tagline(
    lines: list[str],
    bar_x: float,
    x: float,
    y: float,
    size: float,
    edge: float,
    floor: float,
) -> tuple[str, str]:
    """The taglines behind their blue bar at bar_x, on a reel, one at a time on the 3 s beat.

    The lines are set in the ink, so the bar is the accent and the intro's keywords are
    the only blue words on the card. A line too long for the window steps down towards
    `floor` (see _fit_line). Returns (svg, the reel's clip for the defs).
    """
    clip = "tag"
    fitted = [_fit_line(line, size, floor, edge - x) for line in lines if line][:4]
    if not fitted:
        return "", ""
    bar = (
        f'<rect x="{bar_x:g}" y="{y - size * 0.9:g}" width="2" height="{size * 1.1:g}" '
        f'rx="1" fill="{kit.BLUE}"/>'
    )
    if len(fitted) == 1:
        line, fit = fitted[0]
        return bar + kit.text(x, y, line, fit, kit.INK, "s"), ""
    pitch = round(size * 1.7)
    rows = "".join(
        kit.text(x, y + index * pitch, line, fit, kit.INK, "s")
        for index, (line, fit) in enumerate([*fitted, fitted[0]])
    )
    slot = T / len(fitted)
    turns = [slot * (index + 1) for index in range(len(fitted))]
    window = _window(clip, x - 2, y - size - 1, edge - x + 2, size + 7)
    return bar + _reel(rows, pitch, turns, clip), window


def _pill(
    now: str, x: float, y: float, column: float, size: float, hug: bool
) -> tuple[str, float]:
    """The availability pill: the green live dot and the line as he wrote it.

    Returns (svg, height).
    """
    lines = kit.balance(kit.wrap_text(now, column - 42, size))
    step = size + 4
    tall = max(26, 8 + step * len(lines))
    first = y + tall / 2 - step * (len(lines) - 1) / 2
    wide, pin = column, ""
    if hug and len(lines) == 1:
        # one line hugs its text. textLength pins the line to the width the pill is cut
        # for, so the space after it matches the space before the dot in any font.
        length = round(kit.text_width(lines[0], size) * SANS_FIT)
        wide, pin = min(column, 28 + length + 12), f' textLength="{length:g}"'
    out = [
        f'<rect x="{x:g}" y="{y:g}" width="{wide:g}" height="{tall:g}" rx="13" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>',
        kit.live_dot(x + 15, first, kit.GREEN, 3.5),
    ]
    for index, line in enumerate(lines):
        out.append(
            kit.text(
                x + 28,
                first + step * index + size * 0.36,
                line,
                size,
                kit.INK,
                "s",
                extra=pin,
            )
        )
    return "".join(out), tall


def _lit(x: float, y: float, w: float, h: float, extra: str = "") -> str:
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="10" fill="{kit.BLUE_TINT}" '
        f'stroke="{kit.BLUE_EDGE}" stroke-width="1.5"{extra}>'
    )


def _selector(count: int, x: float, y: float, w: float, h: float, pitch: float) -> str:
    """One lit border that steps along the proof row, a cell at a time, between the scene's beats."""
    if count < 2:
        return _lit(x, y, w, h) + "</rect>"
    loop, slot = _proof_clock(count)
    moves, blink = [(0.0, 0.0)], [(0.0, "1")]
    for index in range(1, count):
        at = PROOF_AT + slot * (index - 1)
        moves += [(at - 0.35, (index - 1) * pitch), (at, index * pitch)]
    # back to the first cell: fade out at the last one, fade in at the first
    home = PROOF_AT + slot * (count - 1)
    moves += [(home - 0.2, (count - 1) * pitch), (home - 0.15, 0.0), (loop, 0.0)]
    blink += [
        (home - 0.35, "1"),
        (home - 0.2, "0"),
        (home - 0.15, "0"),
        (home, "1"),
        (loop, "1"),
    ]
    return (
        _lit(x, y, w, h)
        + _anim("opacity", blink, loop)
        + _travel(moves, dur=loop)
        + "</rect>"
    )


def _label(ctx: dict) -> str:
    proof = ", ".join(f"{cell['value']} {cell['label']}" for cell in ctx["proof"])
    parts = [f"{NAME}, {ctx['aws_title_long']}, {ctx['location']}."]
    if ctx["availability"]:
        parts.append(ctx["availability"].rstrip(".") + ".")
    parts.append(ctx["intro"])
    if proof:
        parts.append(proof + ".")
    spoken = [said for _, said, _, _ in NODES]
    parts.append(
        f"The diagram is a cloud platform at the centre of {', '.join(spoken[:-1])} and "
        f"{spoken[-1]}, which come up one at a time until the platform is live."
    )
    return " ".join(parts)


# ---------------------------------------------------------------- desktop
def _desktop(ctx: dict) -> str:
    w, left, column = 840, 24, 424
    edge = left + column
    leading, floor = 18, 256  # the proof row never sits higher than this

    def column_body(drop: float) -> tuple[str, str, str, float]:
        """The name, role, tagline, pill and intro, set `drop` lower.

        Returns (what is there from the first frame, what enters, the tagline's clip,
        the last intro baseline).
        """
        fixed = kit.text(
            left - 2,
            88 + drop,
            NAME,
            56,
            kit.INK,
            "t",
            extra=' style="letter-spacing:-1.6px"',
        ) + kit.text(left, 116 + drop, ctx["aws_title_long"], 16, kit.INK, "s")
        entering, clip = _tagline(
            ctx["hero_lines"], left, left + 12, 143 + drop, 14.5, edge, 12.5
        )
        y = 180 + drop
        if ctx["availability"]:
            pill, tall = _pill(
                ctx["availability"], left, 158 + drop, column, 12.5, True
            )
            entering += pill
            y = 158 + drop + tall + 22
        intro, count = _intro(
            ctx["intro"], ctx["intro_keywords"], left, y, column, 13.5, leading
        )
        return fixed, entering + intro, clip, y + (count - 1) * leading

    # the proof row sits under whichever column ends lower, and as much lower again as puts
    # the card's foot on the 8px grid. Where the left column ends short of it (no pill, or a
    # shorter intro), the block under the kicker is centred in the space it has, so the
    # slack is shared above the name and below the intro.
    cells = ctx["proof"][:4]
    tall = 56 if cells else -16
    last = column_body(0)[3]
    top = math.ceil((max(floor, last + 14) + tall + 24) / 8) * 8 - tall - 24
    fixed, entering, window, _ = column_body(round((top - last - 14) / 2))
    out = [_kicker(ctx, left, edge, 32, 11), fixed, kit.group(0, entering)]

    # the scene panel fills the height above the proof row
    sx, sy, sw, sh = 464, 24, 352, top - 40
    out.append(_scene_block(sx, sy, sw, sh, False))

    if cells:
        gap = 16
        wide = (w - 2 * left - gap * (len(cells) - 1)) / len(cells)
        row = [
            f'<rect x="{left + index * (wide + gap):g}" y="{top:g}" width="{wide:g}" height="{tall}" rx="10" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
            for index in range(len(cells))
        ]
        row.append(_selector(len(cells), left, top, wide, tall, wide + gap))
        for index, cell in enumerate(cells):
            x = left + index * (wide + gap)
            row.append(
                kit.text(x + 14, top + 30, cell["value"], 24, kit.INK, "n")
                + kit.text(
                    x + 14, top + 45, cell["label"].upper(), kit.MICRO, kit.META, "m"
                )
            )
        out.append(kit.group(2 * kit.STAGGER, "".join(row)))
    h = top + tall + 24
    defs = _scene_defs(sw, sh, False) + window
    return kit.card_open(w, h, _label(ctx), defs) + "".join(out) + kit.SVG_CLOSE


# ---------------------------------------------------------------- phone
def _phone(ctx: dict) -> str:
    w, pad = 320, 18
    column, edge = w - pad * 2, w - pad
    size, leading = kit.MICRO_PHONE, 17
    out = [
        _kicker(ctx, pad, edge, 26, size),
        kit.text(
            pad - 1, 60, NAME, 32, kit.INK, "t", extra=' style="letter-spacing:-0.9px"'
        ),
    ]

    y = 80.0
    for line in _role_lines(ctx["aws_title_long"], column, 14.5):
        out.append(kit.text(pad, y, line, 14.5, kit.INK, "s"))
        y += 18
    y += 2
    # the longest line still ends inside the column by kit's measure, so the bar sits closer
    body, window = _tagline(ctx["hero_lines"], pad, pad + 7, y, 13, edge, 11.5)
    y += 16 if body else -8  # the pill clears the tagline's descenders

    if ctx["availability"]:
        pill, tall = _pill(ctx["availability"], pad, y, column, 12.5, False)
        body += pill
        y += tall + 8
    scene_y, scene_h = y, PHONE["high"]
    y += scene_h + 16
    intro, count = _intro(
        ctx["intro"], ctx["intro_keywords"], pad, y, column, 13.5, leading
    )
    out.append(kit.group(0, body + intro))
    out.append(_scene_block(pad, scene_y, column, scene_h, True))
    y += (count - 1) * leading

    cells = ctx["proof"][:4]
    if cells:
        y += 12
        gap = 8
        wide = (column - gap) / 2
        labels = [
            kit.wrap_text(cell["label"].upper(), wide - 24, size, True, kit.TRACK)
            for cell in cells
        ]
        # every cell is as tall as the longest label of the four needs, so the grid is even
        most = max(len(lines) for lines in labels)
        tall = max(44, 26 + 13 * most)
        inset = (tall - 26 - 13 * most) / 2
        loop, slot = _proof_clock(len(cells))
        row = []
        for index, cell in enumerate(cells):
            x = pad + (index % 2) * (wide + gap)
            top = y + (index // 2) * (tall + gap)
            row.append(
                f'<rect x="{x:g}" y="{top:g}" width="{wide:g}" height="{tall:g}" rx="10" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
            )
            if len(cells) > 1:
                # the cells sit in two rows, so the lit border fades from one to the next
                rest = "" if index == 0 else ' opacity="0"'
                since = PROOF_AT + slot * (index - 1) - 0.2
                row.append(
                    _lit(x, top, wide, tall, rest)
                    + _on(since, since + slot, dur=loop)
                    + "</rect>"
                )
            row.append(
                kit.text(x + 12, top + inset + 21, cell["value"], 21, kit.INK, "n")
            )
            for line_index, line in enumerate(labels[index]):
                row.append(
                    kit.text(
                        x + 12,
                        top + inset + 34 + line_index * 13,
                        line,
                        size,
                        kit.META,
                        "m",
                    )
                )
        out.append(kit.group(2 * kit.STAGGER, "".join(row)))
        rows = (len(cells) + 1) // 2
        y += rows * tall + (rows - 1) * gap
    h = round(y + 16)
    defs = _scene_defs(column, scene_h, True) + window
    return kit.card_open(w, h, _label(ctx), defs) + "".join(out) + kit.SVG_CLOSE


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return the hero at both widths."""
    return {"hero.svg": _desktop(ctx), "hero-mobile.svg": _phone(ctx)}
