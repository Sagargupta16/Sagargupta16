"""Coding stats and certification status: competitive, certs-status, and the phone twins of the vendored cards."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# A current-look port: the drawing moved here from render-svgs.py and mobile_cards.py
# unchanged in layout, on kit's palette and clock and the Card phone engine.
# github.svg, leetcode.svg and certs.svg are drawn by his actions; this module
# draws their 320px twins from the same snapshot.
from __future__ import annotations

import math
import re

import kit
from mobile_cards import CONTENT_WIDTH, MICRO, PAD, WIDTH, Card, text_width

MISSING = "-"
DOT = chr(0xB7)  # the middle dot the phone cards join two facts with
RED = "#f87171"  # LeetCode's Hard bar; the kit has no red because nothing else may use one
# An empty day, then four levels of the blue family; the brightest is a tint the kit
# does not carry. Every level reaches 3:1 on the card.
HEAT = (kit.HAIR_STRONG, kit.BLUE, kit.BLUE_EDGE, kit.BLUE_LIGHT, "#93c5fd")
HEX_COLOR = re.compile("#[0-9a-fA-F]{6}")
BADGE_COLUMNS, BADGE_SIZE = 4, 56
# Credly keeps a badge after its course is withdrawn and marks the name.
RETIRED = re.compile("retired", re.IGNORECASE)
# The list under TOP FINISHES: it includes a 4th place, so it is not called a podium.
TOP_FINISH = re.compile("(1st|2nd|3rd|4th) Place")
KICK_START = re.compile(
    "Rank ([0-9]+) - Google Kick Start '([0-9]{2}), Round ([A-Za-z0-9]+)"
)
DASHES = re.compile(f"[{chr(0x2013)}{chr(0x2014)}]")
GALLERY_NOTE = "The Credly gallery below also includes learning and partner badges."
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


def _number(value: object) -> str:
    if value is None or value == "":
        return MISSING
    return f"{value:,}" if isinstance(value, int) else str(value)


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
    lines = [
        f"Previously earned: {c['name']}. Expired {c['expired']}."
        for c in certs["lapsed"]
    ]
    lines.extend(f"Expiry not recorded: {name}." for name in _unrecorded(data, ctx))
    if not lines:
        lines = ["Active status is based on the recorded certification expiry dates."]
    lines.append(GALLERY_NOTE)
    return title, lines


# ---------------------------------------------------------------- desktop: competitive
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


def _chip_rows(
    labels: list[str], top: float, width: float
) -> list[tuple[float, float, str]]:
    """Place mono chips left to right from x=24, wrapping into as many rows as they need."""
    placed, x, y = [], 24.0, top
    for label in labels:
        chip = kit.chip_width(label)
        if x > 24 and x + chip > width - 24:
            x, y = 24.0, y + 32
        placed.append((x, y, label))
        x += chip + 8
    return placed


def competitive(ctx: dict) -> str:
    tiles = _competitive_tiles(ctx)
    w = 840
    # the chips wrap into as many rows as they need; the card grows to fit
    placed = _chip_rows(
        [
            title.replace(" Place - ", "  ").replace(", ", " ").upper()
            for title in _finish_titles(ctx)
        ],
        134,
        w,
    )
    h = placed[-1][1] + 44 if placed else 134
    tile_width = (w - 32 - (len(tiles) - 1) * 10) / len(tiles)
    parts = [
        kit.svg_open(w, h, _competitive_label(ctx)),
        kit.style(),
        kit.frame(w, h),
        kit.eyebrow(24, 30, "Competitive programming", kit.AMBER),
    ]
    for index, (key, value, label) in enumerate(tiles):
        x = 16 + index * (tile_width + 10)
        parts.append(
            f"<g>{kit.enter(0.1 + index * 0.1)}"
            f'<rect x="{x:.1f}" y="44" width="{tile_width:.1f}" height="72" rx="10" '
            f'fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
            + kit.text(x + 14, 64, key, kit.MICRO, kit.AMBER, "m")
            + kit.text(x + 14, 90, value, 20, kit.INK, "n")
            + kit.text(x + 14, 107, label.upper(), kit.MICRO, kit.META, "m")
            + "</g>"
        )
    for index, (x, y, label) in enumerate(placed):
        chip, _ = kit.chip(
            x,
            y,
            label,
            kit.BODY,
            height=24,
            fill=f"{kit.AMBER}12",
            stroke=f"{kit.AMBER}44",
        )
        parts.append(f"<g>{kit.enter(0.5 + index * 0.06)}{chip}</g>")
    return "".join(parts) + kit.SVG_CLOSE


# ---------------------------------------------------------------- desktop: certification status
def _sans(
    x: float, y: float, content: str, size: float, fill: str, weight: int = 0
) -> str:
    """Text with its font on the element, as the note card has always drawn it."""
    bold = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{x:g}" y="{y:g}" fill="{fill}" font-family="{kit.SANS}" '
        f'font-size="{size:g}"{bold}>{kit.esc(content)}</text>'
    )


def _note(
    title: str, lines: list[str], attrs: str = "", accent: str = kit.BLUE_LIGHT
) -> str:
    """A wrapped status card whose lines fade in one after another."""
    width = 840
    wrapped = [line for text in lines for line in kit.wrap_text(text, width - 40, 14)]
    title_lines = kit.wrap_text(title, width - 40, 20)
    start = 28 + len(title_lines) * 25
    height = start + len(wrapped) * 23 + 18
    parts = [
        kit.svg_open(width, height, _status_label(title, lines)).replace(
            'role="img"', f'role="img"{attrs}', 1
        ),
        kit.frame(width, height),
        f'<rect x="0" y="16" width="3" height="22" rx="1.5" fill="{accent}">'
        + kit.loop("opacity", "1;0.4;1", "0;0.5;1", 3)
        + "</rect>",
    ]
    for index, text in enumerate(title_lines):
        parts.append(
            f"<g>{kit.enter(0.15 + index * 0.1)}"
            f"{_sans(20, 32 + index * 25, text, 20, accent, 700)}</g>"
        )
    for index, text in enumerate(wrapped):
        parts.append(
            f"<g>{kit.enter(0.15 + (len(title_lines) + index) * 0.1)}"
            f"{_sans(20, start + index * 23, text, 14, kit.BODY)}</g>"
        )
    return "".join(parts) + kit.SVG_CLOSE


def certs_status(data: dict, ctx: dict) -> str:
    title, lines = _status_copy(data, ctx)
    # validate-readme.py reads the count off the root and checks it against the snapshot
    count = ctx["certs"]["active_count"]
    return _note(title, lines, f' data-active-certifications="{count}"')


# ---------------------------------------------------------------- phone helpers
def _updated(card: Card, ctx: dict, source: str) -> None:
    value = (ctx.get("updated") or {}).get(source)
    if value:
        card.y += 4
        card.lines(
            f"UPDATED {str(value)[:10]}",
            size=MICRO,
            color=kit.META,
            weight=700,
            mono=True,
        )


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


def _heatmap(card: Card, weeks: list[list[int]]) -> None:
    """Draw recent contribution weeks that fill in column by column."""
    counts = sorted(count for week in weeks for count in week if count)
    cuts = [counts[len(counts) * q // 4] for q in (1, 2, 3)] if counts else []
    step, top = 14, card.y
    with card.block():
        for column, week in enumerate(weeks):
            cells = "".join(
                f'<rect x="{PAD + column * step}" y="{top + row * step:g}" width="10" height="10" '
                f'rx="2" fill="{HEAT[_level(count, cuts)]}"/>'
                for row, count in enumerate(week)
            )
            card.parts.append(
                f"<g>{kit.enter(card.begin + column * 0.03, 0.3)}{cells}</g>"
            )
    card.y = top + 7 * step + 10


def _language_bar(card: Card, languages: list[list]) -> None:
    """Draw GitHub's stacked language bar, revealed left to right, with a legend."""
    total = sum(percent for _, percent, _ in languages) or 1
    colors = [
        _legible(color) if HEX_COLOR.fullmatch(color or "") else kit.META
        for *_, color in languages
    ]
    labels = [f"{name} {percent:g}%" for name, percent, _ in languages]
    top, x = card.y, float(PAD)
    segments = []
    for (_, percent, _), color in zip(languages, colors):
        width = CONTENT_WIDTH * percent / total
        segments.append(
            f'<rect x="{x:.1f}" y="{top:g}" width="{width:.1f}" height="8" fill="{color}"/>'
        )
        x += width
    # two legend columns while every entry fits its own; one long name
    # (Jupyter Notebook) and the legend takes a single column instead of overlapping
    half = CONTENT_WIDTH / 2
    columns = (
        2 if all(text_width(label, 13) <= half - 15 - 8 for label in labels) else 1
    )
    with card.block():
        card.parts.append(
            # the clip slides in from the left, so the bar is whole at rest
            f'<clipPath id="langs"><rect x="{PAD}" y="{top:g}" width="{CONTENT_WIDTH}" height="8" rx="4">'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="-{CONTENT_WIDTH} 0;-{CONTENT_WIDTH} 0;0 0" {kit.held(card.begin, 1)}/>'
            f'</rect></clipPath><g clip-path="url(#langs)">{"".join(segments)}</g>'
        )
        for index, (label, color) in enumerate(zip(labels, colors)):
            lx = PAD + (index % columns) * half
            ly = top + 28 + (index // columns) * 22
            card.parts.append(
                f'<circle cx="{lx + 5:g}" cy="{ly - 4:g}" r="4" fill="{color}"/>'
            )
            card.lines(label, x=lx + 15, y=ly - 13, size=13, color=kit.BODY)
    card.y = top + 28 + math.ceil(len(languages) / columns) * 22


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
    card = Card(
        "GitHub activity, past 12 months: "
        + ", ".join(f"{value} {label.lower()}" for value, label in tiles)
        + (f". {stars}" if stars else "")
    )
    with card.block():
        card.label("GitHub activity")
        card.label("Past 12 months", kit.META)
    card.metrics(tiles)
    calendar = github.get("calendar") or []
    if calendar:
        card.label("Last 20 weeks")
        _heatmap(card, calendar[-20:])
    if stars:
        card.lines(stars, size=13, color=kit.BODY)
        card.y += 14
    languages = github.get("languages") or []
    if languages:
        card.label("Top languages")
        _language_bar(card, languages)
    _updated(card, ctx, "github")
    return card.finish()


# ---------------------------------------------------------------- phone: leetcode
def _rating_chart(card: Card, history: list[float]) -> None:
    if len(history) < 2:
        return
    card.label("Contest rating history", kit.AMBER)
    low, high = min(history), max(history)
    left, right = PAD + 40, WIDTH - PAD - 6
    top, bottom = card.y + 6, card.y + 112
    with card.block():
        for value, y in ((high, top), (low, bottom)):
            card.lines(
                str(round(value)),
                y=y + 4 - MICRO,
                size=MICRO,
                color=kit.META,
                weight=700,
                mono=True,
            )
            card.parts.append(
                f'<path d="M{left} {y:g}H{right}" stroke="{kit.HAIR_STRONG}"/>'
            )
        points = [
            (
                left + index * (right - left) / (len(history) - 1),
                bottom - (value - low) / max(high - low, 1) * (bottom - top),
            )
            for index, value in enumerate(history)
        ]
        path = " ".join(
            f"{'M' if index == 0 else 'L'}{x:.2f} {y:.2f}"
            for index, (x, y) in enumerate(points)
        )
        card.parts.append(
            kit.draw(path, card.begin, 0.8, kit.AMBER, 2, ' stroke-linejoin="round"')
        )
        x, y = points[-1]
        # the end point arrives with the line, then keeps pulsing
        card.parts.append(
            f"<g>{kit.enter(card.begin + 0.8, 0.3)}"
            f"{kit.live_dot(round(x, 2), round(y, 2), kit.AMBER, 3)}</g>"
        )
    card.y = bottom + 14
    card.lines(
        f"Peak {round(high):,} {DOT} {len(history)} rated contests",
        size=13,
        color=kit.BODY,
    )


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
    card = Card(
        heading.replace(f" {DOT}", "")
        + ": "
        + ", ".join(f"{value} {label.lower()}" for value, label in tiles),
        kit.AMBER,
    )
    card.label(heading)
    card.metrics(tiles)
    colors = {"Easy": kit.GREEN, "Medium": kit.AMBER, "Hard": RED}
    for label, (solved, total) in (leetcode.get("by_difficulty") or {}).items():
        with card.block():
            card.lines(f"{label} {DOT} {solved:,} / {total:,}", size=13, color=kit.BODY)
            card.y += 2
            fill = CONTENT_WIDTH * min(solved / total, 1) if total else 0
            card.parts.append(
                f'<rect x="{PAD}" y="{card.y:g}" width="{CONTENT_WIDTH}" height="6" rx="3" '
                f'fill="{kit.HAIR_STRONG}"/>'
                # the bar grows from its left end; at rest it is its full length
                f'<g transform="translate({PAD} {card.y:g})"><rect width="{fill:.1f}" height="6" '
                f'rx="3" fill="{colors.get(label, kit.BLUE_LIGHT)}">'
                f'<animateTransform attributeName="transform" type="scale" values="0 1;0 1;1 1" '
                f"{kit.held(card.begin, 0.9)}/></rect></g>"
            )
            card.y += 16
    card.y += 6
    _rating_chart(card, leetcode.get("history") or [])
    _updated(card, ctx, "leetcode")
    return card.finish()


# ---------------------------------------------------------------- phone: certifications
def _normal_name(name: str) -> str:
    return " ".join(DASHES.sub("-", name).split()).casefold()


def _badge_grid(card: Card, badges: list[dict]) -> None:
    """Lay the Credly badge images out in a grid; a row enters together and each badge floats."""
    cell = CONTENT_WIDTH / BADGE_COLUMNS
    for start in range(0, len(badges), BADGE_COLUMNS):
        with card.block():
            for column, badge in enumerate(badges[start : start + BADGE_COLUMNS]):
                x = PAD + column * cell + (cell - BADGE_SIZE) / 2
                title = (
                    f"<title>{kit.esc(badge['name'])}</title>"
                    if badge.get("name")
                    else ""
                )
                card.parts.append(
                    f"<g>{title}"
                    '<animateTransform attributeName="transform" type="translate" values="0 0;0 -3;0 0" '
                    f'dur="4s" begin="{(start + column) * 0.2:.1f}s" repeatCount="indefinite"/>'
                    f'<image href="{badge["image"]}" x="{x:.1f}" y="{card.y:g}" width="{BADGE_SIZE}" '
                    f'height="{BADGE_SIZE}"/></g>'
                )
        card.y += BADGE_SIZE + 12


def _certification_list(card: Card, data: dict, ctx: dict, badges: list[dict]) -> None:
    """List certifications by status, then the other badges, when no images are known."""
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
        (
            "Expiry not recorded",
            [(name, "Expiry not recorded") for name in _unrecorded(data, ctx)],
        ),
    ]
    for label, entries in groups:
        if not entries:
            continue
        if card.y > PAD:
            card.divider()
        card.label(label)
        for name, detail in entries:
            card.row(name, metadata=detail, size=14)
    known = {_normal_name(name) for _, entries in groups for name, _ in entries}
    names = list(
        dict.fromkeys(
            badge["name"]
            for badge in badges
            if badge.get("name") and _normal_name(badge["name"]) not in known
        )
    )
    if names:
        card.divider()
        card.label("Professional & training badges")
        card.chips(names, size=12.5, mono=False, color=kit.INK)


