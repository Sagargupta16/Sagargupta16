"""The open-source record: the summary over the merged ledger, and the pull requests still in review.

Two cards at two widths, all drawn from ctx["oss"]:

- oss.svg: four tiles (merged upstream, repositories, their combined stars, open
  pull requests) over the merged ledger, a git-log rail of the newest merges. Five
  rows are in view and the ledger steps up a row every 4 s, so its six rows close
  on the 24 s page clock; the poster is the newest five, and the newest merge
  carries the green merged mark, pulsing. On each step the top row fades out
  before the rows move and the arriving row fades in after, so no row is ever
  drawn half cut by the window. Under the ledger, ALSO MERGED INTO names the
  repositories it does not show, the most starred first, and the rest of the pull
  requests fold into "+N more pull requests on GitHub".
- oss-review.svg: the repositories with open pull requests as counter chips, the
  most starred first, under the one amber mark (IN REVIEW), then the community line.

Each has a -mobile.svg twin at 320px: the tiles two by two over the same six rows,
and the review chips as a list. The merged list is no longer a card of its own.
The alt text names every repository with a merge.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
from __future__ import annotations

import re
from itertools import pairwise

import kit

T = kit.T
WIDTH, PHONE = 840, 320
PAD, PHONE_PAD = 24, 16
# Both widths show this many ledger rows and count the rest into one "+N more"
# line, so the cards stop growing with every merge and the two widths agree.
MERGED_SHOWN = 6
WINDOW = 5  # desktop ledger rows in view; the poster is the newest five
STEP = 4.0  # the ledger moves on a row this often: 6 rows x 4 s = 24 s
ROLL = 0.4  # how long one move takes
# a row crossing the window's edge fades over this long: the leaving one before
# the move, the arriving one after it, so the step ends on the beat
FADE = 0.3
PITCH = 40  # one desktop ledger row
INSET = 10  # the first ledger row's top, down from the panel's
ALSO_SHOWN = 3  # repositories ALSO MERGED INTO names at both widths before "+N more"
ALSO_GAP = 20  # between two of those names
FOOT = 24  # one line under the desktop ledger's rule
# desktop chip rows before the rest of the repositories fold into a count
REVIEW_ROWS = 3
PHONE_REVIEW = 6  # repositories listed on the phone review card
PHONE_TITLE = 3  # lines a pull request title may take on the phone before it is cut
SMOOTH = "0.4 0 0.2 1"  # ease in and out, for a move that travels and stops
PR_URL = re.compile(r"^https://github\.com/[^/]+/[^/]+/pull/(\d+)$")
COMMIT_URL = re.compile(r"/commit/([0-9a-f]{7})")
COUNTER = "rgba(255,255,255,0.10)"  # GitHub's grey counter pill
# 16 x 16 line glyphs for the tiles, drawn like GitHub's own marks
GLYPHS = {
    "merge": '<circle cx="4" cy="3.5" r="2"/><circle cx="4" cy="12.5" r="2"/><circle cx="12" cy="8" r="2"/>'
    '<path d="M4 5.5v5M4 5.5c0 2.5 2.5 2.5 6 2.5"/>',
    "repo": '<path d="M4.5 2h8v12h-8A1.5 1.5 0 0 1 3 12.5v-9A1.5 1.5 0 0 1 4.5 2zM3 11.5h9.5"/>',
    "star": '<path d="M8 1.4 10.1 5.75 14.9 6.35 11.45 9.65 12.35 14.45 8 12.2 3.65 14.45 4.55 9.65 1.1 6.35 5.9 5.75Z"/>',
    "pr": '<circle cx="4" cy="3.5" r="2"/><circle cx="4" cy="12.5" r="2"/><circle cx="12" cy="12.5" r="2"/>'
    '<path d="M4 5.5v5M12 10.5V7a2.5 2.5 0 0 0-2.5-2.5H7M8.6 2.9 7 4.5l1.6 1.6"/>',
}


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


def _by_stars(rows: list[dict]) -> list[tuple[str, int]]:
    """(repository, stars) for each repository once, the most starred first; a tie keeps the rows' order."""
    stars: dict[str, int] = {}
    for row in rows:
        stars[row["repo"]] = max(stars.get(row["repo"], 0), row.get("stars") or 0)
    return sorted(stars.items(), key=lambda item: -item[1])


def _also(oss: dict) -> list[tuple[str, int]]:
    """The repositories with a merge that the ledger's rows do not show, the most starred first."""
    shown = {row["repo"] for row in oss["merged"][:MERGED_SHOWN]}
    return [item for item in _by_stars(oss["merged"]) if item[0] not in shown]


def _reach(stars: int) -> str:
    """Round the combined stars down, so the tile never claims more than the live count: 238K+, 1.2M+."""
    return kit.compact(stars) + "+" if stars >= 1000 else str(stars)


def _tiles(oss: dict) -> list[tuple[str, str, str]]:
    """(value, label, glyph) for the four tiles, in the order both widths draw them."""
    return [
        (str(oss["merged_count"]), "MERGED UPSTREAM", "merge"),
        (str(oss["repos"]), "REPOS WITH MERGES", "repo"),
        (_reach(oss["combined_stars"]), "COMBINED STARS", "star"),
        (str(oss["open_count"]), "OPEN PRS", "pr"),
    ]


