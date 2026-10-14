"""Self-contained 320px SVG layouts selected by README picture sources.

The phone cards move like the desktop ones: blocks fade and rise into place in
order, accents pulse, a shine sweeps each card, timelines and charts draw in.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
from __future__ import annotations

import datetime
import math
import re
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from html import escape

WIDTH, PAD, BODY_SIZE = 320, 20, 17
CONTENT_WIDTH = WIDTH - PAD * 2
BG, CARD, WHITE = "#0b1012", "#0f171c", "#f3f4f6"
MUTED, BLUE, SKY = "#b1bfcc", "#60a5fa", "#38bdf8"
GREEN, AMBER, BORDER = "#4ade80", "#fbbf24", "#26343d"
RED, TRACK = "#f87171", "#1b2630"
SANS = "'Segoe UI',-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
MISSING = "-"
# Credly separates "Developer" and "Associate" with an en dash (U+2013) where
# the portfolio has a hyphen; em dashes (U+2014) are folded the same way.
DASHES = re.compile(f"[{chr(0x2013)}{chr(0x2014)}]")
# Each block starts STAGGER after the previous one; LAST_START caps the delay
# so a long card has finished drawing within a few seconds.
STAGGER, FADE, LAST_START = 0.1, 0.45, 2.4
# Empty day, then four levels; every level reaches 3:1 on the card.
HEAT = (TRACK, "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd")


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
    return 0.76 if character.isupper() else 0.64


def text_width(text: str, size: float = BODY_SIZE) -> float:
    """Conservative sans-serif glyph advances for portable line wrapping."""
    return sum(_advance(character) for character in text) * size


def wrap_text(text: str, width: float, size: float = BODY_SIZE) -> list[str]:
    """Wrap words, splitting long tokens without dropping any content."""
    lines, current = [], ""
    for word in str(text).split():
        candidate = f"{current} {word}" if current else word
        if text_width(candidate, size) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        for character in word:
            if current and text_width(current + character, size) > width:
                lines.append(current)
                current = ""
            current += character
    if current:
        lines.append(current)
    return lines


def _text(x: float, y: float, size: float, weight: int, color: str, text: str) -> str:
    return (
        f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" '
        f'font-weight="{weight}" fill="{color}">{escape(text)}</text>'
    )


def _enter(begin: float, body: str) -> str:
    """Fade in while rising 10px, once, then hold: the desktop cards' entrance."""
    return (
        f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{begin:.2f}s" dur="{FADE}s" fill="freeze"/>'
        f'<animateTransform attributeName="transform" type="translate" from="0 10" to="0 0" '
        f'begin="{begin:.2f}s" dur="{FADE}s" fill="freeze"/>{body}</g>'
    )


def _draw(
    d: str,
    color: str,
    begin: float,
    dur: float = 0.6,
    width: float = 1,
    extra: str = "",
) -> str:
    """A path that draws itself in once; pathLength makes the dash its full length."""
    return (
        f'<path d="{d}" stroke="{color}" stroke-width="{width:g}" fill="none" '
        f'pathLength="1" stroke-dasharray="1"{extra}>'
        f'<animate attributeName="stroke-dashoffset" values="1;0" begin="{begin:.2f}s" '
        f'dur="{dur:g}s" fill="freeze"/></path>'
    )


def _pulse(cx: float, cy: float, color: str, r: float = 4) -> str:
    """A ring that keeps widening and fading from a live point."""
    return (
        f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="none" stroke="{color}" stroke-width="1.5">'
        f'<animate attributeName="r" values="{r:g};{r + 7:g}" dur="2.4s" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values="0.9;0" dur="2.4s" repeatCount="indefinite"/></circle>'
    )


