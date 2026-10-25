"""Render an animated LeetCode contest rating card as a self-contained SVG.

This file is the whole action: action.yml sets up Python and runs it with the
inputs as environment variables. It also runs standalone:

    LEETCODE_USERNAME=your-username python leetcode_card.py

Data comes from LeetCode's public GraphQL endpoint, which is unofficial and
needs no auth. When a fetch fails the existing card is kept, so a flaky API
never blanks a README. Stdlib only, because action.yml installs nothing else.

GitHub serves README images through an <img>, so the SVG must stay fully
self-contained: no scripts, no external fonts or images, CSS and SMIL only.
"""

from __future__ import annotations

import colorsys
import datetime as dt
import itertools
import json
import math
import os
import re
import sys
import urllib.request
from html import escape
from http.client import HTTPException
from pathlib import Path

DEFAULT_OUTPUT = "assets/leetcode.svg"
DEFAULT_THEME = "dark"
DEFAULT_TITLE = "LEETCODE CONTEST RATING | {contests} CONTESTS"
HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}")

# Named palettes. "ink" is the RGB that muted labels, gridlines and tracks are
# drawn in at partial alpha; "text" is the solved count; "accent" is the default
# accent. "dark" is the palette of the profile README card this action was
# extracted from, and stays its default.
THEMES = {
    "dark": {
        "bg": "#0b1012",
        "ink": "255,255,255",
        "text": "#f3f4f6",
        "accent": "#f59e0b",
    },
    "light": {
        "bg": "#ffffff",
        "ink": "31,35,40",
        "text": "#1f2328",
        "accent": "#b45309",
    },
    "github-dark": {
        "bg": "#0d1117",
        "ink": "230,237,243",
        "text": "#e6edf3",
        "accent": "#4493f8",
    },
    "github-light": {
        "bg": "#ffffff",
        "ink": "31,35,40",
        "text": "#1f2328",
        "accent": "#0969da",
    },
    "dracula": {
        "bg": "#282a36",
        "ink": "248,248,242",
        "text": "#f8f8f2",
        "accent": "#bd93f9",
    },
    "nord": {
        "bg": "#2e3440",
        "ink": "236,239,244",
        "text": "#eceff4",
        "accent": "#88c0d0",
    },
}
BG = THEMES[DEFAULT_THEME]["bg"]
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
SANS = "'Segoe UI',Inter,-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"
LC_COLORS = {"Easy": "#00b8a3", "Medium": "#ffc01e", "Hard": "#ef4743"}
SVG_CLOSE = "</svg>"
# WCAG 1.4.3 for text under 24 px (18.66 px bold). Every text color on the card meets it,
# the big badge line included, though 3:1 would do there.
MIN_CONTRAST = 4.5

W = 840
CHART_BOX = (40, 540, 70, 220)  # left, right, top, bottom of the rating chart
PANEL_X = 600

# The heatmap is GitHub's layout: one column per week, Sunday on top, the last
# column the current week. 53 columns of 12 px cells on a 15 px pitch span
# x = 24 to 816, the same margins as the rest of the card.
HEATMAP_WEEKS = 53
HEATMAP_CELL = 12
HEATMAP_PITCH = 15
HEATMAP_X = 24
# The heatmap starts 24 px above the bottom of the card it extends and adds this much
HEATMAP_HEIGHT = 176
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN")
MONTHS += ("JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

GRAPHQL_URL = "https://leetcode.com/graphql"
ALLOWED_HOSTS = ("https://leetcode.com/",)
QUERY_HEAD = (
    "query($u:String!){userContestRanking(username:$u){rating topPercentage "
    "attendedContestsCount badge{name}} userContestRankingHistory(username:$u)"
    "{attended rating} allQuestionsCount{difficulty count} matchedUser(username:$u)"
    "{submitStats{acSubmissionNum{difficulty count}}"
)
# The past year of submissions per UTC day, as a JSON string of {timestamp: count}
CALENDAR_FIELD = " userCalendar{submissionCalendar}"


def leetcode_query(heatmap: bool = False) -> str:
    """The one GraphQL query a run sends; the calendar is only asked for when it is drawn."""
    return QUERY_HEAD + (CALENDAR_FIELD if heatmap else "") + "}}"


LEETCODE_QUERY = leetcode_query()
# What a fetch can fail with: network and HTTP errors, bad JSON, a missing user,
# or a response whose shape changed under us (the API is unofficial).
FETCH_ERRORS = (
    OSError,
    HTTPException,
    ValueError,
    LookupError,
    TypeError,
    AttributeError,
)


def fetch(url: str, body: dict, timeout: int = 20) -> bytes:
    """POST body as JSON and return the raw response; allowlisted https URLs only."""
    if not url.startswith(ALLOWED_HOSTS):
        raise ValueError(f"refusing to fetch {url}")
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "User-Agent": "leetcode-card-action (+https://github.com/Sagargupta16/leetcode-card-action)",
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
        },
    )
    # scheme and host were checked against ALLOWED_HOSTS above
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return resp.read()


