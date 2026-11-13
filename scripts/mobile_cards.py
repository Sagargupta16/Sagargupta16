"""The phone layout engine: a 320px card that flows top to bottom on the kit's palette, type and clock.

Card API. Each call draws at card.y and moves it down; text is escaped for you; colours come from kit.

    card = Card("One sentence saying what the card shows", accent=kit.BLUE_LIGHT)  # the aria-label
    card.label("merged upstream")                  mono micro-label, uppercased, 11.5px
    card.lines("Body copy.", size=14, color=kit.BODY)   wrapped and balanced; mono=True for data
    card.row(title, detail, metadata)              strong title, mono metadata, body detail; bullet=True
    card.metrics([("13", "Merged upstream")])      bordered stat tiles, two columns, no word ever split
    card.chips(["Terraform", "AWS"], max_rows=2)   centred mono pills in rows; returns how many it drew
    card.pills([("5X CERTIFIED", kit.SKY)])        status pills in their own colour, flowed into rows
    card.status("BUILDING AT AWS")                 one pill with the green live dot
    card.divider()                                 a hairline that draws in
    card.raw(svg, height)                          your own drawing: y from 0, x from the card's left edge
    with card.block(): ...                         everything inside enters as one group
    svg = card.finish(defs, backdrop, attrs)       the file; attrs is a dict of extra root attributes

    card = Card("2 open pull requests waiting on review", kit.AMBER)
    card.label("2 open PRs")
    card.row("ansible/ansible", "Fix the inventory cache key", "PR #1234")
    card.chips(repos, max_rows=2)
    svg = card.finish()

Each call is one entrance (fade and rise, 0.08 s apart, all over by 1.6 s). A card's budget is about 14
animated elements, so group short calls with block(). card.width is 320, PAD the side padding and
CONTENT_WIDTH the column. Move card.y by hand for extra spacing. Mono text is not uppercased for you
except in label(), metrics() labels and row() metadata.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# Only the layout lives here. The cards themselves are in scripts/cards/, and the
# palette, fonts, text metrics and motion all come from kit, so one fact has one
# colour and one clock at both widths.
from __future__ import annotations

import datetime
import math
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

import kit

WIDTH, PAD, BODY_SIZE = 320, 18, 15
CONTENT_WIDTH = WIDTH - PAD * 2
MICRO = kit.MICRO_PHONE  # every mono micro-label on a phone card
LEADING = 0.38  # gap below each line, as a share of its font size
# Blocks start STAGGER apart; LAST_START caps the delay so a long card has
# finished entering by about 1.6 s.
STAGGER, LAST_START = kit.STAGGER, 1.2
TILE_GAP, TILE_INSET = 10, 10
VALUE_SIZES = {1: 24, 2: 22, 3: 18}  # a tile's numeral, by columns in the row
VALUE_FLOOR = 16
PILL_HEIGHT = 26


def text_width(text: str, size: float = BODY_SIZE, mono: bool = False) -> float:
    """Measure text as this engine draws it: kit's advances, mono at the micro-label tracking."""
    return kit.text_width(text, size, mono, kit.TRACK)


def wrap_text(
    text: str, width: float, size: float = BODY_SIZE, mono: bool = False
) -> list[str]:
    """Wrap to a pixel width, then keep one short word from sitting alone on the last line."""
    lines = kit.wrap_text(text, width, size, mono, kit.TRACK)
    balanced = kit.balance(lines)
    if balanced and text_width(balanced[-1], size, mono) <= width:
        return balanced
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
    # The root <svg> carries the sans stack as an attribute, so this attribute
    # wins for mono text. A text{} rule in <style> would beat both.
    font = f' font-family="{kit.MONO}" letter-spacing="{kit.TRACK:g}"' if mono else ""
    align = f' text-anchor="{anchor}"' if anchor else ""
    return (
        f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" font-weight="{weight}" '
        f'fill="{color}"{font}{align}>{kit.esc(text)}</text>'
    )


def _tint(x: float, y: float, width: float, height: float, color: str) -> str:
    """A pill in its own colour: a faint fill and an outline that still reaches 3:1."""
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="{PILL_HEIGHT / 2:g}" '
        f'fill="{color}" fill-opacity="0.08" stroke="{color}" stroke-opacity="0.55"/>'
    )


