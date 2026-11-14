"""The career cards: the experience rails, education, and the AWS reviews, talks and programs.

Three cards at two widths, drawn from ctx["milestones"], ctx["engagements"],
ctx["education"] and ctx["recognition"]: experience.svg, education.svg and
publications.svg at 840px, and their -mobile.svg twins at 320px.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# The look is kit's: flat cards on BG, one blue family, mono micro-labels, and
# green only on what is live (the current role and the engagement going on
# now). Each card has one motion on the 12 s page clock and every poster is
# the finished card:
#   experience    a light runs the whole career: along the milestone rail, down
#                 from the current role, back along the bracket and through the
#                 engagements, lighting each panel as it passes and landing on
#                 the one going on now
#   education     a light runs through the degrees in the order they were taken
#   publications  a spotlight steps from panel to panel
from __future__ import annotations

import re

import kit

T = kit.T
WIDTH, PHONE = 840, 320
LEFT, RIGHT = 24, WIDTH - 24  # the desktop content edges
PHONE_PAD = 16
DOT = chr(0xB7)  # the middle dot a phone line joins two facts with
JOIN = chr(0x2060)  # holds two words on one line while a phone line wraps
SEP = " | "  # between the parts of an eyebrow (SVG shows a run of spaces as one)

# ---------------------------------------------------------------- the loop
LOOP_AT = 2.0  # the light leaves once the entrance is over
SPEED = 420.0  # px per second along a rail
RUN_MAX = 5.5  # the whole run never takes longer than this
CHIP_GAP = 6

# ---------------------------------------------------------------- experience
# Both layouts show the newest four engagements, so a fifth cannot crowd the rail.
ENGAGEMENTS_SHOWN = 4
RAIL_Y = 74  # the milestone rail
STOP_R = 6  # a stop's ring
TITLE, WHERE = 13, 12  # a milestone's title and organisation
SECTOR = 12.5  # the bracketed sector under an engagement's "Customer <n>"
LABEL_GAP = 12  # kept between two neighbouring labels on one line
TICK_END = 30  # a bracket tick ends this far above its stop: the date label's baseline is 16 up
PANEL_GAP = 12  # between two engagement panels
PANEL_INSET = 12  # a panel's text keeps this far inside its edges
# rail titles are a 700, between kit's strong and title
HEAD_CSS = f".h{{font-family:{kit.SANS};font-weight:700}}"


# ---------------------------------------------------------------- shared helpers
def _r(value: float) -> float:
    return round(value * 2) / 2


def _lines(text: str, width: float, size: float, mono: bool = False) -> list[str]:
    tracking = kit.TRACK if mono else 1
    return kit.balance(kit.wrap_text(text, width, size, mono, tracking))


def _mono_width(text: str, size: float = kit.MICRO) -> float:
    """A mono micro-label's drawn width: kit's measure without the tracking after the last letter."""
    return kit.text_width(text, size, True, kit.TRACK) - kit.TRACK


def _width(text: str, size: float, mono: bool = False) -> float:
    return _mono_width(text, size) if mono else kit.text_width(text, size)


def _keys(points: list[tuple[float, float]], dur: float) -> tuple[str, str]:
    values = ";".join(f"{value:g}" for _, value in points)
    times = ";".join(f"{round(second / dur, 4):g}" for second, _ in points)
    return values, times


def _on(start: float, end: float, fade: float = 0.25, dur: float = T) -> str:
    """An opacity loop that is 1 from start+fade to end and 0 otherwise; the span may wrap past dur."""
    length = (end - start) % dur or dur

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
    values, times = _keys([(m, round(max(0.0, level(m)), 3)) for m in marks], dur)
    return kit.loop("opacity", values, times, dur)


def _light(x: float, y: float, w: float, h: float, start: float, end: float) -> str:
    """A border that rests hidden and lights while the run passes its panel."""
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="10" fill="none" '
        f'stroke="{kit.SKY}" stroke-width="1.5" opacity="0">{_on(start, end)}</rect>'
    )


def _beam(d: str, length: float, begin: float, run: float) -> str:
    """kit's travelling light, `run` seconds along a path `length` px long, once per loop from `begin`."""
    dash = max(4.0, min(30.0, 100 * 44 / max(length, 1)))
    return kit.beam(d, T, begin, run / T, kit.BLUE_LIGHT, 2, dash)


def _passes(begin: float, run: float, length: float, at: float) -> float:
    """When the middle of a _beam started at `begin` passes `at` px along its path."""
    dash = max(4.0, min(30.0, 100 * 44 / max(length, 1)))
    share = 100 * at / max(length, 1)
    return begin + run * (share + dash / 2) / (100 + dash)


def _panel(x: float, y: float, w: float, h: float, lit: bool = False) -> str:
    fill, stroke = (
        (kit.BLUE_TINT, kit.BLUE_EDGE) if lit else (kit.CARD, kit.HAIR_STRONG)
    )
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="10" fill="{fill}" stroke="{stroke}"/>'


def _centred(
    lines: list[str], x: float, y: float, step: float, size: float, color: str, cls: str
) -> str:
    return "".join(
        kit.text(x, y + index * step, line, size, color, cls, "middle")
        for index, line in enumerate(lines)
    )


def _stack(
    lines: list[str], x: float, y: float, step: float, size: float, color: str, cls: str
) -> str:
    return "".join(
        kit.text(x, y + index * step, line, size, color, cls)
        for index, line in enumerate(lines)
    )


def _years(texts: list[str]) -> list[int]:
    return [int(year) for text in texts for year in re.findall(r"\b(\d{4})\b", text)]


def _fit_parts(parts: list[str], room: float, size: float) -> str:
    """Join an eyebrow's parts; past the room the last parts are left off, the first always stays."""
    while len(parts) > 1 and _mono_width(SEP.join(parts).upper(), size) > room:
        parts = parts[:-1]
    return SEP.join(parts)