def certs_mobile(data: dict, ctx: dict) -> str:
    # a retired badge is not a current credential, so the grid leaves it out
    badges = [
        badge
        for badge in ctx.get("badges") or []
        if not RETIRED.search(badge.get("name") or "")
    ]
    images = [badge for badge in badges if badge.get("image")]
    names = [badge["name"] for badge in images if badge.get("name")]
    label = "Certifications and professional badges"
    if names:
        label = f"{len(images)} Credly badges: " + ", ".join(names)
    card = Card(label, kit.SKY)
    if images:
        card.label(f"{len(images)} Credly badges")
        _badge_grid(card, images)
    else:
        _certification_list(card, data, ctx, badges)
    return card.finish()


# ---------------------------------------------------------------- phone: competitive, status
def competitive_mobile(ctx: dict) -> str:
    rank, geeks, hacker = _platform_values(ctx)
    tiles = [
        (rank, "LeetCode best rank"),
        (geeks, "GeeksforGeeks solved"),
        (hacker, "HackerRank problem solving"),
    ]
    contests = ctx.get("contests") or []
    if best := kick_start(contests):
        place, year, round_name = best
        tiles.append((f"#{place}", f"Kick Start 20{year} Round {round_name}"))
    card = Card(_competitive_label(ctx), kit.AMBER)
    card.label("Competitive programming")
    card.metrics(tiles)
    finishes = top_finishes(contests)
    if finishes:
        card.label("Top finishes")
        for entry in finishes:
            card.row(
                entry["title"],
                metadata=f" {DOT} ".join(
                    part for part in (entry.get("date"), entry.get("organizer")) if part
                ),
                size=14,
            )
    return card.finish()


def certs_status_mobile(data: dict, ctx: dict) -> str:
    certs = ctx["certs"]
    title, lines = _status_copy(data, ctx)
    unrecorded = _unrecorded(data, ctx)
    card = Card(_status_label(title, lines), kit.SKY)
    card.label("Certification status")
    card.metrics(
        [
            (str(certs["active_count"]), "Active certifications"),
            (
                str(len(certs["lapsed"]) + len(unrecorded)),
                "Expired or unrecorded" if unrecorded else "Previously earned",
            ),
        ]
    )
    for cert in certs["lapsed"]:
        card.row(cert["name"], metadata=f"Expired {cert['expired']}", size=14)
    for name in unrecorded:
        card.row(name, metadata="Expiry not recorded", size=14)
    card.lines(GALLERY_NOTE, size=12.5, color=kit.BODY)
    return card.finish(attrs={"data-active-certifications": certs["active_count"]})


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
