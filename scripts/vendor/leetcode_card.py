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
DEFAULT_ACCENT = "#f59e0b"
DEFAULT_TITLE = "LEETCODE CONTEST RATING | {contests} CONTESTS"
HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}")

# Palette and type of the profile README card this action was extracted from
BG = "#0b1012"
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

GRAPHQL_URL = "https://leetcode.com/graphql"
ALLOWED_HOSTS = ("https://leetcode.com/",)
LEETCODE_QUERY = (
    "query($u:String!){userContestRanking(username:$u){rating topPercentage "
    "attendedContestsCount badge{name}} userContestRankingHistory(username:$u)"
    "{attended rating} allQuestionsCount{difficulty count} matchedUser(username:$u)"
    "{submitStats{acSubmissionNum{difficulty count}}}}"
)
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
    return {
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


def fetch_profile(username: str) -> dict:
    raw = fetch(GRAPHQL_URL, {"query": LEETCODE_QUERY, "variables": {"u": username}})
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


def readable(color: str) -> str:
    """color if text in it reaches MIN_CONTRAST on the card, else the nearest lighter shade that does.

    BG is near black, so only lighter shades gain contrast, and white (19.1:1) always gets there.
    """
    if contrast(color) >= MIN_CONTRAST:
        return color
    r, g, b, _ = parse_color(color)
    hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    shades = (
        colorsys.hls_to_rgb(hue, min(light + step / 1000, 1.0), sat)
        for step in range(1, 1001)
    )
    hexes = ("#" + "".join(f"{round(v * 255):02x}" for v in rgb) for rgb in shades)
    return next(h for h in hexes if contrast(h) >= MIN_CONTRAST)


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


def aria_label(lc: dict, username: str) -> str:
    if lc["rating"] is None:
        return f"LeetCode {username}: no contests yet, {lc['solved']} solved"
    badge = f"{lc['badge']}, " if lc["badge"] else ""
    top = "" if lc["top"] is None else f", top {lc['top']}%"
    return (
        f"LeetCode {username}: {badge}rating {lc['rating']}{top}, "
        f"{lc['contests']} contests, {lc['solved']} solved"
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


def render_chart(history: list[int], accent: str) -> list[str]:
    """Gridlines, the rating line drawing itself in, the area under it, the peak."""
    x0, x1, y0, y1 = CHART_BOX
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
    tx, anchor = (
        (px - 6, "end") if px - 6 - len(label) * 6.6 >= 12 else (px + 6, "start")
    )
    parts = []
    for frac in (0, 0.5, 1):
        y = y1 - (y1 - y0) * frac
        parts.append(
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="rgba(255,255,255,0.06)"/>'
            f'<text class="m" x="{x1 + 8}" y="{y + 3:.1f}" fill="rgba(255,255,255,0.45)" font-size="8">{round(lo + span * frac)}</text>'
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
            f'<text class="m" x="{tx:.1f}" y="{py - 12:.1f}" text-anchor="{anchor}" fill="{accent}" font-size="9" opacity="0">{label}'
            '<set attributeName="opacity" to="1" begin="2.6s" fill="freeze"/></text>'
        ),
    ]


def render_headline(x: int, y: int, lc: dict, accent: str) -> list[str]:
    big, sub = headline(lc)
    parts = [
        f'<text class="v" x="{x}" y="{y}" fill="{accent}" font-size="30">{escape(big)}</text>'
    ]
    if sub:
        parts.append(
            f'<text class="m" x="{x}" y="{y + 20}" fill="rgba(255,255,255,0.55)" font-size="9">{escape(sub)}</text>'
        )
    return parts


def render_solved(x: int, y: int, lc: dict) -> list[str]:
    """Solved count with one animated progress bar per difficulty under it."""
    parts = [
        (
            f'<text class="v" x="{x}" y="{y}" fill="#f3f4f6" font-size="22">{lc["solved"]:,}'
            '<tspan class="m" font-size="9" fill="rgba(255,255,255,0.5)">  SOLVED</tspan></text>'
        )
    ]
    for j, (level, (done, total)) in enumerate(lc["by_difficulty"].items()):
        by = y + 22 + j * 22
        bar = 200 * (done / total if total else 0)
        parts.append(
            f'<text class="m" x="{x}" y="{by}" fill="{LC_COLORS[level]}" font-size="8.5">{level.upper()}</text>'
            f'<text class="m" x="{x + 200}" y="{by}" text-anchor="end" fill="rgba(255,255,255,0.5)" font-size="8.5">{done}/{total}</text>'
            f'<rect x="{x}" y="{by + 5}" width="200" height="5" rx="2.5" fill="rgba(255,255,255,0.07)"/>'
            f'<rect x="{x}" y="{by + 5}" width="{bar:.1f}" height="5" rx="2.5" fill="{LC_COLORS[level]}" transform="scale(0 1)" style="transform-origin:{x}px 0">'
            f'<animateTransform attributeName="transform" type="scale" from="0 1" to="1 1" begin="{0.6 + j * 0.2:.1f}s" dur="0.9s" fill="freeze"/></rect>'
        )
    return parts


def render_card(
    lc: dict, username: str, title: str = DEFAULT_TITLE, accent: str = DEFAULT_ACCENT
) -> str:
    """Return the card SVG. A line needs two rated contests; below that the chart is left out.

    An accent too dark to read on the card is lightened to the nearest shade that is.
    """
    accent = readable(accent)
    chart = len(lc["history"]) >= 2
    h = 270 if chart else 188
    heading = title.replace("{contests}", str(lc["contests"]))
    parts = [
        svg_open(W, h, aria_label(lc, username)),
        (
            f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.v{{font-family:{SANS};font-weight:800}}"
            ".ring{animation:ring 2.2s ease-out infinite;transform-origin:center;transform-box:fill-box}"
            "@keyframes ring{0%{opacity:0.9;transform:scale(1)}100%{opacity:0;transform:scale(2.8)}}</style>"
        ),
        (
            f'<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{accent}" stop-opacity="0.28"/>'
            f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient></defs>'
        ),
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="32" fill="{accent}" font-size="10">{escape(heading)}</text>',
    ]
    if chart:
        parts += render_chart(lc["history"], accent)
        parts += render_headline(PANEL_X, 84, lc, accent)
        parts += render_solved(PANEL_X, 146, lc)
    else:
        parts += render_headline(24, 84, lc, accent)
        parts += render_solved(PANEL_X, 84, lc)
    parts.append(SVG_CLOSE)
    return "".join(parts)


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
    output = Path(os.environ.get("LEETCODE_OUTPUT") or DEFAULT_OUTPUT)
    accent = (os.environ.get("LEETCODE_ACCENT") or DEFAULT_ACCENT).strip()
    title = os.environ.get("LEETCODE_TITLE") or DEFAULT_TITLE
    if not username:
        annotate(
            "error",
            "username is required: set the username input (LEETCODE_USERNAME when run by hand)",
        )
        return 1
    if not HEX_COLOR.fullmatch(accent):
        annotate("error", f"accent must be a hex color such as #f59e0b, got {accent!r}")
        return 1
    try:
        lc = fetch_profile(username)
    except FETCH_ERRORS as exc:
        reason = f"{type(exc).__name__}: {exc}"
        if output.is_file():
            annotate(
                "warning",
                f"LeetCode fetch failed, keeping the existing {output}. {reason}",
            )
            return 0
        annotate(
            "error", f"LeetCode fetch failed and there is no {output} to keep. {reason}"
        )
        return 1
    svg = render_card(lc, username, title, accent)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8", newline="\n")
    print(f"wrote {output} ({len(svg):,} bytes)")
    set_outputs(lc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