def parse_calendar(raw: str | None) -> dict[dt.date, int]:
    """LeetCode's submissionCalendar, a JSON string keyed by UTC-midnight timestamps, by date."""
    return {
        dt.datetime.fromtimestamp(int(ts), dt.UTC).date(): int(n)
        for ts, n in json.loads(raw or "{}").items()
    }


def parse_profile(payload: dict, username: str) -> dict:
    """Return the numbers the card shows, read from one GraphQL response."""
    data = payload["data"]
    user = data["matchedUser"]
    if user is None:
        raise LookupError(f"LeetCode user {username!r} does not exist")
    if payload.get("errors"):
        # a partial answer would draw a wrong card over the last good one
        raise LookupError(f"LeetCode answered with errors: {payload['errors'][0]}")
    rank = data["userContestRanking"]  # null until the first rated contest
    top = (rank or {}).get("topPercentage")
    solved = {
        x["difficulty"]: x["count"] for x in user["submitStats"]["acSubmissionNum"]
    }
    totals = {x["difficulty"]: x["count"] for x in data["allQuestionsCount"]}
    lc = {
        "badge": ((rank or {}).get("badge") or {}).get("name") or "",
        "rating": round(rank["rating"]) if rank else None,
        "top": None if top is None else round(top, 2),
        "contests": rank["attendedContestsCount"] if rank else 0,
        "solved": solved["All"],
        "by_difficulty": {
            k: [solved.get(k, 0), totals.get(k, 0)] for k in ("Easy", "Medium", "Hard")
        },
        "history": [
            round(x["rating"])
            for x in data["userContestRankingHistory"] or []
            if x["attended"]
        ],
    }
    if "userCalendar" in user:
        lc["calendar"] = parse_calendar(
            (user["userCalendar"] or {}).get("submissionCalendar")
        )
    return lc


def fetch_profile(username: str, heatmap: bool = False) -> dict:
    query = leetcode_query(heatmap)
    raw = fetch(GRAPHQL_URL, {"query": query, "variables": {"u": username}})
    return parse_profile(json.loads(raw), username)


def parse_color(color: str) -> tuple[float, float, float, float]:
    """#rgb, #rrggbb or rgba(r,g,b,a), the forms the card uses, as (r, g, b, alpha)."""
    if color.startswith("rgba("):
        r, g, b, a = (float(x) for x in color[5:-1].split(","))
        return r, g, b, a
    digits = color.lstrip("#")
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), 1.0


def luminance(r: float, g: float, b: float) -> float:
    """WCAG 2.2 relative luminance of an sRGB color with 0 to 255 channels."""

    def linear(v: float) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)


