"""Phone layouts (320px wide), the README images below 1012px and wherever <picture> is unsupported."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# The phone cards keep the desktop cards' look: mono micro-labels, flat bordered
# tiles, badge images, and motion (blocks fade and rise in order,
# accents pulse, a shine sweeps each card, timelines and charts draw in). Long
# lists are capped with a "+N more" line so the page stays a scroll, not a wall.
from __future__ import annotations

import datetime
import math
import re
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from html import escape

WIDTH, PAD, BODY_SIZE = 320, 18, 15
CONTENT_WIDTH = WIDTH - PAD * 2
BG, CARD, WHITE = "#0b1012", "#0f171c", "#f3f4f6"
MUTED, BLUE, SKY = "#b1bfcc", "#60a5fa", "#38bdf8"
GREEN, AMBER, BORDER = "#4ade80", "#fbbf24", "#26343d"
RED, TRACK = "#f87171", "#1b2630"
SANS = "'Segoe UI',-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
MISSING = "-"
LEADING = 0.38  # gap below each line, as a share of its font size
MERGED_SHOWN, OPEN_SHOWN = 6, 5
BADGE_COLUMNS, BADGE_SIZE = 4, 56
# Credly separates "Developer" and "Associate" with an en dash (U+2013) where
# the portfolio has a hyphen; em dashes (U+2014) are folded the same way.
DASHES = re.compile(f"[{chr(0x2013)}{chr(0x2014)}]")
# Each block starts STAGGER after the previous one; LAST_START caps the delay
# so a long card has finished drawing within a few seconds.
STAGGER, FADE, LAST_START = 0.1, 0.45, 2.4
# Empty day, then four levels; every level reaches 3:1 on the card.
HEAT = (TRACK, "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd")
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def _advance(character: str) -> float:
    if unicodedata.combining(character):
        return 0
    if unicodedata.east_asian_width(character) in {"W", "F"}:
        return 1.05
    if character in "W@%M":
        return 1
    if character in "ilI.,:;'!|`":
        return 0.34
    if character in " fjrt()[]":
        return 0.44
    return 0.7 if character.isupper() else 0.58


def text_width(text: str, size: float = BODY_SIZE, mono: bool = False) -> float:
    """Measure text conservatively: sans glyph advances, or monospace plus tracking."""
    if mono:
        return len(text) * (size * 0.6 + 1)
    return sum(_advance(character) for character in text) * size


def wrap_text(
    text: str, width: float, size: float = BODY_SIZE, mono: bool = False
) -> list[str]:
    """Wrap words, splitting long tokens without dropping any content."""
    lines, current = [], ""
    for word in str(text).split():
        candidate = f"{current} {word}" if current else word
        if text_width(candidate, size, mono) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        # a token too long for a line breaks after "/", "-", "_" or "." first,
        # and only splits between letters where no separator fits
        for piece in re.findall(r"[^/\-_.]+[/\-_.]*|[/\-_.]+", word):
            if current and text_width(current + piece, size, mono) > width:
                lines.append(current)
                current = ""
            for character in piece:
                if current and text_width(current + character, size, mono) > width:
                    lines.append(current)
                    current = ""
                current += character
    if current:
        lines.append(current)
    return lines


def _text(
    x: float,
    y: float,
    size: float,
    weight: int,
    color: str,
    text: str,
    mono: bool = False,
    anchor: str = "",
) -> str:
    font = f' font-family="{MONO}" letter-spacing="1"' if mono else ""
    align = f' text-anchor="{anchor}"' if anchor else ""
    return (
        f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" font-weight="{weight}" '
        f'fill="{color}"{font}{align}>{escape(text)}</text>'
    )


def _held(begin: float, dur: float) -> str:
    """Timing that runs from 0 s and holds the start value until begin, so the rest frame can be the finished one."""
    total = begin + dur
    return f'keyTimes="0;{begin / total:.3f};1" dur="{total:.2f}s" fill="freeze"'


def _enter(begin: float, body: str) -> str:
    """Fade in while rising 10px, once, then hold: the desktop cards' entrance, poster-safe."""
    times = _held(begin, FADE)
    return (
        f'<g><animate attributeName="opacity" values="0;0;1" {times}/>'
        f'<animateTransform attributeName="transform" type="translate" values="0 10;0 10;0 0" {times}/>'
        f"{body}</g>"
    )


def _draw(
    d: str,
    color: str,
    begin: float,
    dur: float = 0.6,
    width: float = 1,
    extra: str = "",
) -> str:
    """Draw a path in once; pathLength makes the dash its full length, drawn at rest."""
    return (
        f'<path d="{d}" stroke="{color}" stroke-width="{width:g}" fill="none" '
        f'pathLength="1" stroke-dasharray="1"{extra}>'
        f'<animate attributeName="stroke-dashoffset" values="1;1;0" {_held(begin, dur)}/></path>'
    )


