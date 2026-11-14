"""Coding stats and certification status: competitive, certs-status, and the phone twins of the vendored cards.

competitive: the contest record. Tiles for LeetCode's best contest rank, GeeksforGeeks,
HackerRank and the best Kick Start round sit beside a ledger of the top finishes, and a lit
row steps down the ledger on the 12 s clock.
certs-status: one cell per active certification. A thin ring shows the share of its validity
left, with the months that share is inside it, and a light runs each ring in turn.
github-mobile, leetcode-mobile and certs-mobile: the 320px twins of the cards his actions
draw (github.svg, leetcode.svg, certs.svg), from the same snapshot.

Every card is flat on kit's surface, rests on its finished frame (entrances come from
kit.group, kit.draw and kit.ring) and loops on the page clock.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
from __future__ import annotations

import datetime
import math
import re

import kit
from mobile_cards import cert_issuer

T = kit.T
W, PHONE = 840, 320
PAD, PHONE_PAD = 24, 18  # side padding: desktop, phone
COLUMN = PHONE - 2 * PHONE_PAD
TOP = 46  # where a desktop card's body starts, under the eyebrow at y=30
GAP = 12
STAGGER, LAST_START = kit.STAGGER, 1.2

MISSING = "-"
DOT = chr(0xB7)  # the middle dot two facts are joined with
# An empty day, then four levels of the blue family; the brightest is a tint the kit
# does not carry. Every level reaches 3:1 on the card.
HEAT = (kit.HAIR_STRONG, kit.BLUE, kit.BLUE_EDGE, kit.BLUE_LIGHT, "#93c5fd")
HEX_COLOR = re.compile("#[0-9a-fA-F]{6}")
# The LeetCode tiles and marks: amber is LeetCode's colour on the page and nothing else's.
AMBER_TINT = "rgba(245,158,11,0.10)"
AMBER_EDGE = "rgba(245,158,11,0.55)"
AMBER_LIGHT = (
    "#fde68a"  # the light that runs the rating line, pale enough to show on it
)
# Credly keeps a badge after its course is withdrawn and marks the name.
RETIRED = re.compile("retired", re.IGNORECASE)
# The list under TOP FINISHES: it includes a 4th place, so it is not called a podium.
TOP_FINISH = re.compile("(1st|2nd|3rd|4th) Place")
KICK_START = re.compile(
    "Rank ([0-9]+) - Google Kick Start '([0-9]{2}), Round ([A-Za-z0-9]+)"
)
YEAR = re.compile("(?:19|20)[0-9]{2}")
DASHES = re.compile(f"[{chr(0x2013)}{chr(0x2014)}]")
GALLERY_NOTE = "The Credly gallery below also includes learning and partner badges."
# How long a certification stays valid, by issuer: AWS certifications for three years,
# HashiCorp's for two. An issuer missing here gets no ring rather than a guessed share.
VALIDITY_YEARS = {"AWS": 3, "TERRAFORM": 2}
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
LEDGER_CAP = 7  # the most finishes a ledger lists; past it the last row says +N more
# Every tile is counted over the same contribution calendar: the past 12 months.
# Stars are a lifetime total, so they sit in a line of their own under the heatmap.
GITHUB_TILES = [
    ("contributions", "Contributions"),
    ("commits", "Commits"),
    ("prs", "Pull requests"),
    ("active_days", "Active days"),
    ("streak", "Current streak"),
    ("longest", "Longest streak"),
]
WEEKS = 20  # the heatmap's window on a phone
# the share of kit's sans measure a 600-weight line sets at (as in the hero)
SANS_FIT = 0.9
# The Credly images are inlined, so they are most of the phone badge card's weight. Every
# image together stays inside IMAGE_BUDGET, whatever the data, which keeps the file under
# the validator's 100 KB error line (past its 50 KB warning: the cost of showing the partner
# and AI badges on phones). The certifications take the budget first, in whole rows of
# CERT_ROW; then one row of BADGE_ROW learning and partner badges, the most relevant first.
# What does not fit is counted in a line that points to Credly, where the card links.
IMAGE_BUDGET, CERT_ROW, BADGE_ROW = 84_000, 3, 5
# The learning and partner badges a phone shows first, by name: the Claude Code partner
# badge, ambassador roles, accreditations from L200 up, then L100, then proficiency badges.
# A badge that matches none keeps its Credly place behind them.
RELEVANT = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        "claude",
        "ambassador",
        r"\(L[2-9]00\)",
        r"accreditation|\(L100\)",
        "proficient",
    )
]
SLIDE = 0.35  # how long the lit border takes to reach its next item


def _number(value: object) -> str:
    if value is None or value == "":
        return MISSING
    return f"{value:,}" if isinstance(value, int) else str(value)


# ---------------------------------------------------------------- text and timing helpers
def _mono(label: str, size: float) -> float:
    """The drawn width of a mono micro-label: kit's measure without the tracking after the last letter."""
    return kit.text_width(label, size, True, kit.TRACK) - kit.TRACK


def _clip(text: str, room: float, size: float, mono: bool = False) -> str:
    """Shorten text to a width: whole words first, then letters, ending in three dots."""

    def fits(value: str) -> bool:
        return kit.text_width(value, size, mono, kit.TRACK) <= room

    if fits(text):
        return text
    while " " in text and not fits(text + "..."):
        text = text.rsplit(" ", 1)[0]
    while len(text) > 1 and not fits(text + "..."):
        text = text[:-1]
    return text.rstrip(" ,;:.-") + "..."


def _lines(
    text: str, room: float, size: float, cap: int, mono: bool = False
) -> list[str]:
    """Wrap to a width and keep at most `cap` lines, the last one clipped with three dots."""
    lines = kit.wrap_text(text, room, size, mono, kit.TRACK)
    if len(lines) <= cap:
        return kit.balance(lines) if not mono else lines
    return [*lines[: cap - 1], _clip(" ".join(lines[cap - 1 :]), room, size, mono)]


def _seconds(value: float) -> str:
    return f"{round(value / 1, 4):g}"


def _loop(
    attribute: str, points: list[tuple[float, str]], dur: float, extra: str = ""
) -> str:
    """A repeating animation through (seconds, value) points from 0 to dur."""
    values = ";".join(value for _, value in points)
    times = ";".join(f"{round(second / dur, 4):g}" for second, _ in points)
    tag = "animateTransform" if attribute == "transform" else "animate"
    kind = ' type="translate"' if attribute == "transform" else ""
    return (
        f'<{tag} attributeName="{attribute}"{kind} values="{values}" keyTimes="{times}"{extra} '
        f'dur="{dur:g}s" repeatCount="indefinite"/>'
    )


def _slots(count: int) -> tuple[float, float]:
    """(loop, slot) for a lit border that visits `count` items: 12 s when each gets 1.5 s or more."""
    loop = T if count * 1.5 <= T else 2 * T
    return loop, loop / max(count, 1)


def _stepper(offsets: list[tuple[float, float]]) -> str:
    """Walk the element these sit in through (dx, dy) offsets, one slot each, on the page clock.

    The element's own place is the first offset, so a still render shows the first item lit.
    A move along a row or a column slides; a move to a new row, and the wrap back to the
    first item, fades out, jumps and fades back in. A lone item has nowhere to go, so its
    border breathes on the 3 s beat instead and the card still moves.
    """
    count = len(offsets)
    if count < 2:
        return _loop("opacity", [(0.0, "1"), (1.5, "0.4"), (3.0, "1")], 3)
    loop, slot = _slots(count)
    moves, fades, splines = [(0.0, offsets[0])], [(0.0, "1")], []
    for index in range(1, count + 1):
        end = loop if index == count else index * slot
        before, after = offsets[index - 1], offsets[index % count]
        along = index < count and (before[0] == after[0] or before[1] == after[1])
        if along:
            moves += [(end - SLIDE, before), (end, after)]
            splines += ["0 0 1 1", "0.4 0 0.2 1"]
        else:
            moves += [(end - 0.2, before), (end - 0.19, after)]
            splines += ["0 0 1 1", "0 0 1 1"]
            fades += [
                (end - 0.35, "1"),
                (end - 0.2, "0"),
                (end - 0.15, "0"),
                (end, "1"),
            ]
    if moves[-1][0] < loop:
        moves.append((loop, moves[-1][1]))
        splines.append("0 0 1 1")
    if fades[-1][0] < loop:
        fades.append((loop, "1"))
    spline = f' calcMode="spline" keySplines="{";".join(splines)}"'
    out = _loop(
        "transform", [(t, f"{dx:g} {dy:g}") for t, (dx, dy) in moves], loop, spline
    )
    if len(fades) > 2:
        out += _loop("opacity", fades, loop)
    return out