def contrast(fg: str, bg: str = BG) -> float:
    """WCAG 2.2 contrast ratio of fg on the opaque bg; a translucent fg is blended over bg first."""
    *top, alpha = parse_color(fg)
    *under, _ = parse_color(bg)
    painted = [t * alpha + u * (1 - alpha) for t, u in zip(top, under, strict=True)]
    a, b = luminance(*painted), luminance(*under)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def readable(color: str, bg: str = BG) -> str:
    """color if text in it reaches MIN_CONTRAST on bg, else the nearest shade of its hue that does.

    On a dark card only lighter shades gain contrast and white gets there; on a light card
    only darker ones do and black gets there. Every theme's bg is one or the other.
    """
    if contrast(color, bg) >= MIN_CONTRAST:
        return color
    step_sign = 1 if contrast("#ffffff", bg) >= contrast("#000000", bg) else -1
    r, g, b, _ = parse_color(color)
    hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    shades = (
        colorsys.hls_to_rgb(
            hue, min(max(light + step_sign * step / 1000, 0.0), 1.0), sat
        )
        for step in range(1, 1001)
    )
    hexes = ("#" + "".join(f"{round(v * 255):02x}" for v in rgb) for rgb in shades)
    return next(h for h in hexes if contrast(h, bg) >= MIN_CONTRAST)


def muted(theme: dict, alpha: float) -> str:
    """Label text in the theme's ink at alpha, raised in 0.01 steps until it reaches MIN_CONTRAST."""
    for a in (round(alpha + i / 100, 2) for i in range(101)):
        color = f"rgba({theme['ink']},{a:g})"
        if a >= 1 or contrast(color, theme["bg"]) >= MIN_CONTRAST:
            return color
    raise AssertionError("unreachable: alpha 1 always returns")


def blend(color: str, bg: str, alpha: float) -> str:
    """color painted at alpha over bg, as the opaque hex a browser shows."""
    top, under = parse_color(color), parse_color(bg)
    return "#" + "".join(
        f"{round(t * alpha + u * (1 - alpha)):02x}"
        for t, u in zip(top[:3], under[:3], strict=True)
    )


def heat_colors(accent: str, bg: str) -> list[str]:
    """Four heatmap shades of the accent, the faintest still 3:1 on bg (WCAG 1.4.11).

    The faintest is the accent at the lowest alpha over bg that reaches 3:1, at least 0.35;
    the other three step evenly from there to the full accent.
    """
    low = next(
        a
        for a in (round(0.35 + i / 100, 2) for i in range(66))
        if a >= 1 or contrast(blend(accent, bg, a), bg) >= 3
    )
    return [blend(accent, bg, low + (1 - low) * i / 3) for i in range(4)]


def palette(theme: str = DEFAULT_THEME, accent: str | None = None) -> dict:
    """Every color the card paints for a theme, text colors already raised to MIN_CONTRAST.

    The dark theme with its default accent gives exactly the colors of the 1.0 card.
    """
    t = THEMES[theme]
    bg, ink = t["bg"], t["ink"]
    accent = readable(accent or t["accent"], bg)
    return {
        "bg": bg,
        "accent": accent,
        "text": readable(t["text"], bg),
        "axis": muted(t, 0.45),
        "sub": muted(t, 0.55),
        "label": muted(t, 0.5),
        "border": f"rgba({ink},0.08)",
        "grid": f"rgba({ink},0.06)",
        "track": f"rgba({ink},0.07)",
        "difficulty": {k: readable(v, bg) for k, v in LC_COLORS.items()},
        "heat": heat_colors(accent, bg),
    }


def svg_open(w: int, h: int, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(label)}">'
    )


def headline(lc: dict) -> tuple[str, str]:
    """Return the big line and the line under it: the badge, else the rating."""
    if lc["rating"] is None:
        return "No contests yet", ""
    top = "" if lc["top"] is None else f"  |  TOP {lc['top']}%"
    if lc["badge"]:
        return lc["badge"], f"RATING {lc['rating']}{top}"
    return str(lc["rating"]), f"CONTEST RATING{top}"


