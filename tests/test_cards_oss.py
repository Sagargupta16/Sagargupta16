"""Checks for the open-source cards: the files, their bounds and motion, the ledger and the review chips.

The shared checks run on the checked-in snapshot and assert rules, never values, so a
data refresh cannot fail them. Each lane rule has its own test on a small fixture.
"""

from __future__ import annotations

import copy
import importlib.util
import re
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("render_svgs", SCRIPTS / "render-svgs.py")
renderer = importlib.util.module_from_spec(SPEC)
sys.modules["render_svgs"] = renderer
SPEC.loader.exec_module(renderer)
renderer.OFFLINE = True

import kit
from cards import oss

SVG = "{http://www.w3.org/2000/svg}"
ANIMATIONS = {f"{SVG}animate", f"{SVG}animateTransform"}
DATA = renderer.load_data()
CTX = renderer.build_context(DATA)
FILES = oss.render(DATA, CTX)
NAMES = {"oss.svg", "oss-mobile.svg", "oss-review.svg", "oss-review-mobile.svg"}
DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}
ALSO = "ALSO MERGED INTO"


def on_clock(dur: float) -> bool:
    """The page clock, or a stepped ticker of rows x a 2, 3 or 4 s step (plan section 2)."""
    rows = dur / oss.STEP
    return dur in CLOCK or (
        oss.STEP in (2, 3, 4) and rows == int(rows) and 2 <= rows <= oss.MERGED_SHOWN
    )


LINE = "Community impact: a confirmed fix in example/selfhost, plus 2 accepted answers"
COMMIT = "https://github.com/acme/vpc/commit/489899c7198b6d0099275e2ffee6852b98c6012b"
LONG_TITLE = "Replace the deprecated argument everywhere it is still read " * 4
LONG_REPO = (
    "terraform-aws-modules-with-a-long-owner/terraform-aws-dynamodb-table-number"
)


def entry(repo: str, number: int, stars: int, date: str = "", title: str = "") -> dict:
    return {
        "repo": repo,
        "title": title or f"Fix number {number} in {repo}",
        "url": f"https://github.com/{repo}/pull/{number}",
        "date": date,
        "stars": stars,
    }


def context(
    merged: list[dict] | None = None,
    opened: list[dict] | None = None,
    line: str = "",
) -> dict:
    """A context shaped like build_context's, holding only what the oss cards read."""
    merged, opened = merged or [], opened or []
    repos = {row["repo"]: row["stars"] for row in merged}
    return {
        "updated": {"portfolio": "2026-11-13T07:52:34+00:00"},
        "oss": {
            "merged": merged,
            "open": opened,
            "merged_count": len(merged),
            "open_count": len(opened),
            "repos": len(repos),
            "combined_stars": sum(repos.values()),
            "community_line": line,
        },
    }


def merged_rows(count: int) -> list[dict]:
    """count merged pull requests, newest first, one repository each."""
    return [
        entry(
            f"owner{index}/repo{index}",
            100 + index,
            5000 - index,
            f"2026-10-{28 - index % 28:02d}",
        )
        for index in range(count)
    ]


def long_context() -> dict:
    merged = [
        entry(f"{LONG_REPO}-{n}", 50_000 + n, 1_234_567, "2026-03-24", LONG_TITLE)
        for n in range(40)
    ]
    opened = [
        entry(f"some-very-long-organisation/a-repository-with-a-long-name-{i}", n, i)
        for i in range(20)
        for n in (1, 2)
    ]
    return context(merged, opened, LINE * 3)


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314


def texts(svg: str) -> list[str]:
    return [element.text or "" for element in parse(svg).iter(f"{SVG}text")]


def width(element: ET.Element) -> float:
    """A label's width as the module measures it: mono for c, m and k, tracked for m and k."""
    content, size = element.text or "", float(element.attrib["font-size"])
    cls = element.get("class")
    if cls in ("m", "k"):
        track = kit.TRACK if cls == "m" else 2
        return kit.text_width(content, size, True, track) - (track if content else 0)
    if cls == "c":
        return kit.text_width(content, size, True, 0)
    return kit.text_width(content, size)


def span(element: ET.Element) -> tuple[float, float]:
    """Return the left and right edge of a text element."""
    x, wide = float(element.attrib["x"]), width(element)
    anchor = element.get("text-anchor")
    if anchor == "middle":
        return x - wide / 2, x + wide / 2
    if anchor == "end":
        return x - wide, x
    return x, x + wide


def walk(svg: str) -> list[tuple[ET.Element, list[ET.Element]]]:
    """Every element with the chain of its ancestors, root first."""
    out = []

    def visit(element: ET.Element, chain: list[ET.Element]) -> None:
        out.append((element, chain))
        for child in element:
            visit(child, [*chain, element])

    visit(parse(svg), [])
    return out


def clipped(chain: list[ET.Element]) -> bool:
    return any(node.get("clip-path") == "url(#ledger)" for node in chain)


def boxes(svg: str) -> list[tuple[float, float, float, float]]:
    """The panels, tiles, chips and pills drawn on the card (not its frame, not a clip)."""
    out = []
    for element, chain in walk(svg):
        if element.tag != f"{SVG}rect" or "rx" not in element.attrib:
            continue
        if any(node.tag == f"{SVG}clipPath" for node in chain):
            continue
        x, y = float(element.attrib["x"]), float(element.attrib["y"])
        if x < 1 and y < 1:
            continue  # the card's own frame
        out.append(
            (x, y, float(element.attrib["width"]), float(element.attrib["height"]))
        )
    return out