def _first_fit(candidates: list[str], room: float, size: float) -> str:
    """The first of the candidates, longest first, that fits the room as a mono micro-label."""
    for candidate in candidates:
        if _mono_width(candidate.upper(), size) <= room:
            return candidate
    return candidates[-1]


# ---------------------------------------------------------------- shared facts
def _engagements(ctx: dict) -> tuple[list[dict], int]:
    """Return the newest engagements, oldest first, and how many older ones are left out."""
    rows = list(ctx["engagements"])
    return rows[-ENGAGEMENTS_SHOWN:], max(len(rows) - ENGAGEMENTS_SHOWN, 0)


def _sector(row: dict) -> str:
    """The line under an engagement's "Customer <n>": its sector in brackets, or "" when it has none."""
    return f"({row['sector']})" if row["sector"] else ""


def _customers_only(rows: list[dict]) -> bool:
    return all(row["kind"] == "customer" for row in rows)


def _heading(rows: list[dict]) -> str:
    """Name the engagement rows: customer engagements only while every row is a customer."""
    return "Customer engagements" if _customers_only(rows) else "Engagements at AWS"


def _role(ctx: dict, row: dict) -> str:
    """The role, said to be held at AWS where the heading does not already say so."""
    suffix = ", AWS" if _customers_only(ctx["engagements"]) else ""
    return f"{row['role']}{suffix}".upper() if row["role"] else ""


def _current(milestones: list[dict]) -> int:
    """The stop the engagements open from: the current role, or the last stop."""
    flagged = [index for index, m in enumerate(milestones) if m["current"]]
    return flagged[-1] if flagged else len(milestones) - 1


def _year_label(m: dict) -> str:
    return f"{m['year']}  FULL TIME" if m["current"] else str(m["year"])


def _experience_eyebrow(ctx: dict, room: float, size: float) -> str:
    """The span of the rail and how many engagements it opens into, as long as the room allows."""
    milestones, everyone = ctx["milestones"], ctx["engagements"]
    span = f"{milestones[0]['year']} to now" if milestones else "Career"
    if not everyone:
        return span
    count = len(everyone)
    noun = "engagement" if count == 1 else "engagements"
    forms = [f"{count} {noun} at AWS", f"{count} {noun}"]
    if _customers_only(everyone):
        forms.insert(0, f"{count} customer {noun} at AWS")
    return _first_fit([f"{span}{SEP}{form}" for form in forms] + [span], room, size)


def _experience_label(ctx: dict, rows: list[dict]) -> str:
    career = "; ".join(
        f"{m['year']}, {m['what']}, {m['where']}, {m['city']}"
        for m in ctx["milestones"]
    )
    if not rows:
        return f"Career: {career}"
    # named from every engagement, not just the rows shown
    everyone = ctx["engagements"]
    prefix = (
        "Customer engagements at AWS"
        if _customers_only(everyone)
        else _heading(everyone)
    )
    work = "; ".join(
        ", ".join(
            part for part in (f"{e['title']} {_sector(e)}".strip(), e["role"]) if part
        )
        + f" ({e['when']})"
        for e in rows
    )
    return f"Career: {career}. {prefix}: {work}"


def _education_label(rows: list[dict]) -> str:
    return "Education: " + "; ".join(
        ", ".join(
            part
            for part in (
                e["degree"],
                e["school"],
                e["city"],
                e["when"],
            )
            if part
        )
        for e in rows
    )


def _recognition_label(groups: list) -> str:
    return "Reviews, talks and recognition at AWS: " + "; ".join(
        f"{text} ({year})" if year else text
        for _, items in groups
        for text, year in items
    )


def _chip_rows(labels: list, room: float, size: float, cap: int = 3) -> list[list[str]]:
    """Up to `cap` stack names, in order, on one row; a second row only when the first holds fewer than two.

    A name too wide for what is left is passed over and the shorter names after it get their turn.
    """
    names = [str(label) for label in labels]

    def fill(pool: list[str], limit: int) -> list[str]:
        row, used = [], 0.0
        for name in pool:
            width = kit.chip_width(name, size)
            if len(row) < limit and used + width <= room:
                row.append(name)
                used += width + CHIP_GAP
        return row

    first = fill(names, cap)
    if len(first) >= 2 or len(first) == cap:
        return [first] if first else []
    second = fill([name for name in names if name not in first], cap - len(first))
    return [row for row in (first, second) if row]


def _chips(
    rows: list[list[str]],
    x: float,
    y: float,
    size: float,
    height: float,
    centred: bool = True,
) -> str:
    out = []
    for index, row in enumerate(rows):
        widths = [kit.chip_width(label, size) for label in row]
        total = sum(widths) + CHIP_GAP * (len(row) - 1)
        cx = x - total / 2 if centred else x
        for label, width in zip(row, widths):
            svg, _ = kit.chip(
                _r(cx), y + index * (height + 6), label, kit.BLUE_LIGHT, size, height
            )
            out.append(svg)
            cx += width + CHIP_GAP
    return "".join(out)


# ---------------------------------------------------------------- experience: the milestone rail
def _bands(m: dict, room: float) -> dict[str, list[str]]:
    """A stop's label lines: title, organisation and city wrapped to `room` (0 keeps each on one line)."""

    def wrap(text: str, size: float, mono: bool = False) -> list[str]:
        if not text:
            return []
        return _lines(text, room, size, mono) if room else [text]

    return {
        "title": wrap(m["what"], TITLE),
        "where": wrap(m["where"], WHERE),
        "city": wrap(m["city"].upper(), kit.MICRO, True),
    }


