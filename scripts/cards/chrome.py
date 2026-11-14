"""The page chrome: section headers, the connect row, call-to-action buttons, get-this-card strips and the footer."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# Drawn in kit's look, the one the hero and the project cards carry: flat
# surfaces, one blue family, mono micro-labels and one motion per file that
# means something, on the page clock. There is no divider image any more: each
# section header owns the break above it and keeps CLEAR px empty on top.
from __future__ import annotations

import math

import kit

WIDE, PHONE = 840, 320
SMOOTH = "0.4 0 0.2 1"  # ease in and out, for a move that goes and comes back
ELLIPSIS = "..."  # three ASCII dots where a label has to be cut to fit

# ---------------------------------------------------------------- section headers
# Headers sit on the page with no surface, so each comes as a dark and a light
# file. #60a5fa is 2.5:1 on white, so the light page gets the deeper blues.
THEMES = ("dark", "light")
LIGHT_INK, LIGHT_KICKER, LIGHT_EDGE = kit.BG, "#1d4ed8", "#0284c7"
LIGHT_META = "#57606a"  # GitHub's own muted text on white, 6.4:1
INKS = {
    "dark": {
        "ink": kit.INK,
        "number": kit.BLUE_LIGHT,
        "meta": kit.META,
        "rule": "rgba(255,255,255,0.12)",
        "accent": kit.BLUE_EDGE,
        "light": kit.SKY,
        "chip": kit.HAIR_FILL,
        "edge": kit.HAIR_STRONG,
        "lit": kit.BLUE_EDGE,
    },
    "light": {
        "ink": LIGHT_INK,
        "number": LIGHT_KICKER,
        "meta": LIGHT_META,
        "rule": "rgba(11,16,18,0.14)",
        "accent": LIGHT_KICKER,
        "light": LIGHT_EDGE,
        "chip": "rgba(11,16,18,0.03)",
        "edge": "rgba(11,16,18,0.18)",
        "lit": LIGHT_KICKER,
    },
}
CLEAR = 12  # the section break the header owns: nothing is drawn above this line
ACCENT = 40  # the blue tab the rule starts with, under the title
RULE_LOOP, RULE_TRAVEL = 6.0, 2.0  # the light crosses the rule in 2 s, then rests 4 s
CHIP_H, CHIP_PAD = 24, 10
# beside the kicker the chip is slimmer, so it clears the break and the title
KICKER_CHIP_H = 20
GAP = 24  # the least room between a line of text and the datum chip beside it
LIGHT_PX = 96  # the length of the light on the rule
# The header's measures at each width: the kicker's size, class, tracking, first
# baseline and line pitch; the title's size, its first baseline below the last
# kicker line and its pitch; the datum chip's text size; the rule below the last
# baseline and the room under the rule.
HEADER_DESKTOP = {
    "w": WIDE, "kicker": 11, "cls": "k", "track": 2, "first": 27, "pitch": 16,
    "title": 24, "drop": 30, "lead": 30, "datum": kit.MICRO, "rule": 12.5, "foot": 6.5,
}  # fmt: skip
HEADER_PHONE = {
    "w": PHONE, "kicker": kit.MICRO_PHONE, "cls": "m", "track": kit.TRACK, "first": 27,
    "pitch": 16, "title": 22, "drop": 29, "lead": 27, "datum": kit.MICRO_PHONE,
    "rule": 13, "foot": 6.5,
}  # fmt: skip


def kicker_text(number: str, subtitle: str) -> str:
    """The line above a header's title: its number and its subtitle, either may be empty."""
    return " / ".join(part for part in (number, subtitle.upper()) if part)


def _kicker_line(line: str, number: str, inks: dict) -> str:
    """A kicker line with the section number in blue; the rest takes the text's muted fill."""
    if number and (line == number or line.startswith(f"{number} ")):
        tail = kit.esc(line[len(number) :])
        return f'<tspan fill="{inks["number"]}">{kit.esc(number)}</tspan>{tail}'
    return kit.esc(line)


def _fit_datum(datum: str, size: float, room: float) -> str:
    """The datum, or as many of its words as fit a chip `room` wide, then an ellipsis."""
    words = datum.split()
    text = datum
    while len(words) > 1 and kit.chip_width(text, size, CHIP_PAD) > room:
        words.pop()
        text = " ".join(words) + ELLIPSIS
    return text


