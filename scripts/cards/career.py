"""The career cards: the experience rails, education, and the AWS reviews, talks and programs.

Three cards at two widths, drawn from ctx["milestones"], ctx["engagements"],
ctx["education"] and ctx["recognition"]: experience.svg, education.svg and
publications.svg at 840px, and their -mobile.svg twins at 320px.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
from __future__ import annotations

import kit
from mobile_cards import MICRO, PAD, Card, wrap_text
from mobile_cards import WIDTH as PHONE_WIDTH

WIDTH = 840
# Both layouts show the newest four engagements, so a fifth cannot crowd the rail.
ENGAGEMENTS_SHOWN = 4
RAIL_LEFT, RAIL_RIGHT, RAIL_Y = 70, 772, 84  # the milestone rail
SUB_LEFT, SUB_RIGHT = 120, 720  # the engagement rail under the current role
START, STEP = 0.1, 0.12  # the first stop's entrance, then the delay from stop to stop
EDGE = 4  # a centred label stays this far inside the card
ROLE_GAP = 12  # kept between the mono role lines of two neighbouring stops
ROW, LINE, TOP = 46, 15, 50  # a list row, an extra wrapped line, the first row's rule
TICK_END = 30  # a bracket tick ends this far above its stop: the date label's baseline is 16 up
SECOND_WRAP = 104  # characters on a list row's second line
ROW_RULE = "rgba(255,255,255,0.06)"  # the hairline over each list row
PANEL_WRAP, PANEL_WRAP_WIDE = 50, 105  # characters per line in a half and a full panel
PANEL_ACCENTS = (kit.BLUE_LIGHT, kit.GREEN, kit.AMBER)  # the live card's three panels
DOT = chr(0xB7)  # the middle dot the phone cards join two facts with
JOIN = chr(0x2060)  # holds two words on one line while the phone detail wraps
# rail titles and a list row's first line are a 700, between kit's strong and title
HEAD_CSS = f".h{{font-family:{kit.SANS};font-weight:700}}"
# The ring around a live stop. It runs in CSS on the circle itself; the entrance
# belongs to the group around it, so the ring cannot show before its stop does.
RING_CSS = (
    ".now{animation:ring 2s ease-out infinite;transform-origin:center;transform-box:fill-box}"
    "@keyframes ring{0%{opacity:0.9;transform:scale(1)}100%{opacity:0;transform:scale(2.6)}}"
)


# ---------------------------------------------------------------- shared facts
def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3].rsplit(" ", 1)[0] + "..."


def _wrap(text: str, width: int) -> list[str]:
    """Wrap by character count, never leaving one short word alone on the last line."""
    lines, current = [], ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    if len(lines) > 1 and " " not in lines[-1] and " " in lines[-2]:
        head, moved = lines[-2].rsplit(" ", 1)
        if len(moved) + 1 + len(lines[-1]) <= width:
            lines[-2:] = [head, f"{moved} {lines[-1]}"]
    return lines


def _engagements(ctx: dict) -> tuple[list[dict], int]:
    """Return the newest engagements, oldest first, and how many older ones are left out."""
    rows = list(ctx["engagements"])
    return rows[-ENGAGEMENTS_SHOWN:], max(len(rows) - ENGAGEMENTS_SHOWN, 0)


def _customers_only(rows: list[dict]) -> bool:
    return all(row["kind"] == "customer" for row in rows)


def _heading(rows: list[dict]) -> str:
    """Name the engagement rows: customer engagements only while every row is a customer."""
    return "Customer engagements" if _customers_only(rows) else "Engagements at AWS"


def _experience_label(ctx: dict, rows: list[dict]) -> str:
    career = "; ".join(
        f"{m['year']}, {m['what']}, {m['where']}, {m['city']}"
        for m in ctx["milestones"]
    )
    if not rows:
        return f"Career: {career}"
    # named from every engagement, not just the rows shown: a hidden program counts
    everyone = ctx["engagements"]
    prefix = (
        "Customer engagements at AWS"
        if _customers_only(everyone)
        else _heading(everyone)
    )
    work = "; ".join(
        ", ".join(part for part in (e["client"], e["role"]) if part) + f" ({e['when']})"
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


# ---------------------------------------------------------------- experience
def _room(x: float, step: float) -> float:
    """The width a label centred on x may take: the step to the next stop, or the room to the card's edge."""
    return min(step, 2 * (min(x, WIDTH - x) - EDGE))