def _pulse(cx: float, cy: float, color: str, r: float = 4) -> str:
    """Draw a ring that keeps widening and fading from a live point."""
    return (
        f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" stroke="{color}" stroke-width="1.5">'
        f'<animate attributeName="r" values="{r:g};{r + 7:g}" dur="2.4s" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values="0.9;0" dur="2.4s" repeatCount="indefinite"/></circle>'
    )


class Card:
    """One phone card: a column of staggered blocks inside the shared frame."""

    def __init__(self, label: str, accent: str = BLUE):
        """Start an empty card; label becomes its title and accessible name."""
        self.name, self.accent = label, accent
        self.parts: list[str] = []
        self.y: float = PAD
        self.begin = 0.15
        self._depth = 0

    @contextmanager
    def block(self, step: float = STAGGER) -> Iterator[None]:
        """Draw everything inside as one entrance, after the previous block."""
        start = len(self.parts)
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1
        if self._depth == 0 and len(self.parts) > start:
            body = "".join(self.parts[start:])
            del self.parts[start:]
            self.parts.append(_enter(self.begin, body))
            self.begin = min(self.begin + step, LAST_START)

    def lines(
        self,
        text: str,
        *,
        x: float = PAD,
        y: float | None = None,
        width: float = CONTENT_WIDTH,
        size: float = BODY_SIZE,
        color: str = WHITE,
        weight: int = 500,
        mono: bool = False,
    ) -> float:
        cursor = self.y if y is None else y
        with self.block():
            for line in wrap_text(text, width, size, mono):
                cursor += size
                self.parts.append(_text(x, cursor, size, weight, color, line, mono))
                cursor += size * LEADING
        if y is None:
            self.y = cursor
        return cursor

    def label(self, text: str, color: str | None = None) -> None:
        """Write a mono micro-label, the desktop cards' section marker."""
        self.lines(
            text.upper(), size=12, color=color or self.accent, weight=700, mono=True
        )
        self.y += 8

    def divider(self) -> None:
        self.y += 6
        with self.block():
            self.parts.append(
                _draw(f"M{PAD} {self.y:g}H{WIDTH - PAD}", BORDER, self.begin)
            )
        self.y += 14

    def row(
        self,
        title: str,
        detail: str = "",
        metadata: str = "",
        size: float = BODY_SIZE,
        *,
        bullet: bool = False,
        weight: int = 650,
    ) -> None:
        x = PAD + 14 if bullet else PAD
        width = WIDTH - PAD - x
        with self.block():
            if bullet:
                self.parts.append(
                    f'<circle cx="{PAD + 3}" cy="{self.y + size * 0.65:g}" r="2.5" fill="{self.accent}"/>'
                )
            self.lines(title, x=x, width=width, size=size, weight=weight)
            if metadata:
                self.y += 3
                self.lines(
                    metadata.upper(),
                    x=x,
                    width=width,
                    size=11.5,
                    color=self.accent,
                    weight=700,
                    mono=True,
                )
            if detail:
                self.y += 3
                self.lines(detail, x=x, width=width, size=13.5, color=MUTED)
        self.y += 12

    def metrics(self, items: list[tuple[str, str]], columns: int = 2) -> None:
        gap = 10
        tile = (CONTENT_WIDTH - gap * (columns - 1)) / columns
        inset = 10 if columns == 2 else 8
        inner = tile - 2 * inset
        value_size, label_size = (22, 12) if columns == 2 else (18, 11)
        for index in range(0, len(items), columns):
            group = items[index : index + columns]
            height = max(
                22
                + len(wrap_text(value, inner, value_size)) * value_size * (1 + LEADING)
                + len(wrap_text(label, inner, label_size)) * label_size * (1 + LEADING)
                for value, label in group
            )
            for column, (value, label) in enumerate(group):
                x = PAD + column * (tile + gap)
                with self.block():
                    self.parts.append(
                        f'<rect x="{x:g}" y="{self.y:g}" width="{tile:g}" '
                        f'height="{height:g}" rx="10" fill="{CARD}" stroke="{BORDER}"/>'
                    )
                    bottom = self.lines(
                        value,
                        x=x + inset,
                        y=self.y + 8,
                        width=inner,
                        size=value_size,
                        color=self.accent,
                        weight=750,
                    )
                    self.lines(
                        label,
                        x=x + inset,
                        y=bottom + 2,
                        width=inner,
                        size=label_size,
                        color=MUTED,
                    )
            self.y += height + gap

    def chips(self, labels: list[str], size: float = 13, mono: bool = False) -> None:
        x, line_bottom = float(PAD), self.y
        for label in labels:
            chip_width = min(CONTENT_WIDTH, text_width(label, size, mono) + 18)
            # 2px of slack so a label measured to fit never wraps inside its own chip
            rows = len(wrap_text(label, chip_width - 16, size, mono))
            chip_height = rows * size * (1 + LEADING) + 10
            if x + chip_width > WIDTH - PAD:
                x, self.y = float(PAD), line_bottom + 6
            with self.block(step=0.04):
                self.parts.append(
                    f'<rect x="{x:g}" y="{self.y:g}" width="{chip_width:g}" '
                    f'height="{chip_height:g}" rx="8" fill="{CARD}" stroke="{BORDER}"/>'
                )
                self.lines(
                    label,
                    x=x + 9,
                    y=self.y + 4,
                    width=chip_width - 16,
                    size=size,
                    mono=mono,
                )
            line_bottom = max(line_bottom, self.y + chip_height)
            x += chip_width + 6
        self.y = line_bottom + 12

    def pills(self, items: list[tuple[str, str]]) -> None:
        """Lay out mono status pills, the desktop profile strip's look, two to a row."""
        gap = 8
        width = (CONTENT_WIDTH - gap) / 2
        for index, (text, color) in enumerate(items):
            x = PAD + (index % 2) * (width + gap)
            top = self.y + (index // 2) * 34
            with self.block(step=0.06):
                self.parts.append(
                    f'<rect x="{x:g}" y="{top:g}" width="{width:g}" height="26" rx="13" '
                    f'fill="{color}14" stroke="{color}55"/>'
                    + _text(
                        x + width / 2, top + 17, 11, 700, color, text, True, "middle"
                    )
                )
        self.y += math.ceil(len(items) / 2) * 34 + 4

    def finish(self, defs: str = "", backdrop: str = "") -> str:
        height = int(self.y + PAD + 0.999)
        # skewX(-18) leans the shine left as it goes down, so tall cards travel further
        sweep = WIDTH + 280 + math.ceil(height * 0.33)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(self.name, quote=True)}">'
            f"<title>{escape(self.name)}</title>"
            f"<style>text{{font-family:{SANS};font-variant-numeric:tabular-nums}}</style>"
            '<defs><linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset="0.5" stop-color="#fff" stop-opacity="0.06"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<clipPath id="card"><rect x="1" y="1" width="{WIDTH - 2}" height="{height - 2}" rx="14"/></clipPath>{defs}</defs>'
            f'<rect x=".5" y=".5" width="{WIDTH - 1}" height="{height - 1}" rx="14" '
            f'fill="{BG}" stroke="{BORDER}"/>'
            + (f'<g clip-path="url(#card)">{backdrop}</g>' if backdrop else "")
            + f'<rect x="0" y="20" width="3" height="26" rx="1.5" fill="{self.accent}">'
            '<animate attributeName="opacity" values="1;0.4;1" dur="3s" repeatCount="indefinite"/></rect>'
            + "".join(self.parts)
            + f'<g clip-path="url(#card)"><rect x="-140" y="0" width="120" height="{height}" '
            'fill="url(#shine)" transform="skewX(-18)">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;{sweep} 0" '
            f'dur="7s" begin="{self.begin + 0.5:.2f}s" repeatCount="indefinite" additive="sum"/></rect></g>'
            "</svg>"
        )


