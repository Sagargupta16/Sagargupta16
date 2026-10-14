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
    rgb = colorsys.hls_to_rgb(hue, min(lightness, 1.0), saturation)
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb)


def ensure_contrast(color: str, minimum: float) -> str:
    """color when it reaches minimum:1 on the card, else the nearest lighter shade
    of the same hue that does. The card is near-black, so only lighter shades can
    pass, and white (19:1) always does."""
    if contrast(color) >= minimum:
        return color
    hue, lightness, saturation = colorsys.rgb_to_hls(
        *(v / 255 for v in channels(color))
    )
    shades = (
        hls_hex(hue, lightness + step / 1000, saturation) for step in range(1, 1001)
    )
    return next(shade for shade in shades if contrast(shade) >= minimum)


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


def calendar_shades(accent: str) -> list[str]:
    """Fills for calendar levels 0 to 4: the empty-day tint, then four solid shades
    from quiet to busy that each reach 3:1 on the card. The quietest starts from
    the deep shade at 60% over the card (the old middle level) and the busiest is
    the accent, held to 4.5:1 like the title so a dark accent still leaves room
    above the 3:1 floor; the two between are spaced evenly from one to the other."""
    peak = ensure_contrast(accent, TEXT_MIN)
    low = ensure_contrast(mix(BG, deep_shade(peak), 0.6), GRAPHIC_MIN)
    mids = [ensure_contrast(mix(low, peak, t), GRAPHIC_MIN) for t in (1 / 3, 2 / 3)]
    return [EMPTY_DAY, low, *mids, peak]


def svg_open(w: int, h: int, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(label)}">'
    )


def render_card(stats: dict, username: str, title: str, accent: str) -> str:
    cal = stats["calendar"]
    # linguist colors are data: one too dark for the card moves to the nearest
    # lighter shade that reaches 3:1 rather than being dropped
    languages = [
        [name, pct, ensure_contrast(color, GRAPHIC_MIN)]
        for name, pct, color in stats["languages"]
    ]
    # the accent is also the title, which is small text
    accent = ensure_contrast(accent, TEXT_MIN)
    legend_rows = (len(languages) + 2) // 3  # three languages per legend row
    w, h = 840, 300 + 20 * max(2, legend_rows)
    tiles = [
        (f"{stats['contributions']:,}", "contributions, last year"),
        (f"{stats['commits']:,}", "commits"),
        (f"{stats['prs']:,}", "pull requests"),
        (f"{stats['stars']:,}", "stars earned"),
        (f"{stats['followers']:,}", "followers"),
    ]
    label = (
        f"GitHub stats for @{username}: {stats['contributions']} contributions last year, "
        f"{stats['streak']} day streak, {stats['stars']} stars"
    )
    parts = [
        svg_open(w, h, label),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.v{{font-family:{SANS};font-weight:800}}"
        ".c{opacity:0;animation:in .5s ease forwards}@keyframes in{to{opacity:1}}"
        + "".join(
            f".w{i}{{animation-delay:{0.4 + i * 0.03:.2f}s}}" for i in range(len(cal))
        )
        + ".grow{transform:scaleX(0);transform-origin:left;transform-box:fill-box;animation:grow 1.2s .5s ease forwards}"
        "@keyframes grow{to{transform:scaleX(1)}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="30" fill="{accent}" font-size="10">{escape(title)}</text>',
    ]
    tw = (w - 32 - 4 * 10) / 5
    for i, (value, name) in enumerate(tiles):
        x = 16 + i * (tw + 10)
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{0.1 + i * 0.1:.1f}s" dur="0.4s" fill="freeze"/>'
            f'<rect x="{x}" y="44" width="{tw}" height="64" rx="10" fill="{CARD}" stroke="rgba(255,255,255,0.07)"/>'
            f'<text class="v" x="{x + 14}" y="76" fill="#f3f4f6" font-size="22">{value}</text>'
            f'<text class="m" x="{x + 14}" y="95" fill="rgba(255,255,255,0.5)" font-size="8">{name.upper()}</text></g>'
        )

    # contribution calendar, one column per week; shades are quartiles of the
    # user's own non-zero days
    nonzero = sorted(c for week in cal for c in week if c)
    cuts = [nonzero[len(nonzero) * q // 4] for q in (1, 2, 3)] if nonzero else [0, 0, 0]
    shades = calendar_shades(accent)
    cell, gap, gx, gy = 9, 2.6, 24, 128
    for wi, week in enumerate(cal):
        for di, count in enumerate(week):
            x = gx + wi * (cell + gap)
            y = gy + di * (cell + gap)
            parts.append(
                f'<rect class="c w{wi}" x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="2" fill="{shades[level(count, cuts)]}"/>'
            )
    sx = gx + len(cal) * (cell + gap) + 18
    parts += [
        f'<rect x="{sx:.1f}" y="{gy}" width="{w - 16 - sx:.1f}" height="{7 * (cell + gap) - gap:.0f}" rx="10" fill="{CARD}" stroke="rgba(255,255,255,0.07)"/>',
        f'<text class="m" x="{sx + 14:.1f}" y="{gy + 20}" fill="{GREEN}" font-size="8.5">CURRENT STREAK</text>',
        f'<text class="v" x="{sx + 14:.1f}" y="{gy + 46}" fill="#f3f4f6" font-size="22">{stats["streak"]}<tspan class="m" font-size="9" fill="rgba(255,255,255,0.5)"> DAYS</tspan></text>',
        f'<text class="m" x="{sx + 14:.1f}" y="{gy + 66}" fill="rgba(255,255,255,0.5)" font-size="8">LONGEST {stats["longest"]}  |  ACTIVE {stats["active_days"]}</text>',
    ]

    # languages, stacked bar plus legend
    ly = 232
    parts.append(
        f'<text class="m" x="24" y="{ly}" fill="rgba(255,255,255,0.5)" font-size="8.5">TOP LANGUAGES BY CODE SIZE</text>'
    )
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
        lx = 24 + (i % 3) * 270
        lyy = ly + 44 + (i // 3) * 20
        parts.append(
            f'<circle cx="{lx + 5}" cy="{lyy - 3}" r="4.5" fill="{color}"/>'
            f'<text class="m" x="{lx + 16}" y="{lyy}" fill="rgba(255,255,255,0.75)" font-size="9">{escape(name.upper())}  {pct}%</text>'
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


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
    accent = parse_accent(read_input("ACCENT") or BLUE_LIGHT)
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

    svg = render_card(stats, username, title, accent) + "\n"
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