def _rail(x1: float, x2: float, y: float, begin: float, dur: float) -> str:
    """A track, and the blue rail drawn over it at a steady pace so it reaches each stop as that stop enters."""
    d = f"M{x1:g} {y:g}H{x2:g}"
    return (
        f'<path d="{d}" stroke="{kit.HAIR_STRONG}" stroke-width="2"/>'
        f'<path d="{d}" stroke="{kit.BLUE}" stroke-width="2" pathLength="1" stroke-dasharray="1" stroke-dashoffset="0">'
        f'<animate attributeName="stroke-dashoffset" values="1;1;0" {kit.held(begin, dur, ease=False)}/></path>'
    )


def _knockouts(points: list[tuple[float, float]], height: float) -> str:
    """A clip that keeps the rails out of every stop, so a stop's ring needs no fill to hide them."""
    holes = "".join(
        f"M{x - 6:g} {y:g}a6 6 0 1 0 12 0a6 6 0 1 0 -12 0Z" for x, y in points
    )
    return (
        '<clipPath id="rails"><path clip-rule="evenodd" '
        f'd="M0 0H{WIDTH}V{height:g}H0Z{holes}"/></clipPath>'
    )


def _stop(x: float, y: float, at: float, color: str, live: bool, labels: str) -> str:
    """One stop on a rail: its outline, then its dot and labels entering as one group.

    A live stop's pulsing ring sits inside that group, so it is hidden until the stop enters.
    """
    ring = (
        f'<circle class="now" cx="{x:g}" cy="{y:g}" r="7" fill="none" stroke="{color}" stroke-width="1.5"/>'
        if live
        else ""
    )
    return (
        f'<circle cx="{x:g}" cy="{y:g}" r="6" fill="none" stroke="{color}" stroke-width="2">'
        f"{kit.enter(at, 0.3, start='0.25')}</circle>"
        f'<g>{kit.enter(at)}{ring}<circle cx="{x:g}" cy="{y:g}" r="2.6" fill="{color}"/>{labels}</g>'
    )


def _centred(
    lines: list[str], x: float, y: float, step: float, size: float, color: str, cls: str
) -> str:
    return "".join(
        kit.text(x, y + index * step, line, size, color, cls, "middle")
        for index, line in enumerate(lines)
    )


