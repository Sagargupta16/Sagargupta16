"""The open-source record: the summary with its repository chips, the merged list and the open list.

Three cards at two widths, all drawn from ctx["oss"]: oss.svg, oss-merged.svg and
oss-review.svg at 840px, and their -mobile.svg twins at 320px.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
from __future__ import annotations

import re

import kit
from mobile_cards import MICRO, Card

WIDTH = 840
# Both layouts cut the merged list here and close it with a "+N more" row, so
# the cards stop growing with every merge and the two widths always agree.
MERGED_SHOWN = 6
OPEN_SHOWN = (
    5  # pull requests on the phone open list; the desktop groups them by repository
)
NUMBERS_SHOWN = 3  # PR numbers beside one repository before the rest fold into "+N"
MONO_CHAR = 7.6  # the advance the desktop chips are measured with at 10.5px
ROW, LINE, TOP = 46, 15, 50  # a list row, an extra wrapped line, the first row's rule
SECOND_WRAP = 104  # characters on a row's second line
PR_URL = re.compile(r"^https://github\.com/[^/]+/[^/]+/pull/(\d+)$")
COMMIT_URL = re.compile(r"/commit/([0-9a-f]{7})")
# the list cards' repository line is a 700, between kit's strong and title
LIST_CSS = f".r{{font-family:{kit.SANS};font-weight:700}}"
ROW_RULE = "rgba(255,255,255,0.06)"  # the hairline over each list row


# ---------------------------------------------------------------- shared facts
def _pr_number(url: str) -> int:
    """Return the pull request number in a GitHub URL, or 0 for a commit or any other link."""
    match = PR_URL.match(url)
    return int(match.group(1)) if match else 0


def _pr_label(url: str) -> str:
    number = _pr_number(url)
    if number:
        return f"#{number}"
    sha = COMMIT_URL.search(url)
    return f"commit {sha.group(1)}" if sha else "link"


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3].rsplit(" ", 1)[0] + "..."


def _wrap(text: str, width: int) -> list[str]:
    """Wrap by character count, never leaving one short word alone on the last line."""
    lines, current = [], ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    lines += [current] if current else []
    if len(lines) > 1 and " " not in lines[-1] and " " in lines[-2]:
        head, moved = lines[-2].rsplit(" ", 1)
        if len(moved) + 1 + len(lines[-1]) <= width:
            lines[-2:] = [head, f"{moved} {lines[-1]}"]
    return lines


def _repos(rows: list[dict]) -> list[str]:
    """Return each repository once, in the order the rows name them."""
    return list(dict.fromkeys(row["repo"] for row in rows))


def _reach(stars: int) -> str:
    """Round the combined stars down, so the tile never claims more than the live count."""
    return f"{stars // 1000}K+" if stars >= 1000 else str(stars)


def _tiles(oss: dict) -> list[tuple[str, str]]:
    return [
        (str(oss["merged_count"]), "merged upstream"),
        (str(oss["open_count"]), "open PRs"),
        (str(oss["repos"]), "repos with merges"),
        (_reach(oss["combined_stars"]), "combined stars"),
    ]


def _oss_chip_label(repo: str, count: int, stars: int) -> str:
    """Return a chip label: repo, a count when merged more than once, and its stars."""
    label = repo
    if count > 1:
        label += f"  x{count}"
    if stars >= 1000:
        label += f"  {stars / 1000:.1f}K"
    elif stars:
        label += f"  {stars}"
    return label


def _chip_labels(oss: dict) -> list[str]:
    """Return one label per repository with a merge, the most starred first, for both layouts."""
    counts: dict[str, int] = {}
    stars: dict[str, int] = {}
    for row in oss["merged"]:
        counts[row["repo"]] = counts.get(row["repo"], 0) + 1
        stars[row["repo"]] = row.get("stars") or 0
    ranked = sorted(counts, key=lambda repo: -stars[repo])
    return [_oss_chip_label(repo, counts[repo], stars[repo]) for repo in ranked]


def _more(hidden: int) -> str:
    return f"+{hidden} more on GitHub →"


def _open_groups(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group the open pull requests by repository, most pull requests first, newest first inside."""
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["repo"], []).append(row)
    ordered = sorted(grouped.items(), key=lambda item: -len(item[1]))
    return [
        (repo, sorted(entries, key=lambda entry: -_pr_number(entry["url"])))
        for repo, entries in ordered
    ]


def _numbers(entries: list[dict]) -> str:
    """Return up to three PR numbers and a "+N" for the rest, so the column cannot reach the title."""
    labels = [_pr_label(entry["url"]) for entry in entries]
    hidden = len(labels) - NUMBERS_SHOWN
    return ", ".join(labels[:NUMBERS_SHOWN]) + (f" +{hidden}" if hidden > 0 else "")