def _lit(
    x: float, y: float, w: float, h: float, r: float = 10, animation: str = ""
) -> str:
    """The lit border: a blue tint under the item and an edge that reaches 3:1."""
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{r:g}" fill="{kit.BLUE_TINT}" '
        f'stroke="{kit.BLUE_EDGE}" stroke-width="1.5">{animation}</rect>'
    )


def _box(
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str = kit.CARD,
    stroke: str = kit.HAIR_STRONG,
    r: float = 10,
) -> str:
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{r:g}" fill="{fill}" stroke="{stroke}"/>'


def _with_attrs(svg: str, attrs: dict) -> str:
    """Put extra attributes on a card's root, for example data-active-certifications."""
    extra = "".join(f' {name}="{kit.esc(str(value))}"' for name, value in attrs.items())
    return svg.replace('role="img"', f'role="img"{extra}', 1)


def _stamp(ctx: dict, source: str) -> str:
    value = (ctx.get("updated") or {}).get(source)
    return f"UPDATED {str(value)[:10]}" if value else ""


def _starts(count: int, first: float = 0.1) -> list[float]:
    """Entrance times for blocks in reading order: STAGGER apart, all started by LAST_START."""
    return [min(first + index * STAGGER, LAST_START) for index in range(count)]


# ---------------------------------------------------------------- shared facts
def top_finishes(contests: list[dict]) -> list[dict]:
    """The contest results that name a place from 1st to 4th, in the portfolio's order."""
    return [entry for entry in contests if TOP_FINISH.match(entry.get("title", ""))]


def kick_start(contests: list[dict]) -> tuple[int, str, str] | None:
    """The best Kick Start result in the contest list as (rank, two-digit year, round)."""
    found = [
        (int(match.group(1)), match.group(2), match.group(3))
        for entry in contests
        if (match := KICK_START.search(entry.get("title", "")))
    ]
    return min(found) if found else None


def finish(entry: dict) -> dict:
    """A top finish split for the ledger: place, event, and the edition and host it was at.

    "1st Place - QFiesta, IGNOSI '22" is place 1ST, event QFiesta, edition IGNOSI '22. A
    title that names no year takes it from the date in the same '22 form, so every row says
    when, and says it the way the alt text does.
    """
    title = str(entry.get("title", ""))
    match = TOP_FINISH.match(title)
    place = match.group(1).upper() if match else ""
    rest = title[match.end() :] if match else title
    rest = rest.strip().removeprefix("-").strip()
    event, _, edition = rest.partition(", ")
    date = str(entry.get("date") or "")
    if date and not re.search("'[0-9]{2}", title):
        edition = f"{edition} '{date[-2:]}" if edition else f"'{date[-2:]}"
    return {
        "place": place,
        "event": event.strip() or title,
        "edition": edition.strip(),
        "host": str(entry.get("organizer") or "").strip(),
    }


def _since(contests: list[dict]) -> str:
    years = [
        int(y) for entry in contests for y in YEAR.findall(str(entry.get("date") or ""))
    ]
    return f"SINCE {min(years)}" if years else ""


def _platform_values(ctx: dict) -> tuple[str, str, str]:
    """LeetCode best contest rank, GeeksforGeeks solved and the HackerRank level, or the placeholder."""
    stats = ctx.get("coding_stats") or {}
    rank = (stats.get("leetcode") or {}).get("best_contest_rank")
    return (
        f"#{rank}" if rank else MISSING,
        _number((stats.get("geeksforgeeks") or {}).get("problems_solved")),
        _number((stats.get("hackerrank") or {}).get("problem_solving")),
    )


def _unrecorded(data: dict, ctx: dict) -> list[str]:
    """Certifications the snapshot lists with no usable expiry date: neither active nor lapsed."""
    certs = ctx["certs"]
    sorted_names = {c["name"] for c in (*certs["active"], *certs["lapsed"])}
    listed = (data.get("portfolio") or {}).get("certifications") or []
    return [
        c["name"] for c in listed if c.get("name") and c["name"] not in sorted_names
    ]


def _status_label(title: str, lines: list[str]) -> str:
    """The status card's alt text as sentences: the title, then each line, each ending in a full stop."""
    return ". ".join([title, *(line.rstrip(".") for line in lines)]) + "."


def _status_copy(data: dict, ctx: dict) -> tuple[str, list[str]]:
    """The certification status card's title and its lines, shared by both widths' labels."""
    certs = ctx["certs"]
    title = " ".join(
        part
        for part in (
            str(certs["active_count"]),
            "active",
            certs["issuer"],
            "certifications",
        )
        if part
    )
    lines = []
    if certs["active"]:
        lines.append(
            "Valid through: "
            + ", ".join(
                f"{c['name']} until {c['expires']}"
                for c in _soonest_first(certs["active"])
            )
        )
    lines += [
        f"Previously earned: {c['name']}. Expired {c['expired']}."
        for c in certs["lapsed"]
    ]
    lines.extend(f"Expiry not recorded: {name}." for name in _unrecorded(data, ctx))
    if len(lines) < 2:
        lines.append(
            "Active status is based on the recorded certification expiry dates."
        )
    lines.append(GALLERY_NOTE)
    return title, lines


# ---------------------------------------------------------------- tiles and place marks
def _competitive_tiles(ctx: dict) -> list[tuple[str, str, str]]:
    rank, geeks, hacker = _platform_values(ctx)
    tiles = [
        # the LeetCode rating and badge have their own card above; this tile adds the best rank
        ("LEETCODE", rank, "best contest rank"),
        ("GEEKSFORGEEKS", geeks, "problems solved"),
        ("HACKERRANK", hacker, "problem solving"),
    ]
    if best := kick_start(ctx.get("contests") or []):
        place, year, round_name = best
        tiles.append((f"KICK START '{year}", f"#{place}", f"round {round_name} rank"))
    return tiles


def _finish_titles(ctx: dict) -> list[str]:
    """Every top finish names its year; add it from the date where the title leaves it out."""
    return [
        entry["title"]
        if re.search("'[0-9]{2}", entry["title"]) or not entry.get("date")
        else f"{entry['title']} '{str(entry['date'])[-2:]}"
        for entry in top_finishes(ctx.get("contests") or [])
    ]


def _competitive_label(ctx: dict) -> str:
    facts = [f"{key} {value} {label}" for key, value, label in _competitive_tiles(ctx)]
    return "Competitive programming: " + "; ".join(facts + _finish_titles(ctx))


# A tile's rhythm from its top edge: (key baseline, numeral baseline, first label baseline,
# label pitch, padding under the last label). Without a key the numeral moves up.
TILE_DESKTOP = (24, 58, 78, 13, 16)
TILE_PHONE = (22, 50, 69, 14, 13)
UNKEYED = 20  # how far the numeral and label rise when a tile has no key
VALUE_FLOOR = 16  # the smallest a tile's numeral steps down to


def _tile_room(width: float, phone: bool) -> float:
    """The width a tile's label wraps to; the tracking after the last letter is not drawn."""
    return width - (24 if phone else 28) + kit.TRACK


def _tile(
    x: float,
    y: float,
    w: float,
    h: float,
    key: str,
    value: str,
    label: list[str],
    phone: bool,
    lit: str = "",
    need: float = 0,
) -> str:
    """A stat tile: the source on top, one numeral, a mono label, hung from the top so a row lines up.

    The LeetCode tile is amber and the others blue. `lit` ("blue" or "amber") tints the lead
    tile of a card. Height past `need` (what the row's tallest tile needs, this tile's own
    need by default) is shared above and below the numeral, the same in every tile of a row.
    """
    micro = kit.MICRO_PHONE if phone else kit.MICRO
    inset, size = (12, 22) if phone else (14, 26)
    # a long figure steps the numeral down rather than leave its tile
    while size > VALUE_FLOOR and kit.text_width(value, size) > w - 2 * inset:
        size -= 1
    key_y, value_y, label_y, pitch, _ = TILE_PHONE if phone else TILE_DESKTOP
    amber = key.startswith("LEETCODE") or lit == "amber"
    fill, stroke = (AMBER_TINT, AMBER_EDGE) if amber else (kit.CARD, kit.HAIR_STRONG)
    if lit == "blue":
        fill, stroke = kit.BLUE_TINT, kit.BLUE_EDGE
    rise = 0 if key else UNKEYED
    drop = max(0.0, (h - (need or _tile_height(len(label), phone, bool(key)))) / 2)
    out = [_box(x, y, w, h, fill, stroke)]
    if key:
        color = kit.AMBER if amber else kit.BLUE_LIGHT
        out.append(kit.text(x + inset, y + key_y, key, micro, color, "m"))
    out.append(
        kit.text(x + inset, y + value_y - rise + drop, value, size, kit.INK, "n")
    )
    for index, line in enumerate(label):
        line_y = y + label_y - rise + drop + index * pitch
        out.append(kit.text(x + inset, line_y, line, micro, kit.META, "m"))
    return "".join(out)


