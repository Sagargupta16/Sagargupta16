"""Render a self-hosted, animated GitHub stats card into one SVG file.

Runs as the composite action defined in action.yml, or standalone:

    GITHUB_TOKEN=<token> INPUT_USERNAME=<user> python github_stats_card.py

A README serves the card through an <img>, so the SVG is fully self-contained:
no scripts, no external fonts or images, CSS and SMIL animation only. Standard
library only, so the action has nothing to install.
"""

from __future__ import annotations

import colorsys
import http.client
import json
import os
import re
import urllib.request
from dataclasses import dataclass, replace
from html import escape
from pathlib import Path
from typing import NoReturn

# Palette of the profile card this design comes from: warm near-black, one
# blue family, green only for the live streak.
BG = "#0b1012"
CARD = "#0f171c"
BLUE = "#2563eb"
BLUE_LIGHT = "#60a5fa"
GREEN = "#22c55e"
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
SANS = "'Segoe UI',Inter,-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"
SVG_CLOSE = "</svg>"

DEFAULT_OUTPUT = "assets/github-stats.svg"
DEFAULT_LANGUAGES = "6"
# Lightness of BLUE relative to BLUE_LIGHT; reused to derive the deep shade of
# any other accent.
DEEP_LIGHTNESS = 0.79
# WCAG 2.2 minimum contrast on the card: 4.5:1 for small text (1.4.3), 3:1 for
# graphics such as calendar cells and language swatches (1.4.11).
TEXT_MIN = 4.5
GRAPHIC_MIN = 3.0
# Empty calendar days: a faint tint that reads as texture, not as data.
EMPTY_DAY = "rgba(255,255,255,0.05)"
UNKNOWN_LANGUAGE_COLOR = "#8b949e"
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
# On a light card the pale levels are the quiet ones, so the busiest calendar
# level is held to 7:1 (WCAG AAA) to leave visible steps above the 3:1 floor.
LIGHT_PEAK_MIN = 7.0
# The compact layout shows the most recent half year of the calendar.
COMPACT_WEEKS = 26
LAYOUTS = ("wide", "compact")


@dataclass(frozen=True)
class Theme:
    """Colors of one card theme. Hex text colors are held to TEXT_MIN on bg and
    card when the card is drawn, so a preset can use its palette's own colors."""

    bg: str
    card: str
    border: str
    tile_border: str
    text: str
    muted: str
    legend: str
    streak: str
    empty: str
    accent: str


# Borders and empty days are rgba tints of the text color: decorative texture,
# exempt from the contrast floors. Every other color is held to them on render.
THEMES = {
    "dark": Theme(
        bg=BG,
        card=CARD,
        border="rgba(255,255,255,0.08)",
        tile_border="rgba(255,255,255,0.07)",
        text="#f3f4f6",
        muted="rgba(255,255,255,0.5)",
        legend="rgba(255,255,255,0.75)",
        streak=GREEN,
        empty=EMPTY_DAY,
        accent=BLUE_LIGHT,
    ),
    # GitHub's dark dimmed palette
    "dim": Theme(
        bg="#22272e",
        card="#2d333b",
        border="rgba(205,217,229,0.14)",
        tile_border="rgba(205,217,229,0.1)",
        text="#cdd9e5",
        muted="#909dab",
        legend="#adbac7",
        streak="#57ab5a",
        empty="rgba(205,217,229,0.07)",
        accent="#539bf5",
    ),
    # GitHub's light palette
    "light": Theme(
        bg="#ffffff",
        card="#f6f8fa",
        border="rgba(31,35,40,0.15)",
        tile_border="rgba(31,35,40,0.1)",
        text="#1f2328",
        muted="#59636e",
        legend="#424a53",
        streak="#1a7f37",
        empty="rgba(31,35,40,0.07)",
        accent="#0969da",
    ),
    "dracula": Theme(
        bg="#282a36",
        card="#2f3241",
        border="rgba(248,248,242,0.12)",
        tile_border="rgba(248,248,242,0.08)",
        text="#f8f8f2",
        muted="#6272a4",
        legend="#e2e2dc",
        streak="#50fa7b",
        empty="rgba(248,248,242,0.06)",
        accent="#bd93f9",
    ),
    "nord": Theme(
        bg="#2e3440",
        card="#3b4252",
        border="rgba(236,239,244,0.12)",
        tile_border="rgba(236,239,244,0.08)",
        text="#eceff4",
        muted="#4c566a",
        legend="#d8dee9",
        streak="#a3be8c",
        empty="rgba(236,239,244,0.06)",
        accent="#88c0d0",
    ),
    "solarized-light": Theme(
        bg="#fdf6e3",
        card="#eee8d5",
        border="rgba(7,54,66,0.15)",
        tile_border="rgba(7,54,66,0.1)",
        text="#073642",
        muted="#657b83",
        legend="#586e75",
        streak="#859900",
        empty="rgba(7,54,66,0.07)",
        accent="#268bd2",
    ),
}
DARK = THEMES["dark"]

