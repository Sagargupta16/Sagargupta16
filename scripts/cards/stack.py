"""The stack card: the tools he works with in four lanes, one lane lighting at a time."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# stack.svg (840 wide) and stack-mobile.svg (320 wide). The AI tools used to
# be a card of their own (ai-stack.svg); they are this card's third lane now.
#
# The list is curated, not fetched: it is what the portfolio backs (its skills
# and the stacks of his projects and engagements), in four lanes from the
# cloud up to the apps. Each tool is a tile with its Simple Icons glyph from
# ctx["icon"], defined once and recoloured with <use>; a tool the icon set
# lacks gets a mono monogram in the same box. The phone shows two rows a
# lane and a +N tile for the rest; the alt text names every tool.
#
# Motion, on the 12 s page clock: the lanes light in turn, 3 s each. The
# lane's border and number light, a sweep lights its tiles left to right,
# and on the desktop a line runs down the rail on the left to the next lane,
# then drains out at the bottom when the last lane is done. At rest (a still
# render) every lane is unlit and every tile is on the card.
from __future__ import annotations

import re

import kit

T = kit.T

# (lane, [(name, simple-icons slug or None, full name for the alt text or None)])
LANES: tuple = (
    (
        "Cloud and IaC",
        (
            ("AWS", "amazonwebservices", "Amazon Web Services"),
            ("Terraform", "terraform", None),
            ("Ansible", "ansible", None),
            ("Cloudflare", "cloudflare", None),
            ("Vercel", "vercel", None),
        ),
    ),
    (
        "CI/CD and platform",
        (
            ("GitHub Actions", "githubactions", None),
            ("Docker", "docker", None),
            ("Linux", "linux", None),
            ("Bash", "gnubash", None),
            ("Go", "go", None),
        ),
    ),
    (
        "AI and agents",
        (
            ("Claude Code", "claude", None),
            ("MCP", "modelcontextprotocol", "Model Context Protocol"),
            ("Bedrock", None, "Amazon Bedrock"),
            ("SageMaker", None, "Amazon SageMaker"),
            ("Kiro", None, None),
            ("Amazon Q", None, None),
            ("Codex", "openai", None),
            ("PyTorch", "pytorch", None),
            ("TensorFlow", "tensorflow", None),
        ),
    ),
    (
        "Apps and data",
        (
            ("TypeScript", "typescript", None),
            ("Python", "python", None),
            ("React", "react", None),
            ("Next.js", "nextdotjs", None),
            ("FastAPI", "fastapi", None),
            ("Node.js", "nodedotjs", None),
            ("PostgreSQL", "postgresql", None),
            ("Tailwind", "tailwindcss", "Tailwind CSS"),
            ("MongoDB", "mongodb", None),
            ("Redis", "redis", None),
            ("JavaScript", "javascript", None),
            ("C++", "cplusplus", None),
        ),
    ),
)

PHONE_ROWS = 2  # the most tile rows a lane shows on the phone; the rest is a +N tile
# A row's tiles widen together to end flush on the right, to this many times
# their own width at most; a sparse row stays left-aligned instead.
STRETCH = 1.6
SWEEP = 1.2  # seconds the light takes to cross a lane's tiles
FADE = 0.3

ICON = kit.BLUE_LIGHT  # a glyph at rest
LIT_ICON = kit.INK
LIT_TILE = "rgba(37,99,235,0.24)"  # a tint: the name under it shows through
LIT_NODE = kit.BLUE
RAIL = "rgba(96,165,250,0.3)"  # the desktop rail the lane numbers sit on
CSS = f".g{{font-family:{kit.MONO};font-weight:700}}"


class Layout:
    """Sizes for one width: the desktop card or its phone twin."""

    def __init__(self, phone: bool) -> None:
        self.phone = phone
        self.w = 320 if phone else 840
        self.pad = 16 if phone else 24
        self.micro = kit.MICRO_PHONE if phone else kit.MICRO
        self.leading = 15 if phone else 13  # between the lines of a wrapped lane label
        self.label_wrap = 72  # the desktop label column: "CI/CD AND" over "PLATFORM"
        self.name = 12.5  # a tool's name, sans
        self.icon = 16  # a glyph, centred in its slot
        self.box = 18  # the slot, and a monogram's box
        self.tile_h = 28 if phone else 30
        self.tile_pad = 7 if phone else 10
        self.icon_gap = 5 if phone else 8
        self.gap = 5 if phone else 6  # between tiles, and between rows
        self.inset = 8 if phone else 9  # a lane panel's padding
        self.node_r = 9 if phone else 10
        self.lane_gap = 8
        self.top = 42 if phone else 46  # the first lane's top edge
        self.bottom = 16 if phone else 20

    def tile_width(self, name: str) -> float:
        return (
            2 * self.tile_pad
            + self.box
            + self.icon_gap
            + kit.text_width(name, self.name)
        )

    def more_width(self, label: str) -> float:
        return 2 * self.tile_pad + kit.text_width(label, self.micro, True, kit.TRACK)


# ---------------------------------------------------------------- icon paths
# Simple Icons paths carry three decimals in a 24-unit box. Each glyph is
# scaled to the 16 px it is drawn at, every point rounded to a tenth of a
# pixel in absolute terms (so the error never adds up along a path) and
# written back relative: about a third of the bytes, and <use> needs no size.
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_ARITY = {
    "M": 2,
    "L": 2,
    "H": 1,
    "V": 1,
    "C": 6,
    "S": 4,
    "Q": 4,
    "T": 2,
    "A": 7,
    "Z": 0,
}


def _segments(d: str) -> list[tuple[str, list[float]]]:
    """Path data as (command, numbers), with implicitly repeated commands written out."""
    out: list[tuple[str, list[float]]] = []
    i = 0
    while i < len(d):
        character = d[i]
        if character.isalpha():
            out.append((character, []))
            i += 1
            continue
        if character in " ,\t\r\n" or not out:
            i += 1
            continue
        command, numbers = out[-1]
        arity = _ARITY[command.upper()]
        if not arity:
            i += 1
            continue
        if len(numbers) == arity:
            command = {"M": "L", "m": "l"}.get(command, command)
            numbers = []
            out.append((command, numbers))
        if command in "Aa" and len(numbers) in (3, 4):  # an arc flag is one digit
            numbers.append(float(character))
            i += 1
            continue
        match = _NUMBER.match(d, i)
        if not match:
            i += 1
            continue
        numbers.append(float(match.group()))
        i = match.end()
    return out


def absolute(d: str) -> list[tuple[str, list[float]]]:
    """Path data as upper-case commands with absolute coordinates."""
    out = []
    x = y = start_x = start_y = 0.0
    for command, a in _segments(d):
        up = command.upper()
        dx, dy = (x, y) if command != up else (0.0, 0.0)
        if up == "Z":
            out.append(("Z", []))
            x, y = start_x, start_y
        elif up == "H":
            x = a[0] + dx
            out.append(("H", [x]))
        elif up == "V":
            y = a[0] + dy
            out.append(("V", [y]))
        elif up == "A":
            x, y = a[5] + dx, a[6] + dy
            out.append(("A", [*a[:5], x, y]))
        else:
            points = [a[k] + (dx if k % 2 == 0 else dy) for k in range(len(a))]
            out.append((up, points))
            x, y = points[-2], points[-1]
            if up == "M":
                start_x, start_y = x, y
    return out


def _number(tenths: int) -> str:
    text = f"{tenths / 10:.1f}".rstrip("0").rstrip(".")
    if text.startswith("0."):
        return text[1:]
    if text.startswith("-0."):
        return "-" + text[2:]
    return "0" if text == "-0" else text


def tight(d: str, scale: float = 1.0) -> str:
    """The same outline in fewer bytes: scaled, points rounded to tenths of a unit, written relative."""
    out, last, previous = [], "", ""
    x = y = start_x = start_y = 0  # where the written path is, in tenths

    def put(command: str, numbers: list[str]) -> None:
        nonlocal last, previous
        if command != last or command == "m":
            out.append(command)
            previous = ""
        for number in numbers:
            if previous and not (
                number.startswith("-") or (number.startswith(".") and "." in previous)
            ):
                out.append(" ")
            out.append(number)
            previous = number
        last = command

    for command, a in absolute(d):
        q = [round(value * scale * 10) for value in a]
        if command == "Z":
            put("z", [])
            x, y = start_x, start_y
            previous = ""
            continue
        if command == "H":
            put("h", [_number(q[0] - x)])
            x = q[0]
            continue
        if command == "V":
            put("v", [_number(q[0] - y)])
            y = q[0]
            continue
        if command == "A":
            rx, ry, turn = q[0], q[1], round(a[2] * 10)  # the angle does not scale
            flags = [str(int(a[3])), str(int(a[4]))]
            put(
                "a",
                [_number(rx), _number(ry), _number(turn), *flags]
                + [_number(q[5] - x), _number(q[6] - y)],
            )
            x, y = q[5], q[6]
            continue
        relative = [q[k] - (x if k % 2 == 0 else y) for k in range(len(q))]
        if command == "L" and relative[1] == 0:
            put("h", [_number(relative[0])])
        elif command == "L" and relative[0] == 0:
            put("v", [_number(relative[1])])
        else:
            put(command.lower(), [_number(value) for value in relative])
        x, y = q[-2], q[-1]
        if command == "M":
            start_x, start_y = x, y
    return "".join(out)


# ---------------------------------------------------------------- layout
def monogram(name: str) -> str:
    """One or two capitals for a tool with no glyph: SageMaker SM, Amazon Q AQ, Kiro K."""
    parts = re.findall(r"[A-Z][a-z]*|[a-z]+|\d+", name)
    return "".join(part[0] for part in parts[:2]).upper() or name[:1].upper() or "?"


def _fit(name: str, room: float, size: float) -> str:
    """The name, or as much of it as fits `room` followed by three dots."""
    if kit.text_width(name, size) <= room:
        return name
    while name and kit.text_width(name + "...", size) > room:
        name = name[:-1]
    return name.rstrip() + "..."


def _greedy(widths: list[float], room: float, gap: float) -> int:
    """How many rows the tiles need when each row takes as many as fit."""
    rows, used = 1, 0.0
    for width in widths:
        if used and used + gap + width > room:
            rows, used = rows + 1, width
        else:
            used = used + gap + width if used else width
    return rows


def _split(widths: list[float], rows: int, gap: float) -> list[tuple[int, int]]:
    """Split the tiles, in order, into `rows` rows whose widest row is as narrow as it can be."""
    n = len(widths)
    inf = float("inf")
    run = [0.0]
    for width in widths:
        run.append(run[-1] + width)
    best = [[inf] * (n + 1) for _ in range(rows + 1)]
    cut = [[0] * (n + 1) for _ in range(rows + 1)]
    best[0][0] = 0.0
    for r in range(1, rows + 1):
        for j in range(r, n + 1):
            for i in range(r - 1, j):
                if best[r - 1][i] == inf:
                    continue
                cost = max(best[r - 1][i], run[j] - run[i] + gap * (j - i - 1))
                if cost < best[r][j]:
                    best[r][j], cut[r][j] = cost, i
    bounds, j = [], n
    for r in range(rows, 0, -1):
        i = cut[r][j]
        bounds.append((i, j))
        j = i
    return bounds[::-1]


def arrange(
    tools: list[tuple], room: float, size: Layout, max_rows: int = 0
) -> tuple[list[list[dict]], int]:
    """Lay one lane's tiles into balanced rows no wider than `room`.

    Returns (rows, hidden): each row a list of {name, slug, x, w} with x from
    the row's left edge, and how many tools a +N tile stands for. With
    max_rows, the lane keeps the tools that fit that many rows and its last
    tile counts the rest.
    """
    longest = room - 2 * size.tile_pad - size.box - size.icon_gap
    items = [
        {"name": _fit(str(name), longest, size.name), "slug": slug, "more": False}
        for name, slug, *_ in tools
    ]
    if not items:
        return [], 0
    widths = [size.tile_width(item["name"]) for item in items]
    hidden = 0
    if max_rows and _greedy(widths, room, size.gap) > max_rows:
        for keep in range(len(items) - 1, 0, -1):
            more = size.more_width(f"+{len(items) - keep}")
            if _greedy([*widths[:keep], more], room, size.gap) <= max_rows:
                break
        else:
            keep = 1
        hidden = len(items) - keep
        label = f"+{hidden}"
        items = [*items[:keep], {"name": label, "slug": None, "more": True}]
        widths = [*widths[:keep], size.more_width(label)]
    rows = []
    for start, end in _split(widths, _greedy(widths, room, size.gap), size.gap):
        row_widths = widths[start:end]
        # every tile widens by the same share until the row is flush, by STRETCH at most
        free = room - size.gap * (len(row_widths) - 1)
        scale = min(STRETCH, free / sum(row_widths))
        x, row = 0.0, []
        for item, width in zip(items[start:end], row_widths):
            row.append(item | {"x": x, "w": width * scale})
            x += width * scale + size.gap
        rows.append(row)
    return rows, hidden


# ---------------------------------------------------------------- timing
def _n(value: float, places: int = 1) -> str:
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _loop(attribute: str, points: list, kind: str = "") -> str:
    """One 12 s animation from [(seconds, value)]; the ends are padded with the first and last value."""
    points = sorted(points, key=lambda point: point[0])
    if points[0][0] > 0:
        points.insert(0, (0, points[0][1]))
    if points[-1][0] < T:
        points.append((T, points[-1][1]))
    values = ";".join(str(value) for _, value in points)
    times = ";".join(_n(min(1.0, at / T), 4) for at, _ in points)
    if kind:
        return (
            f'<animateTransform attributeName="transform" type="{kind}" values="{values}" '
            f'keyTimes="{times}" dur="{T:g}s" repeatCount="indefinite"/>'
        )
    return (
        f'<animate attributeName="{attribute}" values="{values}" keyTimes="{times}" '
        f'dur="{T:g}s" repeatCount="indefinite"/>'
    )


class Clock:
    """The lanes share the 12 s loop: each lights for its slot, 3 s when there are four."""

    def __init__(self, count: int) -> None:
        self.slot = T / max(count, 1)
        self.fade = min(FADE, self.slot / 8)
        self.sweep = min(SWEEP, self.slot / 2)
        self.rest = min(0.1, self.slot / 20)  # dark between two lanes

    def window(self, index: int) -> tuple[float, float]:
        """When lane `index` starts to light and when it is dark again, in seconds."""
        return index * self.slot, (index + 1) * self.slot - self.rest


# ---------------------------------------------------------------- drawing
def _tiles(
    rows: list[list[dict]],
    x0: float,
    y0: float,
    size: Layout,
    symbols: dict,
    lit: bool,
) -> str:
    """One lane's tiles, each part as one group: boxes, glyphs, monograms and names.

    The lit layer is a blue tint over the boxes and the glyphs and monograms
    again in white; the names under it stay as they are, so it draws none.
    """
    boxes, glyphs, marks, letters, names, more = [], [], [], [], [], []
    for r, row in enumerate(rows):
        y = y0 + r * (size.tile_h + size.gap)
        middle = y + size.tile_h / 2
        for tile in row:
            x = x0 + tile["x"]
            boxes.append(
                f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(tile["w"])}" height="{size.tile_h}" rx="7"/>'
            )
            if tile["more"]:
                more.append(
                    f'<text x="{_n(x + tile["w"] / 2)}" y="{_n(middle + size.micro * 0.36)}">{tile["name"]}</text>'
                )
                continue
            content = size.box + size.icon_gap + kit.text_width(tile["name"], size.name)
            left = x + (tile["w"] - content) / 2
            cx = left + size.box / 2  # the middle of the glyph's slot
            symbol = symbols.get(tile["slug"])
            if symbol:
                glyphs.append(
                    f'<use href="#{symbol}" x="{_n(cx - size.icon / 2)}" y="{_n(middle - size.icon / 2)}"/>'
                )
            else:
                half = size.box / 2
                marks.append(
                    f'<rect x="{_n(cx - half)}" y="{_n(middle - half)}" width="{size.box}" height="{size.box}" rx="4"/>'
                )
                letters.append(
                    f'<text x="{_n(cx)}" y="{_n(middle + size.micro * 0.36)}">{kit.esc(monogram(tile["name"]))}</text>'
                )
            names.append(
                f'<text x="{_n(left + size.box + size.icon_gap)}" y="{_n(middle + size.name * 0.36)}">{kit.esc(tile["name"])}</text>'
            )
    fill, edge = (LIT_TILE, kit.BLUE_EDGE) if lit else (kit.BG, kit.HAIR_STRONG)
    glyph = LIT_ICON if lit else ICON
    out = f'<g fill="{fill}" stroke="{edge}">{"".join(boxes)}</g>'
    if glyphs:
        out += f'<g fill="{glyph}">{"".join(glyphs)}</g>'
    if marks:
        out += (
            f'<g fill="none" stroke="{glyph}" stroke-width="1.2">{"".join(marks)}</g>'
        )
        out += f'<g class="g" font-size="{size.micro:g}" fill="{glyph}" text-anchor="middle">{"".join(letters)}</g>'
    if names and not lit:
        out += f'<g class="s" font-size="{size.name:g}" fill="{kit.INK}">{"".join(names)}</g>'
    if more and not lit:
        out += f'<g class="m" font-size="{size.micro:g}" fill="{kit.META}" text-anchor="middle">{"".join(more)}</g>'
    return out


def _node(cx: float, cy: float, number: int, size: Layout, lit: bool) -> str:
    fill, edge, ink = (
        (LIT_NODE, kit.BLUE_LIGHT, kit.INK)
        if lit
        else (kit.BG, kit.BLUE_EDGE, kit.BLUE_LIGHT)
    )
    return (
        f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{size.node_r}" fill="{fill}" stroke="{edge}" stroke-width="1.5"/>'
        + kit.text(
            cx, cy + size.micro * 0.36, str(number), size.micro, ink, "g", "middle"
        )
    )


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _label(lanes: list[tuple]) -> str:
    """The alt text: every tool by its full name, lane by lane."""
    total = sum(len(tools) for _, tools in lanes)
    parts = [f"Tech stack, {_plural(total, 'tool')} in {_plural(len(lanes), 'lane')}."]
    for lane, tools in lanes:
        names = ", ".join(str(full or name) for name, _, full in tools)
        parts.append(f"{lane}: {names}.")
    return " ".join(parts)


def _card(lanes: list[tuple], icon, phone: bool) -> str:
    """The stack card at one width from (lane, tools) pairs; icon(slug) gives a glyph's path data or None."""
    size = Layout(phone)
    lanes = [(str(lane), list(tools)) for lane, tools in lanes if tools]
    count, clock = len(lanes), Clock(len(lanes))
    total = sum(len(tools) for _, tools in lanes)

    symbols, defs = {}, []
    for _, tools in lanes:
        for _, slug, _ in tools:
            if not slug or slug in symbols:
                continue
            path = icon(slug) if icon else None
            if path:
                symbols[slug] = f"i{len(symbols)}"
                defs.append(
                    f'<path id="{symbols[slug]}" d="{tight(path, size.icon / 24)}"/>'
                )

    left, right = size.pad, size.w - size.pad
    node_x = left + size.inset + size.node_r if phone else left + 20
    name_x = node_x + size.node_r + (8 if phone else 10)
    # the desktop column widens for a word longer than it, so no word splits
    words = [word for lane, _ in lanes for word in lane.upper().split()]
    longest_word = max(
        (kit.text_width(word, size.micro, True, kit.TRACK) for word in words),
        default=0,
    )
    wrap = right - size.inset - name_x if phone else max(size.label_wrap, longest_word)
    labels = [
        kit.wrap_text(lane.upper(), wrap, size.micro, True, kit.TRACK)
        for lane, _ in lanes
    ]
    if phone:
        tiles_x0 = left + size.inset
    else:
        # the tiles start after the widest lane label, which wraps to the column
        longest = max(
            (
                kit.text_width(line, size.micro, True, kit.TRACK) - kit.TRACK
                for lines in labels
                for line in lines
            ),
            default=0,
        )
        tiles_x0 = name_x + max(longest, 2 * size.node_r) + 18
    room = right - size.inset - tiles_x0

    panels, body, clips, nodes_y = [], [], [], []
    y = size.top
    for index, (lane, tools) in enumerate(lanes):
        rows, _ = arrange(tools, room, size, PHONE_ROWS if phone else 0)
        rows_h = len(rows) * size.tile_h + (len(rows) - 1) * size.gap
        lines = labels[index]
        label_h = (len(lines) - 1) * size.leading
        if phone:
            # the label is the lane's header line; the tiles sit under it
            node_y = y + size.inset + size.node_r + 1
            first_y = node_y
            tiles_y = node_y + label_h + size.node_r + 9
            height = tiles_y - y + rows_h + size.inset
        else:
            # the label sits beside the first row; one that wraps to more lines
            # than the row holds takes the lane's top and makes it taller
            block = max(size.tile_h, label_h + 2 * size.micro)
            node_y = y + size.inset + block / 2
            first_y = node_y - label_h / 2
            tiles_y = y + size.inset
            height = max(rows_h, block) + 2 * size.inset
        nodes_y.append(node_y)
        name = "".join(
            kit.text(
                name_x,
                first_y + k * size.leading + size.micro * 0.36,
                line,
                size.micro,
                kit.INK,
                "m",
            )
            for k, line in enumerate(lines)
        )
        on, off = clock.window(index)
        # the panels sit under the rail and the nodes on it, so a lane enters in two parts
        at = 0.18 + index * kit.STAGGER
        frame = f'x="{left}" y="{_n(y)}" width="{right - left}" height="{_n(height)}" rx="10"'
        panels.append(
            kit.group(
                at, f'<rect {frame} fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
            )
        )
        sweep_w = room + 4
        hidden = f"{_n(-sweep_w)} 0"
        clip_id = f"sweep{index}"
        clips.append(
            f'<clipPath id="{clip_id}"><rect x="{_n(tiles_x0 - 2)}" y="{_n(y)}" '
            f'width="{_n(sweep_w)}" height="{_n(height)}">'
            + _loop(
                "transform",
                [
                    (on + clock.fade / 2, hidden),
                    (on + clock.fade / 2 + clock.sweep, "0 0"),
                    (off, "0 0"),
                    (off + clock.rest / 2, hidden),
                ],
                "translate",
            )
            + "</rect></clipPath>"
        )
        fade = [(on, 0), (on + clock.fade, 1), (off - clock.fade, 1), (off, 0)]
        lit = (
            f'<g opacity="0">{_loop("opacity", fade)}'
            + f'<rect {frame} fill="none" stroke="{kit.BLUE_EDGE}" stroke-width="1.5"/>'
            + _node(node_x, node_y, index + 1, size, True)
            + f'<g clip-path="url(#{clip_id})">'
            + _tiles(rows, tiles_x0, tiles_y, size, symbols, True)
            + "</g></g>"
        )
        rest = (
            _node(node_x, node_y, index + 1, size, False)
            + name
            + _tiles(rows, tiles_x0, tiles_y, size, symbols, False)
        )
        body.append(kit.group(at, rest + lit))
        y += height + size.lane_gap

    height = y - size.lane_gap + size.bottom if lanes else size.top + size.bottom
    rail = ""
    if not phone and count > 1:
        # the line runs down to each lane as it lights and drains out after the last
        first, last = nodes_y[0], nodes_y[-1]
        d = f"M{_n(node_x)} {_n(first)}V{_n(last)}"

        def gone(index: int) -> str:
            """The dash offset that ends the lit line at that lane's node."""
            return _n(1 - (nodes_y[index] - first) / (last - first), 4)

        points = [(0, "1")]
        for index in range(1, count):
            on, _ = clock.window(index)
            points += [(on - clock.fade, gone(index - 1)), (on, gone(index))]
        _, end = clock.window(count - 1)
        points += [(end - clock.fade, "0"), (end, "-1")]
        rail = (
            kit.draw(d, 0.1, 0.8, RAIL, 1.5)
            + f'<path d="{d}" fill="none" stroke="{kit.BLUE_EDGE}" stroke-width="2" pathLength="1" '
            f'stroke-dasharray="1 1" stroke-dashoffset="1">'
            + _loop("stroke-dashoffset", points)
            + "</path>"
        )
    eyebrow = kit.text(
        size.pad,
        28 if phone else 30,
        f"{_plural(total, 'tool')} in {_plural(count, 'lane')}".upper(),
        size.micro,
        kit.BLUE_LIGHT,
        "m",
    )
    return (
        kit.card_open(
            size.w, height, _label(lanes), "".join(defs) + "".join(clips), CSS
        )
        + kit.group(0.1, eyebrow)
        + "".join(panels)
        + rail
        + "".join(body)
        + kit.SVG_CLOSE
    )


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text}: stack.svg and stack-mobile.svg."""
    icon = ctx.get("icon")
    return {
        "stack.svg": _card(list(LANES), icon, False),
        "stack-mobile.svg": _card(list(LANES), icon, True),
    }