def _datum_runs(datum: str, inks: dict) -> str:
    """The datum with every count in the ink, the way the hero's proof cells set a value; the words stay muted."""
    body = datum.removesuffix(ELLIPSIS)
    runs = [
        f'<tspan fill="{inks["ink"]}">{kit.esc(word)}</tspan>'
        if any(character.isdigit() for character in word)
        else kit.esc(word)
        for word in body.split()
    ]
    return " ".join(runs) + datum[len(body) :]


def _travel(points: list[tuple[float, str]], dur: float, begin: float = 0) -> str:
    """Translate the element it sits in through (second, "x y") points on a loop of dur seconds."""
    values = ";".join(value for _, value in points)
    times = ";".join(f"{round(second / dur, 4):g}" for second, _ in points)
    splines = ";".join(
        SMOOTH if a[1] != b[1] else "0 0 1 1" for a, b in zip(points, points[1:])
    )
    start = f' begin="{begin:g}s"' if begin else ""
    return (
        f'<animateTransform attributeName="transform" type="translate" values="{values}" '
        f'keyTimes="{times}" calcMode="spline" keySplines="{splines}" dur="{dur:g}s"{start} '
        'repeatCount="indefinite"/>'
    )


def _mono_width(line: str, size: float, tracking: float = kit.TRACK) -> float:
    """The visible width kit measures for a mono line: no tracking after its last glyph."""
    return kit.text_width(line, size, True, tracking) - tracking


def _mono(
    x: float,
    y: float,
    line: str,
    size: float,
    fill: str,
    cls: str = "m",
    anchor: str = "",
    tracking: float | None = None,
) -> str:
    """A mono label pinned with textLength to the width kit measures for it.

    kit measures mono at 0.6 em a glyph; Consolas sets narrower. Pinned, an
    arrow or a leader placed beside the label stays the same distance from it
    whichever mono font the viewer has. A `tracking` other than the class's
    own is set inline, where it outranks the class rule.
    """
    own = 0 if cls == "c" else kit.TRACK
    tracking = own if tracking is None else tracking
    wide = _mono_width(line, size, tracking)
    extra = f' textLength="{wide:.1f}"'
    if tracking != own:
        extra += f' style="letter-spacing:{tracking:g}px"'
    return kit.text(x, y, line, size, fill, cls, anchor, extra)


def _flash(points: list[tuple[float, float]], dur: float, begin: float = 0) -> str:
    """An opacity loop through (second, level) points."""
    values = ";".join(f"{level:g}" for _, level in points)
    times = ";".join(f"{round(second / dur, 4):g}" for second, _ in points)
    return kit.loop("opacity", values, times, dur, begin)


def _rule(
    w: float, y: float, inks: dict, chip: tuple[float, float, float, float] | None
) -> str:
    """The rule under a header: a blue tab, a hairline, and the light that crosses it every 6 s.

    The light runs from the tab to the right edge in RULE_TRAVEL seconds. Where the datum
    chip (x, top, width, height) sits, its border lights while the light passes under it.
    """
    length = w - ACCENT
    dash = round(100 * LIGHT_PX / length, 2)
    out = [
        f'<path d="M0 {y:g}H{w:g}" stroke="{inks["rule"]}" stroke-width="1"/>',
        f'<path d="M0 {y:g}H{ACCENT}" stroke="{inks["accent"]}" stroke-width="2"/>',
        kit.beam(
            f"M{ACCENT} {y:g}H{w:g}",
            dur=RULE_LOOP,
            travel=RULE_TRAVEL / RULE_LOOP,
            color=inks["light"],
            width=2,
            dash=dash,
        ),
    ]
    if chip:
        x, top, wide, tall = chip
        # the light's head is at 0 units at 0 s and at 100 + dash units at RULE_TRAVEL
        reach = max(0.0, (x - ACCENT) / length * 100)
        arrive = round(RULE_TRAVEL * reach / (100 + dash), 2)
        out.append(
            f'<rect x="{x:g}" y="{top:g}" width="{wide:.1f}" height="{tall:g}" rx="{tall / 2:g}" '
            f'fill="none" stroke="{inks["lit"]}" stroke-width="1.2" opacity="0">'
            + _flash(
                [
                    (0, 0),
                    (arrive, 0),
                    (arrive + 0.15, 1),
                    (RULE_TRAVEL + 0.2, 1),
                    (RULE_TRAVEL + 0.7, 0),
                    (RULE_LOOP, 0),
                ],
                RULE_LOOP,
            )
            + "</rect>"
        )
    return "".join(out)