def _hidden(oss: dict) -> int:
    """The merged rows past the ledger that GitHub's pull request search will list.

    The README links the card to that search, so a commit (a co-authored fix) is
    left out of the count: the link could not show it.
    """
    return sum(1 for row in oss["merged"][MERGED_SHOWN:] if _pr_number(row["url"]))


def _prs(count: int) -> str:
    return f"{count} more pull request{'' if count == 1 else 's'}"


def _more(hidden: int) -> str:
    """Pull requests, said in full: after a list of repositories a bare "+6 more" reads as six more repositories."""
    return f"+{_prs(hidden)} on GitHub →"


def _first_merge(oss: dict) -> str:
    """The eyebrow's date: the oldest merge, which no row shows (the newest is the ledger's first row)."""
    dates = [row["date"] for row in oss["merged"] if row.get("date")]
    return f"FIRST MERGE {min(dates)}" if dates else "MERGED UPSTREAM"


def _updated(ctx: dict) -> str:
    stamp = str((ctx.get("updated") or {}).get("portfolio") or "")[:10]
    return f"UPDATED {stamp}" if stamp else ""


def _in_review(rows: list[dict]) -> list[tuple[str, int, int]]:
    """(repository, open pull requests, stars) for each repository, the most starred first."""
    counts: dict[str, int] = {}
    stars: dict[str, int] = {}
    for row in rows:
        counts[row["repo"]] = counts.get(row["repo"], 0) + 1
        stars[row["repo"]] = max(stars.get(row["repo"], 0), row.get("stars") or 0)
    ranked = sorted(counts, key=lambda repo: (-stars[repo], -counts[repo], repo))
    return [(repo, counts[repo], stars[repo]) for repo in ranked]


def _open_prs(count: int) -> str:
    if not count:
        return "NO OPEN PRS"
    return "1 OPEN PR" if count == 1 else f"{count} OPEN PRS"


def _review_head(oss: dict, repos: int) -> str:
    """The review card's eyebrow: where the open pull requests are. Their count is the
    summary card's fourth tile, just above, so the eyebrow does not say it again."""
    if not repos:  # nothing open, or a count with no rows to place it
        return _open_prs(oss["open_count"])
    return "1 REPOSITORY" if repos == 1 else f"{repos} REPOSITORIES"


def _community(line: str) -> tuple[str, str]:
    """Split "Community impact: a fix ..." into a label and its sentence; a line with no label stays whole."""
    head, _, rest = line.partition(": ")
    if not rest:
        return "", line
    return head.upper(), rest[:1].upper() + rest[1:]


# ---------------------------------------------------------------- labels
def _summary_label(oss: dict) -> str:
    parts = [
        f"Open source: {oss['merged_count']} contributions merged upstream into "
        f"{oss['repos']} repositories with {_reach(oss['combined_stars'])} combined stars, "
        f"and {oss['open_count']} pull requests open."
    ]
    if oss["merged"]:
        # every repository with a merge, not only the ledger's: the alt text is
        # the one place a reader without the image learns where the work landed
        names = ", ".join(repo for repo, _ in _by_stars(oss["merged"]))
        parts.append(f"Merged into, most starred first: {names}.")
        hidden = _hidden(oss)
        if hidden:
            shown = len(oss["merged"][:MERGED_SHOWN])
            parts.append(
                f"The {shown} newest merges are listed, with {_prs(hidden)} on GitHub."
            )
    return " ".join(parts)


def _review_label(oss: dict) -> str:
    repos = _in_review(oss["open"])
    if not repos:
        text = "No pull requests open upstream."
    else:
        listed = ", ".join(
            f"{repo} ({count})" if count > 1 else repo for repo, count, _ in repos
        )
        text = f"{oss['open_count']} pull requests in review upstream: {listed}."
    line = oss.get("community_line") or ""
    return f"{text} {line}." if line else text


# ---------------------------------------------------------------- drawing helpers
def _width(text: str, size: float, cls: str = "b") -> float:
    """The width kit measures for a label of this class: mono for c and m, tracked for m."""
    if cls == "m":
        return kit.text_width(text, size, True, kit.TRACK) - kit.TRACK
    if cls == "c":
        return kit.text_width(text, size, True, 0)
    return kit.text_width(text, size)


def _mono(
    x: float,
    y: float,
    text: str,
    size: float,
    fill: str,
    cls: str = "c",
    anchor: str = "",
) -> str:
    """A mono label pinned to the width kit measured for it.

    Whatever sits after it (a counter, a star) is placed by that measure, so
    textLength holds the gap even where the viewer's mono font is narrower.
    """
    pin = f' textLength="{_width(text, size, cls):.1f}" lengthAdjust="spacing"'
    return kit.text(x, y, text, size, fill, cls, anchor, pin if text else "")