class Card:
    def __init__(self, label: str, accent: str = BLUE):
        self.label, self.accent = label, accent
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
    ) -> float:
        cursor = self.y if y is None else y
        with self.block():
            for line in wrap_text(text, width, size):
                cursor += size
                self.parts.append(_text(x, cursor, size, weight, color, line))
                cursor += size * 0.42
        if y is None:
            self.y = cursor
        return cursor

    def title(self, text: str) -> None:
        self.lines(text, size=20, color=self.accent, weight=700)
        self.y += 12

    def divider(self) -> None:
        self.y += 8
        with self.block():
            self.parts.append(
                _draw(f"M{PAD} {self.y:g}H{WIDTH - PAD}", BORDER, self.begin)
            )
        self.y += 16

    def row(self, title: str, detail: str = "", metadata: str = "") -> None:
        with self.block():
            self.lines(title, weight=650)
            if metadata:
                self.y += 4
                self.lines(metadata, size=15, color=self.accent)
            if detail:
                self.y += 5
                self.lines(detail, color=MUTED)
        self.y += 16

    def metrics(self, items: list[tuple[str, str]]) -> None:
        gap, tile_width = 12, (CONTENT_WIDTH - 12) / 2
        inner = tile_width - 20
        for index in range(0, len(items), 2):
            pair = items[index : index + 2]
            height = max(
                24
                + len(wrap_text(value, inner, 26)) * 26 * 1.42
                + len(wrap_text(label, inner, 15)) * 15 * 1.42
                for value, label in pair
            )
            for column, (value, label) in enumerate(pair):
                x = PAD + column * (tile_width + gap)
                with self.block():
                    self.parts.append(
                        f'<rect x="{x:g}" y="{self.y:g}" width="{tile_width:g}" '
                        f'height="{height:g}" rx="10" fill="{CARD}" stroke="{BORDER}"/>'
                    )
                    bottom = self.lines(
                        value,
                        x=x + 10,
                        y=self.y + 10,
                        width=inner,
                        size=26,
                        color=self.accent,
                        weight=750,
                    )
                    self.lines(
                        label,
                        x=x + 10,
                        y=bottom + 4,
                        width=inner,
                        size=15,
                        color=MUTED,
                    )
            self.y += height + gap

    def chips(self, labels: list[str]) -> None:
        x, line_bottom = float(PAD), self.y
        for label in labels:
            chip_width = min(CONTENT_WIDTH, text_width(label, 16) + 20)
            chip_height = len(wrap_text(label, chip_width - 20, 16)) * 23 + 16
            if x + chip_width > WIDTH - PAD:
                x, self.y = float(PAD), line_bottom + 8
            with self.block(step=0.04):
                self.parts.append(
                    f'<rect x="{x:g}" y="{self.y:g}" width="{chip_width:g}" '
                    f'height="{chip_height:g}" rx="8" fill="{CARD}" stroke="{BORDER}"/>'
                )
                self.lines(
                    label, x=x + 10, y=self.y + 7, width=chip_width - 20, size=16
                )
            line_bottom = max(line_bottom, self.y + chip_height)
            x += chip_width + 8
        self.y = line_bottom + 12

    def finish(self, defs: str = "", backdrop: str = "") -> str:
        height = int(self.y + PAD + 0.999)
        # skewX(-18) leans the shine left as it goes down, so tall cards travel further
        sweep = WIDTH + 280 + math.ceil(height * 0.33)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(self.label, quote=True)}">'
            f"<title>{escape(self.label)}</title>"
            f"<style>text{{font-family:{SANS};font-variant-numeric:tabular-nums}}</style>"
            '<defs><linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset="0.5" stop-color="#fff" stop-opacity="0.06"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<clipPath id="card"><rect x="1" y="1" width="{WIDTH - 2}" height="{height - 2}" rx="14"/></clipPath>{defs}</defs>'
            f'<rect x=".5" y=".5" width="{WIDTH - 1}" height="{height - 1}" rx="14" '
            f'fill="{BG}" stroke="{BORDER}"/>'
            + (f'<g clip-path="url(#card)">{backdrop}</g>' if backdrop else "")
            + f'<rect x="0" y="22" width="3" height="28" rx="1.5" fill="{self.accent}">'
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
        card.y += 6
        card.lines(f"Updated {str(value)[:10]}", size=14, color=MUTED)