def aria_label(lc: dict, username: str, activity: dict | None = None) -> str:
    past_year = (
        ""
        if activity is None
        else f", {activity['total']} submissions in the past year"
    )
    if lc["rating"] is None:
        return f"LeetCode {username}: no contests yet, {lc['solved']} solved{past_year}"
    badge = f"{lc['badge']}, " if lc["badge"] else ""
    top = "" if lc["top"] is None else f", top {lc['top']}%"
    return (
        f"LeetCode {username}: {badge}rating {lc['rating']}{top}, "
        f"{lc['contests']} contests, {lc['solved']} solved{past_year}"
    )


def chart_points(history: list[int]) -> list[tuple[float, float]]:
    """Map two or more ratings onto the chart box: oldest left, lowest at the bottom."""
    x0, x1, y0, y1 = CHART_BOX
    lo = min(history)
    span = max(max(history) - lo, 1)
    last = len(history) - 1
    return [
        (x0 + (x1 - x0) * i / last, y1 - (y1 - y0) * (r - lo) / span)
        for i, r in enumerate(history)
    ]


def render_chart(history: list[int], pal: dict) -> list[str]:
    """Gridlines, the rating line drawing itself in, the area under it, the peak."""
    x0, x1, y0, y1 = CHART_BOX
    accent = pal["accent"]
    lo, hi = min(history), max(history)
    span = max(hi - lo, 1)
    pts = chart_points(history)
    line = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    length = sum(math.dist(a, b) for a, b in itertools.pairwise(pts))
    area = f"{line} L{x1} {y1} L{x0} {y1} Z"
    px, py = pts[history.index(hi)]
    lx, ly = pts[-1]
    label = f"PEAK {hi}"
    # The label ends just left of the peak, unless that runs off the card's left edge
    # (7.5 px a character: 10.5 px mono with the card's 1.2 px tracking)
    tx, anchor = (
        (px - 6, "end") if px - 6 - len(label) * 7.5 >= 12 else (px + 6, "start")
    )
    parts = []
    for frac in (0, 0.5, 1):
        y = y1 - (y1 - y0) * frac
        parts.append(
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{pal["grid"]}"/>'
            f'<text class="m" x="{x1 + 8}" y="{y + 3:.1f}" fill="{pal["axis"]}" font-size="10.5">{round(lo + span * frac)}</text>'
        )
    return [
        *parts,
        f'<path d="{area}" fill="url(#area)" opacity="0"><animate attributeName="opacity" to="1" begin="2.2s" dur="0.8s" fill="freeze"/></path>',
        (
            f'<path d="{line}" fill="none" stroke="{accent}" stroke-width="2" stroke-linejoin="round" stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}">'
            f'<animate attributeName="stroke-dashoffset" from="{length:.0f}" to="0" dur="2.4s" begin="0.2s" fill="freeze"/></path>'
        ),
        (
            f'<circle class="ring" cx="{px:.1f}" cy="{py:.1f}" r="5" fill="none" stroke="{accent}" stroke-width="1.5" opacity="0">'
            '<set attributeName="opacity" to="1" begin="2.6s" fill="freeze"/></circle>'
        ),
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="{accent}" opacity="0"><set attributeName="opacity" to="1" begin="2.6s" fill="freeze"/></circle>',
        (
            f'<text class="m" x="{tx:.1f}" y="{py - 12:.1f}" text-anchor="{anchor}" fill="{accent}" font-size="10.5" opacity="0">{label}'
            '<set attributeName="opacity" to="1" begin="2.6s" fill="freeze"/></text>'
        ),
    ]


def render_headline(x: int, y: int, lc: dict, pal: dict) -> list[str]:
    big, sub = headline(lc)
    parts = [
        f'<text class="v" x="{x}" y="{y}" fill="{pal["accent"]}" font-size="30">{escape(big)}</text>'
    ]
    if sub:
        parts.append(
            f'<text class="m" x="{x}" y="{y + 20}" fill="{pal["sub"]}" font-size="10.5">{escape(sub)}</text>'
        )
    return parts