def _number(value: object) -> str:
    if value is None or value == "":
        return MISSING
    return f"{value:,}" if isinstance(value, int) else str(value)


def _updated(card: Card, data: dict, source: str) -> None:
    updates = data.get("source_updated_at") or {}
    value = updates.get(source) if isinstance(updates, dict) else None
    if value:
        card.y += 4
        card.lines(
            f"UPDATED {str(value)[:10]}", size=11, color=MUTED, weight=700, mono=True
        )


def cert_status(certificate: dict, today: datetime.date) -> tuple[str, str]:
    """Classify a certification: active through its expiry day, unknown without an ISO date."""
    try:
        expires = datetime.date.fromisoformat(str(certificate.get("expiryDate") or ""))
    except ValueError:
        return "unknown", "Expiry not recorded"
    if expires < today:
        return "expired", f"Expired {expires.isoformat()}"
    return "active", f"Valid through {expires.isoformat()}"


def _rotating(
    card: Card, phrases: list[str], *, size: float, color: str, slot: float = 3.0
) -> None:
    """Let phrases take turns in one slot, as on the desktop hero; each may wrap."""
    wrapped = [wrap_text(phrase, CONTENT_WIDTH, size) for phrase in phrases]
    count, top = len(wrapped), card.y
    with card.block():
        for index, lines in enumerate(wrapped):
            a, d = index / count, (index + 1) / count
            b, c = a + 0.04, d - 0.04
            times = sorted(
                {0.0, round(a, 3), round(b, 3), round(c, 3), round(d, 3), 1.0}
            )
            values = ["1" if round(b, 3) <= t <= round(c, 3) else "0" for t in times]
            texts = "".join(
                _text(
                    PAD, top + size + row * size * (1 + LEADING), size, 500, color, line
                )
                for row, line in enumerate(lines)
            )
            # where SMIL does not run, the first phrase stands in for the set
            rest = "" if index == 0 else ' opacity="0"'
            card.parts.append(
                f'<g{rest}><animate attributeName="opacity" values="{";".join(values)}" '
                f'keyTimes="{";".join(f"{t:g}" for t in times)}" dur="{slot * count:g}s" '
                f'repeatCount="indefinite"/>{texts}</g>'
            )
    card.y = top + max(len(lines) for lines in wrapped) * size * (1 + LEADING)