def size_of(svg: str) -> tuple[float, float]:
    _, _, w, h = map(float, parse(svg).attrib["viewBox"].split())
    return w, h


def offsets(animation: ET.Element) -> list[float]:
    return [float(value.split()[1]) for value in animation.get("values").split(";")]


def ticker(svg: str) -> ET.Element | None:
    """The ledger's step loop, when the ledger turns."""
    for element, chain in walk(svg):
        if element.tag == f"{SVG}animateTransform" and clipped(chain):
            if element.get("repeatCount") == "indefinite":
                return element
    return None


def at(animation: ET.Element, second: float, dur: float) -> float:
    """The animation's value at `second`, read linearly between keyframes (the last number of a translate)."""
    values = [float(v.split()[-1]) for v in animation.get("values").split(";")]
    times = [float(t) * dur for t in animation.get("keyTimes").split(";")]
    if second >= times[-1]:
        return values[-1]
    for (t0, v0), (t1, v1) in zip(zip(times, values), zip(times[1:], values[1:])):
        if t0 <= second <= t1:
            return v0 if t1 == t0 else v0 + (v1 - v0) * (second - t0) / (t1 - t0)
    return values[0]


def moves_of(animation: ET.Element) -> list[tuple[float, float]]:
    """(start, end) seconds of each stretch where a translate loop changes its value."""
    dur = float(animation.get("dur").rstrip("s"))
    times = [float(t) * dur for t in animation.get("keyTimes").split(";")]
    stops = offsets(animation)
    return [
        (start, end)
        for start, end, a, b in zip(times, times[1:], stops, stops[1:])
        if a != b
    ]


def row_fades(svg: str) -> list[tuple[float, ET.Element]]:
    """(baseline, its fade loop) for every drawn ledger row, top to bottom."""
    out = []
    for element, chain in walk(svg):
        if element.tag != f"{SVG}text" or not clipped(chain):
            continue
        if element.get("fill") != kit.BLUE_LIGHT or element.get("class") != "c":
            continue
        fades = [
            child
            for node in chain
            for child in node
            if child.tag == f"{SVG}animate"
            and child.get("attributeName") == "opacity"
            and child.get("repeatCount") == "indefinite"
        ]
        out.append((float(element.attrib["y"]), fades[-1]))
    return sorted(out, key=lambda item: item[0])


def ledger_repos(svg: str) -> list[tuple[float, str]]:
    """(baseline, repository) for every ledger row drawn under the clip, top to bottom."""
    rows = []
    for element, chain in walk(svg):
        if element.tag == f"{SVG}text" and clipped(chain):
            if element.get("fill") == kit.BLUE_LIGHT and element.get("class") == "c":
                rows.append((float(element.attrib["y"]), element.text or ""))
    return sorted(rows)


def clip_rect(svg: str) -> tuple[float, float, float, float]:
    rect = next(
        clip.find(f"{SVG}rect")
        for clip in parse(svg).iter(f"{SVG}clipPath")
        if clip.get("id") == "ledger"
    )
    return tuple(float(rect.attrib[key]) for key in ("x", "y", "width", "height"))


def footer_top(svg: str) -> float:
    """The baseline of the ALSO MERGED INTO label, or past the card when there is none."""
    labels = [
        float(e.attrib["y"]) for e in parse(svg).iter(f"{SVG}text") if e.text == ALSO
    ]
    return labels[0] if labels else float("inf")


def also_names(svg: str) -> list[str]:
    """What ALSO MERGED INTO lists, in reading order: the names, then any "+N more"."""
    top = footer_top(svg)
    shown = [
        (float(e.attrib["y"]), float(e.attrib["x"]), e.text or "")
        for e, chain in walk(svg)
        if e.tag == f"{SVG}text"
        and e.get("class") == "c"
        and not clipped(chain)
        and top <= float(e.attrib["y"]) < top + 70
    ]
    return [
        text for _, _, text in sorted(shown) if not re.fullmatch(r"[0-9.,]+[KM]?", text)
    ]


def phone_repos(svg: str) -> list[str]:
    """The phone ledger's repositories, the wrapped lines of one name joined."""
    top = footer_top(svg)
    lines = [
        (float(e.attrib["y"]), e.text or "")
        for e in parse(svg).iter(f"{SVG}text")
        if e.get("fill") == kit.BLUE_LIGHT
        and e.get("class") == "c"
        and float(e.attrib["y"]) < top
    ]
    out, last = [], None
    for y, text in sorted(lines):
        if last is not None and y - last <= 15.5:
            out[-1] += text
        else:
            out.append(text)
        last = y
    return out