def _halves(m: dict, bands: dict[str, list[str]]) -> list[float]:
    """Half the width of each line band a stop draws: year, title, organisation, city."""

    def widest(lines: list[str], size: float, mono: bool = False) -> float:
        return max((_width(line, size, mono) for line in lines), default=0) / 2

    return [
        _mono_width(_year_label(m)) / 2,
        widest(bands["title"], TITLE),
        widest(bands["where"], WHERE),
        widest(bands["city"], kit.MICRO, True),
    ]


def _spread(halves: list[list[float]]) -> list[float] | None:
    """Stop positions that keep every band's neighbours LABEL_GAP apart and the outer labels on the padding.

    The steps are as even as the labels allow: a pair that needs more room
    takes it, and the rest share what is left equally. None when they cannot fit.
    """
    outer = [max(h) for h in halves]
    if len(halves) == 1:
        return [WIDTH / 2] if 2 * outer[0] <= RIGHT - LEFT else None
    x0, x1 = LEFT + outer[0], RIGHT - outer[-1]
    need = [
        max(a + b for a, b in zip(halves[i], halves[i + 1])) + LABEL_GAP
        for i in range(len(halves) - 1)
    ]
    room = x1 - x0
    if sum(need) > room:
        return None
    low, high = 0.0, room
    for _ in range(40):
        mid = (low + high) / 2
        if sum(max(n, mid) for n in need) > room:
            high = mid
        else:
            low = mid
    steps = [max(n, low) for n in need]
    xs = [x0]
    for step in steps:
        xs.append(xs[-1] + step)
    xs[-1] = x1
    return [_r(x) for x in xs]


def _top_layout(milestones: list[dict]) -> tuple[list[float], list[dict]]:
    """Each stop's x and its label lines: labels wrap only as far as they must for every one to fit."""
    for room in (0, 220, 190, 160, 130, 110, 90):
        bands = [_bands(m, room) for m in milestones]
        xs = _spread([_halves(m, b) for m, b in zip(milestones, bands)])
        if xs:
            return xs, bands
    # nothing fits: even steps, every label wrapped to its step (a best effort for a very long rail)
    count = len(milestones)
    step = (RIGHT - LEFT) / count
    xs = [_r(LEFT + step / 2 + index * step) for index in range(count)]
    return xs, [_bands(m, step - LABEL_GAP) for m in milestones]


def _rail(x1: float, x2: float, y: float, begin: float, dur: float) -> str:
    """A track, and the blue rail drawn over it at a steady pace so it reaches each stop as that stop enters."""
    d = f"M{x1:g} {y:g}H{x2:g}"
    return (
        f'<path d="{d}" stroke="{kit.HAIR_STRONG}" stroke-width="2"/>'
        f'<path d="{d}" stroke="{kit.BLUE}" stroke-width="2" pathLength="1" stroke-dasharray="1" stroke-dashoffset="0">'
        f'<animate attributeName="stroke-dashoffset" values="1;1;0" {kit.held(begin, max(dur, 0.1), ease=False)}/></path>'
    )


def _knockouts(
    points: list[tuple[float, float]], width: float, height: float, r: float = STOP_R
) -> str:
    """A clip that keeps the rails and the light out of every stop, so a stop's ring needs no fill to hide them."""
    holes = "".join(
        f"M{x - r:g} {y:g}a{r:g} {r:g} 0 1 0 {2 * r:g} 0a{r:g} {r:g} 0 1 0 {-2 * r:g} 0Z"
        for x, y in points
    )
    return (
        '<clipPath id="rails"><path clip-rule="evenodd" '
        f'd="M0 0H{width:g}V{height:g}H0Z{holes}"/></clipPath>'
    )


def _stop(x: float, y: float, at: float, color: str, live: bool, labels: str) -> str:
    """One stop: its ring, its centre and its labels entering as one group.

    A live stop's centre is kit's live dot, so its pulse sits inside the group
    and cannot show before its stop does.
    """
    centre = (
        kit.live_dot(x, y, kit.GREEN, 3)
        if live
        else f'<circle cx="{x:g}" cy="{y:g}" r="2.6" fill="{color}"/>'
    )
    return (
        f"<g>{kit.enter(at, 0.3)}"
        f'<circle cx="{x:g}" cy="{y:g}" r="{STOP_R}" fill="none" stroke="{color}" stroke-width="2"/>'
        f"{centre}{labels}</g>"
    )


# ---------------------------------------------------------------- experience: the engagement panels
def _panels(ctx: dict, rows: list[dict]) -> dict:
    """The engagement panels' geometry and lines, shared so every panel is one height and every role starts at one y."""
    count = len(rows)
    across = count if count > 1 else 2
    width = _r((RIGHT - LEFT - PANEL_GAP * (across - 1)) / across)
    xs = [LEFT + index * (width + PANEL_GAP) for index in range(count)]
    room = width - 2 * PANEL_INSET
    sectors = [_lines(_sector(e), room, SECTOR) if e["sector"] else [] for e in rows]
    roles = [_lines(_role(ctx, e), room, kit.MICRO, True) for e in rows]
    chips = [_chip_rows(e.get("stack") or [], room, kit.MICRO) for e in rows]
    sector_lines = max((len(s) for s in sectors), default=0)
    role_lines = max((len(r) for r in roles), default=0)
    chip_lines = max((len(c) for c in chips), default=0)
    # baselines from the panel's top: the title, the first sector line, the first role line, the chips' top
    title = 26
    sector = title + 18
    role = (sector + 15 * (sector_lines - 1) if sector_lines else title) + 19
    last = role + 14 * (role_lines - 1) if role_lines else role - 19
    chip_top = last + 12
    bottom = chip_top + 26 * chip_lines - 6 + 14 if chip_lines else last + 16
    return {
        "xs": xs,
        "width": width,
        "sectors": sectors,
        "roles": roles,
        "chips": chips,
        "title": title,
        "sector": sector,
        "role": role,
        "chip_top": chip_top,
        "height": bottom,
    }