def _live_pill(card: Card, label: str) -> None:
    width = text_width(label, 11.5, mono=True) + 40
    with card.block():
        card.parts.append(
            f'<rect x="{PAD}" y="{card.y:g}" width="{width:g}" height="26" rx="13" '
            f'fill="{GREEN}14" stroke="{GREEN}55"/>'
            f'<circle cx="{PAD + 15}" cy="{card.y + 13:g}" r="4" fill="{GREEN}">'
            '<animate attributeName="opacity" values="1;0.35;1" dur="1.8s" repeatCount="indefinite"/></circle>'
            + _text(PAD + 26, card.y + 17, 11.5, 700, GREEN, label, mono=True)
        )
    card.y += 26


def _node_graph(
    card: Card, nodes: list[tuple[int, int, str]], links: list[tuple[int, int]]
) -> None:
    """Draw the desktop hero's node graph, scaled to the phone column."""
    xs, ys = [x for x, _, _ in nodes], [y for _, y, _ in nodes]
    span_x, span_y = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
    top = card.y
    points = [
        (
            PAD + 20 + (x - min(xs)) / span_x * (CONTENT_WIDTH - 40),
            top + 20 + (y - min(ys)) / span_y * 84,
        )
        for x, y, _ in nodes
    ]
    hub = max(range(len(nodes)), key=lambda i: sum(i in link for link in links))
    with card.block():
        for a, b in links:
            (x1, y1), (x2, y2) = points[a], points[b]
            card.parts.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                'stroke="rgba(255,255,255,0.12)" stroke-width="1"/>'
            )
        spokes = [link for link in links if hub in link]
        for index, (a, b) in enumerate(spokes):
            (x1, y1), (x2, y2) = points[a], points[b]
            card.parts.append(
                # parked on its start node (under it) until it begins, not in the top-left corner
                f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="2.4" fill="{SKY}"><animateMotion dur="2.4s" begin="{index * 0.45:.2f}s" '
                f'repeatCount="indefinite" path="M0 0 L{x2 - x1:.1f} {y2 - y1:.1f}"/></circle>'
            )
        for index, ((x, y), (_, _, label)) in enumerate(zip(points, nodes)):
            r = 17 if index == hub else 13
            stroke = BLUE if index == hub else "rgba(255,255,255,0.16)"
            fill = f"{BLUE}26" if index == hub else CARD
            card.parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.3">'
                f'<animate attributeName="r" values="{r};{r + 1.5};{r}" dur="3s" begin="{index * 0.4:.1f}s" '
                'repeatCount="indefinite"/></circle>'
                + _text(
                    x,
                    y + 3.5,
                    10.5,
                    700,
                    BLUE if index == hub else "rgba(255,255,255,0.7)",
                    label,
                    mono=True,
                    anchor="middle",
                )
            )
    card.y = top + 124


HERO_DEFS = (
    '<pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">'
    '<path d="M24 0H0V24" fill="none" stroke="rgba(255,255,255,0.035)" stroke-width="1"/></pattern>'
    f'<linearGradient id="scan" x1="0" x2="1"><stop offset="0" stop-color="{SKY}" stop-opacity="0"/>'
    f'<stop offset="0.5" stop-color="{SKY}" stop-opacity="0.10"/><stop offset="1" stop-color="{SKY}" stop-opacity="0"/></linearGradient>'
)
HERO_BACKDROP = (
    f'<rect width="{WIDTH}" height="100%" fill="url(#grid)"/>'
    '<rect x="-160" y="0" width="160" height="100%" fill="url(#scan)">'
    f'<animateTransform attributeName="transform" type="translate" values="0 0;{WIDTH + 160} 0" '
    'dur="6s" repeatCount="indefinite"/></rect>'
)


def _hero(data: dict, context: dict) -> str:
    title = context.get("aws_title", "Cloud Consultant")
    card = Card(f"Sagar Gupta, {title} at AWS", SKY)
    card.lines("HI, I AM", size=12, color=BLUE, weight=700, mono=True)
    card.y += 4
    card.lines("Sagar Gupta", size=32, weight=800)
    card.y += 8
    card.lines(f"{title} at AWS", size=16, weight=650)
    card.y += 8
    phrases = context.get("hero_lines") or []
    if len(phrases) > 1:
        _rotating(card, phrases, size=14, color=MUTED)
    else:
        card.lines("DevOps · MLOps · AI agent tooling", size=14, color=MUTED)
    card.y += 14
    _live_pill(card, "BUILDING CLOUD AT AWS")
    card.y += 10
    card.lines("HYDERABAD, INDIA", size=11.5, color=MUTED, weight=700, mono=True)
    graph = context.get("hero_graph")
    if graph:
        _node_graph(card, *graph)
    return card.finish(HERO_DEFS, HERO_BACKDROP)