def _experience(ctx: dict, rows: list[dict], hidden: int, label: str) -> str:
    """The milestone rail to the current role, which then opens into its engagements on a second rail."""
    milestones = ctx["milestones"]
    step = (RAIL_RIGHT - RAIL_LEFT) / max(len(milestones) - 1, 1)
    xs = [RAIL_LEFT + index * step for index in range(len(milestones))]
    # a title too long for its stop wraps, and every stop's organisation and
    # city drop by the same amount so the row stays aligned
    titles = [wrap_text(m["what"], _room(x, step), 13) for m, x in zip(milestones, xs)]
    drop = 16 * (max((len(title) for title in titles), default=1) - 1)
    city_y = RAIL_Y + 63 + drop
    bracket_y, sub_y = city_y + 23, city_y + 87

    # the engagement labels wrap to the step between their stops, so the rail
    # reads the same with two rows or four and neighbours never touch
    sub_step = (SUB_RIGHT - SUB_LEFT) / max(len(rows) - 1, 1)
    sub_xs = [SUB_LEFT + index * sub_step for index in range(len(rows))]
    clients = [
        wrap_text(e["client"], _room(x, sub_step), 13) for e, x in zip(rows, sub_xs)
    ]
    # under CUSTOMER ENGAGEMENTS each role says it was held at AWS; the other heading already does
    suffix = ", AWS" if _customers_only(ctx["engagements"]) else ""
    roles = [
        wrap_text(
            f"{e['role']}{suffix}".upper(),
            _room(x, sub_step) - ROLE_GAP,
            kit.MICRO,
            True,
        )
        if e["role"]
        else []
        for e, x in zip(rows, sub_xs)
    ]
    sub_drop = 16 * (max((len(client) for client in clients), default=1) - 1)
    role_y = sub_y + 46 + sub_drop
    role_lines = max((len(role) for role in roles), default=0)
    height = role_y + 14 * max(role_lines - 1, 0) + 18 if rows else city_y + 20

    draw = STEP * (len(milestones) - 1)
    open_at = START + draw + 0.08
    sub_start = open_at + 0.1
    rails = _rail(RAIL_LEFT, RAIL_RIGHT, RAIL_Y, START, draw)
    stops = []
    for index, (m, x) in enumerate(zip(milestones, xs)):
        color = kit.GREEN if m["current"] else kit.BLUE_LIGHT
        year = f"{m['year']}  FULL TIME" if m["current"] else m["year"]
        labels = (
            kit.text(x, RAIL_Y - 22, year, kit.MICRO, color, "m", "middle")
            + _centred(titles[index], x, RAIL_Y + 30, 16, 13, kit.INK, "h")
            + kit.text(x, RAIL_Y + 47 + drop, m["where"], 11.5, kit.BODY, "h", "middle")
            + kit.text(x, city_y, m["city"].upper(), kit.MICRO, kit.META, "m", "middle")
        )
        stops.append(
            _stop(x, RAIL_Y, START + STEP * index, color, m["current"], labels)
        )
    opening = ""
    if rows:
        # the current role opens into its engagements: a drop from under its
        # city, then a bracket over the second rail with a tick down to each stop
        heading = _heading(ctx["engagements"]).upper()
        if hidden:
            heading += f", NEWEST {len(rows)} OF {len(rows) + hidden}"
        # each tick stops above its date label, so no hairline runs through the text
        ticks = "".join(f"M{x:g} {bracket_y:g}V{sub_y - TICK_END:g}" for x in sub_xs)
        opening = (
            f"<g>{kit.enter(open_at)}"
            f'<path d="M{RAIL_RIGHT} {city_y + 9:g}V{bracket_y:g}H{SUB_LEFT}" fill="none" stroke="{kit.GREEN}" '
            'stroke-opacity="0.53" stroke-width="1.4" stroke-dasharray="3 4"/>'
            + kit.text(SUB_LEFT, bracket_y - 8, heading, kit.MICRO, kit.GREEN, "m")
            + f'</g><path d="{ticks}" stroke="{kit.HAIR_STRONG}"/>'
        )
        rails += _rail(
            SUB_LEFT, SUB_RIGHT, sub_y, sub_start, STEP * max(len(rows) - 1, 1)
        )
        for index, (e, x) in enumerate(zip(rows, sub_xs)):
            color = kit.GREEN if e["ongoing"] else kit.SKY
            labels = (
                kit.text(
                    x, sub_y - 16, e["when"].upper(), kit.MICRO, color, "m", "middle"
                )
                + _centred(clients[index], x, sub_y + 28, 16, 13, kit.INK, "h")
                + _centred(roles[index], x, role_y, 14, kit.MICRO, kit.META, "m")
            )
            stops.append(
                _stop(x, sub_y, sub_start + STEP * index, color, e["ongoing"], labels)
            )
    points = [(x, RAIL_Y) for x in xs] + [(x, sub_y) for x in sub_xs]
    return (
        kit.card_open(
            WIDTH, height, label, _knockouts(points, height), HEAD_CSS + RING_CSS
        )
        + kit.eyebrow(24, 30, "Career")
        + f'<g clip-path="url(#rails)">{rails}</g>'
        + opening
        + "".join(stops)
        + kit.SVG_CLOSE
    )