def _fit(text: str, room: float, size: float, cls: str = "b") -> str:
    """The text whole when it fits `room`, else cut at a word (or a character) and closed with three dots."""
    if _width(text, size, cls) <= room:
        return text
    cut = text
    while " " in cut and _width(cut + "...", size, cls) > room:
        cut = cut.rsplit(" ", 1)[0]
    while cut and _width(cut + "...", size, cls) > room:
        cut = cut[:-1]
    return cut.rstrip(" ,;:.") + "..."


def _lines(text: str, room: float, size: float, cap: int, cls: str = "b") -> list[str]:
    """Wrap to `room`; past `cap` lines the last kept line ends in three dots."""
    mono = cls != "b"
    lines = kit.wrap_text(text, room, size, mono, 0)
    if len(lines) <= cap:
        return lines if mono else kit.balance(lines)
    rest = ("" if mono else " ").join(lines[cap - 1 :])
    return [*lines[: cap - 1], _fit(rest, room, size, cls)]


def _glyph(name: str, x: float, y: float, clear: float = 0) -> str:
    """A tile's glyph with its top left at x, y; left out when the numeral reaches `clear` past x."""
    if clear > x:
        return ""
    return (
        f'<g transform="translate({x:g} {y:g})" fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round">{GLYPHS[name]}</g>'
    )


def _star_width(stars: int, size: float) -> float:
    return 14 + _width(kit.compact(stars), size, "c")


def _star(x: float, baseline: float, stars: int, size: float, fill: str) -> str:
    """A star and the compact count after it, from x on the text baseline."""
    top = baseline - size * 0.36 - 5
    return (
        f'<path d="{kit.STAR}" fill="{kit.SKY}" transform="translate({x:g} {top:.1f})"/>'
        + _mono(x + 14, baseline, kit.compact(stars), size, fill)
    )


def _counter(x: float, mid: float, count: int, size: float) -> tuple[str, float]:
    """GitHub's counter: the number in a grey pill from x. Returns (svg, width)."""
    pill = _width(str(count), size, "c") + 12
    return (
        f'<rect x="{x:g}" y="{mid - 9:g}" width="{pill:g}" height="18" rx="9" fill="{COUNTER}"/>'
        + kit.text(
            x + pill / 2, mid + size * 0.36, str(count), size, kit.INK, "c", "middle"
        )
    ), pill


def _node(cx: float, cy: float, newest: bool, pulse: bool = True) -> str:
    """A merge on the rail: hollow, or for the newest the green disc with a tick, the card's one green.

    With `pulse` the disc is kit's 2 s status point, so the record shows its
    latest merge as live even while the ledger rests (or never turns).
    """
    if not newest:
        return f'<circle cx="{cx:g}" cy="{cy:g}" r="4.5" fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="1.5"/>'
    disc = (
        kit.live_dot(cx, cy, kit.GREEN, 6.5)
        if pulse
        else f'<circle cx="{cx:g}" cy="{cy:g}" r="6.5" fill="{kit.GREEN}"/>'
    )
    return disc + (
        f'<path transform="translate({cx:g} {cy:g}) scale(0.87)" d="{kit.TICK}" fill="none" '
        f'stroke="{kit.BG}" stroke-width="2.07" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _waiting(cx: float, cy: float) -> str:
    """A quiet blue status point for an empty record, so the card still moves."""
    return kit.live_dot(cx, cy, kit.BLUE_LIGHT, 3.5)


def _rail(x: float, upper: float, lower: float) -> str:
    """The stretch of rail between two nodes, stopping short of each so a hollow node stays hollow."""
    if lower - upper <= 16:
        return ""
    return f'<path d="M{x:g} {upper + 8:g}V{lower - 8:g}" stroke="{kit.HAIR_STRONG}" stroke-width="2"/>'


_keys = kit.keys


def _travel(moves: list[tuple[float, float]], dur: float) -> str:
    """Move the element it sits in (y) from 0 through `moves`, each (second, y) taking ROLL and landing at that second.

    It holds after the last move until dur, so the loop's last frame is the
    last move's: the caller either moves home there or draws its opening rows
    again at that offset.
    """
    points = [(0.0, 0.0)]
    for second, offset in moves:
        points += [(second - ROLL, points[-1][1]), (second, offset)]
    if points[-1][0] < dur:
        points.append((dur, points[-1][1]))
    values, times = _keys([(second, f"0 {at:g}") for second, at in points], dur)
    splines = ";".join(
        SMOOTH if a[1] != b[1] else "0 0 1 1" for a, b in pairwise(points)
    )
    return (
        f'<animateTransform attributeName="transform" type="translate" values="{values}" '
        f'keyTimes="{times}" calcMode="spline" keySplines="{splines}" dur="{dur:g}s" repeatCount="indefinite"/>'
    )


def _fade(points: list[tuple[float, float]], dur: float) -> str:
    """An opacity loop through (second, level) points, held from the last point to dur."""
    if points[-1][0] < dur:
        points = [*points, (dur, points[-1][1])]
    values, times = _keys([(second, f"{level:g}") for second, level in points], dur)
    return kit.loop("opacity", values, times, dur)


def _move_end(step: int) -> float:
    """When the ledger's move for `step` (1-based) lands: FADE before the beat, so the arriving row's fade ends on it."""
    return step * STEP - FADE


def _row_fade(index: int, rows: int) -> str:
    """The opacity loop of drawn ledger row `index` while `rows` rows turn through the window.

    A row is at 0 for the whole of any move that carries it across a window
    edge: the top row fades out just before its move, the bottom row fades in
    just after, so the clip never cuts through a line of text.
    """
    level = 1.0 if index < WINDOW else 0.0
    points = [(0.0, level)]
    arrive, leave = (
        index - WINDOW + 1,
        index + 1,
    )  # the steps that bring it in and take it out
    if 1 <= arrive <= rows:
        points += [(_move_end(arrive), 0.0), (_move_end(arrive) + FADE, 1.0)]
    if leave <= rows:
        start = _move_end(leave) - ROLL
        points += [(start - FADE, 1.0), (start, 0.0)]
    return _fade(sorted(points), rows * STEP)


def _on(start: float, end: float, dur: float, fade: float = 0.3) -> str:
    """An opacity loop at 1 from start+fade to end and 0 otherwise; the span may wrap past dur."""
    length = (end - start) % dur or dur

    def level(second: float) -> float:
        since = (second - start) % dur
        if since <= fade:
            return since / fade
        if since <= length:
            return 1.0
        if since <= length + fade:
            return 1 - (since - length) / fade
        return 0.0

    marks = sorted(
        {0.0, dur, start % dur, (start + fade) % dur, end % dur, (end + fade) % dur}
    )
    values, times = _keys(
        [(mark, f"{max(0.0, round(level(mark), 3)):g}") for mark in marks], dur
    )
    return kit.loop("opacity", values, times, dur)


def _spotlight(count: int) -> tuple[float, float]:
    """(loop, slot) for a light that visits `count` items in turn, 2 s or more on each."""
    loop = T if count <= 6 else 2 * T
    return loop, loop / count


def _lit(x: float, y: float, w: float, h: float, index: int, count: int) -> str:
    """The spotlight on item `index`: it rests on the first, so the poster shows one lit."""
    if count < 2:
        return ""
    loop, slot = _spotlight(count)
    rest = "" if index == 0 else ' opacity="0"'
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{w:.1f}" height="{h:g}" rx="{min(h / 2, 12):g}" '
        f'fill="{kit.BLUE_TINT}" stroke="{kit.BLUE_EDGE}" stroke-width="1.5"{rest}>'
        + _on(index * slot - 0.3, (index + 1) * slot - 0.3, loop)
        + "</rect>"
    )