def _profile_badges(data: dict, context: dict) -> str:
    github, leetcode = data.get("github") or {}, data.get("leetcode") or {}
    card = Card("Profile at a glance")
    card.metrics(
        [
            (_number(data.get("views")), "Profile views"),
            (_number(github.get("followers")), "Followers"),
            (_number(github.get("stars")), "Total stars"),
            (
                _number(max(leetcode.get("history") or [leetcode.get("rating", 0)])),
                "Peak rating",
            ),
        ]
    )
    today = datetime.date.fromisoformat(context["today"])
    certificates = context.get("certifications", [])
    active = [c for c in certificates if cert_status(c, today)[0] == "active"]
    start_year, start_month = context.get("career_start", (2024, 8))
    years = today.year - start_year - (today.month < start_month)
    pills = [(f"{len(active)}x certified", SKY)] if certificates else []
    pills.append((f"{max(years, 0)}+ years at AWS", GREEN))
    if leetcode.get("badge"):
        pills.append((f"LeetCode {leetcode['badge']}", AMBER))
    pills.append(("sagargupta.online", BLUE))
    card.pills([(text.upper(), color) for text, color in pills])
    return card.finish().replace(
        'role="img"', f'role="img" data-active-certifications="{len(active)}"', 1
    )


def _intro(data: dict, context: dict) -> str:
    card = Card("About Sagar Gupta")
    card.label("About")
    card.lines(
        (data.get("portfolio") or {}).get("intro") or context.get("aws_title", ""),
        color="#d6dde5",
    )
    card.y += 12
    card.chips(["DevOps", "MLOps", "AWS cloud", "Full stack"])
    return card.finish()


def _experience(data: dict, context: dict) -> str:
    card = Card("Career and AWS customer engagements", GREEN)
    card.label("Career")
    milestones = context.get("milestones", [])
    last = len(milestones) - 1
    for index, (year, role, organization, city) in enumerate(milestones):
        with card.block():
            top = card.y
            card.parts.append(
                f'<circle cx="24" cy="{top + 9:g}" r="4" fill="{GREEN}"/>'
            )
            if index == last:
                card.parts.append(_pulse(24, top + 9, GREEN))
            bottom = card.lines(
                f"{year} · {role}", x=38, y=top, width=WIDTH - PAD - 38, weight=650
            )
            bottom = card.lines(
                f"{organization} · {city}",
                x=38,
                y=bottom + 2,
                width=WIDTH - PAD - 38,
                size=13,
                color=MUTED,
            )
            card.y = bottom + 14
            if index < last:
                rail = f"M24 {top + 17:g}V{card.y:g}"
                card.parts.append(
                    f'<path d="{rail}" stroke="{BORDER}"/>'
                    + _draw(
                        rail, GREEN, card.begin + 0.2, extra=' stroke-opacity="0.6"'
                    )
                )
    card.divider()
    card.label("Customer engagements")
    for when, client, role in reversed(context.get("engagements", [])):
        card.row(client, role, when)
    return card.finish()


def _publications(data: dict, context: dict) -> str:
    card = Card("Publications, talks and recognition", SKY)
    for index, (label, entries) in enumerate(context.get("publications", [])):
        if index:
            card.divider()
        card.label(label)
        for text, year in entries:
            text = text.replace("APG pattern:", "AWS Prescriptive Guidance pattern:")
            card.row(text, metadata=str(year), size=14, bullet=True, weight=500)
    return card.finish()


def _education(data: dict, context: dict) -> str:
    card = Card("Education")
    for entry in (data.get("portfolio") or {}).get("education", [])[:2]:
        details = [entry.get("institution", ""), entry.get("location", "")]
        if entry.get("cgpa"):
            details.append(f"CGPA {entry['cgpa']}")
        card.row(
            entry.get("title", ""),
            " · ".join(d for d in details if d),
            entry.get("date", ""),
        )
    return card.finish()


def _oss(data: dict, context: dict) -> str:
    entries = (data.get("portfolio") or {}).get("oss", [])
    merged = [entry for entry in entries if entry.get("status") == "merged"]
    opened = [entry for entry in entries if entry.get("status") == "open"]
    repositories = sorted({entry["repo"] for entry in merged})
    reach = sum(
        data.get("oss_stars", {}).get(repository, 0) for repository in repositories
    )
    card = Card("Open source contributions", GREEN)
    card.metrics(
        [
            (str(len(merged)), "Merged upstream"),
            (str(len(opened)), "Open PRs"),
            (str(len(repositories)), "Repos with merges"),
            (
                f"{reach // 1000}K+" if reach >= 1000 else str(reach),
                "Combined repo stars",
            ),
        ]
    )
    card.label("Merged into", GREEN)
    card.chips(repositories, size=11.5, mono=True)
    _updated(card, data, "portfolio")
    return card.finish()