class SharedRules(unittest.TestCase):
    CASES = {
        "snapshot": FILES,
        "empty": oss.render({}, context()),
        "short": oss.render({}, context(merged_rows(3), [entry("solo/repo", 5, 40)])),
        "long": oss.render({}, long_context()),
    }

    def each(self):
        for case, files in self.CASES.items():
            for name, svg in files.items():
                yield f"{case}/{name}", name, svg

    def test_the_module_returns_its_four_files(self) -> None:
        for files in self.CASES.values():
            self.assertEqual(set(files), NAMES)
        for name in FILES:
            self.assertRegex(name, renderer.CARD_FILE)
        self.assertNotIn("oss-merged.svg", FILES)  # the merged ledger lives in oss.svg

    def test_every_file_parses_and_carries_a_sentence_for_alt_text(self) -> None:
        for label, name, svg in self.each():
            root = parse(svg)
            self.assertEqual(root.get("role"), "img", label)
            self.assertGreater(len(root.get("aria-label", "")), 20, label)
            self.assertEqual(
                size_of(svg)[0], 320 if name.endswith("-mobile.svg") else 840, label
            )

    def test_text_stays_inside_the_card_and_its_padding(self) -> None:
        for label, name, svg in self.each():
            w, h = size_of(svg)
            pad = oss.PHONE_PAD if name.endswith("-mobile.svg") else oss.PAD
            for element, chain in walk(svg):
                if element.tag != f"{SVG}text":
                    continue
                left, right = span(element)
                where = f"{label}: {element.text!r}"
                self.assertGreaterEqual(left, pad - 0.5, where)
                self.assertLessEqual(right, w - pad + 0.5, where)
                if clipped(chain):
                    continue  # ledger rows below the window step into it; see LedgerTurns
                y, size = float(element.attrib["y"]), float(element.attrib["font-size"])
                self.assertGreaterEqual(y - size * 0.75, 0, where)
                self.assertLessEqual(y + 2, h, where)

    def test_labels_sit_inside_their_boxes(self) -> None:
        for label, _, svg in self.each():
            shapes = boxes(svg)
            for element, chain in walk(svg):
                if element.tag != f"{SVG}text" or clipped(chain):
                    continue
                left, right = span(element)
                y, size = float(element.attrib["y"]), float(element.attrib["font-size"])
                point = ((left + right) / 2, y - size * 0.3)
                inside = [
                    box
                    for box in shapes
                    if box[0] <= point[0] <= box[0] + box[2]
                    and box[1] <= point[1] <= box[1] + box[3]
                ]
                if not inside:
                    continue
                x, top, wide, tall = min(inside, key=lambda box: box[2] * box[3])
                where = f"{label}: {element.text!r}"
                self.assertGreaterEqual(left, x + 3, where)
                self.assertLessEqual(right, x + wide - 3, where)
                self.assertGreaterEqual(y - size * 0.72, top, where)
                self.assertLessEqual(y, top + tall - 2, where)

    def test_no_dash_anywhere(self) -> None:
        sources = {label: svg for label, _, svg in self.each()}
        sources["oss.py"] = (SCRIPTS / "cards" / "oss.py").read_text(encoding="utf-8")
        for name, content in sources.items():
            for dash in DASHES:
                self.assertNotIn(dash, content, name)

    def test_cards_are_self_contained(self) -> None:
        for label, _, svg in self.each():
            for banned in (
                "<set",
                "<script",
                "<image",
                "foreignObject",
                "href",
                "@import",
                "prefers-reduced-motion",
            ):
                self.assertNotIn(banned, svg, f"{label}: {banned}")

    def test_entrances_end_on_the_finished_frame(self) -> None:
        for label, _, svg in self.each():
            for element in parse(svg).iter():
                if element.tag not in ANIMATIONS or element.get("fill") != "freeze":
                    continue
                values = element.attrib["values"].split(";")
                finished = "1" if element.get("attributeName") == "opacity" else "0 0"
                self.assertEqual(values[-1], finished, label)
                self.assertTrue(element.attrib["keyTimes"].startswith("0;"), label)
                self.assertLessEqual(
                    float(element.attrib["dur"].rstrip("s")), 1.7, label
                )

    def test_text_rests_visible(self) -> None:
        """No label or any of its groups carries an opacity: entrances come from kit and end at 1."""
        for label, _, svg in self.each():
            for element, chain in walk(svg):
                if element.tag != f"{SVG}text":
                    continue
                for node in [*chain, element]:
                    self.assertIsNone(node.get("opacity"), f"{label}: {element.text!r}")

    def test_hidden_at_rest_means_in_transit(self) -> None:
        """Anything resting at opacity 0 is a spotlight's other stop: it carries a repeating fade."""
        for label, _, svg in self.each():
            for element in parse(svg).iter():
                if element.get("opacity") != "0":
                    continue
                fades = [
                    child
                    for child in element
                    if child.tag == f"{SVG}animate"
                    and child.get("attributeName") == "opacity"
                    and child.get("repeatCount") == "indefinite"
                ]
                self.assertTrue(fades, label)
                peak = max(float(value) for value in fades[0].get("values").split(";"))
                self.assertGreater(peak, 0.5, label)

    def test_loops_sit_on_the_page_clock_and_close(self) -> None:
        for label, _, svg in self.each():
            moving = 0
            for element, chain in walk(svg):
                if element.tag not in ANIMATIONS:
                    continue
                moving += 1
                values = element.attrib["values"].split(";")
                if element.get("keyTimes"):
                    times = [float(t) for t in element.attrib["keyTimes"].split(";")]
                    self.assertEqual(len(times), len(values), label)
                    self.assertEqual((times[0], times[-1]), (0.0, 1.0), label)
                    self.assertEqual(times, sorted(times), label)
                if element.get("repeatCount") != "indefinite":
                    continue
                dur = float(element.attrib["dur"].rstrip("s"))
                self.assertTrue(on_clock(dur), f"{label}: {dur}")
                name = element.get("attributeName")
                if name == "r" or (name == "opacity" and element.get("dur") == "2s"):
                    continue  # kit.live_dot's ring widens, fades and restarts
                if clipped(chain):
                    continue  # the ledger closes on drawn-again rows; see LedgerTurns
                self.assertEqual(values[0], values[-1], f"{label}: {element.attrib}")
            self.assertGreater(moving, 0, f"{label} has no motion")

    def test_every_card_keeps_moving_in_every_state(self) -> None:
        """A loop runs on every file, however few merges or open pull requests there are."""
        for count in (0, 1, 2, 5, 6, 13):
            for opened in ([], [entry("solo/repo", 5, 40)]):
                files = oss.render({}, context(merged_rows(count), opened))
                for name, svg in files.items():
                    loops = [
                        e
                        for e in parse(svg).iter()
                        if e.tag in ANIMATIONS and e.get("repeatCount") == "indefinite"
                    ]
                    self.assertTrue(
                        loops, f"{count} merged, {len(opened)} open: {name}"
                    )

    def test_motion_budget_and_weight(self) -> None:
        for label, _, svg in self.each():
            animated = {
                id(parent)
                for parent in parse(svg).iter()
                for child in parent
                if child.tag in ANIMATIONS
            }
            self.assertLessEqual(len(animated), 40, label)
            self.assertLessEqual(len(svg.encode("utf-8")), 30_000, label)

    def test_text_keeps_the_size_floor(self) -> None:
        for label, name, svg in self.each():
            floor = kit.MICRO_PHONE if name.endswith("-mobile.svg") else kit.MICRO
            for element in parse(svg).iter(f"{SVG}text"):
                self.assertGreaterEqual(
                    float(element.attrib["font-size"]),
                    floor,
                    f"{label}: {element.text!r}",
                )

    def test_ids_are_unique_and_every_reference_resolves(self) -> None:
        for label, _, svg in self.each():
            ids = re.findall(r' id="([^"]+)"', svg)
            self.assertEqual(len(ids), len(set(ids)), label)
            for reference in re.findall(r"url\(#([^)]+)\)", svg):
                self.assertIn(reference, ids, label)

    def test_green_only_on_the_newest_merge_and_amber_only_in_review(self) -> None:
        for label, name, svg in self.each():
            review = name.startswith("oss-review")
            for element in parse(svg).iter():
                colours = {element.get("fill"), element.get("stroke")}
                if kit.GREEN in colours:
                    self.assertFalse(review, label)
                    # the merged mark: the green disc on the rail
                    self.assertEqual(element.tag, f"{SVG}circle", label)
                    self.assertEqual(element.get("r"), "6.5", label)
                if kit.AMBER in colours:
                    self.assertTrue(review, label)
                    if element.tag == f"{SVG}text":
                        self.assertEqual(element.text, "IN REVIEW", label)
                    else:
                        self.assertEqual(element.tag, f"{SVG}circle", label)

    def test_render_is_pure_and_repeatable(self) -> None:
        before = copy.deepcopy(CTX["oss"])
        self.assertEqual(oss.render(DATA, CTX), FILES)
        self.assertEqual(CTX["oss"], before)