def _words_fit(texts: Iterable[str], width: float, size: float, mono: bool) -> bool:
    return all(
        text_width(word, size, mono) <= width for text in texts for word in text.split()
    )


def _tile_fit(
    items: list[tuple[str, str]], columns: int, label_size: float
) -> tuple[int, float, float]:
    """The column count, numeral size and label size at which no word in a tile has to split."""
    values = [value for value, _ in items]
    labels = [label for _, label in items]
    for count in range(max(columns, 1), 0, -1):
        inner = (CONTENT_WIDTH - TILE_GAP * (count - 1)) / count - 2 * TILE_INSET
        value_size, size = VALUE_SIZES.get(count, VALUE_FLOOR), label_size
        while value_size > VALUE_FLOOR and not _words_fit(
            values, inner, value_size, False
        ):
            value_size -= 1
        while size > MICRO and not _words_fit(labels, inner, size, True):
            size = max(MICRO, size - 0.5)
        if count == 1 or (
            _words_fit(values, inner, value_size, False)
            and _words_fit(labels, inner, size, True)
        ):
            return count, value_size, size
    return 1, VALUE_FLOOR, MICRO


class Card:
    """One phone card: a column of blocks that enter in order inside the shared frame."""

    def __init__(self, label: str, accent: str = kit.BLUE_LIGHT):
        """Start an empty card; label becomes its aria-label, which the README uses as alt text."""
        self.name, self.accent = label, accent
        self.parts: list[str] = []
        self.y: float = PAD
        self.begin = 0.1
        self._depth = 0

    @property
    def width(self) -> int:
        """The card's width in px; the content column runs from PAD to width - PAD."""
        return WIDTH

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
            self.parts.append(kit.group(self.begin, body))
            self.begin = min(self.begin + step, LAST_START)

    def _stack(
        self,
        lines: list[str],
        x: float,
        top: float,
        size: float,
        color: str,
        weight: int,
        mono: bool = False,
        anchor: str = "",
    ) -> float:
        """Write lines that are already wrapped, downwards from top; returns the y below them."""
        for line in lines:
            top += size
            self.parts.append(_text(x, top, size, weight, color, line, mono, anchor))
            top += size * LEADING
        return top

    def lines(
        self,
        text: str,
        *,
        x: float = PAD,
        y: float | None = None,
        width: float | None = None,
        size: float = BODY_SIZE,
        color: str = kit.INK,
        weight: int = 500,
        mono: bool = False,
        anchor: str = "",
    ) -> float:
        """Write wrapped text at the cursor, or at y without moving the cursor; returns the y below it.

        width defaults to the room between x and the padding (both sides of x when anchor is "middle").
        """
        if width is None:
            left, right = x - PAD, WIDTH - PAD - x
            width = {"middle": 2 * min(left, right), "end": left}.get(anchor, right)
        cursor = self.y if y is None else y
        with self.block():
            cursor = self._stack(
                wrap_text(str(text), width, size, mono),
                x,
                cursor,
                size,
                color,
                weight,
                mono,
                anchor,
            )
        if y is None:
            self.y = cursor
        return cursor

    def label(self, text: str, color: str | None = None) -> None:
        """Write a mono micro-label in capitals, the desktop cards' section marker."""
        self.lines(
            text.upper(), size=MICRO, color=color or self.accent, weight=700, mono=True
        )
        self.y += 8

    def divider(self) -> None:
        """Rule off a section with a hairline that draws in from the left."""
        self.y += 6
        self.parts.append(
            kit.draw(
                f"M{PAD} {self.y:g}H{WIDTH - PAD}",
                self.begin,
                kit.ENTER,
                kit.HAIR_STRONG,
                1,
            )
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
        weight: int = 600,
    ) -> None:
        """A list entry that enters as one block: the title, mono metadata in the accent, a body detail."""
        x = PAD + 14 if bullet else PAD
        with self.block():
            if bullet:
                self.parts.append(
                    f'<circle cx="{PAD + 3}" cy="{self.y + size * 0.65:g}" r="2.5" fill="{self.accent}"/>'
                )
            self.lines(title, x=x, size=size, weight=weight)
            if metadata:
                self.y += 3
                self.lines(
                    metadata.upper(),
                    x=x,
                    size=MICRO,
                    color=self.accent,
                    weight=700,
                    mono=True,
                )
            if detail:
                self.y += 3
                self.lines(detail, x=x, size=13.5, color=kit.BODY)
        self.y += 12

    def metrics(
        self,
        items: list[tuple[str, str]],
        columns: int = 2,
        *,
        color: str = kit.INK,
        label_size: float = MICRO,
    ) -> None:
        """Stat tiles: one numeral over a mono micro-label, as on the desktop cards.

        A word is never split: the numeral shrinks first, the label shrinks as far as the
        11.5px floor, and after that the row takes fewer columns than asked for.
        """
        items = [(str(value), str(label).upper()) for value, label in items]
        columns, value_size, label_size = _tile_fit(items, columns, label_size)
        tile = (CONTENT_WIDTH - TILE_GAP * (columns - 1)) / columns
        inner = tile - 2 * TILE_INSET
        for index in range(0, len(items), columns):
            row = [
                (
                    wrap_text(value, inner, value_size),
                    wrap_text(label, inner, label_size, True),
                )
                for value, label in items[index : index + columns]
            ]
            height = max(
                20
                + len(value) * value_size * (1 + LEADING)
                + len(label) * label_size * (1 + LEADING)
                for value, label in row
            )
            for column, (value, label) in enumerate(row):
                x = PAD + column * (tile + TILE_GAP)
                with self.block():
                    self.parts.append(
                        f'<rect x="{x:g}" y="{self.y:g}" width="{tile:g}" height="{height:g}" '
                        f'rx="10" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
                    )
                    bottom = self._stack(
                        value, x + TILE_INSET, self.y + 8, value_size, color, 800
                    )
                    self._stack(
                        label,
                        x + TILE_INSET,
                        bottom + 2,
                        label_size,
                        kit.META,
                        700,
                        True,
                    )
            self.y += height + TILE_GAP

    def chips(
        self,
        labels: list[str],
        size: float = MICRO,
        mono: bool = True,
        *,
        color: str = kit.BLUE_LIGHT,
        max_rows: int = 0,
    ) -> int:
        """Flow pills into rows, each label centred in its pill, as one entrance.

        Stops before a row past max_rows (0 for no cap) and returns how many labels
        it drew, so the caller can add a "+N more" line.
        """
        pad, gap = 10, 6
        line = size * (1 + LEADING)
        x, top, bottom, rows, shown = float(PAD), self.y, self.y, 1, 0
        with self.block():
            for label in labels:
                lines = wrap_text(str(label), CONTENT_WIDTH - 2 * pad, size, mono)
                if not lines:
                    continue
                width = max(text_width(text, size, mono) for text in lines) + 2 * pad
                height = len(lines) * line + 10
                if x > PAD and x + width > WIDTH - PAD:
                    if max_rows and rows >= max_rows:
                        break
                    x, top, rows = float(PAD), bottom + gap, rows + 1
                self.parts.append(
                    f'<rect x="{x:g}" y="{top:g}" width="{width:g}" height="{height:g}" '
                    f'rx="{min(height / 2, 13):g}" fill="{kit.HAIR_FILL}" stroke="{kit.HAIR_STRONG}"/>'
                )
                # centred, so a measuring error shows as even padding on both sides
                self._stack(
                    lines,
                    x + width / 2,
                    top + 5 + size * 0.05,
                    size,
                    color,
                    700 if mono else 600,
                    mono,
                    "middle",
                )
                bottom = max(bottom, top + height)
                x += width + gap
                shown += 1
        if shown:
            self.y = bottom + 12
        return shown

    def pills(self, items: list[tuple[str, str]]) -> None:
        """Status pills as (label, colour), each sized to its label and flowed into rows as one entrance."""
        pad, gap = 12, 8
        line = MICRO * (1 + LEADING)
        x, top, bottom = float(PAD), self.y, self.y
        with self.block():
            for label, color in items:
                lines = wrap_text(label, CONTENT_WIDTH - 2 * pad, MICRO, True)
                if not lines:
                    continue
                width = max(text_width(text, MICRO, True) for text in lines) + 2 * pad
                if x > PAD and x + width > WIDTH - PAD:
                    x, top = float(PAD), bottom + gap
                height = PILL_HEIGHT + (len(lines) - 1) * line
                self.parts.append(_tint(x, top, width, height, color))
                self._stack(
                    lines,
                    x + width / 2,
                    top + (PILL_HEIGHT - line) / 2 + MICRO * 0.05,
                    MICRO,
                    color,
                    700,
                    True,
                    "middle",
                )
                bottom = max(bottom, top + height)
                x += width + gap
        if bottom > self.y:
            self.y = bottom + 12

    def status(self, label: str, color: str = kit.GREEN) -> None:
        """One pill with the pulsing live dot: the current role, an ongoing engagement, a site that is up."""
        lines = wrap_text(label, CONTENT_WIDTH - 40, MICRO, True)
        if not lines:
            return
        line = MICRO * (1 + LEADING)
        width = max(text_width(text, MICRO, True) for text in lines) + 40
        height = PILL_HEIGHT + (len(lines) - 1) * line
        with self.block():
            self.parts.append(
                _tint(PAD, self.y, width, height, color)
                + kit.live_dot(PAD + 15, self.y + PILL_HEIGHT / 2, color, 3.5)
            )
            self._stack(
                lines,
                PAD + 28,
                self.y + (PILL_HEIGHT - line) / 2 + MICRO * 0.05,
                MICRO,
                color,
                700,
                True,
            )
        self.y += height + 12

    def raw(self, svg: str, height: float) -> None:
        """Place a hand-drawn block at the cursor as one entrance, then move down by height.

        Draw it with y measured from 0 at the block's top and x from the card's left
        edge (the column is PAD to width - PAD); kit's text classes work inside it.
        """
        with self.block():
            self.parts.append(f'<g transform="translate(0 {self.y:g})">{svg}</g>')
        self.y += height

    def finish(
        self, defs: str = "", backdrop: str = "", attrs: dict | None = None
    ) -> str:
        """Close the card and return the file.

        backdrop is drawn under the content and clipped to the rounded frame; attrs
        become extra attributes on the root, for example data-active-certifications.
        """
        height = math.ceil(self.y + PAD)
        extra = "".join(
            f' {name}="{kit.esc(str(value))}"' for name, value in (attrs or {}).items()
        )
        return (
            # the sans default sits on the root as an attribute: children inherit it
            # and a mono label's own font-family attribute wins
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{kit.esc(self.name)}" '
            f'font-family="{kit.SANS}"{extra}>'
            + kit.style("svg{font-variant-numeric:tabular-nums}")
            + f'<defs><clipPath id="card"><rect x="1" y="1" width="{WIDTH - 2}" '
            f'height="{height - 2}" rx="{kit.RADIUS - 1}"/></clipPath>{defs}</defs>'
            + kit.frame(WIDTH, height)
            + (f'<g clip-path="url(#card)">{backdrop}</g>' if backdrop else "")
            + f'<rect x="0" y="20" width="3" height="26" rx="1.5" fill="{self.accent}">'
            + kit.loop("opacity", "1;0.4;1", "0;0.5;1", 3)
            + "</rect>"
            + "".join(self.parts)
            + kit.SVG_CLOSE
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


# ---------------------------------------------------------------- rules both scripts share
# render-svgs.py writes the profile with these and validate-readme.py accepts
# nothing else, so the two can never disagree. Like cert_status above, they are
# not layout; they live here because both scripts already import this module.


def cert_issuer(name: str) -> str:
    """Return the short issuer label shown beside a certification count."""
    if name.startswith("AWS"):
        return "AWS"
    if "Terraform" in name:
        return "TERRAFORM"
    return "OTHER"


# Customers are never named on the profile, whatever the portfolio data says. An
# engagement whose name holds a PROGRAMS key is an AWS program and shows that
# program's fixed name. Every other engagement is customer work and shows the
# label for its start month, else GENERIC_CUSTOMER; the portfolio's own wording
# of the client is never used.
PROGRAMS = {"sme program": "MLOps SME Program"}
CUSTOMER_LABELS = {
    "Oct 2024": "Global financial services customer",
    "Aug 2025": "Financial market infrastructure customer",
    "Feb 2026": "Enterprise customer",
}
GENERIC_CUSTOMER = "AWS customer"
# The one public wording of an ambassador role, after an optional "<N>x " count.
PUBLIC_AMBASSADOR = "AWS community ambassador"