def _oss_list(data: dict, status: str) -> str:
    entries = [
        entry
        for entry in (data.get("portfolio") or {}).get("oss", [])
        if entry.get("status") == status
    ]
    merged = status == "merged"
    label = "Merged upstream" if merged else "Open PRs"
    if merged:
        entries.sort(key=lambda entry: entry.get("merged_at") or "", reverse=True)
    shown = MERGED_SHOWN if merged else OPEN_SHOWN
    card = Card(f"{len(entries)} {label}", GREEN if merged else AMBER)
    card.label(f"{len(entries)} {label}")
    for index, entry in enumerate(entries[:shown]):
        if index:
            card.divider()
        number = entry.get("url", "").rstrip("/").rsplit("/", 1)[-1]
        metadata = f"PR #{number}" if number.isdigit() else ""
        if merged and entry.get("merged_at"):
            metadata += f" · {entry['merged_at'][:10]}"
        card.row(entry.get("repo", ""), entry.get("title", ""), metadata, size=14)
    if len(entries) > shown:
        card.lines(
            f"+{len(entries) - shown} more on GitHub →",
            size=14,
            color=card.accent,
            weight=650,
        )
        card.y += 4
    if not merged:
        card.divider()
        card.label("Community impact")
        card.lines(
            "Fixed the AWS Ansible deploy and Elastic IP allocation in forem/selfhost, "
            "plus 3 accepted answers on GitHub Community Q&A.",
            size=13.5,
            color=MUTED,
        )
    _updated(card, data, "portfolio")
    return card.finish()


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
                f'<g><animate attributeName="opacity" values="0;0;1" '
                f'{_held(card.begin + column * 0.05, 0.3)}/>{cells}</g>'
            )
    card.y = top + 7 * step + 10


def _language_bar(card: Card, languages: list[list]) -> None:
    """Draw GitHub's stacked language bar, revealed left to right, with a legend."""
    total = sum(percent for _, percent, _ in languages) or 1
    colors = [
        color if HEX_COLOR.fullmatch(color or "") else MUTED for *_, color in languages
    ]
    top, x = card.y, float(PAD)
    segments = []
    for (_, percent, _), color in zip(languages, colors):
        width = CONTENT_WIDTH * percent / total
        segments.append(
            f'<rect x="{x:.1f}" y="{top:g}" width="{width:.1f}" height="8" fill="{color}"/>'
        )
        x += width
    with card.block():
        card.parts.append(
            f'<clipPath id="langs"><rect x="{PAD}" y="{top:g}" width="{CONTENT_WIDTH}" height="8" rx="4">'
            f'<animate attributeName="width" values="0;{CONTENT_WIDTH}" begin="{card.begin:.2f}s" '
            'dur="1s" fill="freeze"/></rect></clipPath>'
            f'<g clip-path="url(#langs)">{"".join(segments)}</g>'
        )
        for index, ((name, percent, _), color) in enumerate(zip(languages, colors)):
            lx = PAD + (index % 2) * (CONTENT_WIDTH / 2)
            ly = top + 28 + (index // 2) * 22
            card.parts.append(
                f'<circle cx="{lx + 5:g}" cy="{ly - 4:g}" r="4" fill="{color}"/>'
                + _text(lx + 15, ly, 13, 500, MUTED, f"{name} {percent:g}%")
            )
    card.y = top + 28 + math.ceil(len(languages) / 2) * 22


def _github(data: dict, context: dict) -> str:
    github = data.get("github") or {}
    card = Card("GitHub activity")
    card.label("GitHub activity")
    card.metrics(
        [
            (_number(github.get(key)), label)
            for key, label in [
                ("contributions", "Contributions"),
                ("commits", "Commits"),
                ("prs", "Pull requests"),
                ("stars", "Stars"),
                ("streak", "Current streak"),
                ("longest", "Longest streak"),
            ]
        ],
        columns=3,
    )
    calendar = github.get("calendar") or []
    if calendar:
        card.label("Last 20 weeks")
        _heatmap(card, calendar[-20:])
    if github.get("active_days"):
        card.lines(
            f"{github['active_days']} active days in the last year",
            size=13,
            color=MUTED,
        )
        card.y += 14
    languages = github.get("languages") or []
    if languages:
        card.label("Top languages")
        _language_bar(card, languages)
    _updated(card, data, "github")
    return card.finish()


def _rating_chart(card: Card, history: list[float]) -> None:
    if len(history) < 2:
        return
    card.label("Contest rating history", AMBER)
    low, high = min(history), max(history)
    left, right = PAD + 40, WIDTH - PAD - 6
    top, bottom = card.y + 6, card.y + 112
    with card.block():
        for value, y in [(high, top), (low, bottom)]:
            card.parts.append(
                _text(PAD, y + 4, 11.5, 700, MUTED, str(round(value)), mono=True)
                + f'<path d="M{left} {y:g}H{right}" stroke="{BORDER}"/>'
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
            _draw(path, AMBER, card.begin, 1.6, 2, ' stroke-linejoin="round"')
        )
        x, y = points[-1]
        card.parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{AMBER}"/>'
            + _pulse(x, y, AMBER, 3)
        )
    card.y = bottom + 14
    card.lines(
        f"Peak {round(high):,} · {len(history)} rated contests", size=13, color=MUTED
    )