class Tiles(unittest.TestCase):
    def test_tiles_show_the_context_counts_at_both_widths(self) -> None:
        record = CTX["oss"]
        for name in ("oss.svg", "oss-mobile.svg"):
            shown = texts(FILES[name])
            for value in (
                record["merged_count"],
                record["open_count"],
                record["repos"],
            ):
                self.assertIn(str(value), shown, name)
            self.assertIn(oss._reach(record["combined_stars"]), shown, name)

    def test_combined_stars_round_down(self) -> None:
        self.assertEqual(oss._reach(238_999), "238K+")
        self.assertEqual(oss._reach(1_234_567), "1.2M+")
        self.assertEqual(oss._reach(999), "999")

    def test_the_merged_tile_is_the_emphasised_one(self) -> None:
        files = oss.render({}, context(merged_rows(7), [entry("solo/repo", 5, 40)]))
        for name in ("oss.svg", "oss-mobile.svg"):
            root = parse(files[name])
            tinted = [
                e
                for e in root.iter(f"{SVG}rect")
                if e.get("fill") == kit.BLUE_TINT and e.get("opacity") is None
            ]
            self.assertEqual(len(tinted), 1, name)
            x, y, w, h = (
                float(tinted[0].attrib[k]) for k in ("x", "y", "width", "height")
            )
            inside = [
                e.text
                for e in root.iter(f"{SVG}text")
                if x < float(e.attrib["x"]) < x + w and y < float(e.attrib["y"]) < y + h
            ]
            self.assertEqual(
                inside[:2],
                ["7", "MERGED"] if "-mobile" in name else ["7", "MERGED UPSTREAM"],
                name,
            )

    def test_the_eyebrow_carries_the_first_merge_date(self) -> None:
        """The oldest dated merge, not the newest that the ledger's first row already shows."""
        merged = [*merged_rows(3), {**merged_rows(1)[0], "date": "", "repo": "a/b"}]
        files = oss.render({}, context(merged))
        for name in ("oss.svg", "oss-mobile.svg"):
            self.assertEqual(texts(files[name])[0], "FIRST MERGE 2026-10-26", name)