def _experience(ctx: dict, rows: list[dict], hidden: int, label: str) -> str:
    """The milestone rail to the current role, which opens into its engagements on a second rail."""
    milestones = ctx["milestones"]
    xs, bands = _top_layout(milestones)
    now = _current(milestones)

    def most(key: str) -> int:
        return max((len(b[key]) for b in bands), default=1) or 1

    # every stop's organisation and city start at one y, under the tallest title,
    # so the row stays aligned whichever title wraps
    where_y = RAIL_Y + 43 + 16 * (most("title") - 1)
    city_y = where_y + 16 + 15 * (most("where") - 1)
    city_end = city_y + 14 * (most("city") - 1)
    height = city_end + 22

    # entrances: the rail draws left to right and each stop enters as the rail reaches it
    start, step = 0.1, 0.12
    draw = step * max(len(milestones) - 1, 1)
    rails = _rail(xs[0], xs[-1], RAIL_Y, start, draw) if len(xs) > 1 else ""
    stops = []
    for index, (m, x) in enumerate(zip(milestones, xs)):
        live = bool(m["current"])
        color = kit.GREEN if live else kit.BLUE_LIGHT
        labels = (
            kit.text(x, RAIL_Y - 16, _year_label(m), kit.MICRO, color, "m", "middle")
            + _centred(bands[index]["title"], x, RAIL_Y + 26, 16, TITLE, kit.INK, "h")
            + _centred(bands[index]["where"], x, where_y, 15, WHERE, kit.BODY, "s")
            + _centred(bands[index]["city"], x, city_y, 14, kit.MICRO, kit.META, "m")
        )
        stops.append(_stop(x, RAIL_Y, start + step * index, color, live, labels))
    points = [(x, RAIL_Y) for x in xs]

    opening, lights, beams = "", "", ""
    x_now = xs[now] if xs else LEFT
    if rows:
        p = _panels(ctx, rows)
        bracket_y = city_end + 34
        sub_y = bracket_y + 42
        top = sub_y + 16
        height = top + p["height"] + 20
        sub_xs = [_r(x + p["width"] / 2) for x in p["xs"]]
        open_at = start + draw + 0.08
        sub_start = open_at + 0.1
        heading = _heading(ctx["engagements"]).upper()
        if hidden:
            heading += f", NEWEST {len(rows)} OF {len(rows) + hidden}"
        # the current role opens into its engagements: a drop from under its city,
        # a bracket over the second rail, and a tick down to each stop that ends
        # above its date label, so no hairline runs through the text
        ticks = "".join(f"M{x:g} {bracket_y:g}V{sub_y - TICK_END:g}" for x in sub_xs)
        opening = (
            f"<g>{kit.enter(open_at)}"
            f'<path d="M{x_now:g} {city_end + 10:g}V{bracket_y:g}H{sub_xs[0]:g}" fill="none" '
            f'stroke="{kit.BLUE_EDGE}" stroke-width="1.4" stroke-dasharray="3 4"/>'
            + kit.text(LEFT, bracket_y - 10, heading, kit.MICRO, kit.BLUE_LIGHT, "m")
            + f'</g><path d="{ticks}" stroke="{kit.HAIR_STRONG}"/>'
        )
        if len(rows) > 1:
            rails += _rail(
                sub_xs[0], sub_xs[-1], sub_y, sub_start, step * (len(rows) - 1)
            )
        for index, (e, x, px) in enumerate(zip(rows, sub_xs, p["xs"])):
            live = bool(e["ongoing"])
            color = kit.GREEN if live else kit.BLUE_LIGHT
            body = (
                _panel(px, top, p["width"], p["height"], live)
                + kit.text(
                    x, sub_y - 16, e["when"].upper(), kit.MICRO, color, "m", "middle"
                )
                + kit.text(x, top + p["title"], e["title"], 15, kit.INK, "h", "middle")
                + _centred(
                    p["sectors"][index], x, top + p["sector"], 15, SECTOR, kit.META, "b"
                )
                + _centred(
                    p["roles"][index], x, top + p["role"], 14, kit.MICRO, kit.META, "m"
                )
                + _chips(p["chips"][index], x, top + p["chip_top"], kit.MICRO, 20)
            )
            stops.append(_stop(x, sub_y, sub_start + step * index, color, live, body))
        points += [(x, sub_y) for x in sub_xs]

        # the run: along the milestone rail to the current role, down and back
        # along the bracket, then through the engagements, lighting each panel
        first = f"M{xs[0]:g} {RAIL_Y}H{x_now:g}"
        drop_d = f"M{x_now:g} {city_end + 10:g}V{bracket_y:g}H{sub_xs[0]:g}V{sub_y - TICK_END:g}"
        lengths = [
            x_now - xs[0],
            (bracket_y - city_end - 10)
            + (x_now - sub_xs[0])
            + (sub_y - TICK_END - bracket_y),
            sub_xs[-1] - sub_xs[0],
        ]
        pace = max(SPEED, sum(lengths) / RUN_MAX)
        runs = [length / pace for length in lengths]
        begins = [LOOP_AT, LOOP_AT + runs[0], LOOP_AT + runs[0] + runs[1]]
        if lengths[0] > 0:
            beams += _beam(first, lengths[0], begins[0], runs[0])
        beams += _beam(drop_d, lengths[1], begins[1], runs[1])
        if len(rows) > 1:
            beams += _beam(
                f"M{sub_xs[0]:g} {sub_y}H{sub_xs[-1]:g}", lengths[2], begins[2], runs[2]
            )
        for index, (x, px) in enumerate(zip(sub_xs, p["xs"])):
            at = (
                _passes(begins[2], runs[2], lengths[2], x - sub_xs[0])
                if len(rows) > 1
                else begins[2]
            )
            hold = 2.4 if index == len(rows) - 1 else 1.2
            lights += _light(px, top, p["width"], p["height"], at - 0.15, at + hold)
    elif len(xs) > 1:
        beams = _beam(
            f"M{xs[0]:g} {RAIL_Y}H{x_now:g}",
            x_now - xs[0],
            LOOP_AT,
            (x_now - xs[0]) / SPEED,
        )

    eyebrow = _experience_eyebrow(ctx, RIGHT - LEFT, kit.MICRO)
    return (
        kit.card_open(WIDTH, height, label, _knockouts(points, WIDTH, height), HEAD_CSS)
        + kit.group(0, kit.eyebrow(LEFT, 30, eyebrow), "0 0")
        + f'<g clip-path="url(#rails)">{rails}{beams}</g>'
        + opening
        + "".join(stops)
        + lights
        + kit.SVG_CLOSE
    )