def _merged_label(oss: dict) -> str:
    rows = oss["merged"]
    if not rows:
        return "Contributions merged upstream"
    hidden = len(rows) - MERGED_SHOWN
    more = f", and {hidden} more on GitHub" if hidden > 0 else ""
    return (
        f"{len(rows)} contributions merged upstream, newest first: "
        + ", ".join(_repos(rows[:MERGED_SHOWN]))
        + more
    )


def _open_label(oss: dict) -> str:
    rows = oss["open"]
    if not rows:
        return "Pull requests open upstream"
    repos = [repo for repo, _ in _open_groups(rows)]
    return f"{len(rows)} pull requests open upstream, in " + ", ".join(repos)


def _summary_label(oss: dict) -> str:
    return (
        f"Open source: {oss['merged_count']} merged upstream, {oss['open_count']} open PRs, "
        f"{oss['repos']} repositories with merges"
    )


# ---------------------------------------------------------------- desktop
def _chip_rows(labels: list[str], top: float) -> list[tuple[float, float, float, str]]:
    """Place 10.5px mono chips left to right, wrapping into as many rows as they need."""
    chips, x, y = [], 24.0, top
    for label in labels:
        width = 20 + len(label) * MONO_CHAR
        if x + width > WIDTH - 24 and x > 24:
            x, y = 24.0, y + 32
        chips.append((x, y, width, label))
        x += width + 8
    return chips


def _summary(oss: dict) -> str:
    # merged-into chips, biggest projects first; the card grows to fit every row
    chips = _chip_rows(_chip_labels(oss), 128)
    height = chips[-1][1] + 44 if chips else 128
    parts = [
        kit.card_open(WIDTH, height, _summary_label(oss)),
        kit.eyebrow(24, 30, "OPEN SOURCE  |  MERGED UPSTREAM"),
    ]
    tile = (WIDTH - 32 - 3 * 10) / 4
    for index, (value, label) in enumerate(_tiles(oss)):
        x = 16 + index * (tile + 10)
        parts.append(
            f"<g>{kit.enter(0.1 + index * 0.1)}"
            f'<rect x="{x:.1f}" y="44" width="{tile:.1f}" height="62" rx="10" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
            + kit.text(x + 14, 76, value, 22, kit.INK, "n")
            + kit.text(x + 14, 95, label.upper(), kit.MICRO, kit.META, "m")
            + "</g>"
        )
    for index, (x, y, width, label) in enumerate(chips):
        parts.append(
            f"<g>{kit.enter(0.5 + index * 0.06)}"
            f'<rect x="{x:.1f}" y="{y:g}" width="{width:.1f}" height="24" rx="12" fill="{kit.SKY}12" stroke="{kit.SKY}44"/>'
            + kit.text(x + width / 2, y + 16, label, kit.MICRO, kit.BODY, "m", "middle")
            + "</g>"
        )
    parts.append(kit.SVG_CLOSE)
    return "".join(parts)


def _list_card(
    label: str,
    kicker: str,
    rows: list[tuple[str, str, str]],
    accent: str,
    more: str = "",
    footer: str = "",
) -> str:
    """Return a card of rows: bold primary, dimmed secondary line, mono meta on the right.

    more is one closing row in the accent; footer is a sentence under the list, wrapped to the card.
    """
    # a secondary line that does not fit wraps once instead of being cut
    seconds = [_wrap(secondary, SECOND_WRAP) for _, secondary, _ in rows]
    for index, lines in enumerate(seconds):
        if len(lines) > 2:
            seconds[index] = [lines[0], _clip(" ".join(lines[1:]), SECOND_WRAP)]
    footers = kit.balance(kit.wrap_text(footer, WIDTH - 48, 11)) if footer else []
    height = (
        TOP
        + sum(ROW + LINE * (len(lines) - 1) for lines in seconds)
        + (30 if more else 0)
        + (34 + LINE * (len(footers) - 1) if footers else 12)
    )
    parts = [
        kit.card_open(WIDTH, height, label, css=LIST_CSS),
        kit.text(24, 31, kicker, kit.MICRO, accent, "m"),
    ]
    y = TOP
    rule = f'x1="24" x2="{WIDTH - 24}" stroke="{ROW_RULE}"/>'
    for index, ((primary, _, meta), lines) in enumerate(zip(rows, seconds)):
        second = "".join(
            kit.text(44, y + 37 + line * LINE, content, 11.5, kit.META)
            for line, content in enumerate(lines)
        )
        parts.append(
            f"<g>{kit.enter(0.15 + index * 0.07, shift='-8 0')}"
            f'<line y1="{y}" y2="{y}" {rule}'
            f'<circle cx="30" cy="{y + 23}" r="3" fill="{accent}"/>'
            + kit.text(44, y + 20, _clip(primary, 60), 13.5, kit.INK, "r")
            + second
            + kit.text(
                WIDTH - 24, y + 20, meta.upper(), kit.MICRO, kit.META, "m", "end"
            )
            + "</g>"
        )
        y += ROW + LINE * (len(lines) - 1)
    if more:
        parts.append(
            f"<g>{kit.enter(0.15 + len(rows) * 0.07, shift='-8 0')}"
            f'<line y1="{y}" y2="{y}" {rule}'
            + kit.text(44, y + 21, more, 12, accent, "r")
            + "</g>"
        )
    first = height - 14 - LINE * (len(footers) - 1)
    parts += [
        kit.text(24, first + index * LINE, line, 11, kit.META)
        for index, line in enumerate(footers)
    ]
    parts.append(kit.SVG_CLOSE)
    return "".join(parts)


