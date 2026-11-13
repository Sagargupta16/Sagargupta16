"""The hero: the first screen of the profile, with a Terraform run as its scene.

Left: the greeting, the name, the role, one tagline at a time, the availability pill and the
intro sentence. Right: two changes run PLAN, GUARDRAILS and APPLY. The compliant one passes
every stage and rolls out to the accounts; the one that is not is turned off the rail at the
guardrails and drops into the result line, marked. Below both: the proof row. The scene keeps
one 12 s clock on a 1.5 s beat, and every element rests on the finished, checked state, so a
still render shows the whole card.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
from __future__ import annotations

import math
from itertools import pairwise

import kit

T = kit.T
NAME = "Sagar Gupta"

# ---------------------------------------------------------------- the clock
# Seconds on the 12 s loop. The scene's beats sit on a 1.5 s grid and the tagline
# turns on 0, 3, 6 and 9. The proof row's light keeps off both: it moves at 5 and 11,
# while a change waits in the guardrails and once the run has closed.
BEAT = 1.5
REWIND = 2.5  # the finished frame holds until here, then clears right to left
WIPE = 0.4  # how long the clearing takes
DOCK = (3.0, 4.5, 6.0)  # the first change docks at PLAN, GUARDRAILS, APPLY
STAY = 0.9  # a change stays docked this long; the stage ticks as it leaves
FOLLOW = 2 * BEAT  # the second change runs this far behind the first
DENY = DOCK[1] + FOLLOW  # it reaches the guardrails here and is turned away
TURN = DENY + 0.5  # it leaves the gate for the fork
LAND = DENY + 1.2  # and comes to rest in the result line
# The label row is narrower than a change, so the denied one is out of sight while it drops
# through it: it has faded out by GONE, just off the rail, and fades back in its slot from BACK.
GONE, BACK = TURN + 0.35, LAND - 0.1
ROLLOUT = 7.5  # the first change reaches the accounts
DONE = 10.5  # the closing check and the result line
ROLL = 0.3  # how long a reel takes to turn to its next row
PROOF_AT = 5.0  # the proof light's first move; the rest follow a whole slot apart
PROOF_SLOT = 6.0  # how long the light rests on a cell when there are four

# The two changes, in Terraform plan notation. They are a diagram's examples,
# not claims: + adds, ~ updates in place, and the second is not compliant.
PASSED, HELD = "+ vpc", "~ s3"
TITLE = "TERRAFORM RUN"
STAGES = ("PLAN", "GUARDRAILS", "APPLY")
TARGET = "ACCOUNTS"
STATUS = (  # what the result line says while the run is going, and from when
    ("PLANNING", DOCK[0]),
    ("CHECKING", DOCK[1]),
    ("APPLYING", DOCK[2]),
    ("ROLLING OUT", ROLLOUT),
)
APPLIED, DENIED = "1 APPLIED", "1 DENIED"

ICONS = (
    "M3 6h4M5 4v4M10 6h11M3 12h4M10 12h8M3 18h4M5 16v4M10 18h11",  # plan: a diff
    "M12 2.8l7.5 2.8v5.6c0 4.8-3.2 8.3-7.5 10-4.3-1.7-7.5-5.2-7.5-10V5.6z",  # guardrails: a shield
    "M3.5 12h11.5M10.5 7l5 5-5 5M20 5v14",  # apply: an arrow landing on its target
)
TICK = "M-3.4 0.2l2.3 2.3 4.5-4.8"
CROSS = "M-2.4 -2.4l4.8 4.8M2.4 -2.4l-4.8 4.8"
PIN = "M0 -5.5a3.6 3.6 0 0 1 3.6 3.6c0 2.7-3.6 6.4-3.6 6.4s-3.6-3.7-3.6-6.4a3.6 3.6 0 0 1 3.6-3.6z"
TILE = (
    "rgba(255,255,255,0.04)"  # a stage tile; translucent, so the rail shows through it
)
SMOOTH = "0.4 0 0.2 1"  # ease in and out, for a change that travels and stops
JOIN = chr(0x2060)  # holds a keyword phrase together while the intro wraps
FILL = (
    0.6  # a keyword phrase may break across lines sooner than leave a line this short
)
SANS_FIT = 0.9  # kit measures sans text wide on purpose; a 600-weight line sets at about this share

# The scene's measures at each width. plain and gate are tile widths, lift is how far the
# gate stands past its neighbours, icon and rail are offsets from the tiles' top edge,
# track is the labels' letter-spacing and high is the panel height the stages are placed for.
DESKTOP = {
    "left": 18, "right": 18, "plain": 52, "gate": 76, "top": 52, "tall": 84, "lift": 6,
    "icon": 25, "rail": 59, "scale": 1.1, "cell": 14, "space": 6, "rows": 3, "columns": 4,
    "size": kit.MICRO, "track": kit.TRACK, "label": 22, "ring": 10, "chip": 18, "pad": 6,
    "title": 31, "foot": 44, "pitch": 28, "high": 216,
}  # fmt: skip
PHONE = {
    "left": 10, "right": 12, "plain": 44, "gate": 72, "top": 13, "tall": 42, "lift": 3,
    "icon": 12, "rail": 30, "scale": 0.72, "cell": 11, "space": 5, "rows": 2, "columns": 3,
    "size": kit.MICRO_PHONE, "track": 0.8, "label": 18, "ring": 7, "chip": 16, "pad": 3,
    "title": 0, "foot": 26, "pitch": 24, "high": 106,
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
def _stroke(d: str, color: str, width: float, at: str = "") -> str:
    move = f' transform="translate({at})"' if at else ""
    return (
        f'<path{move} d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _badge(cx: float, cy: float, r: float, fill: str, ink: str = kit.INK) -> str:
    """A done mark: a filled disc with a tick, on a stage's corner or in the result line."""
    return f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{fill}"/>' + _stroke(
        TICK, ink, 1.7, f"{cx:g} {cy:g}"
    )