def _header(
    number: str, title: str, subtitle: str, theme: str, datum: str, g: dict
) -> str:
    """One section header, laid out for the measures in g.

    The datum comes as ctx writes it and is shown upper case in its chip; the
    aria-label, which the README uses as alt text, carries it whole.
    """
    w, inks = g["w"], INKS[theme]
    kicker = kit.balance(
        kit.wrap_text(
            kicker_text(number, subtitle), w - 2, g["kicker"], True, g["track"]
        )
    )
    titles = kit.balance(kit.wrap_text(title, w - 2, g["title"]))
    out, rows = [], []
    y = g["first"]
    for line in kicker:
        out.append(
            f'<text class="{g["cls"]}" x="0" y="{y:g}" font-size="{g["kicker"]:g}" fill="{inks["meta"]}">'
            f"{_kicker_line(line, number, inks)}</text>"
        )
        # a chip beside a kicker of two lines would sit on the second
        if len(kicker) == 1:
            right = kit.text_width(line, g["kicker"], True, g["track"]) - g["track"]
            # (the chip text's baseline, the line's right edge, the chip's height):
            # beside the kicker its text shares the kicker's baseline
            rows.append((y, right, KICKER_CHIP_H))
        y += g["pitch"]
    y += g["drop"] - g["pitch"]
    for line in titles:
        out.append(kit.text(0, y, line, g["title"], inks["ink"], "t"))
        y += g["lead"]
    last = y - g["lead"]
    # beside the title the chip is centred on the title's lower-case letters
    middle = last - (g["title"] - g["datum"]) * 0.36
    rows.insert(0, (middle, kit.text_width(titles[-1], g["title"]), CHIP_H))

    chip = None
    if datum:
        shown = _fit_datum(datum.upper(), g["datum"], w - 1)
        wide = kit.chip_width(shown, g["datum"], CHIP_PAD)
        x = w - wide - 0.5
        # beside the last title line, else beside the kicker, else on a row of its own
        spot = next(
            ((base, tall) for base, right, tall in rows if right + GAP <= x), None
        )
        if spot is None:
            x, spot = 0.5, (last + 12 + CHIP_H / 2 + g["datum"] * 0.36, CHIP_H)
            last += 12 + CHIP_H - 2
        base, tall = spot
        top = round(base - g["datum"] * 0.36 - tall / 2, 1)
        chip = (x, top, wide, tall)
        out.append(
            f'<rect x="{x:g}" y="{top:g}" width="{wide:.1f}" height="{tall:g}" rx="{tall / 2:g}" '
            f'fill="{inks["chip"]}" stroke="{inks["edge"]}"/>'
            f'<text class="m" x="{x + wide / 2:.1f}" y="{base:.1f}" '
            f'font-size="{g["datum"]:g}" fill="{inks["meta"]}" text-anchor="middle">{_datum_runs(shown, inks)}</text>'
        )
    rule = round(last + g["rule"], 1)
    h = math.ceil(rule + g["foot"])
    return (
        kit.svg_open(w, h, f"{title}: {datum}" if datum else title)
        + kit.style()
        + "".join(out)
        + _rule(w, rule, inks, chip)
        + kit.SVG_CLOSE
    )


def render_header(
    number: str, title: str, subtitle: str, theme: str, datum: str = ""
) -> str:
    return _header(number, title, subtitle, theme, datum, HEADER_DESKTOP)


def render_header_phone(
    number: str, title: str, subtitle: str, theme: str, datum: str = ""
) -> str:
    return _header(number, title, subtitle, theme, datum, HEADER_PHONE)


# ---------------------------------------------------------------- the connect row
# Four buttons under the hero, in the hero's own tile style: CARD with a hairline,
# lit the way the hero's proof row lights a cell. The resume is the primary: a
# blue button a light circles. The others light in turn, a slot apart, so one
# light walks the row on the same 6 s clock.
CONNECT_W, CONNECT_H, CONNECT_RADIUS = 128, 40, 10
CONNECT_LOOP = 6.0
CONNECT_STEP = 1.5  # seconds between one button's turn and the next
CONNECT_SIZE = 11.5
CONNECT_DASH = 14  # the primary's light, in hundredths of its border
ICON, ICON_GAP = 16, 8
WHITE = "#ffffff"


def _icon(path: str, x: float, y: float, fill: str) -> str:
    """A 24 x 24 Simple Icons path drawn ICON px square with its top left at x, y."""
    scale = ICON / 24
    return f'<path transform="translate({x:g} {y:g}) scale({scale:g})" d="{kit.esc(path)}" fill="{fill}"/>'