def cert_status(certificate: dict, today: datetime.date) -> tuple[str, str]:
    """The one expiry rule for every card and count: active through the expiry
    day; anything without a valid ISO date is unknown, never active."""
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
    """Phrases take turns in one slot, as on the desktop hero; each may wrap."""
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
                _text(PAD, top + size + row * size * 1.42, size, 500, color, line)
                for row, line in enumerate(lines)
            )
            card.parts.append(
                f'<g opacity="0"><animate attributeName="opacity" values="{";".join(values)}" '
                f'keyTimes="{";".join(f"{t:g}" for t in times)}" dur="{slot * count:g}s" '
                f'repeatCount="indefinite"/>{texts}</g>'
            )
    card.y = top + max(len(lines) for lines in wrapped) * size * 1.42


def _live_pill(card: Card, label: str) -> None:
    width = len(label) * 7.6 + 44
    with card.block():
        card.parts.append(
            f'<rect x="{PAD}" y="{card.y:g}" width="{width:g}" height="28" rx="14" '
            f'fill="{GREEN}14" stroke="{GREEN}55"/>'
            f'<circle cx="{PAD + 16}" cy="{card.y + 14:g}" r="4" fill="{GREEN}">'
            '<animate attributeName="opacity" values="1;0.35;1" dur="1.8s" repeatCount="indefinite"/></circle>'
            f'<text x="{PAD + 28}" y="{card.y + 18:g}" font-size="11" font-weight="700" '
            f'font-family="{MONO}" letter-spacing="1" fill="{GREEN}">{escape(label)}</text>'
        )
    card.y += 28


def _node_graph(
    card: Card, nodes: list[tuple[int, int, str]], links: list[tuple[int, int]]
) -> None:
    """The desktop hero's node graph, scaled to the phone column."""
    xs, ys = [x for x, _, _ in nodes], [y for _, y, _ in nodes]
    span_x, span_y = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
    top = card.y
    points = [
        (
            PAD + 22 + (x - min(xs)) / span_x * (CONTENT_WIDTH - 44),
            top + 22 + (y - min(ys)) / span_y * 96,
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
                f'<circle r="2.4" fill="{SKY}"><animateMotion dur="2.4s" begin="{index * 0.45:.2f}s" '
                f'repeatCount="indefinite" path="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}"/></circle>'
            )
        for index, ((x, y), (_, _, label)) in enumerate(zip(points, nodes)):
            r = 18 if index == hub else 14
            stroke = f"{BLUE}dd" if index == hub else "rgba(255,255,255,0.16)"
            fill = f"{BLUE}26" if index == hub else CARD
            card.parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.3">'
                f'<animate attributeName="r" values="{r};{r + 1.5};{r}" dur="3s" begin="{index * 0.4:.1f}s" '
                'repeatCount="indefinite"/></circle>'
                f'<text x="{x:.1f}" y="{y + 3.5:.1f}" text-anchor="middle" font-size="9" font-weight="700" '
                f'font-family="{MONO}" letter-spacing="1" '
                f'fill="{BLUE if index == hub else "rgba(255,255,255,0.7)"}">{escape(label)}</text>'
            )
    card.y = top + 140


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
    card.lines("HI, I AM", size=15, color=BLUE, weight=700)
    card.y += 8
    card.lines("Sagar Gupta", size=34, weight=750)
    card.y += 12
    card.lines(f"{title} at AWS", weight=650)
    card.y += 12
    phrases = context.get("hero_lines") or []
    if len(phrases) > 1:
        _rotating(card, phrases, size=16, color=MUTED)
    else:
        card.lines("DevOps · MLOps · AI agent tooling", color=MUTED)
    card.y += 16
    _live_pill(card, "BUILDING CLOUD AT AWS")
    card.y += 10
    card.lines("Hyderabad, India", size=15, color=MUTED)
    graph = context.get("hero_graph")
    if graph:
        card.y += 4
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
    if certificates:
        card.lines(
            f"{len(active)} active certifications", size=16, color=SKY, weight=650
        )
    start_year, start_month = context.get("career_start", (2024, 8))
    years = today.year - start_year - (today.month < start_month)
    card.lines(f"{max(years, 0)}+ years at AWS", size=16, color=GREEN)
    if leetcode.get("badge"):
        card.lines(f"LeetCode {leetcode['badge']}", size=16, color=AMBER)
    card.lines("sagargupta.online", size=16, color=BLUE)
    return card.finish().replace(
        'role="img"', f'role="img" data-active-certifications="{len(active)}"', 1
    )