class LedgerShowsTheNewest(unittest.TestCase):
    """The ledger shows the newest rows: five in the desktop window, six on the phone."""

    def test_the_desktop_window_rests_on_the_newest_five(self) -> None:
        svg = oss.render({}, context(merged_rows(9)))["oss.svg"]
        _, top, _, tall = clip_rect(svg)
        resting = [repo for y, repo in ledger_repos(svg) if top < y < top + tall]
        self.assertEqual(resting, [f"owner{i}/repo{i}" for i in range(oss.WINDOW)])

    def test_the_phone_lists_the_newest_six(self) -> None:
        svg = oss.render({}, context(merged_rows(9)))["oss-mobile.svg"]
        self.assertEqual(oss.MERGED_SHOWN, 6)
        self.assertEqual(
            phone_repos(svg), [f"owner{i}/repo{i}" for i in range(oss.MERGED_SHOWN)]
        )

    def test_the_newest_merge_carries_the_green_mark(self) -> None:
        files = oss.render({}, context(merged_rows(3)))
        for name in ("oss.svg", "oss-mobile.svg"):
            marks = [
                e
                for e in parse(files[name]).iter(f"{SVG}circle")
                if e.get("fill") == kit.GREEN
            ]
            nodes = sorted(
                float(e.attrib["cy"])
                for e in parse(files[name]).iter(f"{SVG}circle")
                if e.get("r") in ("4.5", "6.5")
            )
            self.assertEqual(len(marks), 1, name)
            self.assertEqual(float(marks[0].attrib["cy"]), nodes[0], name)

    def test_rows_carry_date_number_and_stars(self) -> None:
        files = oss.render({}, context([entry("acme/bank", 42, 24_153, "2026-10-24")]))
        for name in ("oss.svg", "oss-mobile.svg"):
            joined = " ".join(texts(files[name]))
            self.assertIn("2026-10-24", joined, name)
            self.assertIn("#42", joined, name)
            self.assertIn("24K", texts(files[name]), name)

    def test_a_commit_is_labelled_as_a_commit(self) -> None:
        self.assertEqual(oss._pr_label(COMMIT), "commit 489899c")
        self.assertEqual(oss._pr_number(COMMIT), 0)
        row = {
            "repo": "acme/vpc",
            "title": "Co-authored fix",
            "url": COMMIT,
            "date": "",
            "stars": 9,
        }
        files = oss.render({}, context([row]))
        self.assertIn("commit 489899c", texts(files["oss.svg"]))
        self.assertIn("COMMIT 489899C", texts(files["oss-mobile.svg"]))

    def test_long_names_and_titles_are_cut_with_three_dots(self) -> None:
        files = oss.render({}, long_context())
        for name in ("oss.svg", "oss-mobile.svg"):
            cut = [t for t in texts(files[name]) if t.endswith("...")]
            self.assertTrue(cut, name)


class MoreOnGitHub(unittest.TestCase):
    """+N more counts the rows past the ledger that GitHub's pull request search lists."""

    def more(self, svg: str) -> list[str]:
        return [t for t in texts(svg) if "on GitHub" in t]

    def test_both_widths_count_the_same_rows(self) -> None:
        files = oss.render({}, context(merged_rows(9)))
        for name in ("oss.svg", "oss-mobile.svg"):
            self.assertEqual(
                self.more(files[name]), ["+3 more pull requests on GitHub →"], name
            )
            self.assertIn(
                "3 more pull requests on GitHub", parse(files[name]).get("aria-label")
            )

    def test_one_more_is_singular(self) -> None:
        files = oss.render({}, context(merged_rows(7)))
        self.assertEqual(
            self.more(files["oss.svg"]), ["+1 more pull request on GitHub →"]
        )

    def test_a_commit_past_the_ledger_is_not_counted(self) -> None:
        commit = {
            "repo": "acme/vpc",
            "title": "Co-authored fix",
            "url": COMMIT,
            "date": "",
            "stars": 9,
        }
        files = oss.render({}, context([*merged_rows(6), commit]))
        for name in ("oss.svg", "oss-mobile.svg"):
            self.assertEqual(self.more(files[name]), [], name)
        files = oss.render({}, context([*merged_rows(6), commit, *merged_rows(8)[6:7]]))
        for name in ("oss.svg", "oss-mobile.svg"):
            self.assertEqual(
                self.more(files[name]), ["+1 more pull request on GitHub →"], name
            )

    def test_six_or_fewer_have_no_more_line(self) -> None:
        for count in (0, 1, 5, 6):
            for name, svg in oss.render({}, context(merged_rows(count))).items():
                self.assertEqual(self.more(svg), [], f"{count}: {name}")

    def test_the_cards_stop_growing_past_the_cap(self) -> None:
        for name in ("oss.svg", "oss-mobile.svg"):
            heights = {
                count: size_of(oss.render({}, context(merged_rows(count)))[name])[1]
                for count in (6, 7, 13, 40)
            }
            self.assertEqual(heights[13], heights[40], name)
            self.assertLess(heights[6], heights[7], name)  # the lines under the rule
            # the desktop names the other repositories on one line; the phone on
            # up to ALSO_SHOWN lines, so it may grow until those are full
            self.assertLessEqual(heights[7], heights[13], name)
            if name == "oss.svg":
                self.assertEqual(heights[7], heights[13], name)