def render_connect_button(
    label: str, icon_path: str | None, index: int, primary: bool = False
) -> str:
    """One 128px link button; its border lights in its turn, or a light circles it if it is the primary."""
    w, h, r = CONNECT_W, CONNECT_H, CONNECT_RADIUS
    shape = (
        f'x="0.75" y="0.75" width="{w - 1.5:g}" height="{h - 1.5:g}" rx="{r - 0.75:g}"'
    )
    word = label.upper()
    text_w = kit.text_width(word, CONNECT_SIZE, True, kit.TRACK) - kit.TRACK
    group = text_w + (ICON + ICON_GAP if icon_path else 0)
    x = round((w - group) / 2, 1)
    ink = WHITE if primary else kit.INK
    begin = index * CONNECT_STEP
    out = [kit.svg_open(w, h, label), kit.style()]
    if primary:
        out.append(f'<rect {shape} fill="{kit.BLUE}" stroke="{kit.BLUE_EDGE}"/>')
        out.append(
            _circling(
                kit.rounded_rect_path(0.75, 0.75, w - 1.5, h - 1.5, r - 0.75),
                w - 1.5,
                h - 1.5,
                r - 0.75,
                begin,
            )
        )
    else:
        out.append(f'<rect {shape} fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>')
        # the hero's lit cell: a blue tint and a blue edge, on for its turn only
        out.append(
            f'<rect {shape} fill="{kit.BLUE_TINT}" stroke="{kit.BLUE_EDGE}" stroke-width="1.5" opacity="0">'
            + _flash(
                [(0, 0), (0.25, 1), (1.15, 1), (1.45, 0), (CONNECT_LOOP, 0)],
                CONNECT_LOOP,
                begin,
            )
            + "</rect>"
        )
    if icon_path:
        out.append(_icon(icon_path, x, (h - ICON) / 2, ink))
        x += ICON + ICON_GAP
    out.append(_mono(x, h / 2 + CONNECT_SIZE * 0.36, word, CONNECT_SIZE, ink))
    out.append(kit.SVG_CLOSE)
    return "".join(out)


def _circling(d: str, w: float, h: float, r: float, begin: float) -> str:
    """The primary button's light: one dash that circles its border once every CONNECT_LOOP s.

    kit.beam(closed=True) with a start: a still frame shows the dash round the
    top right corner, where it reads as a light on its way round rather than a
    mark on the top edge.
    """
    around = 2 * (w + h) - (8 - 2 * math.pi) * r
    dash = CONNECT_DASH
    corner = (
        (w - 2 * r + math.pi * r / 4) / around * 100
    )  # the middle of the corner's arc
    start = round(-(corner - dash / 2), 2)
    timing = f' begin="{begin:g}s"' if begin else ""
    return (
        f'<path d="{d}" fill="none" stroke="{WHITE}" stroke-width="1.5" stroke-linecap="round" '
        f'pathLength="100" stroke-dasharray="{dash:g} {100 - dash:g}" stroke-dashoffset="{start:g}">'
        f'<animate attributeName="stroke-dashoffset" values="{start:g};{start - 100:g}" '
        f'dur="{CONNECT_LOOP:g}s"{timing} repeatCount="indefinite"/></path>'
    )


# ---------------------------------------------------------------- call-to-action buttons
CTA_W, CTA_H, CTA_PAD = 250, 44, 16
# These buttons have no phone twin: the README shows them 250px wide on a phone
# too, so their label keeps the phone floor and never steps down in size.
CTA_SIZE = kit.MICRO_PHONE
CTA_GAPS = (
    12,
    8,
)  # label to arrow; the narrow gap only where no tracking is left to give
CTA_LOOP, NUDGE = 3.0, 3  # the arrow nudges 3px once every 3 s
ARROW_W = 10
ARROW = "M0 0H10M6 -4L10 0L6 4"  # drawn from its tail at 0, 0, pointing right


def cta_labels(ctx: dict) -> dict[str, str]:
    """{file stem: label} for the wide buttons, counted from ctx.

    The portfolio button is left out while the project count is unknown: a
    made-up number is worse than a missing link.
    """
    labels: dict[str, str] = {}
    count = int(ctx.get("project_count") or 0)
    if count:
        labels["cta-portfolio"] = f"View all {count} projects"
    labels["cta-community"] = f"See all {len(ctx.get('tools') or [])} community tools"
    labels["cta-profile"] = "Back to profile"
    return labels