def _in_review_mark(right: float, baseline: float, size: float) -> str:
    """IN REVIEW in amber with its pulsing dot, ending at `right`: the only amber in this lane."""
    wide = _width("IN REVIEW", size, "m")
    return kit.live_dot(
        right - wide - 11, baseline - size * 0.36, kit.AMBER, 3.5
    ) + kit.text(right, baseline, "IN REVIEW", size, kit.AMBER, "m", "end")


def _also_flow(
    also: list[tuple[str, int]],
    left: float,
    right: float,
    baseline: float,
    lines: int,
    pitch: float,
) -> tuple[str, float]:
    """The ALSO MERGED INTO names from `left` on `baseline`, each with its star, in at most `lines` lines.

    At most ALSO_SHOWN names, so both widths name the same ones; past them, or
    past what fits, a "+N more" closes the last line, and names give way from
    the end until it fits. Returns (svg, the baseline of its last line).
    """
    more = _width(f"+{len(also)} more", 12, "c") + ALSO_GAP if len(also) > 1 else 0
    placed, x, line = [], left, 0
    for repo, stars in also[:ALSO_SHOWN]:
        tail = 8 + _star_width(stars, 11.5) if stars else 0
        name = _fit(repo, right - left - tail, 12, "c")
        if x > left and x + _width(name, 12, "c") + tail > right:
            line, x = line + 1, left
            if line >= lines:
                break
        if line == lines - 1:
            # the last line keeps room for a "+N more" after this name
            name = _fit(repo, right - x - tail - more, 12, "c")
            if name != repo and len(name) < 8:
                break
        width = _width(name, 12, "c") + tail
        placed.append((name, stars, x, line, width))
        x += width + ALSO_GAP
    while len(placed) < len(also) and placed:
        _, _, last_x, _, last_w = placed[-1]
        if last_x + last_w + more <= right:
            break
        placed.pop()
    out = []
    for name, stars, x, line, width in placed:
        y = baseline + line * pitch
        out.append(_mono(x, y, name, 12, kit.BLUE_LIGHT))
        if stars:
            out.append(
                _star(x + width - _star_width(stars, 11.5), y, stars, 11.5, kit.META)
            )
    left_out = len(also) - len(placed)
    last = baseline + (placed[-1][3] if placed else 0) * pitch
    if left_out:
        x = placed[-1][2] + placed[-1][4] + ALSO_GAP if placed else left
        out.append(_mono(x, last, f"+{left_out} more", 12, kit.META))
    return "".join(out), last