# ---------------------------------------------------------------- experience: phone
def _detail(first: str, second: str, width: float, size: float) -> list[str]:
    """Wrap 'first · second' so the dot between them never ends or starts a line.

    The dot is held to the word after it with JOIN while the line breaks are chosen;
    the space comes back before anything is drawn. A dot that lands at a line break
    is dropped: the break already separates the two.
    """
    text = f" {DOT}{JOIN}".join(part for part in (first, second) if part)
    lines = [line.replace(JOIN, " ") for line in kit.wrap_text(text, width, size)]
    return [
        line.removeprefix(f"{DOT} ") if index else line
        for index, line in enumerate(lines)
    ]


def _experience_phone(ctx: dict, rows: list[dict], hidden: int, label: str) -> str:
    """A NOW panel (the current role and the engagement going on now), then one rail down through the rest, newest first."""
    w, pad = PHONE, PHONE_PAD
    size = kit.MICRO_PHONE
    milestones = ctx["milestones"]
    now = _current(milestones) if milestones else -1
    ongoing = [e for e in rows if e["ongoing"]][-1:]
    older = [e for e in reversed(rows) if e not in ongoing]
    out, at = [], 0.0

    def enter(body: str) -> None:
        nonlocal at
        out.append(kit.group(at, body))
        at = min(at + kit.STAGGER, 1.2)

    eyebrow = _experience_eyebrow(ctx, w - 2 * pad, size)
    enter(kit.text(pad, 26, eyebrow.upper(), size, kit.BLUE_LIGHT, "m"))
    y = 40.0
    panel_bottom = y
    lights = ""
    if now >= 0:
        m = milestones[now]
        inner, room = pad + 14, w - 2 * pad - 28
        top = y
        parts = []
        y += 26
        live = bool(m["current"])
        color = kit.GREEN if live else kit.BLUE_LIGHT
        parts.append(
            (kit.live_dot(inner + 4, y - 4, kit.GREEN, 3.5) if live else "")
            + kit.text(inner + (16 if live else 0), y, _year_label(m), size, color, "m")
        )
        for line in _lines(m["what"], room, 16.5):
            y += 22
            parts.append(kit.text(inner, y, line, 16.5, kit.INK, "h"))
        for line in _detail(m["where"], m["city"], room, 13.5):
            y += 19
            parts.append(kit.text(inner, y, line, 13.5, kit.BODY, "b"))
        for e in ongoing:
            y += 16
            parts.append(
                f'<path d="M{inner:g} {y:g}H{w - pad - 14:g}" stroke="{kit.HAIR_STRONG}"/>'
            )
            y += 24
            parts.append(
                kit.live_dot(inner + 4, y - 4, kit.GREEN, 3.5)
                + kit.text(inner + 16, y, e["when"].upper(), size, kit.GREEN, "m")
            )
            y += 23
            parts.append(kit.text(inner, y, e["title"], 16.5, kit.INK, "h"))
            for line in _lines(_sector(e), room, 13.5) if e["sector"] else []:
                y += 19
                parts.append(kit.text(inner, y, line, 13.5, kit.META, "b"))
            for line in _lines(_role(ctx, e), room, size, True):
                y += 19
                parts.append(kit.text(inner, y, line, size, kit.META, "m"))
            chips = _chip_rows(e.get("stack") or [], room, size)
            if chips:
                y += 12
                parts.append(_chips(chips, inner, y, size, 24, centred=False))
                y += 30 * len(chips) - 6
        y += 18
        panel_bottom = y
        enter(_panel(pad, top, w - 2 * pad, y - top, True) + "".join(parts))
        y += 14

    # one rail down the left through every older engagement and milestone
    rail_x, text_x, room = pad + 8, pad + 24, w - pad - (pad + 24)
    nodes = []
    if older or hidden:
        y += 18
        heading = _heading(ctx["engagements"]).upper()
        enter(kit.text(text_x, y, heading, size, kit.BLUE_LIGHT, "m"))
        for e in older:
            y += 26
            parts = [kit.text(text_x, y, e["when"].upper(), size, kit.BLUE_LIGHT, "m")]
            nodes.append(y - 4)
            y += 21
            parts.append(kit.text(text_x, y, e["title"], 15, kit.INK, "h"))
            for line in _lines(_sector(e), room, 13.5) if e["sector"] else []:
                y += 18
                parts.append(kit.text(text_x, y, line, 13.5, kit.META, "b"))
            for line in _lines(_role(ctx, e), room, size, True):
                y += 18
                parts.append(kit.text(text_x, y, line, size, kit.META, "m"))
            enter("".join(parts))
        if hidden:
            y += 24
            enter(kit.text(text_x, y, f"+{hidden} EARLIER", size, kit.META, "m"))
        y += 8
    before = [m for index, m in enumerate(milestones) if index != now]
    if before:
        y += 18
        enter(kit.text(text_x, y, "MILESTONES", size, kit.BLUE_LIGHT, "m"))
        for m in reversed(before):
            y += 26
            year = str(m["year"])
            nodes.append(y - 4)
            offset = _mono_width(year, size) + 10
            title = _lines(m["what"], room - offset, 15)
            parts = [kit.text(text_x, y, year, size, kit.BLUE_LIGHT, "m")]
            parts.append(_stack(title, text_x + offset, y, 19, 15, kit.INK, "h"))
            y += 19 * (len(title) - 1)
            for line in _detail(m["where"], m["city"], room, 13.5):
                y += 19
                parts.append(kit.text(text_x, y, line, 13.5, kit.BODY, "b"))
            enter("".join(parts))
    height = round(y + 22)

    # the rail runs from the oldest stop up into the NOW panel; the light climbs
    # it, oldest to newest, and the panel lights as the light arrives
    rail, defs = "", ""
    if nodes:
        bottom = nodes[-1]
        length = bottom - panel_bottom
        run = max(1.6, min(3.0, length / SPEED * 1.6))
        defs = _knockouts([(rail_x, cy) for cy in nodes], w, height, 4)
        rail = (
            '<g clip-path="url(#rails)">'
            + kit.draw(
                f"M{rail_x} {panel_bottom:g}V{bottom:g}", 0.2, 0.9, kit.HAIR_STRONG, 2
            )
            + _beam(f"M{rail_x} {bottom:g}V{panel_bottom:g}", length, LOOP_AT, run)
            + "</g>"
            + kit.group(
                0.2,
                "".join(
                    f'<circle cx="{rail_x}" cy="{cy:g}" r="4" fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="2"/>'
                    for cy in nodes
                ),
                "0 0",
            )
        )
        if now >= 0:
            arrive = LOOP_AT + run
            lights = _light(
                pad, 40, w - 2 * pad, panel_bottom - 40, arrive - 0.3, arrive + 2.2
            )
    return (
        kit.card_open(w, height, label, defs, HEAD_CSS)
        + rail
        + "".join(out)
        + lights
        + kit.SVG_CLOSE
    )