def _arrow(
    x: float, y: float, back: bool, dur: float, at: float, begin: float = 0
) -> str:
    """The link arrow, its tail at x, y, nudging NUDGE px the way it points at `at` s of its loop."""
    turn = ' transform="scale(-1 1)"' if back else ""
    shift = -NUDGE if back else NUDGE
    move = _travel(
        [
            (0, "0 0"),
            (at, "0 0"),
            (at + 0.25, f"{shift} 0"),
            (at + 0.6, "0 0"),
            (dur, "0 0"),
        ],
        dur,
        begin,
    )
    return (
        f'<g transform="translate({x:g} {y:g})"><g>{move}<path{turn} d="{ARROW}" fill="none" '
        f'stroke="{kit.BLUE_LIGHT}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></g></g>'
    )


def _cta_fit(word: str) -> tuple[float, float]:
    """(tracking, gap) at which the label and its arrow fit the button at CTA_SIZE.

    The tracking gives way first, from kit.TRACK down to 0, then the gap to the
    arrow narrows; the size never does.
    """
    room = CTA_W - 2 * CTA_PAD - ARROW_W
    glyphs = len(word) * CTA_SIZE * 0.6
    for gap in CTA_GAPS:
        spare = room - gap - glyphs
        if spare >= 0:
            tracking = min(kit.TRACK, spare / max(1, len(word) - 1))
            return math.floor(tracking * 10) / 10, gap
    return 0.0, CTA_GAPS[-1]


def render_cta(label: str, back: bool = False) -> str:
    """A 250px outlined button: the label and an arrow that nudges on the 3 s beat; `back` points it left."""
    w, h, size = CTA_W, CTA_H, CTA_SIZE
    word = label.upper()
    tracking, gap = _cta_fit(word)
    text_w = _mono_width(word, size, tracking)
    group = text_w + gap + ARROW_W
    x = round((w - group) / 2, 1)
    base = h / 2 + size * 0.36
    if back:
        arrow = _arrow(x + ARROW_W, h / 2, True, CTA_LOOP, 0.2)  # tail on the right
        words = _mono(x + ARROW_W + gap, base, word, size, kit.INK, tracking=tracking)
    else:
        words = _mono(x, base, word, size, kit.INK, tracking=tracking)
        arrow = _arrow(x + text_w + gap, h / 2, False, CTA_LOOP, 0.2)
    return (
        kit.svg_open(w, h, label)
        + kit.style()
        + f'<rect x="0.75" y="0.75" width="{w - 1.5:g}" height="{h - 1.5:g}" rx="10" fill="{kit.CARD}" '
        f'stroke="{kit.BLUE_EDGE}" stroke-width="1.2"/>' + words + arrow + kit.SVG_CLOSE
    )


# ---------------------------------------------------------------- get-this-card strips
# A slim link line under a card: the ask, a dotted leader and the repository of
# the public action that makes that card. A light runs the leader to the repo
# every 6 s and the arrow nudges as it lands.
STRIP_H, STRIP_PHONE_H = 36, 60
STRIP_LOOP, STRIP_TRAVEL = 6.0, 2.0
OWNER = "Sagargupta16"


def get_card_label(repo: str, card: str) -> str:
    return f"Get the {card} for your own profile: {OWNER}/{repo}"


def strip_ask(card: str) -> str:
    return f"GET {'THESE CARDS' if card.endswith('cards') else 'THIS CARD'} FOR YOUR PROFILE"