def _tile_height(label_lines: int, phone: bool, keyed: bool = True) -> float:
    """The least height a tile needs for its key, numeral and label lines."""
    _, _, label_y, pitch, foot = TILE_PHONE if phone else TILE_DESKTOP
    return label_y + (label_lines - 1) * pitch + foot - (0 if keyed else UNKEYED)


PLACE_STYLE = {
    "1ST": (kit.BLUE, kit.BLUE, kit.INK),
    "2ND": (kit.BLUE_TINT, kit.BLUE_EDGE, kit.BLUE_LIGHT),
}


def _place(x: float, cy: float, place: str, phone: bool) -> str:
    """The place as a mono pill: 1st filled blue, 2nd tinted, the rest outlined."""
    micro = kit.MICRO_PHONE if phone else kit.MICRO
    h = 20 if phone else 18
    w = _place_width(phone)
    fill, stroke, ink = PLACE_STYLE.get(
        place, (kit.HAIR_FILL, kit.HAIR_STRONG, kit.BODY)
    )
    return _box(x, cy - h / 2, w, h, fill, stroke, h / 2) + kit.text(
        x + w / 2, cy + micro * 0.36, place, micro, ink, "m", "middle"
    )


def _place_width(phone: bool) -> float:
    return _mono("4TH", kit.MICRO_PHONE if phone else kit.MICRO) + (18 if phone else 16)


def _tally(finishes: list[dict]) -> str:
    counts: dict[str, int] = {}
    for entry in finishes:
        counts[entry["place"]] = counts.get(entry["place"], 0) + 1
    return "  ".join(f"{count}X {place}" for place, count in counts.items())


def _ledger_rows(finishes: list[dict]) -> tuple[list[dict], int]:
    """The finishes a ledger lists, and how many it leaves to a +N more row."""
    if len(finishes) <= LEDGER_CAP:
        return finishes, 0
    return finishes[: LEDGER_CAP - 1], len(finishes) - LEDGER_CAP + 1


# ---------------------------------------------------------------- desktop: competitive
ROW, HEAD = 24, 34  # a ledger row's pitch, and the ledger panel's header band
PANEL_RADIUS = 12  # the ledger panel; stat tiles keep 10
EVENT_SHARE = (
    0.55  # the share of a ledger row its event keeps before its edition is cut
)


def _ledger(x: float, y: float, w: float, h: float, finishes: list[dict]) -> str:
    """The TOP FINISHES panel: a header with the tally, then one row a finish, a lit row stepping down."""
    shown, more = _ledger_rows(finishes)
    micro = kit.MICRO
    out = [_box(x, y, w, h, r=PANEL_RADIUS)]
    out.append(kit.text(x + 16, y + 22, "TOP FINISHES", micro, kit.BLUE_LIGHT, "m"))
    tally = _tally(finishes)
    if _mono(tally, micro) <= w - 48 - _mono("TOP FINISHES", micro):
        out.append(kit.text(x + w - 16, y + 22, tally, micro, kit.META, "m", "end"))
    out.append(f'<path d="M{x + 1:g} {y + HEAD:g}H{x + w - 1:g}" stroke="{kit.HAIR}"/>')
    top = y + HEAD + 4
    out.append(
        _lit(
            x + 6,
            top + 1,
            w - 12,
            ROW - 2,
            7,
            _stepper([(0, i * ROW) for i in range(len(shown))]),
        )
    )
    badge = _place_width(False)
    for index, entry in enumerate(shown):
        cy = top + index * ROW + ROW / 2
        left = x + 14
        right = x + w - 14
        out.append(_place(left, cy, entry["place"], False))
        text_x = left + badge + 12
        span = right - text_x
        # the event keeps its width up to EVENT_SHARE of the row: the edition and host give
        # way first, the host dropped, then the edition clipped
        keep = min(kit.text_width(entry["event"], 13), EVENT_SHARE * span)
        meta_room = span - keep - 16
        meta = f" {DOT} ".join(
            part.upper() for part in (entry["edition"], entry["host"]) if part
        )
        if _mono(meta, micro) > meta_room and entry["host"]:
            meta = entry["edition"].upper()
        meta = _clip(meta, meta_room + kit.TRACK, micro, True) if meta else ""
        room = span - (_mono(meta, micro) + 16 if meta else 0)
        if meta:
            out.append(
                kit.text(right, cy + micro * 0.36, meta, micro, kit.META, "m", "end")
            )
        out.append(
            kit.text(
                text_x, cy + 4.6, _clip(entry["event"], room, 13), 13, kit.INK, "s"
            )
        )
    if more:
        cy = top + len(shown) * ROW + ROW / 2
        out.append(
            kit.text(x + 14, cy + micro * 0.36, f"+{more} MORE", micro, kit.META, "m")
        )
    return "".join(out)