GRAPHQL_URL = "https://api.github.com/graphql"
ALLOWED_HOSTS = ("https://api.github.com/",)

# Public, non-fork repositories the user owns, 100 per page.
REPOS = (
    "repositories(ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC,first:100,after:$cursor)"
    "{pageInfo{hasNextPage endCursor} nodes{name stargazerCount "
    "languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}"
)
QUERY_HEAD = "query($login:String!,$cursor:String){user(login:$login){"
STATS_QUERY = (
    QUERY_HEAD
    + "followers{totalCount} "
    + REPOS
    + " contributionsCollection{totalCommitContributions totalPullRequestContributions "
    "contributionCalendar{totalContributions weeks{contributionDays{contributionCount}}}}}}"
)
REPOS_QUERY = QUERY_HEAD + REPOS + "}}"


def fetch(url: str, body: dict, token: str, timeout: int = 20) -> bytes:
    # https only, and only the host this script reads from
    if not url.startswith(ALLOWED_HOSTS):
        raise ValueError(f"refusing to fetch {url}")
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "github-stats-card-action",
        },
    )
    # scheme and host were checked against ALLOWED_HOSTS above
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return resp.read()


def query_user(query: str, login: str, token: str, cursor: str | None = None) -> dict:
    """Run one GraphQL query rooted at user(login:) and return that user."""
    variables = {"login": login, "cursor": cursor}
    reply = json.loads(
        fetch(GRAPHQL_URL, {"query": query, "variables": variables}, token)
    )
    if reply.get("errors"):
        raise ValueError("; ".join(str(e.get("message", e)) for e in reply["errors"]))
    return reply["data"]["user"]


def streaks(days: list[int]) -> tuple[int, int]:
    """Current and longest run of days with at least one contribution."""
    longest = run = 0
    for count in days:
        run = run + 1 if count else 0
        longest = max(longest, run)
    current = 0
    # today may still be empty; a streak is only broken by an empty yesterday
    tail = days[:-1] if days and days[-1] == 0 else days
    for count in reversed(tail):
        if not count:
            break
        current += 1
    return current, longest