def _repo_fit(repo: str, size: float, room: float, owner: bool = True) -> str:
    """The repository as owner/name when it fits (and `owner` allows it), else the bare name, else the name cut short."""
    for option in (f"{OWNER}/{repo}", repo)[0 if owner else 1 :]:
        if kit.text_width(option, size, True, 0) <= room:
            return option
    keep = max(1, int(room // (size * 0.6)) - len(ELLIPSIS))
    return repo[:keep] + ELLIPSIS


def _leader(x0: float, x1: float, y: float) -> str:
    """The dotted line from the ask to the repo, and the light that runs it."""
    d = f"M{x0:g} {y:g}H{x1:g}"
    dash = round(100 * 40 / (x1 - x0), 2)
    return (
        f'<path d="{d}" stroke="{kit.HAIR_STRONG}" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="0.1 6"/>'
        + kit.beam(
            d,
            dur=STRIP_LOOP,
            travel=STRIP_TRAVEL / STRIP_LOOP,
            color=kit.SKY,
            width=1.6,
            dash=min(dash, 40),
        )
    )


def render_get_this_card(repo: str, card: str) -> str:
    """The 840px strip: the ask on the left, the repository and its arrow on the right."""
    w, h, pad, size = WIDE, STRIP_H, 16, 11.5
    mid = h / 2
    ask = strip_ask(card)
    ask_end = pad + _mono_width(ask, kit.MICRO)
    arrow_x = w - pad - ARROW_W
    room = arrow_x - 10 - (ask_end + GAP)
    name = _repo_fit(repo, size, room)
    name_x = arrow_x - 10 - _mono_width(name, size, 0)
    out = [
        kit.svg_open(w, h, get_card_label(repo, card)),
        kit.style(),
        kit.frame(w, h, 10),
        _mono(pad, mid + kit.MICRO * 0.36, ask, kit.MICRO, kit.META),
        _mono(name_x, mid + size * 0.36, name, size, kit.BLUE_LIGHT, "c"),
    ]
    if name_x - 14 - (ask_end + 14) >= 24:
        out.append(_leader(ask_end + 14, name_x - 14, mid))
    out.append(_arrow(arrow_x, mid, False, STRIP_LOOP, STRIP_TRAVEL))
    out.append(kit.SVG_CLOSE)
    return "".join(out)


def render_get_this_card_phone(repo: str, card: str) -> str:
    """The 320px strip on two lines: the ask, then the repository with its leader and arrow.

    The phone strips show the bare repository name, so the four read alike
    whatever their names' lengths; the owner is in the aria-label and the link.
    """
    w, h, pad, size = PHONE, STRIP_PHONE_H, 16, 12
    ask = strip_ask(card)
    arrow_x = w - pad - ARROW_W
    name = _repo_fit(repo, size, arrow_x - 10 - pad, owner=False)
    name_end = pad + _mono_width(name, size, 0)
    line = 43
    out = [
        kit.svg_open(w, h, get_card_label(repo, card)),
        kit.style(),
        kit.frame(w, h, 10),
        _mono(pad, 24, ask, kit.MICRO_PHONE, kit.META),
        _mono(pad, line, name, size, kit.BLUE_LIGHT, "c"),
    ]
    if arrow_x - 10 - (name_end + 10) >= 24:
        out.append(_leader(name_end + 10, arrow_x - 10, line - size * 0.36))
    out.append(_arrow(arrow_x, line - size * 0.36, False, STRIP_LOOP, STRIP_TRAVEL))
    out.append(kit.SVG_CLOSE)
    return "".join(out)


# ---------------------------------------------------------------- footer
# The page closes on its route: a wave with a stop for each section header,
# 01 to 09, and an end node. A comet runs the wave from the first stop to the
# end; each stop lights as it passes and the end node rings when it lands.
# The comet's dot and its tail are two dashes of one path, measured in the same
# pathLength units and moved by the same offsets, so they cannot drift apart.
FOOTER_LINES = ["Thanks for visiting", "More at sagargupta.online"]
# the signature alone: the hero already shows the place and the role, and the
# stop labels already count the sections
FOOTER_NAME = "SAGAR GUPTA"
FOOTER_DISCLAIMER_INK = "#a8b4c1"
WAVE_UNITS = 1000
TAIL = 0.12  # the comet's tail, as a share of the wave
REST_PX = 16  # in a still frame the comet's head is this far short of the end node
COMET_DOT = 0.1  # a dash this short is drawn as its round cap: the dot
FOOTER_LOOP = 12.0
COMET_TRAVEL = 4.0  # the head runs from the first stop until the tail has left the wave
HOLD, DIM = 10.4, 10.8  # the stops stay lit until HOLD and are dark again by DIM
END_R = 4.5
STOP_DIM = kit.META  # the ring of a stop the comet has not reached yet
# The footer's measures at each width: the eyebrow's baseline, the rotating line's
# baseline, size and floor, the wave's centre line and amplitude, the stop labels
# below the wave, and the disclaimer's size, gap below the labels and leading.
FOOTER_DESKTOP = {
    "w": WIDE, "pad": 24, "eyebrow": 30, "micro": kit.MICRO, "line": 70, "size": 28,
    "floor": 20, "wave": 98, "amp": 7, "label": 20, "note": 11, "note_gap": 24,
    "note_lead": 16, "foot": 20,
}  # fmt: skip
FOOTER_PHONE = {
    "w": PHONE, "pad": 18, "eyebrow": 28, "micro": kit.MICRO_PHONE, "line": 62,
    "size": 22, "floor": 16, "wave": 90, "amp": 4, "label": 20, "note": 12,
    "note_gap": 24, "note_lead": 17, "foot": 18,
}  # fmt: skip


def _wave(x0: float, x1: float, y: float, halves: int, amp: float) -> tuple[str, float]:
    """A wave of `halves` equal half-waves from x0 to x1 that crosses y at every join.

    Returns (path data, the length of one half-wave). Each half-wave is one cubic
    with both handles a third of the way in, at 4/3 of the amplitude, so the
    curve peaks at `amp` and the joins stay smooth.
    """
    step = (x1 - x0) / halves
    lift = amp * 4 / 3
    d = [f"M{x0:g} {y:g}"]
    for index in range(halves):
        a, b = x0 + index * step, x0 + (index + 1) * step
        side = -1 if index % 2 == 0 else 1
        d.append(
            f"C{a + step / 3:.1f} {y + side * lift:.1f} {b - step / 3:.1f} {y + side * lift:.1f} {b:.1f} {y:g}"
        )
    # one half-wave's length, from 64 points along its cubic
    points = []
    for i in range(65):
        t = i / 64
        bx = (
            3 * (1 - t) ** 2 * t * (step / 3)
            + 3 * (1 - t) * t**2 * (2 * step / 3)
            + t**3 * step
        )
        by = (3 * (1 - t) ** 2 * t + 3 * (1 - t) * t**2) * lift
        points.append((bx, by))
    half = sum(math.dist(p, q) for p, q in zip(points, points[1:]))
    return "".join(d), half


def _comet(
    d: str, color: str, width: float, dash: float, lead: float, tail: float, rest: float
) -> str:
    """One dash of the wave, placed `lead` units behind the comet's head.

    The head runs from 0 to WAVE_UNITS + tail in COMET_TRAVEL seconds, so the
    tail has left the wave before it rests; a dash offset of `lead - head` puts
    this dash `lead` units behind the head: the tail's length for the tail, 0
    for the dot. `rest` is where the head sits in a still frame.
    """
    end = WAVE_UNITS + tail
    share = round(COMET_TRAVEL / FOOTER_LOOP, 4)
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}" stroke-linecap="round" '
        f'pathLength="{WAVE_UNITS}" stroke-dasharray="{dash:g} {2 * end:g}" stroke-dashoffset="{lead - rest:g}">'
        f'<animate attributeName="stroke-dashoffset" values="{lead:g};{lead - end:g};{lead - end:g}" '
        f'keyTimes="0;{share:g};1" dur="{FOOTER_LOOP:g}s" repeatCount="indefinite"/></path>'
    )