def competitive(ctx: dict) -> str:
    tiles = _competitive_tiles(ctx)
    contests = ctx.get("contests") or []
    finishes = [finish(entry) for entry in top_finishes(contests)]
    since = _since(contests)
    eyebrow = "COMPETITIVE PROGRAMMING" + (f"  |  {since}" if since else "")
    out = [kit.eyebrow(PAD, 30, eyebrow)]
    starts = _starts(len(tiles) + 1)
    if not finishes:
        # no ledger: the tiles share the card's width in one row
        tw = (W - 2 * PAD - GAP * (len(tiles) - 1)) / len(tiles)
        labels = [
            kit.wrap_text(
                label.upper(), _tile_room(tw, False), kit.MICRO, True, kit.TRACK
            )
            for *_, label in tiles
        ]
        th = max(_tile_height(len(lines), False) for lines in labels)
        for index, ((key, value, _), lines) in enumerate(zip(tiles, labels)):
            x = PAD + index * (tw + GAP)
            tile = _tile(x, TOP, tw, th, key, value, lines, False, need=th)
            out.append(kit.group(starts[index], tile))
        h = TOP + th + PAD
        return (
            kit.card_open(W, h, _competitive_label(ctx)) + "".join(out) + kit.SVG_CLOSE
        )
    # the tiles two by two on the left, the ledger on the right; both blocks share one height
    tw = 160
    columns = 2
    rows = math.ceil(len(tiles) / columns)
    widths = [
        2 * tw + GAP if index == len(tiles) - 1 and index % columns == 0 else tw
        for index in range(len(tiles))
    ]
    labels = [
        kit.wrap_text(
            label.upper(), _tile_room(width, False), kit.MICRO, True, kit.TRACK
        )
        for (*_, label), width in zip(tiles, widths)
    ]
    shown, more = _ledger_rows(finishes)
    panel = HEAD + 4 + (len(shown) + (1 if more else 0)) * ROW + 6
    need = max(_tile_height(len(lines), False) for lines in labels)
    block = max(panel, rows * need + (rows - 1) * GAP)
    th = (block - (rows - 1) * GAP) / rows
    for index, ((key, value, _), lines, width) in enumerate(zip(tiles, labels, widths)):
        x = PAD + (index % columns) * (tw + GAP)
        y = TOP + (index // columns) * (th + GAP)
        tile = _tile(x, y, width, th, key, value, lines, False, need=need)
        out.append(kit.group(starts[index], tile))
    px = PAD + columns * tw + GAP + 16
    out.append(kit.group(starts[-1], _ledger(px, TOP, W - PAD - px, block, finishes)))
    h = TOP + block + PAD
    return kit.card_open(W, h, _competitive_label(ctx)) + "".join(out) + kit.SVG_CLOSE


# ---------------------------------------------------------------- certifications: validity
def _today(ctx: dict) -> datetime.date:
    return datetime.date.fromisoformat(str(ctx["today"])[:10])


def _years_before(day: datetime.date, years: int) -> datetime.date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


def _validity(cert: dict, today: datetime.date, prefix: str) -> dict:
    """What a certification's cell shows: its name split from its level, and how much validity it has left.

    share is None, and the cell draws no ring, when the expiry is not an ISO date or the
    issuer's validity period is not known: the ring is never a guess.
    """
    name = str(cert.get("name") or "")
    short = name.removeprefix(prefix) if prefix else name
    level = ""
    if " - " in short:
        short, level = short.rsplit(" - ", 1)
    out = {
        "name": short,
        "level": level.upper(),
        "share": None,
        "left": "",
        "unit": "",
        "until": "",
    }
    try:
        expires = datetime.date.fromisoformat(str(cert.get("expires") or ""))
    except ValueError:
        return out
    out["until"] = f"{MONTHS[expires.month - 1]} {expires.year}"
    days = (expires - today).days
    months = (expires.year - today.year) * 12 + expires.month - today.month
    months -= 1 if expires.day < today.day else 0
    if months >= 1:
        out["left"], out["unit"] = str(months), "MO"
    else:
        out["left"], out["unit"] = str(max(days, 0)), "DAY" if days == 1 else "DAYS"
    years = VALIDITY_YEARS.get(cert_issuer(name))
    if years:
        span = (expires - _years_before(expires, years)).days
        out["share"] = max(0.0, min(1.0, days / span))
    return out


def _arc(cx: float, cy: float, r: float, share: float) -> str:
    """The ring's arc as a path, clockwise from 12 o'clock, for the light that runs it."""
    angle = 2 * math.pi * min(share, 0.999)
    ex, ey = cx + r * math.sin(angle), cy - r * math.cos(angle)
    return f"M{cx:g} {cy - r:g}A{r:g} {r:g} 0 {1 if share > 0.5 else 0} 1 {ex:.2f} {ey:.2f}"


def _gauge(cx: float, cy: float, r: float, cert: dict, at: float, phone: bool) -> str:
    """The validity ring with the time left inside it.

    When the share is unknown there is no ring, only a hairline circle; with no expiry at
    all the circle holds the placeholder rather than a guessed time.
    """
    micro = kit.MICRO_PHONE if phone else kit.MICRO
    out = []
    if cert["share"] is not None:
        out.append(kit.ring(cx, cy, r, cert["share"], kit.BLUE_EDGE, at, 0.9, 3.5))
    else:
        out.append(
            f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" stroke="{kit.HAIR}" stroke-width="1"/>'
        )
    if cert["left"]:
        # on a phone the unit sits a pixel higher, where the ring is wide enough for DAYS
        lift = 1 if phone else 0
        out.append(
            kit.text(cx, cy + 2 - lift, cert["left"], 15, kit.INK, "n", "middle")
        )
        out.append(
            kit.text(cx, cy + 13 - lift, cert["unit"], micro, kit.META, "m", "middle")
        )
    else:
        out.append(kit.text(cx, cy + 5, MISSING, 15, kit.META, "n", "middle"))
    return "".join(out)


def _ring_lights(
    rings: list[tuple[float, float, float, float]], first: float = 1.6
) -> str:
    """A short light runs each ring's arc in turn, so the shares are read one by one on the 12 s clock."""
    out = []
    lit = [ring for ring in rings if ring[3] >= 0.04]
    for index, (cx, cy, r, share) in enumerate(lit):
        begin = first + index * T / max(len(lit), 1)
        length = 2 * math.pi * r * share
        out.append(_light(_arc(cx, cy, r, share), length, round(begin, 2)))
    return "".join(out)


def _light(
    d: str,
    length: float,
    begin: float,
    travel: float = 0.14,
    color: str = kit.INK,
    width: float = 4,
    dash: float = 34,
    dur: float = T,
) -> str:
    """A short light that runs path d (`length` px long) once a loop from `begin`, then rests hidden.

    kit.beam parks its dash exactly on the path's ends, where a round cap still paints a
    dot; this light parks a cap's width past either end, as projects.py's beam does.
    `dash` is the light's share of the path in hundredths.
    """
    margin = 100 * (width / 2 + 1) / max(length, 1)
    rest, gone = dash + margin, -(100 + margin)
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}" stroke-linecap="round" '
        f'pathLength="100" stroke-dasharray="{dash:g} {100 + dash + 2 * margin:.1f}" stroke-dashoffset="{rest:.1f}">'
        f'<animate attributeName="stroke-dashoffset" values="{rest:.1f};{gone:.1f};{gone:.1f}" '
        f'keyTimes="0;{travel:g};1" dur="{dur:g}s" begin="{begin:g}s" repeatCount="indefinite"/></path>'
    )


def _prefix(ctx: dict) -> str:
    """The issuer's words a cell can drop because the eyebrow says them."""
    return "AWS Certified " if ctx["certs"].get("issuer") == "AWS" else ""


def _soonest_first(certs: list[dict]) -> list[dict]:
    """The active certifications by expiry, soonest first, so the first cell is the next
    expiry the eyebrow names; one with no recorded date goes last, ties keep their order."""
    return sorted(
        certs,
        key=lambda c: (
            not YEAR.match(str(c.get("expires") or "")),
            str(c.get("expires") or ""),
        ),
    )


def _next_expiry(certs: list[dict]) -> str:
    """The month the first active certification expires, as JUL 2027, or empty."""
    dates = sorted(
        str(c.get("expires") or "")
        for c in certs
        if YEAR.match(str(c.get("expires") or ""))
    )
    if not dates:
        return ""
    year, month = dates[0][:4], int(dates[0][5:7])
    return f"{MONTHS[month - 1]} {year}"


def _active_mark(right: float, y: float, count: int, size: float) -> str:
    """The one green on the card: a live dot and the active count, right-aligned at y.

    With nothing active there is nothing live, so the count is a grey caption.
    """
    label = f"{count} ACTIVE"
    if not count:
        return kit.text(right, y, label, size, kit.META, "m", "end")
    width = _mono(label, size)
    return kit.live_dot(right - width - 12, y - size * 0.36, kit.GREEN, 3.5) + kit.text(
        right, y, label, size, kit.GREEN, "m", "end"
    )


def _mark_width(count: int, size: float) -> float:
    """How much of a row the active mark takes, its dot included."""
    return _mono(f"{count} ACTIVE", size) + (12 + 3.5 if count else 0)


def _others(data: dict, ctx: dict) -> list[tuple[str, str, str]]:
    """The caption entries: (micro label, name, mono detail) for each lapsed or unrecorded certification."""
    rows = [
        ("PREVIOUSLY EARNED", c["name"], f"EXPIRED {c['expired']}")
        for c in ctx["certs"]["lapsed"]
    ]
    rows += [("EXPIRY NOT RECORDED", name, "") for name in _unrecorded(data, ctx)]
    return rows


# ---------------------------------------------------------------- desktop: certification status
CELL_COLUMNS = 5
RING = 22  # a validity ring's radius, at both widths


def certs_status(data: dict, ctx: dict) -> str:
    certs = ctx["certs"]
    today = _today(ctx)
    prefix = _prefix(ctx)
    cells = [_validity(cert, today, prefix) for cert in _soonest_first(certs["active"])]
    issuer = certs.get("issuer") or ""
    head = " ".join(part for part in (issuer, "CERTIFIED") if part)
    parts = [head, "VALIDITY LEFT"] + (
        [f"NEXT EXPIRY {n}"] if (n := _next_expiry(certs["active"])) else []
    )
    out = [
        kit.eyebrow(PAD, 30, "  |  ".join(parts)),
        _active_mark(W - PAD, 30, certs["active_count"], kit.MICRO),
    ]

    # rows as even as the count allows (6 as 3 + 3, 7 as 4 + 3), the short row centred
    rows = max(1, math.ceil(len(cells) / CELL_COLUMNS))
    columns = max(1, math.ceil(len(cells) / rows))
    cw = min(256, (W - 2 * PAD - GAP * (columns - 1)) / columns)
    room = cw - 28
    # kit measures sans text wide on purpose; a 600-weight name sets at about SANS_FIT of it,
    # so the wrap uses the set width and "Machine Learning" keeps to one line
    names = [_lines(cell["name"], room / SANS_FIT, 13.5, 3) for cell in cells]
    tallest = max((len(lines) for lines in names), default=1)
    leveled = any(cell["level"] for cell in cells)
    # the name hangs under the ring; the level sits on the cell's foot, level with its neighbours'
    ch = 14 + 44 + 16 + tallest * 17 + (18 if leveled else 0) + 10
    rings, y = [], TOP
    starts = _starts(len(cells) + 1)
    short = rows * columns - len(cells)  # empty places in the last row
    for index, (cell, lines) in enumerate(zip(cells, names)):
        row = index // columns
        shift = short * (cw + GAP) / 2 if row == rows - 1 else 0
        x = PAD + shift + (index % columns) * (cw + GAP)
        y = TOP + row * (ch + GAP)
        cx, cy = x + 14 + RING, y + 14 + RING
        body = [
            _box(x, y, cw, ch),
            _gauge(cx, cy, RING, cell, starts[index] + 0.2, False),
        ]
        body.append(kit.text(x + 72, y + 32, "EXPIRES", kit.MICRO, kit.META, "m"))
        until = cell["until"] or MISSING
        body.append(kit.text(x + 72, y + 50, until, 13, kit.INK, "c"))
        for line_index, line in enumerate(lines):
            body.append(
                kit.text(x + 14, y + 88 + line_index * 17, line, 13.5, kit.INK, "s")
            )
        if cell["level"]:
            body.append(
                kit.text(x + 14, y + ch - 14, cell["level"], kit.MICRO, kit.META, "m")
            )
        out.append(kit.group(starts[index], "".join(body)))
        if cell["share"] is not None:
            rings.append((cx, cy, RING, cell["share"]))
    if not cells:
        out.append(
            kit.text(
                PAD, TOP + 22, "No active certification on record.", 14, kit.BODY, "b"
            )
        )
        bottom = TOP + 30
    else:
        bottom = TOP + rows * (ch + GAP) - GAP
    out.append(_ring_lights(rings))

    # one caption line per lapsed or unrecorded certification, the names in one column
    y = bottom
    captions = []
    others = _others(data, ctx)
    x = PAD + max((_mono(label, kit.MICRO) for label, *_ in others), default=0) + 16
    for label, name, detail in others:
        y += 30
        line = [kit.text(PAD, y, label, kit.MICRO, kit.META, "m")]
        tail = _mono(detail, kit.MICRO) + 12 if detail else 0
        line.append(
            kit.text(x, y, _clip(name, W - PAD - x - tail, 13), 13, kit.BODY, "b")
        )
        if detail:
            line.append(kit.text(W - PAD, y, detail, kit.MICRO, kit.META, "m", "end"))
        captions.append("".join(line))
    if captions:
        divider = f'<path d="M{PAD} {bottom + 12:g}H{W - PAD}" stroke="{kit.HAIR}"/>'
        out.append(kit.group(starts[-1], divider + "".join(captions)))
        y += 6
    h = math.ceil(y + PAD)
    title, lines = _status_copy(data, ctx)
    svg = (
        kit.card_open(W, h, _status_label(title, lines)) + "".join(out) + kit.SVG_CLOSE
    )
    # validate-readme.py reads the count off the root and checks it against the snapshot
    return _with_attrs(svg, {"data-active-certifications": certs["active_count"]})