def _leetcode(data: dict, context: dict) -> str:
    leetcode = data.get("leetcode") or {}
    card = Card("LeetCode coding and contest statistics", AMBER)
    card.label(f"LeetCode · {leetcode.get('badge', '')}".rstrip(" ·"))
    card.metrics(
        [
            (_number(leetcode.get("rating")), "Contest rating"),
            (
                f"{leetcode['top']}%" if leetcode.get("top") is not None else MISSING,
                "Top worldwide",
            ),
            (_number(leetcode.get("solved")), "Problems solved"),
            (_number(leetcode.get("contests")), "Contests"),
        ]
    )
    colors = {"Easy": GREEN, "Medium": AMBER, "Hard": RED}
    for label, (solved, total) in (leetcode.get("by_difficulty") or {}).items():
        with card.block():
            card.lines(f"{label} · {solved:,} / {total:,}", size=13, color=MUTED)
            card.y += 2
            fill = CONTENT_WIDTH * min(solved / total, 1) if total else 0
            card.parts.append(
                f'<rect x="{PAD}" y="{card.y:g}" width="{CONTENT_WIDTH}" height="6" rx="3" fill="{TRACK}"/>'
                f'<rect x="{PAD}" y="{card.y:g}" width="{fill:.1f}" height="6" rx="3" fill="{colors.get(label, BLUE)}">'
                f'<animate attributeName="width" values="0;{fill:.1f}" begin="{card.begin:.2f}s" '
                'dur="0.9s" fill="freeze"/></rect>'
            )
            card.y += 16
    card.y += 6
    _rating_chart(card, leetcode.get("history") or [])
    _updated(card, data, "leetcode")
    return card.finish()


def _normal_name(name: str) -> str:
    return re.sub(r"\s+", " ", DASHES.sub("-", name)).casefold()


def _badge_grid(card: Card, badges: list[tuple[str, str]]) -> None:
    """Lay the Credly badge images out in a grid; each floats like the desktop gallery."""
    cell = CONTENT_WIDTH / BADGE_COLUMNS
    for index, (name, image) in enumerate(badges):
        column, row = index % BADGE_COLUMNS, index // BADGE_COLUMNS
        x = PAD + column * cell + (cell - BADGE_SIZE) / 2
        y = card.y + row * (BADGE_SIZE + 12)
        with card.block(step=0.04):
            card.parts.append(
                f"<g><title>{escape(name)}</title>"
                f'<animateTransform attributeName="transform" type="translate" values="0 0;0 -3;0 0" '
                f'dur="4s" begin="{index * 0.2:.1f}s" repeatCount="indefinite"/>'
                f'<image href="{image}" x="{x:.1f}" y="{y:g}" width="{BADGE_SIZE}" '
                f'height="{BADGE_SIZE}"/></g>'
            )
    rows = math.ceil(len(badges) / BADGE_COLUMNS)
    card.y += rows * (BADGE_SIZE + 12)


def _certification_list(card: Card, context: dict) -> None:
    """List certifications by status, then the other badges, when no images are known."""
    certificates = context.get("certifications", [])
    today = datetime.date.fromisoformat(context["today"])
    groups = [
        ("active", "Active certifications"),
        ("expired", "Previously earned"),
        ("unknown", "Expiry not recorded"),
    ]
    for status, label in groups:
        entries = [
            (certificate, detail)
            for certificate in certificates
            for state, detail in [cert_status(certificate, today)]
            if state == status
        ]
        if not entries:
            continue
        if card.y > PAD:
            card.divider()
        card.label(label)
        for certificate, detail in entries:
            card.row(certificate["name"], metadata=detail, size=14)
    known = {_normal_name(certificate["name"]) for certificate in certificates}
    badge_names = list(
        dict.fromkeys(
            name
            for name, _url in context.get("badges", [])
            if _normal_name(name) not in known
        )
    )
    if badge_names:
        card.divider()
        card.label("Professional & training badges")
        card.chips(badge_names, size=12.5)


def _certifications(data: dict, context: dict) -> str:
    card = Card("Certifications and professional badges", SKY)
    images = context.get("badge_images") or []
    if images:
        card.label(f"{len(images)} Credly badges")
        _badge_grid(card, images)
    else:
        _certification_list(card, context)
    return card.finish()


def _competitive(data: dict, context: dict) -> str:
    portfolio = data.get("portfolio") or {}
    stats = portfolio.get("coding_stats") or {}
    card = Card("Competitive programming results", AMBER)
    card.label("Competitive programming")
    best_rank = stats.get("leetcode", {}).get("best_contest_rank")
    metrics = [
        (f"#{best_rank}" if best_rank else MISSING, "LeetCode best rank"),
        (
            _number(stats.get("geeksforgeeks", {}).get("problems_solved")),
            "GeeksforGeeks solved",
        ),
        (
            _number(stats.get("hackerrank", {}).get("problem_solving")),
            "HackerRank problem solving",
        ),
    ]
    kickstart = next(
        (
            entry
            for entry in portfolio.get("contests", [])
            if "Round E" in entry.get("title", "")
        ),
        None,
    )
    if kickstart and (rank := re.search(r"Rank (\d+)", kickstart["title"])):
        metrics.append((f"#{rank.group(1)}", "Kick Start 2022 Round E"))
    card.metrics(metrics)
    podium = [
        entry
        for entry in portfolio.get("contests", [])
        if re.match(r"(1st|2nd|3rd|4th) Place", entry.get("title", ""))
    ]
    if podium:
        card.label("Podium finishes")
        for entry in podium:
            card.row(
                entry["title"],
                metadata=" · ".join(
                    part for part in (entry.get("date"), entry.get("organizer")) if part
                ),
                size=14,
            )
    return card.finish()