# ---------------------------------------------------------------- education
_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ),
        1,
    )
}


def _months(when: str) -> tuple[int, int] | None:
    """(start, end) as month counts for 'May 2018 to August 2021', or None when it does not read that way."""
    found = re.findall(r"([A-Za-z]+)\s+(\d{4})", when)
    keys = [
        int(year) * 12 + _MONTHS[name[:3].lower()]
        for name, year in found
        if name[:3].lower() in _MONTHS
    ]
    return (keys[0], keys[-1]) if len(keys) >= 2 else None


def _chronological(rows: list[dict]) -> list[dict]:
    """Oldest first when every row's dates read, else as given."""
    keys = [_months(row["when"]) for row in rows]
    if all(keys):
        return [row for _, row in sorted(zip(keys, rows), key=lambda pair: pair[0])]
    return list(rows)


def _education_eyebrow(rows: list[dict], room: float, size: float) -> str:
    count = len(rows)
    parts = [f"{count} degree{'s' if count != 1 else ''}"]
    years = _years([row["when"] for row in rows])
    if years:
        low, high = min(years), max(years)
        parts.append(f"{low} to {high}" if high > low else str(low))
    return _fit_parts(parts, room, size)


def _degree_tile(entry: dict, w: float, phone: bool) -> dict:
    """A degree tile's lines: the dates (with the city beside them where it fits), degree, school, city."""
    room = w - 2 * (16 if phone else 18)
    micro = kit.MICRO_PHONE if phone else kit.MICRO
    when = _lines(entry["when"].upper(), room, micro, True) if entry["when"] else []
    city = entry["city"].upper()
    beside = (
        not phone
        and bool(city)
        and len(when) == 1
        and _mono_width(when[0], micro) + 16 + _mono_width(city, micro) <= room
    )
    body = 13.5 if phone else 13
    return {
        "when": when,
        "degree": _lines(entry["degree"], room, 15.5 if phone else 15),
        "school": (
            _detail(entry["school"], entry["city"], room, body)
            if phone
            else _lines(entry["school"], room, body)
        ),
        "beside": city if beside else "",
        "city": [] if phone or beside or not city else _lines(city, room, micro, True),
        "size": 15.5 if phone else 15,
        "body": body,
        "micro": micro,
        "inset": 16 if phone else 18,
    }


def _degree_height(t: dict) -> float:
    tall = 26 + 14 * (max(len(t["when"]), 1) - 1) + 22 + 19 * (len(t["degree"]) - 1)
    if t["school"]:
        tall += 20 + 18 * (len(t["school"]) - 1)
    if t["city"]:
        tall += 18 + 14 * (len(t["city"]) - 1)
    return tall + 18


def _degree_body(t: dict, x: float, y: float, w: float) -> str:
    tx = x + t["inset"]
    out = [_stack(t["when"], tx, y + 26, 14, t["micro"], kit.BLUE_LIGHT, "m")]
    if t["beside"]:
        out.append(
            kit.text(
                x + w - t["inset"],
                y + 26,
                t["beside"],
                t["micro"],
                kit.META,
                "m",
                "end",
            )
        )
    cy = y + 26 + 14 * (max(len(t["when"]), 1) - 1) + 22
    out.append(_stack(t["degree"], tx, cy, 19, t["size"], kit.INK, "h"))
    cy += 19 * (len(t["degree"]) - 1)
    if t["school"]:
        cy += 20
        out.append(_stack(t["school"], tx, cy, 18, t["body"], kit.BODY, "b"))
        cy += 18 * (len(t["school"]) - 1)
    if t["city"]:
        cy += 18
        out.append(_stack(t["city"], tx, cy, 14, t["micro"], kit.META, "m"))
    return "".join(out)