# ---------------------------------------------------------------- phone helpers
def _eyebrow(label: str, fill: str = kit.BLUE_LIGHT) -> str:
    """kit.eyebrow at the phone's mono floor: the line of data a phone card opens with."""
    return kit.text(PHONE_PAD, 30, label.upper(), kit.MICRO_PHONE, fill, "m")


def _phone_card(
    h: float, label: str, blocks: list[str], defs: str = "", attrs: dict | None = None
) -> str:
    svg = (
        kit.card_open(PHONE, math.ceil(h), label, defs)
        + "".join(blocks)
        + kit.SVG_CLOSE
    )
    return _with_attrs(svg, attrs) if attrs else svg


def _phone_tiles(
    items: list[tuple[str, str, str]],
    y: float,
    starts: list[float],
    lit: str = "",
) -> tuple[list[str], float]:
    """Tiles two to a row as (key, value, label): no word splits, a row as tall as its tallest label.

    `lit` tints the first tile, the card's lead figure. Returns (blocks, the y under the last row).
    """
    tw = (COLUMN - 10) / 2
    labels = [
        kit.wrap_text(
            label.upper(), _tile_room(tw, True), kit.MICRO_PHONE, True, kit.TRACK
        )
        for *_, label in items
    ]
    out = []
    for row in range(0, len(items), 2):
        pair = list(range(row, min(row + 2, len(items))))
        keyed = any(items[i][0] for i in pair)
        th = max(_tile_height(len(labels[i]), True, keyed) for i in pair)
        for i in pair:
            x = PHONE_PAD + (i % 2) * (tw + 10)
            key, value, _ = items[i]
            tile = _tile(
                x, y, tw, th, key, value, labels[i], True, lit if i == 0 else "", th
            )
            out.append(kit.group(starts[i], tile))
        y += th + 10
    return out, y - 10


def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _legible(color: str) -> str:
    """Lift a language's colour towards white, a tenth at a time, until it reaches 3:1 on the card."""
    floor = _luminance(kit.BG) + 0.05
    channels = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    mixed = color
    for step in range(11):
        mixed = "#" + "".join(
            f"{round(c + (255 - c) * step / 10):02x}" for c in channels
        )
        if (_luminance(mixed) + 0.05) / floor >= 3:
            break
    return mixed


# ---------------------------------------------------------------- phone: github
def _level(count: int, cuts: list[int]) -> int:
    return 0 if count == 0 else 1 + sum(1 for cut in cuts if count > cut)


PITCH, CELL = 14, 11  # the heatmap's column pitch and cell size