def _fit(lines: list[str], size: float, floor: float, room: float) -> float:
    """The largest size from `size` down to `floor` at which every line fits `room`."""
    while size > floor and max(kit.text_width(line, size) for line in lines) > room:
        size = max(floor, size - 0.5)
    return size


def _footer(ctx: dict, g: dict) -> str:
    w, pad = g["w"], g["pad"]
    disclaimer = ctx.get("disclaimer") or ""
    numbers = [str(header[1]) for header in ctx.get("headers") or []]
    out = [kit.text(pad, g["eyebrow"], FOOTER_NAME, g["micro"], kit.BLUE_LIGHT, "m")]
    size = _fit(FOOTER_LINES, g["size"], g["floor"], w - 2 * pad)
    out.append(kit.rotating(FOOTER_LINES, pad, g["line"], "t", size, kit.INK))

    # the route: a stop on each join of the wave, then the end node
    y = g["wave"]
    # the first stop's label starts on the text column's edge; the wave ends on the
    # end node's left edge, so the comet lands on its ring
    label_w = max((_mono_width(n, g["micro"]) for n in numbers), default=0)
    x0, x1 = pad + max(3, label_w / 2), w - pad - 2 * END_R - 1
    node = x1 + END_R
    halves = max(1, len(numbers))
    step = (x1 - x0) / halves
    labelled = step >= label_w + 8
    amp = min(g["amp"], step / 7)
    d, half = _wave(x0, x1, y, halves, amp)
    length = half * halves
    tail = round(WAVE_UNITS * TAIL)
    # the still frame: the comet just short of the end node, arriving
    rest = WAVE_UNITS - round(WAVE_UNITS * REST_PX / length)
    end = WAVE_UNITS + tail
    out.append(
        f'<path d="{d}" fill="none" stroke="{kit.HAIR_STRONG}" stroke-width="1.2"/>'
    )
    stops = []
    for index, number in enumerate(numbers):
        x = x0 + index * step
        lit = round(COMET_TRAVEL * (WAVE_UNITS * index / halves) / end, 2)
        stops.append(
            f'<circle cx="{x:.1f}" cy="{y:g}" r="2.6" fill="none" stroke="{STOP_DIM}" stroke-width="1.2"/>'
            f'<circle cx="{x:.1f}" cy="{y:g}" r="3.2" fill="{kit.BLUE_LIGHT}">'
            + _flash(
                [
                    (0, 0),
                    (lit, 0),
                    (lit + 0.15, 1),
                    (HOLD, 1),
                    (DIM, 0),
                    (FOOTER_LOOP, 0),
                ]
                if lit
                else [
                    (0, 1),
                    (HOLD, 1),
                    (DIM, 0),
                    (FOOTER_LOOP - 0.15, 0),
                    (FOOTER_LOOP, 1),
                ],
                FOOTER_LOOP,
            )
            + "</circle>"
        )
        if labelled:
            stops.append(
                kit.text(x, y + g["label"], number, g["micro"], kit.META, "m", "middle")
            )
    out += stops
    out.append(_comet(d, kit.BLUE_LIGHT, 2, tail, tail, tail, rest))  # the tail
    out.append(_comet(d, kit.SKY, 7, COMET_DOT, 0, tail, rest))  # the dot at its head
    land = round(COMET_TRAVEL * WAVE_UNITS / end, 2)
    out.append(
        f'<circle cx="{node:.1f}" cy="{y:g}" r="{END_R}" fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="1.5" opacity="0">'
        f'<animate attributeName="r" values="{END_R};{END_R};{END_R + 9};{END_R + 9}" '
        f'keyTimes="0;{land / FOOTER_LOOP:.4f};{(land + 1) / FOOTER_LOOP:.4f};1" dur="{FOOTER_LOOP:g}s" repeatCount="indefinite"/>'
        + _flash(
            [(0, 0), (land - 0.01, 0), (land, 0.9), (land + 1, 0), (FOOTER_LOOP, 0)],
            FOOTER_LOOP,
        )
        + "</circle>"
        f'<circle cx="{node:.1f}" cy="{y:g}" r="{END_R}" fill="none" stroke="{kit.BLUE_EDGE}" stroke-width="1.5"/>'
        f'<circle cx="{node:.1f}" cy="{y:g}" r="2" fill="{kit.BLUE_LIGHT}"/>'
    )

    base = y + (g["label"] if labelled else 8) + g["note_gap"]
    note = kit.wrap_text(disclaimer, w - 2 * pad, g["note"]) if disclaimer else []
    for index, line in enumerate(kit.balance(note)):
        out.append(
            kit.text(
                pad,
                base + index * g["note_lead"],
                line,
                g["note"],
                FOOTER_DISCLAIMER_INK,
                "b",
            )
        )
    bottom = (
        base + (len(note) - 1) * g["note_lead"]
        if note
        else y + (g["label"] if labelled else 8)
    )
    h = math.ceil((bottom + g["foot"]) / 2) * 2
    label = f"{'. '.join(FOOTER_LINES)}. {disclaimer}".strip()
    return kit.card_open(w, h, label) + "".join(out) + kit.SVG_CLOSE