def _education(rows: list[dict], label: str) -> str:
    """The degrees side by side, oldest first; a light runs along their top edges in the order they were taken.

    Two to a row (three when there are exactly three); each tile's border lights as the light crosses it.
    """
    order = _chronological(rows)
    count = len(order)
    across = 3 if count == 3 else 2
    gap = 12
    w = _r((RIGHT - LEFT - gap * (across - 1)) / across)
    tiles = [_degree_tile(entry, w, False) for entry in order]
    lines = [tiles[i : i + across] for i in range(0, count, across)]
    heights = [max(_degree_height(t) for t in line) for line in lines]
    top = 44
    height = round(top + sum(heights) + gap * (len(lines) - 1) + 20) if count else 56
    eyebrow = _education_eyebrow(order, RIGHT - LEFT, kit.MICRO)
    parts = [
        kit.card_open(WIDTH, height, label, css=HEAD_CSS),
        kit.group(0, kit.eyebrow(LEFT, 30, eyebrow), "0 0"),
    ]
    beams, lights = [], []
    begin, y, index = LOOP_AT, top, 0
    for line, tall in zip(lines, heights):
        start, end = LEFT + 14, LEFT + len(line) * (w + gap) - gap - 14
        length = end - start
        run = length / SPEED
        beams.append(_beam(f"M{start} {y:g}H{end:g}", length, begin, run))
        for column, t in enumerate(line):
            x = LEFT + column * (w + gap)
            parts.append(
                kit.group(
                    0.1 + index * kit.STAGGER * 2,
                    _panel(x, y, w, tall) + _degree_body(t, x, y, w),
                )
            )
            enters = _passes(begin, run, length, x - start)
            leaves = _passes(begin, run, length, x + w - start)
            hold = 2.0 if index == count - 1 else 0.5
            lights.append(_light(x, y, w, tall, enters - 0.2, leaves + hold))
            index += 1
        begin += run
        y += tall + gap
    return "".join(parts) + "".join(beams) + "".join(lights) + kit.SVG_CLOSE


def _education_phone(rows: list[dict], label: str) -> str:
    """The degrees stacked, newest on top; the light runs their top edges oldest first, bottom to top."""
    w, pad = PHONE, PHONE_PAD
    size = kit.MICRO_PHONE
    tw = w - 2 * pad
    eyebrow = _education_eyebrow(rows, tw, size).upper()
    parts = [kit.group(0, kit.text(pad, 26, eyebrow, size, kit.BLUE_LIGHT, "m"), "0 0")]
    order = list(reversed(_chronological(rows)))  # newest first
    length = tw - 28
    run = length / SPEED
    beams, lights, y = [], [], 40.0
    for index, entry in enumerate(order):
        t = _degree_tile(entry, tw, True)
        tall = _degree_height(t)
        parts.append(
            kit.group(
                0.1 + index * kit.STAGGER * 2,
                _panel(pad, y, tw, tall) + _degree_body(t, pad, y, tw),
            )
        )
        begin = LOOP_AT + (len(order) - 1 - index) * run
        beams.append(_beam(f"M{pad + 14:g} {y:g}H{w - pad - 14:g}", length, begin, run))
        hold = 2.0 if index == 0 else 0.5
        lights.append(_light(pad, y, tw, tall, begin - 0.1, begin + run + hold))
        y += tall + 10
    height = round(y + 6) if order else 48
    return (
        kit.card_open(w, height, label, css=HEAD_CSS)
        + "".join(parts)
        + "".join(beams)
        + "".join(lights)
        + kit.SVG_CLOSE
    )


# ---------------------------------------------------------------- publications
class Pubs:
    """The publications card's measures at one width."""

    def __init__(self, phone: bool) -> None:
        self.phone = phone
        self.w = PHONE if phone else WIDTH
        self.pad = PHONE_PAD if phone else LEFT
        self.micro = kit.MICRO_PHONE if phone else kit.MICRO
        self.size, self.lead, self.gap = (13.5, 18, 30) if phone else (13, 17, 28)
        self.inset = 14 if phone else 16
        self.content = self.w - 2 * self.pad
        self.between = 10 if phone else 12  # between two panels
        self.top = 40 if phone else 44


def _item_lines(text: str, first: float, room: float, size: float) -> list[str]:
    """Wrap an item so only its first line makes way for the year beside it."""
    lines = kit.wrap_text(text, first, size)
    if len(lines) < 2:
        return lines
    words = " ".join(text.split())
    if not words.startswith(lines[0]):
        return kit.balance(lines)
    rest = words[len(lines[0]) :].strip()
    return kit.balance([lines[0], *kit.wrap_text(rest, room, size)])


def _items(items: list, width: float, p: Pubs) -> list[tuple[list[str], str]]:
    """Each item's lines and its year, the year on the right of the first line."""
    room = width - 2 * p.inset
    out = []
    for text, year in items:
        year = str(year or "")
        reserve = _mono_width(year, p.micro) + 14 if year else 0
        out.append((_item_lines(str(text), room - reserve, room, p.size), year))
    return out


def _group_height(rows: list, p: Pubs) -> float:
    lines = sum(len(lines) - 1 for lines, _ in rows)
    return 58 + p.lead * lines + p.gap * max(len(rows) - 1, 0) + 18