def fetch_stats(login: str, token: str, top: int, exclude: set[str]) -> dict:
    user = query_user(STATS_QUERY, login, token)
    page = user["repositories"]
    repos = list(page["nodes"])
    while page["pageInfo"]["hasNextPage"]:
        cursor = page["pageInfo"]["endCursor"]
        page = query_user(REPOS_QUERY, login, token, cursor)["repositories"]
        repos += page["nodes"]
    repos = [r for r in repos if r["name"].lower() not in exclude]

    langs: dict[str, list] = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            color = edge["node"]["color"]
            if not HEX_COLOR.fullmatch(color or ""):
                color = UNKNOWN_LANGUAGE_COLOR
            entry = langs.setdefault(edge["node"]["name"], [0, color])
            entry[0] += edge["size"]
    ranked = sorted(langs.items(), key=lambda kv: -kv[1][0])[:top]
    total = sum(size for size, _ in langs.values()) or 1

    cc = user["contributionsCollection"]
    calendar = [
        [day["contributionCount"] for day in week["contributionDays"]]
        for week in cc["contributionCalendar"]["weeks"]
    ]
    days = [count for week in calendar for count in week]
    current, longest = streaks(days)
    return {
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "prs": cc["totalPullRequestContributions"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "repo_stars": {r["name"]: r["stargazerCount"] for r in repos},
        "followers": user["followers"]["totalCount"],
        "streak": current,
        "longest": longest,
        "active_days": sum(1 for count in days if count),
        "calendar": calendar,
        "languages": [
            [name, round(size * 100 / total, 1), color]
            for name, (size, color) in ranked
        ],
    }


def level(count: int, cuts: list[int]) -> int:
    return 0 if count == 0 else 1 + sum(1 for c in cuts if count > c)


def channels(color: str) -> tuple[int, int, int]:
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return r, g, b


def luminance(color: str) -> float:
    """WCAG 2.2 relative luminance of a #rrggbb color, 0 (black) to 1 (white)."""

    def linear(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(v) for v in channels(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(color: str, bg: str = BG) -> float:
    """WCAG 2.2 contrast ratio of two #rrggbb colors, 1 to 21."""
    a, b = luminance(color), luminance(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def hls_hex(hue: float, lightness: float, saturation: float) -> str:
    rgb = colorsys.hls_to_rgb(hue, min(max(lightness, 0.0), 1.0), saturation)
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb)


def is_dark(bg: str) -> bool:
    """True when white contrasts more with bg than black does."""
    return contrast("#ffffff", bg) >= contrast("#000000", bg)


def ensure_contrast(color: str, minimum: float, bg: str = BG) -> str:
    """color when it reaches minimum:1 on bg, else the nearest shade of the same
    hue that does: lighter on a dark card, darker on a light one. Every preset
    background is close enough to black or white that the far end (white or
    black) always passes."""
    if contrast(color, bg) >= minimum:
        return color
    hue, lightness, saturation = colorsys.rgb_to_hls(
        *(v / 255 for v in channels(color))
    )
    sign = 1 if is_dark(bg) else -1
    shades = (
        hls_hex(hue, lightness + sign * step / 1000, saturation)
        for step in range(1, 1001)
    )
    return next(shade for shade in shades if contrast(shade, bg) >= minimum)


def readable(color: str, theme: Theme) -> str:
    """A text color held to TEXT_MIN on both the card background and the tiles it
    sits on; the dark theme's rgba tints pass as given."""
    if not HEX_COLOR.fullmatch(color):
        return color
    return ensure_contrast(
        ensure_contrast(color, TEXT_MIN, theme.bg), TEXT_MIN, theme.card
    )


def mix(a: str, b: str, t: float) -> str:
    """The solid #rrggbb t of the way from color a to color b."""
    pairs = zip(channels(a), channels(b), strict=True)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in pairs)


def deep_shade(accent: str) -> str:
    """Darker partner of the accent, where the calendar's quietest level starts."""
    if accent == BLUE_LIGHT:
        return BLUE  # the original card's hand-picked pair, kept exact
    r, g, b = (int(accent[i : i + 2], 16) / 255 for i in (1, 3, 5))
    hue, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
    rgb = colorsys.hls_to_rgb(hue, lightness * DEEP_LIGHTNESS, saturation)
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb)


def calendar_shades(accent: str, theme: Theme = DARK) -> list[str]:
    """Fills for calendar levels 0 to 4: the theme's empty-day tint, then four
    solid shades from quiet to busy that each reach 3:1 on the card.

    On a dark card the quietest starts from the deep shade at 60% over the card
    (the old middle level) and the busiest is the accent, held to 4.5:1 like the
    title so a dark accent still leaves room above the 3:1 floor. On a light card
    the quietest is the accent half mixed into the card, darkened to 3:1, and the
    busiest is the accent darkened to LIGHT_PEAK_MIN. The two between are spaced
    evenly from one to the other."""
    bg = theme.bg
    if is_dark(bg):
        peak = ensure_contrast(accent, TEXT_MIN, bg)
        low = ensure_contrast(mix(bg, deep_shade(peak), 0.6), GRAPHIC_MIN, bg)
    else:
        peak = ensure_contrast(accent, LIGHT_PEAK_MIN, bg)
        low = ensure_contrast(mix(bg, peak, 0.5), GRAPHIC_MIN, bg)
    mids = [ensure_contrast(mix(low, peak, t), GRAPHIC_MIN, bg) for t in (1 / 3, 2 / 3)]
    return [theme.empty, low, *mids, peak]


def svg_open(w: int, h: int, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(label)}">'
    )