class EveryRepositoryIsNamed(unittest.TestCase):
    """The ledger shows six rows, so the repositories past it are named under it and in the alt text."""

    PAST = [
        entry("small/tool", 7, 10, "2026-03-01"),
        entry("mid/lib", 8, 900, "2026-02-01"),
        entry("lower/kit", 9, 50, "2026-01-20"),
        entry("acme/bank", 10, 5000, "2026-01-10"),
    ]

    def files(self) -> dict[str, str]:
        return oss.render({}, context([*merged_rows(6), *self.PAST]))

    def test_the_alt_text_names_every_repository_most_starred_first(self) -> None:
        crafted = context([*merged_rows(6), *self.PAST])["oss"]
        for record, files in ((CTX["oss"], FILES), (crafted, self.files())):
            stars: dict[str, int] = {}
            for row in record["merged"]:
                stars[row["repo"]] = max(stars.get(row["repo"], 0), row["stars"] or 0)
            for name in ("oss.svg", "oss-mobile.svg"):
                label = parse(files[name]).get("aria-label")
                listed = label.split("most starred first: ", 1)[1]
                names = listed.split(". ", 1)[0].removesuffix(".").split(", ")
                self.assertEqual(sorted(names), sorted(stars), name)
                self.assertEqual(
                    [stars[repo] for repo in names],
                    sorted(stars.values(), reverse=True),
                    name,
                )

    def test_also_merged_into_names_the_rest_most_starred_first(self) -> None:
        for name, svg in self.files().items():
            if name.startswith("oss-review"):
                continue
            self.assertIn(ALSO, texts(svg), name)
            self.assertEqual(
                also_names(svg)[:3], ["acme/bank", "mid/lib", "lower/kit"], name
            )
            self.assertEqual(also_names(svg)[3:], ["+1 more"], name)
            # each named repository carries its star count
            self.assertIn("5K", texts(svg), name)

    def test_the_line_says_nothing_when_the_ledger_shows_every_repository(self) -> None:
        repeat = [{**row, "date": "2026-01-01"} for row in merged_rows(2)]
        for merged in (merged_rows(6), [*merged_rows(6), *repeat]):
            for name in ("oss.svg", "oss-mobile.svg"):
                svg = oss.render({}, context(merged))[name]
                self.assertNotIn(ALSO, texts(svg), name)

    def test_the_snapshot_names_the_most_starred_repository_past_the_ledger(
        self,
    ) -> None:
        shown = {row["repo"] for row in CTX["oss"]["merged"][: oss.MERGED_SHOWN]}
        rest = [row for row in CTX["oss"]["merged"] if row["repo"] not in shown]
        for name in ("oss.svg", "oss-mobile.svg"):
            if not rest:
                self.assertNotIn(ALSO, texts(FILES[name]), name)
                continue
            top = max(rest, key=lambda row: row["stars"] or 0)["repo"]
            self.assertEqual(also_names(FILES[name])[0], top, name)