# ---------------------------------------------------------------- desktop: summary and ledger
RAIL = 48  # the ledger's rail
ROW_X = 68  # where a ledger row's text starts
STAR_X = 752  # the star column; its count reads on from the star
DATE_END = 734  # the date column ends here
TILE_TOP, TILE_H, TILE_GAP = 44, 60, 16


def _ledger_row(row: dict, top: float, newest: bool, above: float | None) -> str:
    """One merge: the rail up to the node above, the node, the repository and its pull request,
    the date and stars on the right, and the title under them."""
    first, second, node = top + 16, top + 33, top + 12
    label = _pr_label(row["url"])
    date = row.get("date") or ""
    end = DATE_END - _width(date, 11.5, "c") - 16 if date else STAR_X - 16
    repo = _fit(row["repo"], end - ROW_X - _width(label, 12, "c") - 10, 12, "c")
    out = [
        _rail(RAIL, above, node) if above is not None else "",
        _node(RAIL, node, newest),
        _mono(ROW_X, first, repo, 12, kit.BLUE_LIGHT),
        _mono(ROW_X + _width(repo, 12, "c") + 10, first, label, 12, kit.META),
    ]
    if date:
        out.append(kit.text(DATE_END, first, date, 11.5, kit.META, "c", "end"))
    if row.get("stars"):
        out.append(_star(STAR_X, first, row["stars"], 11.5, kit.INK))
    title = _fit(row["title"], WIDTH - PAD - 16 - ROW_X, 13)
    out.append(kit.text(ROW_X, second, title, 13, kit.INK, "b"))
    return "".join(out)


def _ledger(oss: dict, top: float) -> tuple[str, str, float]:
    """The merged ledger from `top`. Returns (svg, its clip, the height it takes)."""
    rows = oss["merged"][:MERGED_SHOWN]
    hidden, also = _hidden(oss), _also(oss)
    # rows start INSET down the panel and the clip starts INSET - 2 down, so a
    # row that has stepped out of view hides its descenders too
    window = INSET + 2 + (min(len(rows), WINDOW) or 1) * PITCH
    foot = bool(also) + bool(hidden)  # the lines under the ledger's rule
    height = window + (10 + FOOT * foot if foot else 0)
    x, w = PAD, WIDTH - 2 * PAD
    out = [
        f'<rect x="{x}" y="{top:g}" width="{w}" height="{height:g}" rx="10" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
    ]
    clip = f'<clipPath id="ledger"><rect x="{x + 1}" y="{top + INSET - 2:g}" width="{w - 2}" height="{window - INSET + 2:g}"/></clipPath>'
    if not rows:
        out.append(
            _waiting(RAIL, top + 26)
            + kit.text(ROW_X, top + 30, "NO MERGES YET", kit.MICRO, kit.META, "m")
        )
        return "".join(out), clip, height
    # past five rows the ledger turns: every row is drawn again under the last,
    # so after the final step the window holds the opening frame
    turns = len(rows) > WINDOW
    drawn = [*rows, *rows[:WINDOW]] if turns else rows
    body = []
    for index, row in enumerate(drawn):
        y = top + INSET + index * PITCH
        # no rail joins the oldest row to the newest drawn again under it: the
        # log starts over there, and a hairline says so
        above = y - PITCH + 12 if index % len(rows) else None
        line = _ledger_row(row, y, index % len(rows) == 0, above)
        if turns:
            line = f"<g>{_row_fade(index, len(rows))}{line}</g>"
        # the rows in view enter one after another; the ones below wait out of sight
        body.append(
            kit.group(0.4 + index * kit.STAGGER, line) if index < WINDOW else line
        )
    moving = ""
    if turns:
        n = len(rows)
        moving = _travel(
            [(_move_end(k), -k * PITCH) for k in range(1, n + 1)], n * STEP
        )
        # the seam shows while the rows on both sides of it do
        start, end = _move_end(n - WINDOW + 1), _move_end(n) - ROLL
        seam = top + INSET + n * PITCH + 1
        body.append(
            f'<path d="M{x + 1} {seam:g}H{x + w - 1}" stroke="{kit.HAIR_STRONG}">'
            + _fade(
                [(0, 0), (start, 0), (start + FADE, 1), (end - FADE, 1), (end, 0)],
                n * STEP,
            )
            + "</path>"
        )
    out.append(f'<g clip-path="url(#ledger)"><g>{moving}{"".join(body)}</g></g>')
    if foot:
        rule = top + window
        out.append(f'<path d="M{x + 1} {rule:g}H{x + w - 1}" stroke="{kit.HAIR}"/>')
        baseline = rule + 22
        if also:
            label = "ALSO MERGED INTO"
            out.append(kit.text(ROW_X, baseline, label, kit.MICRO, kit.META, "m"))
            names, _ = _also_flow(
                also,
                ROW_X + _width(label, kit.MICRO, "m") + 16,
                x + w - 16,
                baseline,
                1,
                FOOT,
            )
            out.append(names)
            baseline += FOOT
        if hidden:
            out.append(
                kit.text(ROW_X, baseline, _more(hidden), 12.5, kit.BLUE_LIGHT, "s")
            )
    return "".join(out), clip, height