def _merged(oss: dict) -> str:
    rows = [
        (row["repo"], row["title"], _pr_label(row["url"]))
        for row in oss["merged"][:MERGED_SHOWN]
    ]
    hidden = len(oss["merged"]) - MERGED_SHOWN
    return _list_card(
        _merged_label(oss),
        f"{oss['merged_count']} MERGED UPSTREAM  |  NEWEST FIRST",
        rows,
        kit.GREEN,
        more=_more(hidden) if hidden > 0 else "",
    )


def _review(oss: dict) -> str:
    rows = [
        (repo, "; ".join(entry["title"] for entry in entries), _numbers(entries))
        for repo, entries in _open_groups(oss["open"])
    ]
    return _list_card(
        _open_label(oss),
        f"{oss['open_count']} OPEN PRS",
        rows,
        kit.AMBER,
        footer=oss.get("community_line") or "",
    )


# ---------------------------------------------------------------- phone
def _updated(card: Card, ctx: dict) -> None:
    stamp = str((ctx.get("updated") or {}).get("portfolio") or "")[:10]
    if stamp:
        card.y += 4
        card.lines(
            f"UPDATED {stamp}", size=MICRO, color=kit.META, weight=700, mono=True
        )


def _summary_phone(oss: dict, ctx: dict) -> str:
    card = Card(_summary_label(oss), kit.GREEN)
    tiles = _tiles(oss)
    tiles[-1] = (tiles[-1][0], "combined repo stars")
    card.metrics(tiles)
    labels = _chip_labels(oss)
    if labels:
        card.label("Merged into")
        card.chips(labels, color=kit.BODY)  # the desktop chips' label colour
    _updated(card, ctx)
    return card.finish()


def _list_phone(oss: dict, ctx: dict, merged: bool) -> str:
    entries = oss["merged"] if merged else oss["open"]
    shown = MERGED_SHOWN if merged else OPEN_SHOWN
    card = Card(
        _merged_label(oss) if merged else _open_label(oss),
        kit.GREEN if merged else kit.AMBER,
    )
    card.label(f"{len(entries)} {'merged upstream' if merged else 'open PRs'}")
    for index, entry in enumerate(entries[:shown]):
        if index:
            card.divider()
        number = _pr_number(entry["url"])
        metadata = [f"PR #{number}" if number else "", entry.get("date") or ""]
        card.row(
            entry["repo"], entry["title"], " · ".join(filter(None, metadata)), size=14
        )
    if len(entries) > shown:
        card.lines(_more(len(entries) - shown), size=14, color=card.accent, weight=600)
        card.y += 4
    line = "" if merged else oss.get("community_line") or ""
    if line:
        # "Community impact: a fix ..." becomes a label over the sentence
        head, _, rest = line.partition(": ")
        card.divider()
        with card.block():
            if rest:
                card.label(head)
            sentence = rest[:1].upper() + rest[1:] if rest else head
            card.lines(sentence, size=13.5, color=kit.BODY)
    _updated(card, ctx)
    return card.finish()


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for the open-source cards, desktop and -mobile."""
    oss = ctx["oss"]
    return {
        "oss.svg": _summary(oss),
        "oss-mobile.svg": _summary_phone(oss, ctx),
        "oss-merged.svg": _merged(oss),
        "oss-merged-mobile.svg": _list_phone(oss, ctx, merged=True),
        "oss-review.svg": _review(oss),
        "oss-review-mobile.svg": _list_phone(oss, ctx, merged=False),
    }