class LedgerTurns(unittest.TestCase):
    """Past five rows the desktop ledger steps up a row every STEP seconds and closes on the page clock."""

    def test_the_ledger_turns_only_past_the_window(self) -> None:
        for count in (1, 5):
            self.assertIsNone(
                ticker(oss.render({}, context(merged_rows(count)))["oss.svg"])
            )
        for count in (6, 13):
            self.assertIsNotNone(
                ticker(oss.render({}, context(merged_rows(count)))["oss.svg"])
            )

    def test_one_row_per_step_through_every_row_on_the_page_clock(self) -> None:
        svg = oss.render({}, context(merged_rows(13)))["oss.svg"]
        animation = ticker(svg)
        self.assertEqual(
            oss.STEP * oss.MERGED_SHOWN, float(animation.get("dur").rstrip("s"))
        )
        self.assertTrue(on_clock(oss.STEP * oss.MERGED_SHOWN))
        stops = list(dict.fromkeys(offsets(animation)))
        self.assertEqual(stops, [-i * oss.PITCH for i in range(oss.MERGED_SHOWN + 1)])
        # each move takes ROLL, STEP after the last, and lands FADE before the
        # beat, so the arriving row's fade ends on it
        self.assertEqual(
            [(round(a, 2), round(b, 2)) for a, b in moves_of(animation)],
            [
                (
                    round(oss.STEP * (i + 1) - oss.FADE - oss.ROLL, 2),
                    round(oss.STEP * (i + 1) - oss.FADE, 2),
                )
                for i in range(oss.MERGED_SHOWN)
            ],
        )

    def test_no_row_is_drawn_while_the_window_cuts_it(self) -> None:
        """A row a move carries across the window's edge is at 0 for all of that move; a row at rest in view is at 1."""
        for count in (6, 13):
            svg = oss.render({}, context(merged_rows(count)))["oss.svg"]
            animation = ticker(svg)
            dur = float(animation.get("dur").rstrip("s"))
            rows = row_fades(svg)
            self.assertEqual(len(rows), oss.MERGED_SHOWN + oss.WINDOW)
            first = rows[0][0]

            def slot(y: float, t: float) -> float:
                return (y - first + at(animation, t, dur)) / oss.PITCH

            moves = moves_of(animation)
            for start, end in moves:
                for y, fade in rows:
                    if all(0 <= slot(y, t) <= oss.WINDOW - 1 for t in (start, end)):
                        continue
                    for k in range(11):
                        t = start + (end - start) * k / 10
                        self.assertAlmostEqual(
                            at(fade, t, dur), 0, 6, f"{count}: {y} at {t}"
                        )
            # midway through each rest, every row in view is fully drawn
            rests = [moves[0][0] / 2] + [
                (a[1] + b[0]) / 2 for a, b in zip(moves, moves[1:])
            ]
            for t in rests:
                for y, fade in rows:
                    if 0 <= slot(y, t) <= oss.WINDOW - 1:
                        self.assertAlmostEqual(
                            at(fade, t, dur), 1, 6, f"{count}: {y} at {t}"
                        )

    def test_no_rail_runs_through_the_seam(self) -> None:
        """The oldest row and the newest drawn again under it are not joined: a hairline marks the start over."""
        svg = oss.render({}, context(merged_rows(13)))["oss.svg"]
        nodes = sorted(
            {
                float(e.attrib["cy"])
                for e, chain in walk(svg)
                if e.tag == f"{SVG}circle"
                and clipped(chain)
                and e.get("r") in ("4.5", "6.5")
            }
        )
        seam = (nodes[oss.MERGED_SHOWN - 1] + nodes[oss.MERGED_SHOWN]) / 2
        rails, lines = [], []
        for element, chain in walk(svg):
            d = element.get("d") or ""
            if element.tag != f"{SVG}path" or not clipped(chain):
                continue
            if d.startswith(f"M{oss.RAIL} "):
                y1, y2 = (float(v) for v in re.findall(r"[\d.]+", d)[1:3])
                rails.append((y1, y2))
            elif "H" in d:
                lines.append(element)
        # every drawn row has a rail up to the one above, but the first and the seam
        self.assertEqual(len(rails), oss.MERGED_SHOWN + oss.WINDOW - 2)
        for y1, y2 in rails:
            self.assertFalse(y1 < seam < y2, (y1, y2))
        self.assertEqual(len(lines), 1)
        y = float(re.findall(r"[\d.]+", lines[0].get("d"))[1])
        self.assertTrue(nodes[oss.MERGED_SHOWN - 1] < y < nodes[oss.MERGED_SHOWN])

    def test_the_last_frame_is_the_first(self) -> None:
        """The rows past the turn are the first rows again, one full turn below them."""
        svg = oss.render({}, context(merged_rows(13)))["oss.svg"]
        rows = ledger_repos(svg)
        names = [repo for _, repo in rows]
        shown = oss.MERGED_SHOWN
        self.assertEqual(names[:shown], [f"owner{i}/repo{i}" for i in range(shown)])
        self.assertEqual(names[shown:], names[: oss.WINDOW])
        turn = -offsets(ticker(svg))[-1]
        for index in range(oss.WINDOW):
            self.assertAlmostEqual(rows[shown + index][0] - rows[index][0], turn)

    def test_every_row_steps_into_the_window(self) -> None:
        svg = oss.render({}, context(merged_rows(13)))["oss.svg"]
        _, top, _, tall = clip_rect(svg)
        stops = set(offsets(ticker(svg)))
        for y, repo in ledger_repos(svg):
            self.assertTrue(any(top < y + stop < top + tall for stop in stops), repo)

    def test_the_phone_ring_visits_each_merge_and_comes_home(self) -> None:
        svg = oss.render({}, context(merged_rows(9)))["oss-mobile.svg"]
        ring = next(e for e in parse(svg).iter(f"{SVG}circle") if e.get("r") == "10")
        animation = ring.find(f"{SVG}animateTransform")
        self.assertEqual(
            float(animation.get("dur").rstrip("s")), oss.STEP * oss.MERGED_SHOWN
        )
        nodes = sorted(
            {
                float(e.attrib["cy"])
                for e in parse(svg).iter(f"{SVG}circle")
                if e.get("r") in ("4.5", "6.5")
            }
        )
        stops = list(dict.fromkeys(offsets(animation)))
        self.assertEqual(
            [round(nodes[0] + stop, 1) for stop in stops], [round(n, 1) for n in nodes]
        )
        self.assertEqual(offsets(animation)[0], offsets(animation)[-1])
        self.assertEqual(float(ring.attrib["cy"]), nodes[0])  # it rests on the newest

    def test_the_phone_ring_goes_home_unseen(self) -> None:
        """It fades out on the oldest merge and in on the newest, never sweeping back up the card."""
        for count in (2, 4, 9):
            svg = oss.render({}, context(merged_rows(count)))["oss-mobile.svg"]
            ring = next(
                e for e in parse(svg).iter(f"{SVG}circle") if e.get("r") == "10"
            )
            travel = ring.find(f"{SVG}animateTransform")
            fade = ring.find(f"{SVG}animate")
            dur = float(travel.get("dur").rstrip("s"))
            self.assertTrue(on_clock(dur), dur)
            self.assertEqual(float(fade.get("dur").rstrip("s")), dur)
            start, end = moves_of(travel)[-1]
            for k in range(11):
                t = start + (end - start) * k / 10
                self.assertAlmostEqual(at(fade, t, dur), 0, 6, f"{count}: {t}")
            for start, end in moves_of(travel)[:-1]:
                self.assertAlmostEqual(at(fade, (start + end) / 2, dur), 1, 6, count)
            self.assertEqual(at(fade, 0, dur), 1, count)