def _summary(oss: dict, ctx: dict) -> str:
    out = [kit.eyebrow(PAD, 30, _first_merge(oss))]
    stamp = _updated(ctx)
    if stamp:
        out.append(kit.eyebrow(WIDTH - PAD, 30, stamp, kit.META, "end"))
    wide = (WIDTH - 2 * PAD - 3 * TILE_GAP) / 4
    for index, (value, label, glyph) in enumerate(_tiles(oss)):
        x = PAD + index * (wide + TILE_GAP)
        # the merged count is the record's headline, so its tile is the emphasised one
        fill, edge = (
            (kit.BLUE_TINT, kit.BLUE_EDGE)
            if index == 0
            else (kit.CARD, kit.HAIR_STRONG)
        )
        out.append(
            kit.group(
                (index + 1) * kit.STAGGER,
                f'<rect x="{x:g}" y="{TILE_TOP}" width="{wide:g}" height="{TILE_H}" rx="10" fill="{fill}" stroke="{edge}"/>'
                + kit.text(x + 16, TILE_TOP + 31, value, 24, kit.INK, "n")
                + kit.text(
                    x + 16, TILE_TOP + TILE_H - 13, label, kit.MICRO, kit.META, "m"
                )
                + _glyph(
                    glyph,
                    x + wide - 30,
                    TILE_TOP + 14,
                    x + 16 + kit.text_width(value, 24) + 8,
                ),
            )
        )
    top = TILE_TOP + TILE_H + 16
    ledger, clip, height = _ledger(oss, top)
    out.append(kit.group(5 * kit.STAGGER, ledger))
    h = top + height + PAD
    return (
        kit.card_open(WIDTH, h, _summary_label(oss), clip)
        + "".join(out)
        + kit.SVG_CLOSE
    )


# ---------------------------------------------------------------- desktop: in review
CHIP_TOP, CHIP_H, CHIP_GAP = 46, 28, 8


def _chip(repo: str, count: int, stars: int, room: float) -> tuple[tuple, float]:
    """One repository chip's (name, count, stars) and its width; a name too long for `room` is cut."""
    tail = 0.0
    if count > 1:
        tail += 8 + _width(str(count), 11, "c") + 12
    if stars:
        tail += 14 + _star_width(stars, 11.5)
    name = _fit(repo, room - 28 - tail, 12, "c")
    return (name, count, stars), 14 + _width(name, 12, "c") + tail + 14


def _draw_chip(
    parts: tuple, x: float, y: float, w: float, index: int, count: int
) -> str:
    name, prs, stars = parts
    mid = y + CHIP_H / 2
    out = [
        f'<rect x="{x:g}" y="{y:g}" width="{w:.1f}" height="{CHIP_H}" rx="{CHIP_H / 2:g}" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>',
        _lit(x, y, w, CHIP_H, index, count),
        _mono(x + 14, mid + 4.3, name, 12, kit.INK),
    ]
    at = x + 14 + _width(name, 12, "c")
    if prs > 1:
        svg, pill = _counter(at + 8, mid, prs, 11)
        out.append(svg)
        at += 8 + pill
    if stars:
        out.append(_star(at + 14, mid + 4.1, stars, 11.5, kit.META))
    return "".join(out)


def _chip_layout(repos: list, left: float, right: float, rows: int) -> tuple[list, int]:
    """Place chips in at most `rows` rows. Returns ([(parts, x, row, width)], how many are left out).

    When some are left out, a "+N more" chip must fit on the last row, so chips
    give way from the end until it does.
    """
    placed, x, row = [], left, 0
    for repo, count, stars in repos:
        parts, width = _chip(repo, count, stars, right - left)
        if x > left and x + width > right:
            row, x = row + 1, left
            if row >= rows:
                break
        placed.append((parts, x, row, width))
        x += width + CHIP_GAP
    while len(placed) < len(repos) and placed:
        more = kit.chip_width(f"+{len(repos) - len(placed)} more")
        _, last_x, _, last_w = placed[-1]
        if last_x + last_w + CHIP_GAP + more <= right:
            break
        placed.pop()
    return placed, len(repos) - len(placed)