def render_solved(x: int, y: int, lc: dict, pal: dict) -> list[str]:
    """Solved count with one animated progress bar per difficulty under it."""
    parts = [
        (
            f'<text class="v" x="{x}" y="{y}" fill="{pal["text"]}" font-size="22">{lc["solved"]:,}'
            f'<tspan class="m" font-size="10.5" fill="{pal["label"]}">  SOLVED</tspan></text>'
        )
    ]
    for j, (level, (done, total)) in enumerate(lc["by_difficulty"].items()):
        by = y + 22 + j * 22
        bar = 200 * (done / total if total else 0)
        color = pal["difficulty"][level]
        parts.append(
            f'<text class="m" x="{x}" y="{by}" fill="{color}" font-size="10.5">{level.upper()}</text>'
            f'<text class="m" x="{x + 200}" y="{by}" text-anchor="end" fill="{pal["label"]}" font-size="10.5">{done}/{total}</text>'
            f'<rect x="{x}" y="{by + 5}" width="200" height="5" rx="2.5" fill="{pal["track"]}"/>'
            f'<rect x="{x}" y="{by + 5}" width="{bar:.1f}" height="5" rx="2.5" fill="{color}" transform="scale(0 1)" style="transform-origin:{x}px 0">'
            f'<animateTransform attributeName="transform" type="scale" from="0 1" to="1 1" begin="{0.6 + j * 0.2:.1f}s" dur="0.9s" fill="freeze"/></rect>'
        )
    return parts


def activity(calendar: dict[dt.date, int], today: dt.date) -> dict:
    """The heatmap window ending today: its first day, a count per day, and the totals."""
    sunday_row = (today.weekday() + 1) % 7  # 0 for Sunday, the top row
    start = today - dt.timedelta(days=sunday_row + 7 * (HEATMAP_WEEKS - 1))
    counts = [
        calendar.get(start + dt.timedelta(days=d), 0)
        for d in range((today - start).days + 1)
    ]
    streak = best = 0
    for n in counts:
        streak = streak + 1 if n else 0
        best = max(best, streak)
    return {
        "start": start,
        "counts": counts,
        "total": sum(counts),
        "active": sum(1 for n in counts if n),
        "streak": best,
    }


def heat_level(count: int, peak: int) -> int:
    """1 to 4 on a log scale, so one busy day does not wash every other day out."""
    return max(1, min(4, math.ceil(4 * math.log(count + 1) / math.log(peak + 1))))


def plural(n: int, word: str) -> str:
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}S"