class ReviewChips(unittest.TestCase):
    """oss-review: one chip per repository, the most starred first, a counter past one PR."""

    OPEN = [
        entry("small/repo", 1, 50),
        entry("big/repo", 2, 100),
        entry("big/repo", 3, 100),
        entry("mid/repo", 4, 70),
    ]

    def names(self, svg: str) -> list[str]:
        return [t for t in texts(svg) if t.endswith("/repo")]

    def test_chips_are_sorted_by_stars_at_both_widths(self) -> None:
        files = oss.render({}, context(opened=self.OPEN))
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            self.assertEqual(
                self.names(files[name]), ["big/repo", "mid/repo", "small/repo"], name
            )

    def test_a_counter_only_past_one_pull_request(self) -> None:
        files = oss.render({}, context(opened=self.OPEN))
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            counters = [
                e.text
                for e in parse(files[name]).iter(f"{SVG}text")
                if e.get("text-anchor") == "middle" and (e.text or "").isdigit()
            ]
            self.assertEqual(counters, ["2"], name)

    def test_the_eyebrow_says_where_not_the_count_the_tile_above_shows(self) -> None:
        """The open count is the summary card's fourth tile, so the review eyebrow
        counts the repositories instead and never repeats it."""
        record = CTX["oss"]
        repos = len({row["repo"] for row in record["open"]})
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            head = texts(FILES[name])[0]
            if repos:
                self.assertNotIn("OPEN PR", head, name)
                self.assertTrue(head.startswith(f"{repos} REPOSITOR"), name)
        files = oss.render({}, context(opened=self.OPEN))
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            self.assertEqual(texts(files[name])[0], "3 REPOSITORIES", name)
        one = oss.render({}, context(opened=[entry("solo/repo", 1, 5)]))
        self.assertEqual(texts(one["oss-review.svg"])[0], "1 REPOSITORY")

    def test_the_spotlight_rests_on_the_first_chip(self) -> None:
        files = oss.render({}, context(opened=self.OPEN))
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            lit = [
                e
                for e in parse(files[name]).iter(f"{SVG}rect")
                if e.get("stroke") == kit.BLUE_EDGE
            ]
            self.assertEqual(len(lit), 3, name)
            self.assertEqual([e.get("opacity") for e in lit], [None, "0", "0"], name)
            for element in lit:
                fade = element.find(f"{SVG}animate")
                loop, slot = oss._spotlight(len(lit))
                self.assertEqual(float(fade.get("dur").rstrip("s")), loop, name)
                self.assertGreaterEqual(slot, 2, name)
        single = oss.render({}, context(opened=[entry("solo/repo", 1, 5)]))
        self.assertNotIn(kit.BLUE_EDGE, single["oss-review.svg"])

    def test_many_repositories_fold_into_a_count(self) -> None:
        files = oss.render({}, long_context())
        desktop = parse(files["oss-review.svg"])
        tops = {
            float(e.attrib["y"])
            for e in desktop.iter(f"{SVG}rect")
            if e.get("height") == str(oss.CHIP_H)
        }
        self.assertLessEqual(len(tops), oss.REVIEW_ROWS)
        shown = len([t for t in texts(files["oss-review.svg"]) if "a-repository" in t])
        self.assertIn(f"+{20 - shown} more", texts(files["oss-review.svg"]))
        phone = [
            t
            for t in texts(files["oss-review-mobile.svg"])
            if t.startswith("some-very")
        ]
        self.assertEqual(len(phone), oss.PHONE_REVIEW)
        self.assertIn(
            f"+{20 - oss.PHONE_REVIEW} more", texts(files["oss-review-mobile.svg"])
        )

    def test_no_open_pull_requests_says_so_without_a_mark(self) -> None:
        files = oss.render({}, context())
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            self.assertEqual(texts(files[name])[0], "NO OPEN PRS", name)
            self.assertNotIn("IN REVIEW", texts(files[name]), name)
            self.assertNotIn(kit.AMBER, files[name], name)


class CommunityLine(unittest.TestCase):
    """Both review cards end with ctx's community line, and say nothing when it is empty."""

    OPEN = [entry("big/repo", 12, 100), entry("small/repo", 7, 50)]

    def sentence(self, svg: str) -> list[str]:
        shown = texts(svg)
        return " ".join(shown[shown.index("COMMUNITY IMPACT") + 1 :]).split()

    def test_both_review_cards_end_with_the_line(self) -> None:
        files = oss.render({}, context(opened=self.OPEN, line=LINE))
        wanted = LINE.partition(": ")[2].split()
        wanted[0] = wanted[0].capitalize()
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            self.assertEqual(self.sentence(files[name]), wanted, name)

    def test_a_long_line_wraps_whole(self) -> None:
        line = CTX["oss"]["community_line"] or LINE * 2
        files = oss.render({}, context(opened=self.OPEN, line=line))
        wanted = line.partition(": ")[2].split()
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            shown = self.sentence(files[name])
            self.assertEqual(
                [w.lower() for w in shown], [w.lower() for w in wanted], name
            )

    def test_a_line_without_a_label_stays_whole(self) -> None:
        files = oss.render(
            {}, context(opened=self.OPEN, line="Two accepted answers on Q&A")
        )
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            self.assertNotIn("COMMUNITY IMPACT", texts(files[name]), name)
            self.assertTrue(
                " ".join(texts(files[name])).endswith("Two accepted answers on Q&A")
            )

    def test_an_empty_line_draws_nothing_and_no_zero(self) -> None:
        files = oss.render({}, context(opened=self.OPEN, line=""))
        with_line = oss.render({}, context(opened=self.OPEN, line=LINE))
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            lowered = files[name].lower()
            self.assertNotIn("community", lowered, name)
            self.assertNotIn("accepted answer", lowered, name)
            self.assertIsNone(re.search(r">\s*0 ", files[name]), name)
            self.assertLess(size_of(files[name])[1], size_of(with_line[name])[1], name)

    def test_the_summary_cards_never_carry_it(self) -> None:
        files = oss.render({}, context(merged_rows(3), self.OPEN, LINE))
        for name in ("oss.svg", "oss-mobile.svg"):
            self.assertNotIn("ommunity", files[name], name)

    def test_the_snapshot_cards_show_exactly_the_context_line(self) -> None:
        line = CTX["oss"]["community_line"]
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            if line:
                wanted = line.partition(": ")[2].split()
                self.assertEqual(
                    [w.lower() for w in self.sentence(FILES[name])],
                    [w.lower() for w in wanted],
                )
            else:
                self.assertNotIn("COMMUNITY IMPACT", texts(FILES[name]))


if __name__ == "__main__":
    unittest.main()