def _group(
    title: str, rows: list, x: float, y: float, w: float, h: float, p: Pubs
) -> str:
    """One group's panel: its title over a rule, then a row per item with its year on the right."""
    edge = x + w - p.inset
    out = [
        _panel(x, y, w, h),
        kit.text(x + p.inset, y + 26, title.upper(), p.micro, kit.BLUE_LIGHT, "m"),
        f'<path d="M{x + p.inset:g} {y + 38:g}H{edge:g}" stroke="{kit.HAIR_STRONG}"/>',
    ]
    cy = y + 58
    for index, (lines, year) in enumerate(rows):
        if index:
            rule = cy - p.gap + 9
            out.append(
                f'<path d="M{x + p.inset:g} {rule:g}H{edge:g}" stroke="{kit.HAIR}"/>'
            )
        out.append(_stack(lines, x + p.inset, cy, p.lead, p.size, kit.INK, "b"))
        if year:
            out.append(kit.text(edge, cy, year, p.micro, kit.META, "m", "end"))
        cy += p.lead * (len(lines) - 1) + p.gap
    return "".join(out)


def _arrange(groups: list, p: Pubs, measure) -> list[list[tuple[int, float]]]:
    """Columns of panels as [(group index, column width)], left to right, in one of two layouts, whichever is shorter.

    Columns: one column per group. Stacked: the biggest group takes the wide
    column and the others stack in a narrow one beside it, on its left when it
    comes first, else on its right. A phone stacks every group in one column.
    """
    count = len(groups)
    if p.phone or count == 1:
        return [[(index, p.content) for index in range(count)]]
    options = []
    if count <= 3:
        col = (p.content - p.between * (count - 1)) / count
        options.append([[(index, col)] for index in range(count)])
    sizes = [len(items) for _, items in groups]
    big = max(range(count), key=lambda index: sizes[index])
    narrow = round((p.content - p.between) * 0.4)
    wide = p.content - p.between - narrow
    if sizes[big] >= 3:
        stack = [(index, narrow) for index in range(count) if index != big]
        options.append([[(big, wide)], stack] if big == 0 else [stack, [(big, wide)]])
    if (
        not options
    ):  # four or more small groups: two columns, each group to the shorter one
        col = (p.content - p.between) / 2
        sides: list[list[tuple[int, float]]] = [[], []]
        for index in range(count):
            tall = [sum(measure(i, col) for i, _ in side) for side in sides]
            sides[0 if tall[0] <= tall[1] else 1].append((index, col))
        options.append(sides)

    def tallest(columns: list) -> float:
        return max(
            sum(measure(i, w) for i, w in column) + p.between * (len(column) - 1)
            for column in columns
        )

    return min(options, key=tallest)


def _publications_card(groups: list, label: str, phone: bool) -> str:
    """The groups as panels of rows; one lit border steps from panel to panel."""
    p = Pubs(phone)
    rows: dict[tuple[int, float], list] = {}

    def measure(index: int, width: float) -> float:
        if (index, width) not in rows:
            rows[(index, width)] = _items(groups[index][1], width, p)
        return _group_height(rows[(index, width)], p)

    columns = _arrange(groups, p, measure) if groups else []
    tall = [
        sum(measure(i, w) for i, w in column) + p.between * (len(column) - 1)
        for column in columns
    ]
    bottom = max(tall, default=0)
    # every column ends on one line: a shorter column shares the difference among its panels
    placed = []
    x = p.pad
    for column, used in zip(columns, tall):
        grow = (bottom - used) / len(column)
        y = p.top
        for index, width in column:
            height = measure(index, width) + grow
            placed.append((index, x, y, width, height))
            y += height + p.between
        x += column[0][1] + p.between
    placed.sort()
    height = round(p.top + bottom + (16 if phone else 20)) if groups else 48

    total = sum(len(items) for _, items in groups)
    years = _years([str(year) for _, items in groups for _, year in items])
    span = []
    if years:
        low, high = min(years), max(years)
        span = [f"{low} to {high}" if high > low else str(low)]
    eyebrow = SEP.join([*span, f"{total} entr{'ies' if total != 1 else 'y'}"]).upper()
    out = [
        kit.card_open(p.w, height, label),
        kit.group(
            0,
            kit.text(p.pad, 26 if phone else 30, eyebrow, p.micro, kit.BLUE_LIGHT, "m"),
            "0 0",
        ),
    ]
    count = len(placed)
    loop = T if count <= 6 else 2 * T
    slot = loop / max(count, 1)
    lights = []
    for order, (index, x, y, width, height_) in enumerate(placed):
        title, _ = groups[index]
        body = _group(title, rows[(index, width)], x, y, width, height_, p)
        out.append(kit.group(0.1 + order * kit.STAGGER * 1.5, body))
        if count > 1:
            # one lit border steps from panel to panel, in reading order; the first is lit at rest
            # each fades in as the one before fades out, so the first is fully lit at 0 s
            rest = "" if order == 0 else ' opacity="0"'
            fade = 0.25
            start = (order * slot - fade) % loop
            lights.append(
                f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height_:g}" rx="10" fill="none" '
                f'stroke="{kit.BLUE_EDGE}" stroke-width="1.5"{rest}>'
                f"{_on(start, (order + 1) * slot - fade, fade, loop)}</rect>"
            )
    # the spotlight enters with the first panel, so no outline shows before its panel does
    spotlight = kit.group(0.1, "".join(lights), "0 0") if lights else ""
    return "".join(out) + spotlight + kit.SVG_CLOSE


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for the experience, education and publications cards at both widths."""
    rows, hidden = _engagements(ctx)
    experience = _experience_label(ctx, rows)
    education = _education_label(ctx["education"])
    recognition = _recognition_label(ctx["recognition"])
    return {
        "experience.svg": _experience(ctx, rows, hidden, experience),
        "experience-mobile.svg": _experience_phone(ctx, rows, hidden, experience),
        "education.svg": _education(ctx["education"], education),
        "education-mobile.svg": _education_phone(ctx["education"], education),
        "publications.svg": _publications_card(ctx["recognition"], recognition, False),
        "publications-mobile.svg": _publications_card(
            ctx["recognition"], recognition, True
        ),
    }