def _intro(data: dict, context: dict) -> str:
    card = Card("About Sagar Gupta")
    card.title("About")
    card.lines(
        (data.get("portfolio") or {}).get("intro") or context.get("aws_title", "")
    )
    card.divider()
    card.chips(["DevOps", "MLOps", "AWS cloud", "Full stack"])
    return card.finish()


def _experience(data: dict, context: dict) -> str:
    card = Card("Career and AWS customer engagements", GREEN)
    card.title("Career")
    milestones = context.get("milestones", [])
    last = len(milestones) - 1
    for index, (year, role, organization, city) in enumerate(milestones):
        with card.block():
            top = card.y
            card.parts.append(
                f'<circle cx="24" cy="{top + 10:g}" r="4" fill="{GREEN}"/>'
            )
            if index == last:
                card.parts.append(_pulse(24, top + 10, GREEN))
            bottom = card.lines(
                f"{year} · {role}", x=38, y=top, width=WIDTH - PAD - 38, weight=650
            )
            bottom = card.lines(
                f"{organization} · {city}",
                x=38,
                y=bottom + 3,
                width=WIDTH - PAD - 38,
                size=16,
                color=MUTED,
            )
            card.y = bottom + 20
            if index < last:
                rail = f"M24 {top + 18:g}V{card.y:g}"
                card.parts.append(
                    f'<path d="{rail}" stroke="{BORDER}"/>'
                    + _draw(
                        rail, GREEN, card.begin + 0.2, extra=' stroke-opacity="0.6"'
                    )
                )
    card.divider()
    card.title("Customer engagements")
    for when, client, role in reversed(context.get("engagements", [])):
        card.row(client, role, when)
    return card.finish()


def _highlights(data: dict, context: dict) -> str:
    portfolio = data.get("portfolio") or {}
    ambassador = next(
        (
            match.group(1)
            for achievement in portfolio.get("achievements", [])
            if (match := re.match(r"(\d+)x TFC", achievement.get("title", "")))
        ),
        None,
    )
    items = [
        ("10/10", "State Street client satisfaction"),
        ("~90%", "Faster account setup"),
        (str(len(portfolio.get("samples", []))), "Published AWS samples"),
    ]
    if ambassador:
        items.append((f"{ambassador}x", "TFC ambassador"))
    card = Card("Highlights from AWS work", GREEN)
    card.metrics(items)
    return card.finish()


def _worked_with(data: dict, context: dict) -> str:
    card = Card("Organizations and roles", GREEN)
    card.title("Worked with")
    for company, role in context.get("worked_with", []):
        card.row(company, role)
    return card.finish()


def _publications(data: dict, context: dict) -> str:
    card = Card("Publications, talks and recognition", SKY)
    for index, (label, entries) in enumerate(context.get("publications", [])):
        if index:
            card.divider()
        card.title(label.capitalize() if label.isupper() else label)
        for text, year in entries:
            text = text.replace("APG pattern:", "AWS Prescriptive Guidance pattern:")
            card.row(text, metadata=str(year))
    return card.finish()