def render_heatmap(act: dict, top: int, pal: dict) -> list[str]:
    """A year of daily submissions in GitHub's week-column layout, sweeping in left to right."""
    gy = top + 54
    counts = act["counts"]
    weeks = math.ceil(len(counts) / 7)
    last_rows = len(counts) - 7 * (weeks - 1)
    right = HEATMAP_X + HEATMAP_WEEKS * HEATMAP_PITCH - (HEATMAP_PITCH - HEATMAP_CELL)
    stats = f"{plural(act['active'], 'ACTIVE DAY')}  |  MAX STREAK {act['streak']:,}"
    parts = [
        f'<line x1="{HEATMAP_X}" y1="{top}" x2="{right}" y2="{top}" stroke="{pal["grid"]}"/>',
        f'<text class="m" x="{HEATMAP_X}" y="{top + 26}" fill="{pal["label"]}" font-size="10.5">{plural(act["total"], "SUBMISSION")} IN THE PAST YEAR</text>',
        f'<text class="m" x="{right}" y="{top + 26}" text-anchor="end" fill="{pal["label"]}" font-size="10.5">{stats}</text>',
    ]
    last_label = -3
    for week in range(weeks):
        days = (act["start"] + dt.timedelta(days=7 * week + d) for d in range(7))
        month_start = next((day for day in days if day.day == 1), None)
        if month_start and week - last_label >= 3:
            parts.append(
                f'<text class="m" x="{HEATMAP_X + week * HEATMAP_PITCH}" y="{top + 46}" fill="{pal["axis"]}" font-size="10.5">{MONTHS[month_start.month - 1]}</text>'
            )
            last_label = week
    # The empty grid is two pattern-filled rects, the full weeks and the current one, so
    # only active days cost markup
    tile = HEATMAP_PITCH * 7 - (HEATMAP_PITCH - HEATMAP_CELL)
    parts.append(
        f'<defs><pattern id="day" x="{HEATMAP_X}" y="{gy}" width="{HEATMAP_PITCH}" height="{HEATMAP_PITCH}" patternUnits="userSpaceOnUse">'
        f'<rect width="{HEATMAP_CELL}" height="{HEATMAP_CELL}" rx="2" fill="{pal["track"]}"/></pattern></defs>'
        f'<g opacity="0"><animate attributeName="opacity" to="1" begin="0.2s" dur="0.6s" fill="freeze"/>'
        f'<rect x="{HEATMAP_X}" y="{gy}" width="{(weeks - 1) * HEATMAP_PITCH}" height="{tile}" fill="url(#day)"/>'
        f'<rect x="{HEATMAP_X + (weeks - 1) * HEATMAP_PITCH}" y="{gy}" width="{HEATMAP_CELL}" height="{last_rows * HEATMAP_PITCH - (HEATMAP_PITCH - HEATMAP_CELL)}" fill="url(#day)"/></g>'
    )
    peak = max(counts, default=0)
    for week in range(weeks):
        cells = [
            f'<rect x="{HEATMAP_X + week * HEATMAP_PITCH}" y="{gy + row * HEATMAP_PITCH}" width="{HEATMAP_CELL}" height="{HEATMAP_CELL}" rx="2" class="l{heat_level(n, peak)}"/>'
            for row, n in enumerate(counts[7 * week : 7 * week + 7])
            if n
        ]
        if cells:
            parts.append(
                f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{0.4 + week * 0.03:.2f}s" dur="0.4s" fill="freeze"/>'
                + "".join(cells)
                + "</g>"
            )
    return parts


def render_card(
    lc: dict,
    username: str,
    title: str = DEFAULT_TITLE,
    accent: str | None = None,
    theme: str = DEFAULT_THEME,
    today: dt.date | None = None,
) -> str:
    """Return the card SVG. A line needs two rated contests; below that the chart is left out.

    accent defaults to the theme's; one too dark (or, on a light theme, too light) to read on
    the card is shifted to the nearest shade that is. A profile fetched with its calendar gets
    the heatmap for the year ending today (UTC unless given).
    """
    pal = palette(theme, accent)
    chart = len(lc["history"]) >= 2
    h = 270 if chart else 188
    act = None
    if "calendar" in lc:
        act = activity(lc["calendar"], today or dt.datetime.now(dt.UTC).date())
        heat_top = h - 24
        h = heat_top + HEATMAP_HEIGHT
    heading = title.replace("{contests}", str(lc["contests"]))
    levels = "".join(
        f".l{n}{{fill:{color}}}" for n, color in enumerate(pal["heat"], start=1)
    )
    parts = [
        svg_open(W, h, aria_label(lc, username, act)),
        (
            f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.v{{font-family:{SANS};font-weight:800}}"
            # the pulse waits for the SMIL set that reveals the ring at 2.6s; a CSS animation
            # outranks the opacity attribute, so without the delay it pulses before the line arrives
            ".ring{animation:ring 2.2s ease-out 2.6s infinite;transform-origin:center;transform-box:fill-box}"
            f"@keyframes ring{{0%{{opacity:0.9;transform:scale(1)}}100%{{opacity:0;transform:scale(2.8)}}}}{levels if act else ''}</style>"
        ),
        (
            f'<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{pal["accent"]}" stop-opacity="0.28"/>'
            f'<stop offset="1" stop-color="{pal["accent"]}" stop-opacity="0"/></linearGradient></defs>'
        ),
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="14" fill="{pal["bg"]}" stroke="{pal["border"]}"/>',
        f'<text class="m" x="24" y="32" fill="{pal["accent"]}" font-size="10.5">{escape(heading)}</text>',
    ]
    if chart:
        parts += render_chart(lc["history"], pal)
        parts += render_headline(PANEL_X, 84, lc, pal)
        parts += render_solved(PANEL_X, 146, lc, pal)
    else:
        parts += render_headline(24, 84, lc, pal)
        parts += render_solved(PANEL_X, 84, lc, pal)
    if act:
        parts += render_heatmap(act, heat_top, pal)
    parts.append(SVG_CLOSE)
    return "".join(parts)