def _experience_phone(ctx: dict, rows: list[dict], hidden: int, label: str) -> str:
    card = Card(label, kit.GREEN)
    card.label("Career")
    milestones = ctx["milestones"]
    last = len(milestones) - 1
    for index, m in enumerate(milestones):
        with card.block():
            top = card.y
            card.parts.append(
                kit.live_dot(24, top + 9, kit.GREEN)
                if m["current"]
                else f'<circle cx="24" cy="{top + 9:g}" r="4" fill="{kit.GREEN}"/>'
            )
            bottom = card.lines(
                f"{m['year']} {DOT} {m['what']}", x=38, y=top, weight=600
            )
            bottom = card.lines(
                f"{m['where']} {DOT} {m['city']}",
                x=38,
                y=bottom + 2,
                size=13,
                color=kit.BODY,
            )
            card.y = bottom + 14
            if index < last:
                rail = f"M24 {top + 17:g}V{card.y:g}"
                card.parts.append(
                    f'<path d="{rail}" stroke="{kit.HAIR_STRONG}"/>'
                    + kit.draw(
                        rail,
                        card.begin + 0.2,
                        0.6,
                        kit.GREEN,
                        1,
                        ' stroke-opacity="0.6"',
                    )
                )
    if rows:
        card.divider()
        card.label(_heading(ctx["engagements"]))
        for e in reversed(rows):
            card.row(e["client"], e["role"], e["when"])
        if hidden:
            card.lines(
                f"+{hidden} EARLIER", size=MICRO, color=kit.META, weight=700, mono=True
            )
    return card.finish()


# ---------------------------------------------------------------- education
def _education(rows: list[dict], label: str) -> str:
    """One row per degree: the degree, its dates on the right, then the school and city."""
    seconds = []
    for entry in rows:
        place = ", ".join(part for part in (entry["school"], entry["city"]) if part)
        lines = _wrap(place, SECOND_WRAP)
        if len(lines) > 2:  # a second line that does not fit wraps once, then is cut
            lines = [lines[0], _clip(" ".join(lines[1:]), SECOND_WRAP)]
        seconds.append(lines)
    height = TOP + sum(ROW + LINE * max(len(lines) - 1, 0) for lines in seconds) + 12
    parts = [
        kit.card_open(WIDTH, height, label, css=HEAD_CSS),
        kit.eyebrow(24, 31, "Education"),
    ]
    y = TOP
    for index, (entry, lines) in enumerate(zip(rows, seconds)):
        parts.append(
            f"<g>{kit.enter(0.15 + index * 0.07, shift='-8 0')}"
            f'<line x1="24" y1="{y}" x2="{WIDTH - 24}" y2="{y}" stroke="{ROW_RULE}"/>'
            f'<circle cx="30" cy="{y + 23}" r="3" fill="{kit.BLUE_LIGHT}"/>'
            + kit.text(44, y + 20, _clip(entry["degree"], 60), 13.5, kit.INK, "h")
            + "".join(
                kit.text(44, y + 37 + line * LINE, content, 11.5, kit.META)
                for line, content in enumerate(lines)
            )
            + kit.text(
                WIDTH - 24,
                y + 20,
                entry["when"].upper(),
                kit.MICRO,
                kit.META,
                "m",
                "end",
            )
            + "</g>"
        )
        y += ROW + LINE * max(len(lines) - 1, 0)
    return "".join(parts) + kit.SVG_CLOSE


def _education_detail(entry: dict, width: float, size: float) -> list[str]:
    """Wrap the school and city so the dot between them never ends or starts a line.

    The dot is held to the word after it with JOIN while the line breaks are chosen;
    the space comes back before anything is drawn. A dot that lands at a line break
    is dropped: the break already separates the two.
    """
    text = f" {DOT}{JOIN}".join(d for d in (entry["school"], entry["city"]) if d)
    lines = [line.replace(JOIN, " ") for line in wrap_text(text, width, size)]
    return [
        line.removeprefix(f"{DOT} ") if index else line
        for index, line in enumerate(lines)
    ]