def _education(data: dict, context: dict) -> str:
    card = Card("Education")
    card.title("Education")
    for entry in (data.get("portfolio") or {}).get("education", [])[:2]:
        card.row(
            entry.get("title", ""), entry.get("institution", ""), entry.get("date", "")
        )
        if entry.get("location"):
            card.lines(entry["location"], size=16, color=MUTED)
        if entry.get("cgpa"):
            card.lines(f"CGPA {entry['cgpa']}", size=16, color=SKY, weight=650)
        achievements = entry.get("achievements") or []
        if achievements:
            card.lines(
                achievements[0].removeprefix("Passed with "), size=16, color=MUTED
            )
        card.y += 20
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
    card.title("Open source")
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
    card.lines("Merged into", size=16, color=GREEN, weight=650)
    card.y += 8
    for repository in repositories:
        card.lines(repository, size=16, color=MUTED)
    _updated(card, data, "portfolio")
    return card.finish()


def _oss_list(data: dict, status: str) -> str:
    entries = [
        entry
        for entry in (data.get("portfolio") or {}).get("oss", [])
        if entry.get("status") == status
    ]
    label = "Merged upstream" if status == "merged" else "Open PRs"
    if status == "merged":
        entries.sort(key=lambda entry: entry.get("merged_at") or "", reverse=True)
    card = Card(f"{len(entries)} {label}", GREEN if status == "merged" else AMBER)
    card.title(f"{len(entries)} {label}")
    for index, entry in enumerate(entries):
        if index:
            card.divider()
        number = entry.get("url", "").rstrip("/").rsplit("/", 1)[-1]
        metadata = f"PR #{number}" if number.isdigit() else ""
        if status == "merged" and entry.get("merged_at"):
            metadata += f" · {entry['merged_at'][:10]}"
        card.row(entry.get("repo", ""), entry.get("title", ""), metadata)
    if status == "open":
        card.divider()
        card.lines("Community impact", color=AMBER, weight=650)
        card.y += 8
        card.lines(
            "Fixed the AWS Ansible deploy and Elastic IP allocation in forem/selfhost, "
            "plus 3 accepted answers on GitHub Community Q&A.",
            color=MUTED,
        )
    _updated(card, data, "portfolio")
    return card.finish()


def _level(count: int, cuts: list[int]) -> int:
    return 0 if count == 0 else 1 + sum(1 for cut in cuts if count > cut)


def _heatmap(card: Card, weeks: list[list[int]]) -> None:
    """Recent contribution weeks that fill in column by column."""
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
                f'<g opacity="0"><animate attributeName="opacity" to="1" '
                f'begin="{card.begin + column * 0.05:.2f}s" dur="0.3s" fill="freeze"/>{cells}</g>'
            )
    card.y = top + 7 * step + 8


def _github(data: dict, context: dict) -> str:
    github = data.get("github") or {}
    card = Card("GitHub activity")
    card.title("GitHub activity")
    card.metrics(
        [
            (_number(github.get(key)), label)
            for key, label in [
                ("contributions", "Contributions"),
                ("commits", "Commits"),
                ("prs", "Pull requests"),
                ("stars", "Stars"),
                ("streak", "Current streak days"),
                ("longest", "Longest streak days"),
            ]
        ]
    )
    if github.get("active_days") is not None:
        card.row("Participation", f"{_number(github['active_days'])} active days")
    calendar = github.get("calendar") or []
    if calendar:
        card.lines("Last 20 weeks", size=16, color=BLUE, weight=650)
        card.y += 8
        _heatmap(card, calendar[-20:])
    languages = github.get("languages") or []
    if languages:
        card.divider()
        card.title("Top languages")
        for language, percent, _color in languages:
            card.lines(f"{language} · {percent:g}%", size=16, color=MUTED)
            card.y += 4
    _updated(card, data, "github")
    return card.finish()