def _review(oss: dict) -> str:
    repos = _in_review(oss["open"])
    head = _review_head(oss, len(repos))
    out = [kit.eyebrow(PAD, 30, head)]
    if repos:
        out.append(_in_review_mark(WIDTH - PAD, 30, kit.MICRO))
    else:
        out.append(
            _waiting(PAD + _width(head, kit.MICRO, "m") + 14, 30 - kit.MICRO * 0.36)
        )
    placed, left_out = _chip_layout(repos, PAD, WIDTH - PAD, REVIEW_ROWS)
    chips, y = [], CHIP_TOP - CHIP_GAP
    for index, (parts, x, row, width) in enumerate(placed):
        top = CHIP_TOP + row * (CHIP_H + CHIP_GAP)
        chips.append(_draw_chip(parts, x, top, width, index, len(placed)))
        y = top + CHIP_H
    if left_out:
        _, x, row, width = placed[-1]
        top = CHIP_TOP + row * (CHIP_H + CHIP_GAP)
        chips.append(
            kit.chip(
                x + width + CHIP_GAP,
                top + 3,
                f"+{left_out} more",
                kit.META,
                height=CHIP_H - 6,
            )[0]
        )
    out.append(kit.group(kit.STAGGER, "".join(chips)))
    label, sentence = _community(oss.get("community_line") or "")
    if sentence:
        rule = y + 18
        x = PAD + 148 if label else PAD
        lines = kit.balance(kit.wrap_text(sentence, WIDTH - PAD - x, 13))
        block = [f'<path d="M{PAD} {rule:g}H{WIDTH - PAD}" stroke="{kit.HAIR}"/>']
        if label:
            block.append(kit.text(PAD, rule + 26, label, kit.MICRO, kit.META, "m"))
        block += [
            kit.text(x, rule + 26 + index * 18, line, 13, kit.BODY, "b")
            for index, line in enumerate(lines)
        ]
        out.append(kit.group(2 * kit.STAGGER, "".join(block)))
        y = rule + 26 + (len(lines) - 1) * 18 - 4
    return (
        kit.card_open(WIDTH, y + PAD, _review_label(oss)) + "".join(out) + kit.SVG_CLOSE
    )