def _certification_status(data: dict, context: dict) -> str:
    certificates = context.get("certifications", [])
    today = datetime.date.fromisoformat(context["today"])
    statuses = [(c, *cert_status(c, today)) for c in certificates]
    active = sum(1 for _, status, _ in statuses if status == "active")
    unknown = any(status == "unknown" for _, status, _ in statuses)
    card = Card(f"{active} active certifications", SKY)
    card.label("Certification status")
    card.metrics(
        [
            (str(active), "Active certifications"),
            (
                str(len(statuses) - active),
                "Expired or unrecorded" if unknown else "Previously earned",
            ),
        ]
    )
    for certificate, status, detail in statuses:
        if status != "active":
            card.row(certificate["name"], metadata=detail, size=14)
    card.lines(
        "The Credly gallery below also includes learning and partner badges.",
        size=12.5,
        color=MUTED,
    )
    return card.finish().replace(
        'role="img"', f'role="img" data-active-certifications="{active}"', 1
    )


def _get_card(name: str) -> str:
    card = Card(f"Get the {name} for your own profile")
    card.lines(f"Get the {name} →", size=14, color=BLUE, weight=650)
    card.lines("Add it to your own profile README.", size=12, color=MUTED)
    return card.finish()


def _footer(data: dict, context: dict) -> str:
    card = Card(
        f"Thanks for visiting. Explore Sagar Gupta's portfolio. {context.get('disclaimer', '')}".strip()
    )
    card.label("Thanks for visiting")
    card.lines("Explore the projects and the work behind them.", color=MUTED)
    card.y += 10
    card.lines("Visit my portfolio →", size=16, weight=700)
    card.lines("SAGARGUPTA.ONLINE", size=11.5, color=BLUE, weight=700, mono=True)
    if context.get("disclaimer"):
        card.y += 10
        card.lines(context["disclaimer"], size=12, color=MUTED)
    return card.finish()


def _header(number: str, title: str, subtitle: str, theme: str) -> str:
    card = Card(title)
    color = "#1d4ed8" if theme == "light" else BLUE
    edge = "#0284c7" if theme == "light" else SKY
    foreground = "#17212b" if theme == "light" else WHITE
    rule = "rgba(11,16,18,0.12)" if theme == "light" else "rgba(255,255,255,0.10)"
    card.y = 10
    card.lines(
        f"{number}  /  {subtitle.upper()}",
        size=11.5,
        color=color,
        weight=700,
        mono=True,
    )
    card.y += 2
    card.lines(title, size=20, weight=750, color=foreground)
    height = int(card.y + 14)
    # the desktop header's accent bar and the light that runs along its rule
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(title, quote=True)}">'
        f"<style>text{{font-family:{SANS}}}</style>"
        f'<defs><linearGradient id="sweep" x1="0" x2="1"><stop offset="0" stop-color="{edge}" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="{color}"/><stop offset="1" stop-color="{edge}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect x="0" y="12" width="4" height="{card.y - 14:g}" rx="2" fill="{color}"/>'
        + "".join(card.parts)
        + f'<line x1="0" y1="{height - 4}" x2="{WIDTH}" y2="{height - 4}" stroke="{rule}" stroke-width="1"/>'
        f'<rect x="-120" y="{height - 5}" width="120" height="2" fill="url(#sweep)">'
        f'<animateTransform attributeName="transform" type="translate" values="0 0;{WIDTH + 120} 0" '
        'dur="3.6s" repeatCount="indefinite"/></rect></svg>'
    )


def render_mobile_cards(data: dict, context: dict) -> dict[str, str]:
    """Render phone variants from supplied data without file or network access."""
    renderers = {
        "hero": _hero,
        "profile-badges": _profile_badges,
        "intro": _intro,
        "experience": _experience,
        "publications": _publications,
        "education": _education,
        "oss": _oss,
        "github": _github,
        "leetcode": _leetcode,
        "certs": _certifications,
        "competitive": _competitive,
        "footer": _footer,
    }
    cards = {
        f"{name}-mobile.svg": renderer(data, context)
        for name, renderer in renderers.items()
    }
    cards["certs-status-mobile.svg"] = _certification_status(data, context)
    for key, name in context.get("get_cards", []):
        cards[f"get-{key}-mobile.svg"] = _get_card(name)
    cards["oss-merged-mobile.svg"] = _oss_list(data, "merged")
    cards["oss-review-mobile.svg"] = _oss_list(data, "open")
    for key, number, title, subtitle in context.get("headers", []):
        for theme in ("dark", "light"):
            cards[f"header-{key}-{theme}-mobile.svg"] = _header(
                number, title, subtitle, theme
            )
    return cards