def _education_phone(rows: list[dict], label: str) -> str:
    card = Card(label)
    for entry in rows:
        with card.block():
            card.lines(entry["degree"], weight=600)
            card.y += 3
            card.lines(
                entry["when"].upper(),
                size=MICRO,
                color=card.accent,
                weight=700,
                mono=True,
            )
            card.y += 3
            card.y = card._stack(
                _education_detail(entry, PHONE_WIDTH - 2 * PAD, 13.5),
                PAD,
                card.y,
                13.5,
                kit.BODY,
                500,
            )
        card.y += 12
    return card.finish()


# ---------------------------------------------------------------- publications
def _panel_height(items: list, wrap: int) -> float:
    return 56 + sum(16 * len(_wrap(text, wrap)) + 24 for text, _ in items) + 4


def _panel(
    title: str,
    items: list,
    x: float,
    y: float,
    width: float,
    height: float,
    accent: str,
    at: float,
    wrap: int,
) -> str:
    out = [
        f"<g>{kit.enter(at, 0.45)}"
        f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="12" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
        f'<rect x="{x:g}" y="{y + 16:g}" width="3" height="22" rx="1.5" fill="{accent}"/>'
        + kit.text(x + 18, y + 31, title.upper(), kit.MICRO, accent, "m")
    ]
    cy = y + 56
    for text, year in items:
        lines = _wrap(text, wrap)
        out.append(
            f'<circle cx="{x + 21:g}" cy="{cy - 4:g}" r="2.5" fill="{accent}"/>'
            + "".join(
                kit.text(x + 32, cy + line * 16, content, 12, kit.BODY)
                for line, content in enumerate(lines)
            )
        )
        cy += 16 * len(lines)
        out.append(kit.text(x + 32, cy, year, kit.MICRO, kit.META, "m"))
        cy += 24
    return "".join(out) + "</g>"


def _publications(groups: list, label: str) -> str:
    """The first two groups side by side, then the rest across the card."""
    pad, gap = 16, 12
    rows = [row for row in (groups[:2], groups[2:]) if row]
    # a row with one panel spans the card, so its lines wrap twice as wide
    widths = [(WIDTH - 2 * pad - gap * (len(row) - 1)) / len(row) for row in rows]
    wraps = [PANEL_WRAP if len(row) > 1 else PANEL_WRAP_WIDE for row in rows]
    heights = [
        max(_panel_height(items, wrap) for _, items in row)
        for row, wrap in zip(rows, wraps)
    ]
    height = 44 + sum(heights) + gap * max(len(rows) - 1, 0) + pad
    parts = [
        kit.card_open(WIDTH, height, label),
        kit.eyebrow(24, 30, "Publications, talks and recognition", kit.SKY),
    ]
    y, index = 44.0, 0
    for row, width, panel_height, wrap in zip(rows, widths, heights, wraps):
        for column, (title, items) in enumerate(row):
            parts.append(
                _panel(
                    title,
                    items,
                    pad + column * (width + gap),
                    y,
                    width,
                    panel_height,
                    PANEL_ACCENTS[index % len(PANEL_ACCENTS)],
                    0.15 + index * 0.12,
                    wrap,
                )
            )
            index += 1
        y += panel_height + gap
    return "".join(parts) + kit.SVG_CLOSE


def _publications_phone(groups: list, label: str) -> str:
    card = Card(label, kit.SKY)
    for index, (title, items) in enumerate(groups):
        if index:
            card.divider()
        card.label(title)
        for text, year in items:
            card.row(text, metadata=str(year), size=14, bullet=True, weight=500)
    return card.finish()


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
        "publications.svg": _publications(ctx["recognition"], recognition),
        "publications-mobile.svg": _publications_phone(ctx["recognition"], recognition),
    }