# ---------------------------------------------------------------- phone
def _phone_tiles(oss: dict, y: float) -> tuple[str, float]:
    """The four tiles two by two from y. Returns (svg, the height they take)."""
    pad, size, gap = PHONE_PAD, kit.MICRO_PHONE, 8
    wide = (PHONE - 2 * pad - gap) / 2
    tiles = _tiles(oss)
    labels = [
        kit.wrap_text(label, wide - 24, size, True, kit.TRACK) for _, label, _ in tiles
    ]
    tall = 54 + 13 * (max(len(lines) for lines in labels) - 1)
    out = []
    for index, (value, _, glyph) in enumerate(tiles):
        x = pad + (index % 2) * (wide + gap)
        top = y + (index // 2) * (tall + gap)
        fill, edge = (
            (kit.BLUE_TINT, kit.BLUE_EDGE)
            if index == 0
            else (kit.CARD, kit.HAIR_STRONG)
        )
        body = (
            f'<rect x="{x:g}" y="{top:g}" width="{wide:g}" height="{tall:g}" rx="10" fill="{fill}" stroke="{edge}"/>'
            + kit.text(x + 12, top + 27, value, 22, kit.INK, "n")
            + _glyph(
                glyph, x + wide - 28, top + 12, x + 12 + kit.text_width(value, 22) + 6
            )
            + "".join(
                kit.text(x + 12, top + 44 + line * 13, text, size, kit.META, "m")
                for line, text in enumerate(labels[index])
            )
        )
        out.append(kit.group((index + 1) * kit.STAGGER, body))
    return "".join(out), 2 * tall + gap


def _summary_phone(oss: dict, ctx: dict) -> str:
    pad, size = PHONE_PAD, kit.MICRO_PHONE
    out = [kit.text(pad, 26, _first_merge(oss), size, kit.BLUE_LIGHT, "m")]
    tiles, tall = _phone_tiles(oss, 40)
    out.append(tiles)
    top = 40 + tall + 12
    rows = oss["merged"][:MERGED_SHOWN]
    rail, x0, right = pad + 14, pad + 30, PHONE - pad - 10
    room = right - x0
    body, nodes, y = [], [], top + 8
    for index, row in enumerate(rows):
        node = y + 12
        parts = [
            _rail(rail, nodes[-1], node) if nodes else "",
            _node(rail, node, index == 0),
        ]
        nodes.append(node)
        line_y = y + 16
        for text in _lines(row["repo"], room, 12, 2, "c"):
            parts.append(kit.text(x0, line_y, text, 12, kit.BLUE_LIGHT, "c"))
            line_y += 15
        line_y += 3
        for text in _lines(row["title"], room, 13.5, PHONE_TITLE):
            parts.append(kit.text(x0, line_y, text, 13.5, kit.INK, "b"))
            line_y += 18
        meta = "  ".join(
            filter(None, [_pr_label(row["url"]).upper(), row.get("date") or ""])
        )
        parts.append(_mono(x0, line_y, meta, size, kit.META, "m"))
        if row.get("stars"):
            parts.append(
                _star(
                    x0 + _width(meta, size, "m") + 12,
                    line_y,
                    row["stars"],
                    size,
                    kit.META,
                )
            )
        body.append(kit.group((5 + index) * kit.STAGGER, "".join(parts)))
        y = line_y + 14
    panel = []
    if not rows:
        panel.append(
            _waiting(rail, top + 26)
            + kit.text(x0, top + 30, "NO MERGES YET", size, kit.META, "m")
        )
        y = top + 50
    end = y + 2
    hidden, also = _hidden(oss), _also(oss)
    if hidden or also:
        panel.append(
            f'<path d="M{pad + 1} {end:g}H{PHONE - pad - 1}" stroke="{kit.HAIR}"/>'
        )
        baseline = end + 23
        if also:
            panel.append(
                kit.text(x0, baseline, "ALSO MERGED INTO", size, kit.META, "m")
            )
            names, last = _also_flow(also, x0, right, baseline + 21, ALSO_SHOWN, 18)
            panel.append(names)
            baseline = last + 27
        if hidden:
            panel.append(
                kit.text(x0, baseline, _more(hidden), 13.5, kit.BLUE_LIGHT, "s")
            )
            baseline += 27
        end = baseline - 27 + 13
    frame = f'<rect x="{pad}" y="{top:g}" width="{PHONE - 2 * pad}" height="{end - top:g}" rx="10" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>'
    cursor = ""
    if len(nodes) > 1:
        # a ring visits one merge after another, a row every 4 s, the beat the
        # desktop ledger steps on; it fades out on the oldest and back in on the
        # newest rather than sweeping back up the card
        n = len(nodes)
        dur, home = n * STEP, _move_end(n)
        moves = [(_move_end(k), nodes[k] - nodes[0]) for k in range(1, n)]
        away = home - ROLL
        cursor = (
            f'<circle cx="{rail}" cy="{nodes[0]:g}" r="10" fill="none" stroke="{kit.BLUE_LIGHT}" stroke-width="1.5">'
            + _travel([*moves, (home, 0.0)], dur)
            + _fade([(0, 1), (away - FADE, 1), (away, 0), (home, 0), (dur, 1)], dur)
            + "</circle>"
        )
    # the ring sits under the rows, so the node it circles is drawn over it
    out.append(
        kit.group(5 * kit.STAGGER, frame + "".join(panel) + cursor) + "".join(body)
    )
    h = end + 14
    stamp = _updated(ctx)
    if stamp:
        out.append(kit.text(pad, end + 30, stamp, size, kit.META, "m"))
        h = end + 46
    return kit.card_open(PHONE, h, _summary_label(oss)) + "".join(out) + kit.SVG_CLOSE


def _review_phone(oss: dict) -> str:
    pad, size = PHONE_PAD, kit.MICRO_PHONE
    repos = _in_review(oss["open"])
    head = _review_head(oss, len(repos))
    out = [kit.text(pad, 26, head, size, kit.BLUE_LIGHT, "m")]
    if repos:
        out.append(_in_review_mark(PHONE - pad, 26, size))
    else:
        out.append(_waiting(pad + _width(head, size, "m") + 14, 26 - size * 0.36))
    shown = repos[:PHONE_REVIEW]
    x, w = pad, PHONE - 2 * pad
    y, rows = 40.0, []
    for index, (repo, count, stars) in enumerate(shown):
        tail = (_width(str(count), size, "c") + 20 if count > 1 else 0) + (
            _star_width(stars, size) + 8 if stars else 0
        )
        names = _lines(repo, w - 28 - tail, 12.5, 2, "c")
        tall = 16 + 16 * len(names)
        mid = y + tall / 2
        parts = [
            f'<rect x="{x}" y="{y:g}" width="{w}" height="{tall:g}" rx="12" fill="{kit.CARD}" stroke="{kit.HAIR_STRONG}"/>',
            _lit(x, y, w, tall, index, len(shown)),
        ]
        first = mid - 8 * (len(names) - 1) + 4.5
        parts += [
            kit.text(x + 14, first + line * 16, text, 12.5, kit.INK, "c")
            for line, text in enumerate(names)
        ]
        at = x + w - 14
        if stars:
            at -= _star_width(stars, size)
            parts.append(_star(at, mid + 4.1, stars, size, kit.META))
            at -= 8
        if count > 1:
            pill = _width(str(count), size, "c") + 12
            at -= pill
            parts.append(_counter(at, mid, count, size)[0])
        rows.append("".join(parts))
        y += tall + 8
    if len(repos) > len(shown):
        rows.append(
            kit.text(
                x + 2,
                y + 12,
                f"+{len(repos) - len(shown)} more",
                13.5,
                kit.BLUE_LIGHT,
                "s",
            )
        )
        y += 26
    out.append(kit.group(kit.STAGGER, "".join(rows)))
    label, sentence = _community(oss.get("community_line") or "")
    end = y - 8
    if sentence:
        rule = y + 6
        block = [f'<path d="M{pad} {rule:g}H{PHONE - pad}" stroke="{kit.HAIR}"/>']
        line_y = rule + 24
        if label:
            block.append(kit.text(pad, line_y, label, size, kit.META, "m"))
            line_y += 20
        lines = kit.balance(kit.wrap_text(sentence, w, 13.5))
        block += [
            kit.text(pad, line_y + index * 19, line, 13.5, kit.BODY, "b")
            for index, line in enumerate(lines)
        ]
        out.append(kit.group(2 * kit.STAGGER, "".join(block)))
        end = line_y + (len(lines) - 1) * 19 - 4
    return (
        kit.card_open(PHONE, end + 20, _review_label(oss))
        + "".join(out)
        + kit.SVG_CLOSE
    )


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for the open-source cards, desktop and -mobile."""
    oss = ctx["oss"]
    return {
        "oss.svg": _summary(oss, ctx),
        "oss-mobile.svg": _summary_phone(oss, ctx),
        "oss-review.svg": _review(oss),
        "oss-review-mobile.svg": _review_phone(oss),
    }