def render_footer(ctx: dict) -> str:
    return _footer(ctx, FOOTER_DESKTOP)


def render_footer_phone(ctx: dict) -> str:
    return _footer(ctx, FOOTER_PHONE)


# ---------------------------------------------------------------- the lane
def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for the headers, buttons, strips and footer at both widths."""
    files: dict[str, str] = {}
    counts = ctx.get("header_counts") or {}
    for key, number, title, subtitle in ctx["headers"]:
        datum = counts.get(key) or ""
        for theme in THEMES:
            files[f"header-{key}-{theme}.svg"] = render_header(
                number, title, subtitle, theme, datum
            )
            files[f"header-{key}-{theme}-mobile.svg"] = render_header_phone(
                number, title, subtitle, theme, datum
            )
    for index, button in enumerate(ctx["connect"]):
        files[f"connect-{button['key']}.svg"] = render_connect_button(
            button["label"], button.get("icon"), index, bool(button.get("primary"))
        )
    for name, label in cta_labels(ctx).items():
        files[f"{name}.svg"] = render_cta(label, back=name == "cta-profile")
    for key, repo, card in ctx["get_cards"]:
        files[f"get-{key}.svg"] = render_get_this_card(repo, card)
        files[f"get-{key}-mobile.svg"] = render_get_this_card_phone(repo, card)
    files["footer.svg"] = render_footer(ctx)
    files["footer-mobile.svg"] = render_footer_phone(ctx)
    return files