def level_cuts(weeks: list[list[int]]) -> list[int]:
    """Quartiles of the non-zero days shown, where calendar levels change."""
    nonzero = sorted(c for week in weeks for c in week if c)
    return [nonzero[len(nonzero) * q // 4] for q in (1, 2, 3)] if nonzero else [0, 0, 0]


def card_head(
    w: int, h: int, label: str, weeks: int, ink: Theme, title: str
) -> list[str]:
    """Opening tag, style, background and title, shared by both layouts."""
    return [
        svg_open(w, h, label),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.v{{font-family:{SANS};font-weight:800}}"
        ".c{opacity:0;animation:in .5s ease forwards}@keyframes in{to{opacity:1}}"
        + "".join(
            f".w{i}{{animation-delay:{0.4 + i * 0.03:.2f}s}}" for i in range(weeks)
        )
        + ".grow{transform:scaleX(0);transform-origin:left;transform-box:fill-box;animation:grow 1.2s .5s ease forwards}"
        "@keyframes grow{to{transform:scaleX(1)}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{ink.bg}" stroke="{ink.border}"/>',
        f'<text class="m" x="24" y="30" fill="{ink.accent}" font-size="10.5">{escape(title)}</text>',
    ]


def tile(
    i: int,
    x: float,
    y: int,
    tw: float,
    th: int,
    value: str,
    name: str,
    ink: Theme,
    sizes: tuple[int, int, float, int],
    name_fill: str = "",
) -> str:
    """One stat tile that fades in; sizes are value font, value y, label font, label y."""
    value_size, value_y, name_size, name_y = sizes
    return (
        f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{0.1 + i * 0.1:.1f}s" dur="0.4s" fill="freeze"/>'
        f'<rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="10" fill="{ink.card}" stroke="{ink.tile_border}"/>'
        f'<text class="v" x="{x + 14}" y="{y + value_y}" fill="{ink.text}" font-size="{value_size}">{value}</text>'
        f'<text class="m" x="{x + 14}" y="{y + name_y}" fill="{name_fill or ink.muted}" font-size="{name_size}">{name.upper()}</text></g>'
    )


def calendar_cells(
    weeks: list[list[int]],
    shades: list[str],
    gx: float,
    gy: float,
    cell: float,
    gap: float,
) -> list[str]:
    """One column per week; shades are quartiles of the shown non-zero days."""
    cuts = level_cuts(weeks)
    return [
        f'<rect class="c w{wi}" x="{gx + wi * (cell + gap):.1f}" y="{gy + di * (cell + gap):.1f}" '
        f'width="{cell}" height="{cell}" rx="2" fill="{shades[level(count, cuts)]}"/>'
        for wi, week in enumerate(weeks)
        for di, count in enumerate(week)
    ]


def language_block(
    languages: list[list],
    ly: int,
    w: int,
    per_row: int,
    column: int,
    ink: Theme,
    heading_size: float,
    legend_size: float,
) -> list[str]:
    """Heading, stacked bar that grows in, and a legend of per_row columns."""
    parts = [
        f'<text class="m" x="24" y="{ly}" fill="{ink.muted}" font-size="{heading_size}">TOP LANGUAGES BY CODE SIZE</text>'
    ]
    total = sum(pct for _, pct, _ in languages) or 1
    x = 24.0
    bar_w = w - 48
    segs = []
    for _, pct, color in languages:
        seg = bar_w * pct / total
        segs.append(
            f'<rect x="{x:.1f}" y="{ly + 10}" width="{seg:.1f}" height="10" fill="{color}"/>'
        )
        x += seg
    parts.append(
        f'<g class="grow"><clipPath id="bar"><rect x="24" y="{ly + 10}" width="{bar_w}" height="10" rx="5"/></clipPath>'
        f'<g clip-path="url(#bar)">{"".join(segs)}</g></g>'
    )
    for i, (name, pct, color) in enumerate(languages):
        lx = 24 + (i % per_row) * column
        lyy = ly + 44 + (i // per_row) * 20
        parts.append(
            f'<circle cx="{lx + 5}" cy="{lyy - 3}" r="4.5" fill="{color}"/>'
            f'<text class="m" x="{lx + 16}" y="{lyy}" fill="{ink.legend}" font-size="{legend_size}">{escape(name.upper())}  {pct}%</text>'
        )
    return parts


def wide_card(
    stats: dict, title: str, label: str, ink: Theme, languages: list
) -> list[str]:
    """840 px: five tiles in a row, the full year, a streak panel, three-column legend.

    No text under 10.5 px, which still reads at 10 px when the card fills a README column.
    """
    cal = stats["calendar"]
    legend_rows = (len(languages) + 2) // 3  # three languages per legend row
    w, h = 840, 300 + 20 * max(2, legend_rows)
    tiles = [
        # the calendar beside it is the year; "contributions, last year" no longer fits at 10.5 px
        (f"{stats['contributions']:,}", "contributions"),
        (f"{stats['commits']:,}", "commits"),
        (f"{stats['prs']:,}", "pull requests"),
        (f"{stats['stars']:,}", "stars earned"),
        (f"{stats['followers']:,}", "followers"),
    ]
    parts = card_head(w, h, label, len(cal), ink, title)
    tw = (w - 32 - 4 * 10) / 5
    for i, (value, name) in enumerate(tiles):
        parts.append(
            tile(i, 16 + i * (tw + 10), 44, tw, 64, value, name, ink, (22, 32, 10.5, 52))
        )

    cell, gap, gx, gy = 9, 2.6, 24, 128
    parts += calendar_cells(cal, calendar_shades(ink.accent, ink), gx, gy, cell, gap)
    sx = gx + len(cal) * (cell + gap) + 18
    parts += [
        f'<rect x="{sx:.1f}" y="{gy}" width="{w - 16 - sx:.1f}" height="{7 * (cell + gap) - gap:.0f}" rx="10" fill="{ink.card}" stroke="{ink.tile_border}"/>',
        f'<text class="m" x="{sx + 14:.1f}" y="{gy + 15}" fill="{ink.streak}" font-size="10.5">CURRENT STREAK</text>',
        f'<text class="v" x="{sx + 14:.1f}" y="{gy + 42}" fill="{ink.text}" font-size="22">{stats["streak"]}<tspan class="m" font-size="10.5" fill="{ink.muted}"> DAYS</tspan></text>',
        # one line at 10.5 px is wider than the panel, so longest and active stack
        f'<text class="m" x="{sx + 14:.1f}" y="{gy + 58}" fill="{ink.muted}" font-size="10.5">LONGEST {stats["longest"]}</text>',
        f'<text class="m" x="{sx + 14:.1f}" y="{gy + 71}" fill="{ink.muted}" font-size="10.5">ACTIVE {stats["active_days"]}</text>',
    ]
    return parts + language_block(languages, 232, w, 3, 270, ink, 10.5, 10.5)


def compact_card(
    stats: dict, title: str, label: str, ink: Theme, languages: list
) -> list[str]:
    """400 px for phones: six tiles in a 3 by 2 grid (the streak is the sixth), the
    last COMPACT_WEEKS weeks, a two-column legend, and no text under 9 px."""
    weeks = stats["calendar"][-COMPACT_WEEKS:]
    legend_rows = max(1, (len(languages) + 1) // 2)  # two languages per legend row
    w, h = 400, 376 + 20 * (legend_rows - 1)
    tiles = [
        (f"{stats['contributions']:,}", "contributions", ""),
        (f"{stats['commits']:,}", "commits", ""),
        (f"{stats['prs']:,}", "pull requests", ""),
        (f"{stats['stars']:,}", "stars earned", ""),
        (f"{stats['followers']:,}", "followers", ""),
        (
            f'{stats["streak"]}<tspan class="m" font-size="9" fill="{ink.muted}"> DAYS</tspan>',
            "current streak",
            ink.streak,
        ),
    ]
    parts = card_head(w, h, label, len(weeks), ink, title)
    gap = 8
    tw = (w - 32 - 2 * gap) / 3
    for i, (value, name, fill) in enumerate(tiles):
        x = round(16 + (i % 3) * (tw + gap), 1)
        y = 44 + (i // 3) * 64
        parts.append(
            tile(i, x, y, round(tw, 1), 56, value, name, ink, (20, 30, 9, 46), fill)
        )

    gy = 196
    year = f"LONGEST {stats['longest']} | ACTIVE {stats['active_days']} / YEAR"
    parts += [
        f'<text class="m" x="24" y="{gy - 10}" fill="{ink.muted}" font-size="9">LAST {len(weeks)} WEEKS</text>',
        f'<text class="m" x="{w - 24}" y="{gy - 10}" fill="{ink.muted}" font-size="9" text-anchor="end">{year}</text>',
    ]
    parts += calendar_cells(weeks, calendar_shades(ink.accent, ink), 24, gy, 10.6, 3)
    return parts + language_block(languages, 316, w, 2, 176, ink, 9, 9)


def render_card(
    stats: dict,
    username: str,
    title: str,
    accent: str,
    theme: str = "dark",
    layout: str = "wide",
) -> str:
    palette = THEMES[theme]
    bg = palette.bg
    # linguist colors are data: one too dark (or too light) for the card moves to
    # the nearest shade that reaches 3:1 rather than being dropped
    languages = [
        [name, pct, ensure_contrast(color, GRAPHIC_MIN, bg)]
        for name, pct, color in stats["languages"]
    ]
    # the accent is also the title, which is small text
    ink = replace(
        palette,
        accent=ensure_contrast(accent, TEXT_MIN, bg),
        text=readable(palette.text, palette),
        muted=readable(palette.muted, palette),
        legend=readable(palette.legend, palette),
        streak=readable(palette.streak, palette),
    )
    label = (
        f"GitHub stats for @{username}: {stats['contributions']} contributions last year, "
        f"{stats['streak']} day streak, {stats['stars']} stars"
    )
    body = compact_card if layout == "compact" else wide_card
    return "".join([*body(stats, title, label, ink, languages), SVG_CLOSE])


def fail(message: str) -> NoReturn:
    print(f"::error::{message}")
    raise SystemExit(1)


def read_input(name: str) -> str:
    """One action input, as action.yml maps it to INPUT_<NAME>."""
    return os.environ.get(f"INPUT_{name}", "").strip()


def parse_accent(value: str) -> str:
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", value)
    if not match:
        fail(f"accent must be a hex color like #60a5fa, got {value!r}")
    return f"#{match.group(1).lower()}"


def parse_languages(value: str) -> int:
    count = int(value) if value.isdigit() else 0
    if count < 1:
        fail(f"languages must be a whole number of at least 1, got {value!r}")
    return count


def parse_choice(name: str, value: str, choices: tuple[str, ...]) -> str:
    choice = value.lower()
    if choice not in choices:
        fail(f"{name} must be one of {', '.join(choices)}, got {value!r}")
    return choice


def parse_exclude(value: str) -> set[str]:
    # "name" or "owner/name"; GitHub repository names are case-insensitive
    return {
        item.strip().rsplit("/", 1)[-1].lower()
        for item in value.split(",")
        if item.strip()
    }


def set_output(name: str, value: object) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with Path(path).open("a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def main() -> None:
    username = read_input("USERNAME")
    if not username:
        fail("no username: set the username input (INPUT_USERNAME when run locally)")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        fail("no token: set the token input (GITHUB_TOKEN when run locally)")
    theme = parse_choice("theme", read_input("THEME") or "dark", tuple(THEMES))
    layout = parse_choice("layout", read_input("LAYOUT") or LAYOUTS[0], LAYOUTS)
    accent = parse_accent(read_input("ACCENT") or THEMES[theme].accent)
    top = parse_languages(read_input("LANGUAGES") or DEFAULT_LANGUAGES)
    exclude = parse_exclude(read_input("EXCLUDE_REPOS"))
    title = read_input("TITLE") or f"GITHUB | @{username.upper()}"
    output = Path(read_input("OUTPUT") or DEFAULT_OUTPUT)

    print(f"Fetching GitHub stats for @{username}")
    try:
        stats = fetch_stats(username, token, top, exclude)
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as exc:
        if output.exists():
            print(
                f"::warning::GitHub API call failed, keeping the existing {output}: {exc}"
            )
            return
        fail(
            f"GitHub API call failed and {output} does not exist yet, "
            f"so there is no card to keep: {exc}"
        )

    svg = render_card(stats, username, title, accent, theme, layout) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8", newline="\n")
    print(
        f"Wrote {output} ({len(svg.encode()):,} bytes): {stats['contributions']:,} "
        f"contributions, {stats['streak']} day streak, {stats['stars']:,} stars"
    )
    set_output("contributions", stats["contributions"])
    set_output("streak", stats["streak"])
    set_output("stars", stats["stars"])


if __name__ == "__main__":
    main()