def _heatmap(weeks: list[list[int]], top: float) -> tuple[str, str, str, float]:
    """Recent contribution weeks: (the clip that reveals them, the cells, the loop over them, height).

    The cells are revealed left to right by one clip that slides in, so the whole window is
    one animated element and rests whole. The loop is a scan column that rests on this week,
    then steps across the window week by week from the oldest, and a ripple on the busiest
    day every 2 s.
    """
    counts = sorted(count for week in weeks for count in week if count)
    cuts = [counts[len(counts) * q // 4] for q in (1, 2, 3)] if counts else []
    height = 6 * PITCH + CELL
    wide = (len(weeks) - 1) * PITCH + CELL
    clip = (
        f'<clipPath id="weeks"><rect x="{PHONE_PAD}" y="{top:g}" width="{wide}" height="{height}">'
        f'<animateTransform attributeName="transform" type="translate" '
        f'values="-{wide} 0;-{wide} 0;0 0" {kit.held(0.3, 0.9)}/></rect></clipPath>'
    )
    cells = (
        '<g clip-path="url(#weeks)">'
        + "".join(
            f'<rect x="{PHONE_PAD + column * PITCH}" y="{top + row * PITCH:g}" width="{CELL}" height="{CELL}" '
            f'rx="2" fill="{HEAT[_level(count, cuts)]}"/>'
            for column, week in enumerate(weeks)
            for row, count in enumerate(week)
        )
        + "</g>"
    )
    last = len(weeks) - 1
    motion = ""
    if last > 0:
        # rests on this week, sweeps from the oldest at 2.4 s, one week a step, home by 11 s
        step = min(0.45, 8.6 / last)
        points = [(0.0, "0 0")] + [
            (2.4 + column * step, f"{(column - last) * PITCH:g} 0")
            for column in range(last + 1)
        ]
        scan = _loop("transform", points, T, ' calcMode="discrete"')
        # outlines are paths that start on their top edge, which runs in the gap above the
        # cells, so the outline is drawn (and measured) on the card, not on a cell
        outline = kit.rounded_rect_path(
            PHONE_PAD + last * PITCH - 2.5, top - 2.5, CELL + 5, height + 5, 4
        )
        motion += (
            f'<path d="{outline}" fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="1.5">'
            f"{scan}</path>"
        )
    if counts:
        # the busiest day: the latest one when two tie
        _, column, row = max(
            (count, column, row)
            for column, week in enumerate(weeks)
            for row, count in enumerate(week)
        )
        cx, cy = PHONE_PAD + column * PITCH + CELL / 2, top + row * PITCH + CELL / 2
        ring = kit.rounded_rect_path(-7, -7, 14, 14, 3)
        motion += (
            f'<g transform="translate({cx:g} {cy:g})"><path d="{ring}" fill="none" '
            f'stroke="{HEAT[-1]}" stroke-width="1.5">'
            '<animateTransform attributeName="transform" type="scale" values="1;1.9" dur="2s" repeatCount="indefinite"/>'
            '<animate attributeName="opacity" values="0.9;0" dur="2s" repeatCount="indefinite"/></path></g>'
        )
    return clip, cells, motion, height


def _language_bar(
    languages: list[list], top: float, at: float
) -> tuple[str, str, float]:
    """GitHub's stacked language bar, revealed left to right, with a legend: (defs, svg, height)."""
    total = sum(percent for _, percent, _ in languages) or 1
    colors = [
        _legible(color) if HEX_COLOR.fullmatch(color or "") else kit.META
        for *_, color in languages
    ]
    labels = [f"{name} {percent:g}%" for name, percent, _ in languages]
    x, segments = float(PHONE_PAD), []
    for (_, percent, _), color in zip(languages, colors):
        width = COLUMN * percent / total
        segments.append(
            f'<rect x="{x:.1f}" y="{top:g}" width="{width:.1f}" height="8" fill="{color}"/>'
        )
        x += width
    # two legend columns while every entry fits its own; one long name
    # (Jupyter Notebook) and the legend takes a single column instead of overlapping
    half = COLUMN / 2
    columns = (
        2 if all(kit.text_width(label, 13) <= half - 15 - 8 for label in labels) else 1
    )
    # the clip slides in from the left, so the bar is whole at rest
    defs = (
        f'<clipPath id="langs"><rect x="{PHONE_PAD}" y="{top:g}" width="{COLUMN}" height="8" rx="4">'
        f'<animateTransform attributeName="transform" type="translate" '
        f'values="-{COLUMN} 0;-{COLUMN} 0;0 0" {kit.held(at, 1)}/></rect></clipPath>'
    )
    out = [f'<g clip-path="url(#langs)">{"".join(segments)}</g>']
    for index, (label, color) in enumerate(zip(labels, colors)):
        lx = PHONE_PAD + (index % columns) * half
        ly = top + 30 + (index // columns) * 22
        out.append(f'<circle cx="{lx + 5:g}" cy="{ly - 4.5:g}" r="4" fill="{color}"/>')
        out.append(kit.text(lx + 15, ly, label, 13, kit.BODY, "b"))
    return defs, "".join(out), 30 + (math.ceil(len(languages) / columns) - 1) * 22


def github_mobile(ctx: dict) -> str:
    github = ctx.get("github") or {}
    tiles = [(_number(github.get(key)), label) for key, label in GITHUB_TILES]
    followers = github.get("followers")
    stars = f" {DOT} ".join(
        part
        for part in (
            f"{_number(github['stars'])} total stars" if github.get("stars") else "",
            f"{_number(followers)} followers" if followers else "",
        )
        if part
    )
    label = (
        "GitHub activity, past 12 months: "
        + ", ".join(f"{value} {name.lower()}" for value, name in tiles)
        + (f". {stars}" if stars else "")
    )
    blocks = [_eyebrow("GitHub  |  Past 12 months")]
    starts = _starts(len(tiles) + 4)
    tile_blocks, y = _phone_tiles(
        [("", value, name) for value, name in tiles], 44, starts, "blue"
    )
    blocks += tile_blocks
    defs = ""
    calendar = github.get("calendar") or []
    if calendar:
        y += 30
        weeks = calendar[-WEEKS:]
        clip, cells, motion, height = _heatmap(weeks, y + 12)
        defs += clip
        blocks.append(
            kit.group(
                starts[len(tiles)],
                kit.text(
                    PHONE_PAD,
                    y,
                    f"LAST {len(weeks)} WEEKS",
                    kit.MICRO_PHONE,
                    kit.BLUE_LIGHT,
                    "m",
                )
                + kit.text(
                    PHONE - PHONE_PAD,
                    y,
                    "THIS WEEK",
                    kit.MICRO_PHONE,
                    kit.META,
                    "m",
                    "end",
                ),
            )
        )
        # the scan and the ripple arrive once the cells are in
        blocks.append(cells + kit.group(1.2, motion, ""))
        y += 12 + height
    if stars:
        y += 28
        blocks.append(
            kit.group(
                starts[len(tiles) + 1],
                kit.text(PHONE_PAD, y, stars, 13.5, kit.BODY, "b"),
            )
        )
    languages = github.get("languages") or []
    if languages:
        y += 34
        at = starts[len(tiles) + 2]
        lang_defs, legend, height = _language_bar(languages, y + 12, at)
        defs += lang_defs
        blocks.append(
            kit.group(
                at,
                kit.text(
                    PHONE_PAD, y, "TOP LANGUAGES", kit.MICRO_PHONE, kit.BLUE_LIGHT, "m"
                )
                + legend,
            )
        )
        y += 12 + height
    stamp = _stamp(ctx, "github")
    if stamp:
        y += 30
        blocks.append(
            kit.group(
                starts[-1],
                kit.text(PHONE_PAD, y, stamp, kit.MICRO_PHONE, kit.META, "m"),
            )
        )
    return _phone_card(y + PHONE_PAD, label, blocks, defs)


# ---------------------------------------------------------------- phone: leetcode
def _years(ctx: dict) -> tuple[str, str]:
    history = ((ctx.get("coding_stats") or {}).get("leetcode") or {}).get(
        "rating_history"
    ) or []
    years = [YEAR.match(str(point[0])) for point in history if point]
    years = [match.group(0) for match in years if match]
    return (years[0], years[-1]) if years else ("", "")


def _rating_chart(
    history: list[float], top: float, years: tuple[str, str], at: float
) -> tuple[str, float]:
    """The contest rating line, drawn in, with a light running it every 6 s and the latest point pulsing."""
    low, high = min(history), max(history)
    left, right = PHONE_PAD + 40, PHONE - PHONE_PAD - 6
    upper, lower = top + 8, top + 104
    out = []
    for value, y in ((high, upper), (low, lower)):
        out.append(
            kit.text(
                PHONE_PAD, y + 4, str(round(value)), kit.MICRO_PHONE, kit.META, "c"
            )
        )
        out.append(f'<path d="M{left} {y:g}H{right}" stroke="{kit.HAIR_STRONG}"/>')
    points = [
        (
            left + index * (right - left) / (len(history) - 1),
            lower - (value - low) / max(high - low, 1) * (lower - upper),
        )
        for index, value in enumerate(history)
    ]
    path = "".join(
        f"{'M' if index == 0 else 'L'}{x:.1f} {y:.1f}"
        for index, (x, y) in enumerate(points)
    )
    out.append(
        kit.draw(
            path,
            at,
            0.9,
            kit.AMBER,
            2,
            ' stroke-linejoin="round" stroke-linecap="round"',
        )
    )
    # the climb, retraced: a light runs the line in 3 s of every 6, from 2 s
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    out.append(_light(path, length, 2, 0.5, AMBER_LIGHT, 3, 8, 6))
    x, y = points[-1]
    out.append(
        f"<g>{kit.enter(at + 0.9, 0.3)}{kit.live_dot(round(x, 1), round(y, 1), kit.AMBER, 3)}</g>"
    )
    height = lower - top
    first, last = years
    if first:
        height += 22
        out.append(kit.text(left, top + height, first, kit.MICRO_PHONE, kit.META, "m"))
        if last and last != first:
            out.append(
                kit.text(
                    right, top + height, last, kit.MICRO_PHONE, kit.META, "m", "end"
                )
            )
    return "".join(out), height


def leetcode_mobile(ctx: dict) -> str:
    leetcode = ctx.get("leetcode") or {}
    heading = f"LeetCode {DOT} {leetcode.get('badge', '')}".rstrip(f" {DOT}")
    tiles = [
        (_number(leetcode.get("rating")), "Contest rating"),
        (
            f"{leetcode['top']}%" if leetcode.get("top") is not None else MISSING,
            "Top worldwide",
        ),
        (_number(leetcode.get("solved")), "Problems solved"),
        (_number(leetcode.get("contests")), "Contests"),
    ]
    label = (
        heading.replace(f" {DOT}", "")
        + ": "
        + ", ".join(f"{value} {name.lower()}" for value, name in tiles)
    )
    badge = leetcode.get("badge")
    eyebrow = "LEETCODE" + (f"  |  {badge}" if badge else "")
    blocks = [_eyebrow(eyebrow, kit.AMBER)]
    starts = _starts(len(tiles) + 4)
    tile_blocks, y = _phone_tiles(
        [("", value, name) for value, name in tiles], 44, starts, "amber"
    )
    blocks += tile_blocks
    difficulty = leetcode.get("by_difficulty") or {}
    rows = []
    for label_, (solved, total) in difficulty.items():
        y += 26
        fill = COLUMN * min(solved / total, 1) if total else 0
        rows.append(
            kit.text(PHONE_PAD, y, label_.upper(), kit.MICRO_PHONE, kit.AMBER, "m")
            + kit.text(
                PHONE - PHONE_PAD,
                y,
                f"{solved:,} / {total:,}",
                12.5,
                kit.BODY,
                "c",
                "end",
            )
            + f'<rect x="{PHONE_PAD}" y="{y + 8:g}" width="{COLUMN}" height="6" rx="3" fill="{kit.HAIR_STRONG}"/>'
            # the bar grows from its left end; at rest it is its full length
            + f'<g transform="translate({PHONE_PAD} {y + 8:g})"><rect width="{fill:.1f}" height="6" rx="3" fill="{kit.AMBER}">'
            + '<animateTransform attributeName="transform" type="scale" values="0 1;0 1;1 1" '
            + f"{kit.held(starts[len(tiles)] + 0.2, 0.9)}/></rect></g>"
        )
        y += 12
    if rows:
        blocks.append(kit.group(starts[len(tiles)], "".join(rows)))
    history = leetcode.get("history") or []
    if len(history) >= 2:
        y += 34
        at = starts[len(tiles) + 1]
        years = _years(ctx)
        chart, height = _rating_chart(history, y + 8, years, at + 0.2)
        # the climb from the first rated contest to the latest, which the tiles do not say
        climb = f"{round(history[-1] - history[0]):+,}" + (
            f" SINCE {years[0]}" if years[0] else ""
        )
        blocks.append(
            kit.group(
                at,
                kit.text(
                    PHONE_PAD, y, "CONTEST RATING", kit.MICRO_PHONE, kit.AMBER, "m"
                )
                + kit.text(
                    PHONE - PHONE_PAD, y, climb, kit.MICRO_PHONE, kit.META, "m", "end"
                )
                + chart,
            )
        )
        y += 8 + height
    stamp = _stamp(ctx, "leetcode")
    if stamp:
        y += 30
        blocks.append(
            kit.group(
                starts[-1],
                kit.text(PHONE_PAD, y, stamp, kit.MICRO_PHONE, kit.META, "m"),
            )
        )
    return _phone_card(y + PHONE_PAD, label, blocks)


# ---------------------------------------------------------------- phone: certifications
def _normal_name(name: str) -> str:
    return " ".join(DASHES.sub("-", name).split()).casefold()


def _badges(
    badges: list[dict],
    x0: float,
    y: float,
    columns: int,
    size: float,
    gap: float,
    starts: list[float],
    center_last: bool,
) -> tuple[list[str], list[tuple[float, float]], float]:
    """Badge images in a grid, a row entering together: (blocks, each badge's top left, height used)."""
    cell = (COLUMN - gap * (columns - 1)) / columns
    blocks, places = [], []
    rows = math.ceil(len(badges) / columns)
    for row in range(rows):
        chunk = badges[row * columns : (row + 1) * columns]
        shift = (columns - len(chunk)) * (cell + gap) / 2 if center_last else 0
        body = []
        for column, badge in enumerate(chunk):
            x = x0 + shift + column * (cell + gap)
            places.append((x, y))
            title = (
                f"<title>{kit.esc(badge['name'])}</title>" if badge.get("name") else ""
            )
            inset = (cell - size) / 2
            body.append(
                f'<g>{title}<image href="{badge["image"]}" x="{x + inset:.1f}" y="{y + inset:.1f}" '
                f'width="{size:g}" height="{size:g}"/></g>'
            )
        blocks.append(kit.group(starts[min(row, len(starts) - 1)], "".join(body)))
        y += cell + gap
    return blocks, places, rows * (cell + gap) - gap


def _certification_list(
    data: dict, ctx: dict, badges: list[dict], y: float
) -> tuple[list[str], float]:
    """Certifications by status, then the other badges by name, when no badge images are known."""
    certs = ctx["certs"]
    groups = [
        (
            "Active certifications",
            [(c["name"], f"Valid through {c['expires']}") for c in certs["active"]],
        ),
        (
            "Previously earned",
            [(c["name"], f"Expired {c['expired']}") for c in certs["lapsed"]],
        ),
        ("Expiry not recorded", [(name, "") for name in _unrecorded(data, ctx)]),
    ]
    known = {_normal_name(name) for _, entries in groups for name, _ in entries}
    names = list(
        dict.fromkeys(
            badge["name"]
            for badge in badges
            if badge.get("name") and _normal_name(badge["name"]) not in known
        )
    )
    if names:
        groups.append(
            ("Professional and training badges", [(name, "") for name in names])
        )
    blocks, at = [], 0.1
    for heading, entries in groups:
        if not entries:
            continue
        y += 26
        body = [
            kit.text(
                PHONE_PAD, y, heading.upper(), kit.MICRO_PHONE, kit.BLUE_LIGHT, "m"
            )
        ]
        y += 4
        for name, detail in entries:
            for line in _lines(name, COLUMN, 13.5, 2):
                y += 19
                body.append(kit.text(PHONE_PAD, y, line, 13.5, kit.INK, "s"))
            if detail:
                y += 17
                body.append(
                    kit.text(
                        PHONE_PAD, y, detail.upper(), kit.MICRO_PHONE, kit.META, "m"
                    )
                )
            y += 6
        blocks.append(kit.group(at, "".join(body)))
        at = min(at + STAGGER, LAST_START)
    return blocks, y


def certs_mobile(data: dict, ctx: dict) -> str:
    gallery = ctx.get("badges") or []
    # a retired badge is not a current credential, so the grid leaves it out; the counts
    # still take every badge, so they agree with the Credly gallery on the desktop page
    badges = [b for b in gallery if not RETIRED.search(b.get("name") or "")]
    images = [badge for badge in gallery if badge.get("image")]
    names = [badge["name"] for badge in images if badge.get("name")]
    label = "Certifications and professional badges"
    if names:
        label = f"{len(images)} Credly badges: " + ", ".join(names)
    if not images:
        blocks, y = _certification_list(data, ctx, badges, 30)
        return _phone_card(
            y + PHONE_PAD,
            label,
            [_eyebrow("Certifications"), *blocks],
        )
    active = {_normal_name(c["name"]) for c in ctx["certs"]["active"]}
    certified = [b for b in images if _normal_name(b.get("name") or "") in active]
    learning = [b for b in images if b not in certified]
    rest = sorted(
        (b for b in learning if not RETIRED.search(b.get("name") or "")),
        key=_relevance,
    )
    # the certifications take the image budget first, in whole rows; with certifications on
    # the card the learning and partner badges get one row, the most relevant first
    shown = _within_budget(certified, IMAGE_BUDGET, CERT_ROW)
    picked = _within_budget(
        rest[:BADGE_ROW] if certified else rest,
        IMAGE_BUDGET - _image_bytes(shown),
        BADGE_ROW,
    )
    blocks = [_eyebrow(f"{len(images)} Credly badges")]
    starts = _starts(8, 0.15)
    rows = math.ceil(len(shown) / CERT_ROW)
    y = 30
    if shown:
        y += 26
        blocks.append(
            kit.text(
                PHONE_PAD,
                y,
                f"{len(certified)} INDUSTRY CERTIFICATIONS",
                kit.MICRO_PHONE,
                kit.META,
                "m",
            )
        )
        y += 12
        gap = 10
        cell = (COLUMN - gap * (CERT_ROW - 1)) / CERT_ROW
        images_, places, height = _badges(
            shown, PHONE_PAD, y, CERT_ROW, 64, gap, starts, True
        )
        # each certification on a tile, and the lit border visiting them in turn; the tile
        # holds an image, not text, so its fill is the faint hair fill, not a solid panel
        tiles = "".join(_box(x, top, cell, cell, kit.HAIR_FILL) for x, top in places)
        x0, y0 = places[0]
        offsets = [(x - x0, top - y0) for x, top in places]
        lit = _lit(x0, y0, cell, cell, 10, _stepper(offsets))
        blocks.append(kit.group(starts[0], tiles + lit))
        blocks += images_
        y += height
    if len(shown) < len(certified):
        what = "MORE CERTIFICATIONS" if shown else "CERTIFICATIONS"
        note, y = _credly_note(
            f"+{len(certified) - len(shown)} {what}", y, starts[rows]
        )
        blocks.append(note)
    kind = "LEARNING AND PARTNER BADGES" if certified else "BADGES"
    if picked:
        y += 30
        heading = f"{len(learning)} {kind}"
        blocks.append(kit.text(PHONE_PAD, y, heading, kit.MICRO_PHONE, kit.META, "m"))
        y += 10
        images_, places, height = _badges(
            picked, PHONE_PAD, y, BADGE_ROW, 46, 2, starts[rows + 1 :], False
        )
        if not shown:
            # no certification row to light, so the lit border walks these badges
            cell = (COLUMN - 2 * (BADGE_ROW - 1)) / BADGE_ROW
            x0, y0 = places[0]
            offsets = [(x - x0, top - y0) for x, top in places]
            lit = _lit(x0, y0, cell, cell, 10, _stepper(offsets))
            blocks.append(kit.group(starts[rows + 1], lit))
        blocks += images_
        y += height
        kind = "MORE"
    if len(picked) < len(learning):
        note, y = _credly_note(f"+{len(learning) - len(picked)} {kind}", y, starts[-1])
        blocks.append(note)
    return _phone_card(y + PHONE_PAD, label, blocks)


def _credly_note(count: str, y: float, at: float) -> tuple[str, float]:
    """What the grid has no room for, counted and found on Credly: (block, the y under it)."""
    lines = kit.balance(
        kit.wrap_text(f"{count} ON CREDLY", COLUMN, kit.MICRO_PHONE, True, kit.TRACK)
    )
    body = []
    y += 12
    for line in lines:
        y += 16
        body.append(kit.text(PHONE_PAD, y, line, kit.MICRO_PHONE, kit.META, "m"))
    return kit.group(at, "".join(body)), y


def _relevance(badge: dict) -> int:
    """A badge's place in RELEVANT: the first pattern its name matches, or after them all."""
    name = badge.get("name") or ""
    return next(
        (rank for rank, pattern in enumerate(RELEVANT) if pattern.search(name)),
        len(RELEVANT),
    )


def _image_bytes(badges: list[dict]) -> int:
    return sum(len(badge.get("image") or "") for badge in badges)


def _within_budget(badges: list[dict], budget: int, row: int) -> list[dict]:
    """The badges, in order, whose images fit the byte budget, cut back to whole rows of `row`."""
    shown, used = [], 0
    for badge in badges:
        used += len(badge.get("image") or "")
        if used > budget:
            break
        shown.append(badge)
    if len(shown) < len(badges):
        shown = shown[: len(shown) - len(shown) % row]
    return shown


# ---------------------------------------------------------------- phone: competitive
PHONE_ROW = 46  # a phone ledger row: the event, then its edition and host


def competitive_mobile(ctx: dict) -> str:
    tiles = _competitive_tiles(ctx)
    contests = ctx.get("contests") or []
    finishes = [finish(entry) for entry in top_finishes(contests)]
    since = _since(contests)
    eyebrow = "COMPETITIVE PROGRAMMING"
    if since and _mono(f"{eyebrow}  |  {since}", kit.MICRO_PHONE) <= COLUMN:
        eyebrow += f"  |  {since}"
    blocks = [_eyebrow(eyebrow)]
    starts = _starts(len(tiles) + 2)
    tile_blocks, y = _phone_tiles(tiles, 44, starts)
    blocks += tile_blocks
    if finishes:
        shown, more = _ledger_rows(finishes)
        y += 30
        head = kit.text(
            PHONE_PAD, y, "TOP FINISHES", kit.MICRO_PHONE, kit.BLUE_LIGHT, "m"
        )
        tally = _tally(finishes)
        if (
            _mono(tally, kit.MICRO_PHONE)
            <= COLUMN - _mono("TOP FINISHES", kit.MICRO_PHONE) - 16
        ):
            head += kit.text(
                PHONE - PHONE_PAD, y, tally, kit.MICRO_PHONE, kit.META, "m", "end"
            )
        y += 8
        text_x = PHONE_PAD + 8 + _place_width(True) + 12
        room = PHONE - PHONE_PAD - 10 - text_x
        rows, top = [], y
        # one event line and one mono line a row, so every row is one height and the lit
        # border fits each of them; a long name ends in three dots, a long line drops the host
        for entry in shown:
            meta = f" {DOT} ".join(
                part.upper() for part in (entry["edition"], entry["host"]) if part
            )
            if _mono(meta, kit.MICRO_PHONE) > room:
                meta = entry["edition"].upper()
            rows.append(
                _place(PHONE_PAD + 8, y + 16, entry["place"], True)
                + kit.text(
                    text_x, y + 20, _clip(entry["event"], room, 14), 14, kit.INK, "s"
                )
                + kit.text(
                    text_x,
                    y + 36,
                    _clip(meta, room, kit.MICRO_PHONE, True),
                    kit.MICRO_PHONE,
                    kit.META,
                    "m",
                )
            )
            y += PHONE_ROW
        offsets = [(0, index * PHONE_ROW) for index in range(len(shown))]
        lit = _lit(PHONE_PAD, top + 1, COLUMN, PHONE_ROW - 2, 8, _stepper(offsets))
        if more:
            y += 18
            rows.append(
                kit.text(
                    PHONE_PAD + 6, y, f"+{more} MORE", kit.MICRO_PHONE, kit.META, "m"
                )
            )
        blocks.append(kit.group(starts[-1], head + lit + "".join(rows)))
    return _phone_card(y + PHONE_PAD, _competitive_label(ctx), blocks)


# ---------------------------------------------------------------- phone: certification status
def certs_status_mobile(data: dict, ctx: dict) -> str:
    certs = ctx["certs"]
    today = _today(ctx)
    cells = [
        _validity(cert, today, _prefix(ctx)) for cert in _soonest_first(certs["active"])
    ]
    issuer = certs.get("issuer") or ""
    head = " ".join(part for part in (issuer, "CERTIFIED") if part)
    # the issuer and the active mark on the first line, what the rings say on the second
    blocks = [
        _eyebrow(head),
        _active_mark(PHONE - PHONE_PAD, 30, certs["active_count"], kit.MICRO_PHONE),
    ]
    # the second line always says what the rings show, and when the first one runs out
    # where it fits; "NEXT EXPIRY JUL 2027" beside it is a few pixels past a phone column
    nxt = _next_expiry(certs["active"])
    options = [f"NEXT EXPIRY {nxt}", f"NEXT {nxt}"] if nxt else []
    second = next(
        (
            line
            for line in (f"VALIDITY LEFT | {option}" for option in options)
            if _mono(line, kit.MICRO_PHONE) <= COLUMN
        ),
        "VALIDITY LEFT",
    )
    y = 52
    blocks.append(kit.text(PHONE_PAD, y, second, kit.MICRO_PHONE, kit.META, "m"))
    y += 14
    starts = _starts(len(cells) + 2)
    rings = []
    # the ring is the desktop's size, 9px inside its row, so DAYS fits inside it; the
    # text keeps 10px clear of the row's right edge
    text_x = PHONE_PAD + 64
    room = PHONE - PHONE_PAD - 10 - text_x
    for index, cell in enumerate(cells):
        names = _lines(cell["name"], room, 14, 2)
        until = f"UNTIL {cell['until']}" if cell["until"] else "EXPIRY NOT RECORDED"
        meta = f" {DOT} ".join(part for part in (cell["level"], until) if part)
        if _mono(meta, kit.MICRO_PHONE) > room:
            # a long level keeps the date and drops the word before it
            meta = f" {DOT} ".join(
                part for part in (cell["level"], cell["until"]) if part
            )
            meta = _clip(meta, room, kit.MICRO_PHONE, True)
        lines = len(names) * 18 + (17 if meta else 0)
        rh = max(64, lines + 28)
        cx, cy = PHONE_PAD + 31, y + rh / 2
        body = [
            _box(PHONE_PAD, y, COLUMN, rh),
            _gauge(cx, cy, RING, cell, starts[index] + 0.2, True),
        ]
        line_y = y + (rh - lines) / 2 + 13
        for line in names:
            body.append(kit.text(text_x, line_y, line, 14, kit.INK, "s"))
            line_y += 18
        if meta:
            body.append(
                kit.text(text_x, line_y + 1, meta, kit.MICRO_PHONE, kit.META, "m")
            )
        blocks.append(kit.group(starts[index], "".join(body)))
        if cell["share"] is not None:
            rings.append((cx, cy, RING, cell["share"]))
        y += rh + 8
    if not cells:
        y += 20
        blocks.append(
            kit.text(
                PHONE_PAD, y, "No active certification on record.", 14, kit.BODY, "b"
            )
        )
        y += 8
    blocks.append(_ring_lights(rings))
    others = _others(data, ctx)
    if others:
        body = []
        y += 18
        for label, name, detail in others:
            body.append(kit.text(PHONE_PAD, y, label, kit.MICRO_PHONE, kit.META, "m"))
            for line in _lines(name, COLUMN, 13.5, 2):
                y += 20
                body.append(kit.text(PHONE_PAD, y, line, 13.5, kit.BODY, "b"))
            if detail:
                y += 18
                body.append(
                    kit.text(PHONE_PAD, y, detail, kit.MICRO_PHONE, kit.META, "m")
                )
            y += 26
        y -= 26
        blocks.append(kit.group(starts[-1], "".join(body)))
    else:
        y -= 8
    title, lines = _status_copy(data, ctx)
    return _phone_card(
        y + PHONE_PAD,
        _status_label(title, lines),
        blocks,
        attrs={"data-active-certifications": certs["active_count"]},
    )


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for every file this module owns, desktop and -mobile."""
    return {
        "competitive.svg": competitive(ctx),
        "competitive-mobile.svg": competitive_mobile(ctx),
        "certs-status.svg": certs_status(data, ctx),
        "certs-status-mobile.svg": certs_status_mobile(data, ctx),
        "github-mobile.svg": github_mobile(ctx),
        "leetcode-mobile.svg": leetcode_mobile(ctx),
        "certs-mobile.svg": certs_mobile(data, ctx),
    }