def _micro(x: float, y: float, label: str, fill: str, g: dict, anchor: str = "") -> str:
    """A scene label: the mono micro-label, set a little tighter where the phone measures ask."""
    tight = ""
    if g["track"] != kit.TRACK:
        tight = f' style="letter-spacing:{g["track"]:g}px"'
    return kit.text(x, y, label, g["size"], fill, "m", anchor, tight)


def _micro_width(label: str, g: dict) -> float:
    return kit.text_width(label, g["size"], True, g["track"]) - g["track"]


def _chip_width(label: str, size: float, pad: float) -> float:
    return round(kit.text_width(label, size, True, 0) + pad * 2)


def _chip(label: str, size: float, tall: float, pad: float, solid: bool) -> str:
    """A change, centred on 0,0: solid while it travels, an outline once it is held."""
    wide = _chip_width(label, size, pad)
    paint, ink = (
        (f'fill="{kit.SKY}"', kit.BG)
        if solid
        else (f'fill="{kit.CARD}" stroke="{kit.META}"', kit.BODY)
    )
    # textLength pins the label to its measured width, so it sits inside the chip in any mono font
    return (
        f'<rect x="{-wide / 2:g}" y="{-tall / 2:g}" width="{wide:g}" height="{tall:g}" rx="5" {paint}/>'
        + kit.text(
            0,
            size * 0.36,
            label,
            size,
            ink,
            "c",
            "middle",
            f' textLength="{wide - pad * 2:g}" style="font-weight:700"',
        )
    )


def _stops(w: float, g: dict) -> tuple[list[float], list[float], float]:
    """Where the three stages and the accounts sit in a panel w wide.

    Returns (centres, widths, fork). The four labels are set with the same clear space
    between every two of them, and each tile is centred over its own label, so a label
    that is wider than its tile never crowds the next one. The fork is where a denied
    change leaves the rail: midway between the guardrails and the apply stage.
    """
    block = g["columns"] * g["cell"] + (g["columns"] - 1) * g["space"]
    widths = [g["plain"], g["gate"], g["plain"], block]
    labels = [_micro_width(name, g) for name in (*STAGES, TARGET)]
    first = g["left"] + max(widths[0], labels[0]) / 2
    last = w - g["right"] - max(widths[-1], labels[-1]) / 2
    gap = (last - first - sum(labels) + (labels[0] + labels[-1]) / 2) / 3
    centers = [first]
    for before, after in pairwise(labels):
        centers.append(centers[-1] + before / 2 + gap + after / 2)
    tiles = (centers[1] + widths[1] / 2 + centers[2] - widths[2] / 2) / 2
    words = (centers[1] + labels[1] / 2 + centers[2] - labels[2] / 2) / 2
    return centers, widths, round((tiles + words) / 2, 1)