def _rating_chart(card: Card, history: list[float]) -> None:
    if len(history) < 2:
        return
    card.divider()
    card.lines("Contest rating history", size=16, color=AMBER, weight=650)
    card.y += 10
    low, high = min(history), max(history)
    left, right = PAD + 42, WIDTH - PAD
    top, bottom = card.y + 8, card.y + 130
    with card.block():
        for value, y in [(high, top), (low, bottom)]:
            card.lines(
                str(round(value)), x=PAD, y=y - 9, width=40, size=13, color=MUTED
            )
            card.parts.append(f'<path d="M{left} {y:g}H{right}" stroke="{BORDER}"/>')
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
    card.y = bottom + 18
    card.lines(
        f"Peak {round(high):,} · {len(history)} rated contests", size=15, color=MUTED
    )


def _leetcode(data: dict, context: dict) -> str:
    leetcode = data.get("leetcode") or {}
    card = Card("LeetCode coding and contest statistics", AMBER)
    card.title(f"LeetCode · {leetcode.get('badge', '')}".rstrip(" ·"))
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
            card.lines(f"{label} · {solved:,} / {total:,}", size=16, color=MUTED)
            fill = CONTENT_WIDTH * min(solved / total, 1) if total else 0
            card.parts.append(
                f'<rect x="{PAD}" y="{card.y:g}" width="{CONTENT_WIDTH}" height="6" rx="3" fill="{TRACK}"/>'
                f'<rect x="{PAD}" y="{card.y:g}" width="{fill:.1f}" height="6" rx="3" fill="{colors.get(label, BLUE)}">'
                f'<animate attributeName="width" values="0;{fill:.1f}" begin="{card.begin:.2f}s" '
                'dur="0.9s" fill="freeze"/></rect>'
            )
            card.y += 16
    _rating_chart(card, leetcode.get("history") or [])
    _updated(card, data, "leetcode")
    return card.finish()


def _normal_name(name: str) -> str:
    return re.sub(r"\s+", " ", DASHES.sub("-", name)).casefold()


def _certifications(data: dict, context: dict) -> str:
    certificates = context.get("certifications", [])
    today = datetime.date.fromisoformat(context["today"])
    card = Card("Certifications and professional badges", SKY)
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
        card.title(label)
        for certificate, detail in entries:
            card.row(certificate["name"], metadata=detail)
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
        card.title("Professional & training badges")
        for name in badge_names:
            card.row(name)
    return card.finish()


STACK_NAMES = {
    "aws": "AWS",
    "githubactions": "GitHub Actions",
    "gitlab": "GitLab",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "cpp": "C++",
    "cs": "C#",
    "r": "R",
    "html": "HTML",
    "css": "CSS",
    "nextjs": "Next.js",
    "tailwind": "Tailwind CSS",
    "materialui": "Material UI",
    "nodejs": "Node.js",
    "fastapi": "FastAPI",
    "graphql": "GraphQL",
    "mongodb": "MongoDB",
    "mysql": "MySQL",
    "postgres": "PostgreSQL",
    "dynamodb": "DynamoDB",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "opencv": "OpenCV",
    "sklearn": "scikit-learn",
    "vscode": "VS Code",
    "github": "GitHub",
}


def _stack(data: dict, context: dict) -> str:
    card = Card("Tech stack and tools")
    card.title("Tech stack")
    card.chips(
        [STACK_NAMES.get(slug, slug.capitalize()) for slug in context.get("stack", [])]
    )
    return card.finish()


def _ai_stack(data: dict, context: dict) -> str:
    card = Card("AI development tools", SKY)
    card.title("AI tools")
    card.chips(context.get("ai_tools", []))
    return card.finish()


def _competitive(data: dict, context: dict) -> str:
    portfolio = data.get("portfolio") or {}
    stats = portfolio.get("coding_stats") or {}
    card = Card("Competitive programming results", AMBER)
    card.title("Competitive programming")
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
    for entry in portfolio.get("contests", []):
        if re.match(r"(1st|2nd|3rd|4th) Place", entry.get("title", "")):
            card.divider()
            card.row(entry["title"], entry.get("organizer", ""), entry.get("date", ""))
    return card.finish()