def parse_outputs(raw: str, default_theme: str) -> list[tuple[Path, str]]:
    """One (path, theme) per non-empty line; a line may end in ?theme=<name> to override the theme."""
    outputs = []
    for line in raw.splitlines():
        path, _, query = line.strip().partition("?")
        path = path.rstrip()
        if not path:
            continue
        theme = default_theme
        if query:
            key, _, value = query.partition("=")
            if key != "theme":
                raise ValueError(
                    f"unknown option {key!r} in output {line.strip()!r}, only theme= is supported"
                )
            theme = value
        if theme not in THEMES:
            raise ValueError(
                f"unknown theme {theme!r}, pick one of {', '.join(THEMES)}"
            )
        outputs.append((Path(path), theme))
    if not outputs:
        raise ValueError("output is empty: give at least one path")
    return outputs


def annotate(level: str, message: str) -> None:
    """Print a GitHub Actions ::warning:: or ::error:: line, escaped like the runner expects."""
    message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{level}::{message}")


def set_outputs(lc: dict) -> None:
    """Append the step outputs to $GITHUB_OUTPUT when running inside Actions."""
    values = {
        "rating": "" if lc["rating"] is None else lc["rating"],
        "badge": lc["badge"],
        "solved": lc["solved"],
        "contests": lc["contests"],
    }
    print(" ".join(f"{name}={value}" for name, value in values.items()))
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as fh:
        # one line per output, so a newline in API data cannot start a new key
        fh.writelines(
            f"{name}={' '.join(str(value).splitlines())}\n"
            for name, value in values.items()
        )


def main() -> int:
    username = os.environ.get("LEETCODE_USERNAME", "").strip()
    accent = (os.environ.get("LEETCODE_ACCENT") or "").strip()
    title = os.environ.get("LEETCODE_TITLE") or DEFAULT_TITLE
    theme = (os.environ.get("LEETCODE_THEME") or DEFAULT_THEME).strip()
    heatmap = (os.environ.get("LEETCODE_HEATMAP") or "false").strip().lower()
    if not username:
        annotate(
            "error",
            "username is required: set the username input (LEETCODE_USERNAME when run by hand)",
        )
        return 1
    if accent and not HEX_COLOR.fullmatch(accent):
        annotate("error", f"accent must be a hex color such as #f59e0b, got {accent!r}")
        return 1
    if heatmap not in {"true", "false"}:
        annotate("error", f"heatmap must be true or false, got {heatmap!r}")
        return 1
    try:
        outputs = parse_outputs(
            os.environ.get("LEETCODE_OUTPUT") or DEFAULT_OUTPUT, theme
        )
    except ValueError as exc:
        annotate("error", str(exc))
        return 1
    try:
        lc = fetch_profile(username, heatmap=heatmap == "true")
    except FETCH_ERRORS as exc:
        reason = f"{type(exc).__name__}: {exc}"
        missing = [str(path) for path, _ in outputs if not path.is_file()]
        if not missing:
            kept = ", ".join(str(path) for path, _ in outputs)
            annotate(
                "warning",
                f"LeetCode fetch failed, keeping the existing {kept}. {reason}",
            )
            return 0
        annotate(
            "error",
            f"LeetCode fetch failed and there is no {', '.join(missing)} to keep. {reason}",
        )
        return 1
    today = dt.datetime.now(dt.UTC).date()
    for path, card_theme in outputs:
        svg = render_card(lc, username, title, accent or None, card_theme, today)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8", newline="\n")
        print(f"wrote {path} ({len(svg):,} bytes, theme {card_theme})")
    set_outputs(lc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