def _scene(w: float, h: float, phone: bool) -> str:
    """The Terraform run, drawn from 0,0 in a w by h panel."""
    g = PHONE if phone else DESKTOP
    left, tall, size = g["left"], g["tall"], g["size"]
    top = g["top"] + max(0.0, h - g["high"]) / 2  # a taller panel centres the stages
    all_centers, all_widths, fork = _stops(w, g)
    centers, widths = all_centers[:3], all_widths[:3]
    xs = [center - width / 2 for center, width in zip(centers, widths)]
    block_center = all_centers[3]
    block_x = block_center - all_widths[3] / 2
    rail = top + g["rail"]
    label_y = top + tall + g["label"]
    start = -g["plain"]  # where a change waits, outside the panel
    foot, pitch, chip, pad = g["foot"], g["pitch"], g["chip"], g["pad"]
    mid = (
        h - foot / 2
    )  # the result line's centre; the denied change comes to rest on it
    held_w = _chip_width(HELD, size, pad)

    out = [
        f'<rect x="0.5" y="0.5" width="{w - 1:g}" height="{h - 1:g}" rx="10" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>',
        f'<rect x="1" y="1" width="{w - 2:g}" height="{h - 2:g}" rx="9" fill="url(#dots)"/>',
    ]
    if g["title"]:
        out.append(_micro(left, g["title"], TITLE, kit.BLUE_LIGHT, g))

    # the result line's rule, then the branch a denied change takes: off the rail after the
    # guardrails and down into the result line, where a slot waits for it
    out.append(
        f'<path d="M0 {h - foot:g}H{w:g}" stroke="{kit.HAIR_STRONG}"/>'
        f'<path d="M{fork:g} {rail:g}V{mid - chip / 2:g}" fill="none" stroke="{kit.META}" stroke-width="1.5" stroke-dasharray="2 4"/>'
        f'<rect x="{fork - held_w / 2:g}" y="{mid - chip / 2:g}" width="{held_w:g}" height="{chip:g}" rx="5" fill="none" stroke="{kit.HAIR_STRONG}" stroke-dasharray="2 3"/>'
    )

    # the rail at rest, then the lit length that follows the first change and stays lit once it lands
    lit = [(0.0, "0"), (REWIND, "0"), (REWIND + WIPE, f"{block_x:g}")]
    for center, dock in zip(centers, DOCK):
        lit += [(dock, f"{block_x - center:g}"), (dock + STAY, f"{block_x - center:g}")]
    lit += [(ROLLOUT, "0"), (T, "0")]
    out.append(
        f'<path d="M0 {rail:g}H{block_x:g}" fill="none" stroke="{kit.HAIR_STRONG}" stroke-width="1.5"/>'
        f'<path d="M0 {rail:g}H{block_x:g}" fill="none" stroke="{kit.BLUE_EDGE}" stroke-width="1.5" '
        f'pathLength="{block_x:g}" stroke-dasharray="{block_x:g} {block_x:g}" stroke-dashoffset="0">'
        + _anim("stroke-dashoffset", lit)
        + "</path>"
        f'<circle cx="{fork:g}" cy="{rail:g}" r="2.5" fill="{kit.BLUE_LIGHT}"/>'
    )

    # the stages: a tile with its glyph, the rail running through it. The guardrails
    # tile is the gate, so it is wider and stands past the other two.
    scale = g["scale"]
    boxes = []
    for index, (x, width, name) in enumerate(zip(xs, widths, STAGES)):
        lift = g["lift"] if index == 1 else 0
        box = (x, top - lift, width, tall + 2 * lift)
        boxes.append(box)
        out.append(
            f'<rect x="{box[0]:g}" y="{box[1]:g}" width="{box[2]:g}" height="{box[3]:g}" rx="8" fill="{TILE}" stroke="{kit.HAIR_STRONG}"/>'
            f'<path transform="translate({centers[index] - 12 * scale:g} {top + g["icon"] - 12 * scale:g}) scale({scale:g})" d="{ICONS[index]}" '
            f'fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
            + _micro(centers[index], label_y, name, kit.INK, g, "middle")
        )
    # an arrow in the gap before the gate and before the accounts; the fork marks the third
    for x in ((xs[0] + widths[0] + xs[1]) / 2, (xs[2] + widths[2] + block_x) / 2):
        out.append(
            _stroke("M-1.75 -3.5l3.5 3.5-3.5 3.5", kit.META, 1.3, f"{x:g} {rail:g}")
        )

    # the gate answers the second change: a ring closes round it once as it shuts
    x, y, width, height = boxes[1]
    out.append(
        f'<rect x="{x - 2.5:g}" y="{y - 2.5:g}" width="{width + 5:g}" height="{height + 5:g}" rx="10" fill="none" stroke="{kit.INK}" stroke-width="1.5" opacity="0">'
        + _on(DENY, DENY + 0.45, 0.15)
        + "</rect>"
    )

    # a stage lights as the first change leaves it, and plan and apply take a done mark on
    # the corner. The gate takes none: its two answers are marked where each change ends up.
    for index, (x, y, width, height) in enumerate(boxes):
        mark = "" if index == 1 else _badge(x + width - 4, y + 4, 8, kit.BLUE_EDGE)
        out.append(
            "<g>"
            + _on(DOCK[index] + STAY - 0.2, REWIND + 0.08 * (2 - index))
            + f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="8" fill="{kit.BLUE_TINT}" stroke="{kit.BLUE_LIGHT}" stroke-width="1.5"/>'
            + mark
            + "</g>"
        )

    # the accounts: whole columns of cells that turn ready one after another
    cell, space, rows, columns = g["cell"], g["space"], g["rows"], g["columns"]
    block_h = rows * cell + (rows - 1) * space
    block_y = min(rail - block_h / 2, top + tall - block_h)
    step = (DONE - ROLLOUT) / columns
    for column in range(columns):
        cx = block_x + column * (cell + space)
        idle = "".join(
            f'<rect x="{cx:g}" y="{block_y + row * (cell + space):g}" width="{cell:g}" height="{cell:g}" rx="3" fill="none" stroke="{kit.HAIR_STRONG}"/>'
            for row in range(rows)
        )
        ready = "".join(
            f'<rect x="{cx:g}" y="{block_y + row * (cell + space):g}" width="{cell:g}" height="{cell:g}" rx="3" fill="{kit.BLUE}" stroke="{kit.BLUE_LIGHT}"/>'
            for row in range(rows)
        )
        out.append(f"{idle}<g>{_on(ROLLOUT + column * step, REWIND)}{ready}</g>")
    out.append(_micro(block_center, label_y, TARGET, kit.INK, g, "middle"))

    # the close: a ring over the accounts that fills with a green check once every column is ready
    ring = g["ring"]
    ring_y = block_y - ring - 5
    out.append(
        f'<circle cx="{block_center:g}" cy="{ring_y:g}" r="{ring:g}" fill="none" stroke="{kit.HAIR_STRONG}" stroke-width="1.5"/>'
        f"<g>{_on(DONE - 0.2, REWIND)}{_badge(block_center, ring_y, ring, kit.GREEN, kit.BG)}</g>"
    )

    # the first change: in from the left, a stop in each stage, then into the accounts
    run = [(0.0, start), (DOCK[0] - 0.3, start)]
    for center, dock in zip(centers, DOCK):
        run += [(dock, center), (dock + STAY, center)]
    run += [(ROLLOUT, block_x + 4), (T, block_x + 4)]
    out.append(
        f'<g opacity="0" transform="translate({start:g} 0)">'
        + _on(DOCK[0] - 0.3, ROLLOUT - 0.3)
        + _travel(run)
        + f'<g transform="translate(0 {rail:g})">{_chip(PASSED, size, chip, pad, True)}</g></g>'
    )

    # the second change follows it, knocks at the guardrails, is turned off the rail at the
    # fork and drops into the result line, where it rests in its slot. The dotted branch
    # shows the way down, so it fades out as it leaves the rail and back in once it is
    # under the labels.
    gate, clear = centers[1], REWIND + WIPE + 0.1
    across = [
        (0.0, fork),
        (clear, fork),
        (clear + 0.1, start),
        (DOCK[0] + FOLLOW - 0.3, start),
        (DOCK[0] + FOLLOW, centers[0]),
        (DOCK[0] + FOLLOW + STAY, centers[0]),
        (DENY, gate),
        (DENY + 0.08, gate - 3),
        (DENY + 0.16, gate + 3),
        (DENY + 0.24, gate - 2),
        (DENY + 0.32, gate),
        (TURN, gate),
        (TURN + 0.3, fork),
        (T, fork),
    ]
    down = [
        (0.0, mid),
        (clear, mid),
        (clear + 0.1, rail),
        (TURN + 0.3, rail),
        (LAND, mid),
        (T, mid),
    ]
    out.append(
        f'<g transform="translate({fork:g} 0)">'
        + _on(DOCK[0] + FOLLOW - 0.3, REWIND + 0.1)
        + _travel(across)
        + f'<g transform="translate(0 {mid:g})">'
        + _travel(down, "y")
        + _on(BACK, GONE - 0.15, 0.15)
        + _chip(HELD, size, chip, pad, False)
        # the travelling face covers the held one until the change is out of sight, so the
        # change comes back in its slot as the held face alone
        + f'<g opacity="0">{_on(clear, GONE, BACK - GONE)}{_chip(HELD, size, chip, pad, True)}</g>'
        + "</g></g>"
    )

    # the result line: where the run is while it goes, then how it ended. The applied
    # count sits on the left; the denied one is written beside the change it stopped.
    base = mid + size * 0.36
    rows_svg = []
    for index, label in enumerate((APPLIED, *(name for name, _ in STATUS), APPLIED)):
        y = index * pitch
        if label == APPLIED:
            rows_svg.append(
                _badge(left + 8, mid + y, 8, kit.BLUE)
                + _micro(left + 22, base + y, label, kit.INK, g)
            )
        else:
            rows_svg.append(
                f'<rect x="{left + 2:g}" y="{mid + y - 4:g}" width="12" height="8" rx="2.5" fill="{kit.SKY}"/>'
                + _micro(left + 22, base + y, label, kit.BLUE_LIGHT, g)
            )
    turns = [at for _, at in STATUS] + [DONE]
    # the denied mark: an outlined disc, quieter than the checks
    mark = fork + held_w / 2 + 13
    out.append(
        _reel("".join(rows_svg), pitch, turns, "run")
        + f"<g>{_on(LAND, REWIND)}"
        + f'<circle cx="{mark:g}" cy="{mid:g}" r="7" fill="none" stroke="{kit.META}" stroke-width="1.3"/>'
        + _stroke(CROSS, kit.INK, 1.6, f"{mark:g} {mid:g}")
        + _micro(mark + 15, base, DENIED, kit.META, g)
        + "</g>"
    )
    return "".join(out)


def _scene_defs(w: float, h: float, phone: bool) -> str:
    g = PHONE if phone else DESKTOP
    fork = _stops(w, g)[2]
    slot = fork - _chip_width(HELD, g["size"], g["pad"]) / 2
    return (
        f'<clipPath id="scene"><rect x="1" y="1" width="{w - 2:g}" height="{h - 2:g}" rx="9"/></clipPath>'
        # the status rows turn in a window that stops short of the denied change's slot
        + _window("run", 1, h - g["foot"] / 2 - g["pitch"] / 2, slot - 9, g["pitch"])
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
    parts.append(
        "The diagram is a Terraform run: one change passes plan, guardrails and apply "
        "and rolls out to the accounts, and one that is not compliant is denied at the guardrails."
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