def _sample(title: str, purpose: str, steps: list[tuple[str, str]]) -> str:
    card = Card(title, SKY)
    card.lines("AWS SAMPLE", size=15, color=SKY, weight=700)
    card.y += 8
    card.title(title)
    card.lines(purpose, color=MUTED)
    card.divider()
    for index, (step, detail) in enumerate(steps, start=1):
        card.row(f"{index:02d} · {step}", detail)
    card.lines("View source on GitHub →", size=16, color=BLUE, weight=650)
    return card.finish()


def _footer(data: dict, context: dict) -> str:
    card = Card("Thanks for visiting. Explore Sagar Gupta's portfolio.")
    card.title("Thanks for visiting")
    card.lines("Explore the projects and the work behind them.", color=MUTED)
    card.y += 16
    card.lines("Visit my portfolio →", weight=700)
    card.lines("sagargupta.online", size=16, color=BLUE)
    return card.finish()


def _header(number: str, title: str, subtitle: str, theme: str) -> str:
    card = Card(title)
    color = "#1d4ed8" if theme == "light" else BLUE
    foreground = "#17212b" if theme == "light" else WHITE
    secondary = "#475569" if theme == "light" else MUTED
    rule = "rgba(11,16,18,0.12)" if theme == "light" else "rgba(255,255,255,0.10)"
    card.lines(number, size=15, color=color, weight=700)
    card.y += 6
    card.lines(title, size=20, weight=700, color=foreground)
    card.y += 5
    card.lines(subtitle, size=15, color=secondary)
    height = int(card.y + 16)
    # the desktop header's accent bar and the light that runs along its rule
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(title, quote=True)}">'
        f"<style>text{{font-family:{SANS}}}</style>"
        f'<defs><linearGradient id="sweep" x1="0" x2="1"><stop offset="0" stop-color="{SKY}" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="{BLUE}"/><stop offset="1" stop-color="{SKY}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect x="0" y="{PAD}" width="4" height="{card.y - PAD:g}" rx="2" fill="{color}"/>'
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
        "highlights": _highlights,
        "worked-with": _worked_with,
        "publications": _publications,
        "education": _education,
        "oss": _oss,
        "github": _github,
        "leetcode": _leetcode,
        "certs": _certifications,
        "stack": _stack,
        "ai-stack": _ai_stack,
        "competitive": _competitive,
        "footer": _footer,
    }
    cards = {
        f"{name}-mobile.svg": renderer(data, context)
        for name, renderer in renderers.items()
    }
    cards["oss-merged-mobile.svg"] = _oss_list(data, "merged")
    cards["oss-review-mobile.svg"] = _oss_list(data, "open")
    cards["sample-org-governance-mobile.svg"] = _sample(
        "AWS Organizations governance",
        "A Terraform governance layer on an existing AWS Control Tower landing zone.",
        [
            ("Organize", "Declare the organizational unit hierarchy."),
            ("Govern", "Apply Organizations policies and Control Tower controls."),
            ("Delegate", "Configure delegated administrators for AWS services."),
        ],
    )
    cards["sample-sagemaker-mlops-mobile.svg"] = _sample(
        "SageMaker image classification MLOps",
        "An end-to-end MLOps pipeline, declared in Terraform.",
        [
            (
                "Ingest and train",
                "Event-driven ingestion and SageMaker training pipelines.",
            ),
            (
                "Evaluate and deploy",
                "Quality gates and human-approved model deployment.",
            ),
            ("Monitor and retrain", "Detect drift and trigger the retraining loop."),
        ],
    )
    for key, number, title, subtitle in context.get("headers", []):
        for theme in ("dark", "light"):
            cards[f"header-{key}-{theme}-mobile.svg"] = _header(
                number, title, subtitle, theme
            )
    return cards
