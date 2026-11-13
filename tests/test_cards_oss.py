"""Checks for the open-source cards: the files, their bounds and motion, and the four fixes of the port.

The shared checks run on the checked-in snapshot and assert rules, never values, so a
data refresh cannot fail them. Each fix has its own test on a small fixture.
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
DATA = renderer.load_data()
CTX = renderer.build_context(DATA)
FILES = oss.render(DATA, CTX)
NAMES = {
    "oss.svg",
    "oss-mobile.svg",
    "oss-merged.svg",
    "oss-merged-mobile.svg",
    "oss-review.svg",
    "oss-review-mobile.svg",
}
DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}
LINE = "Community impact: a confirmed fix in example/selfhost, plus 2 accepted answers"


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
    """count merged entries, newest first, one repository each."""
    return [
        entry(
            f"owner{index}/repo{index}",
            100 + index,
            5000 - index,
            f"2026-10-{28 - index:02d}",
        )
        for index in range(count)
    ]


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314


def texts(svg: str) -> list[str]:
    return [element.text or "" for element in parse(svg).iter(f"{SVG}text")]


def is_mono(element: ET.Element) -> bool:
    return "font-family" in element.attrib or element.get("class") in {"m", "k", "c"}


def span(element: ET.Element) -> tuple[float, float]:
    """Return the left and right edge of a text element, measured the way kit lays text out."""
    size, x = float(element.attrib["font-size"]), float(element.attrib["x"])
    width = kit.text_width(element.text or "", size, is_mono(element), kit.TRACK)
    anchor = element.get("text-anchor")
    if anchor == "middle":
        return x - width / 2, x + width / 2
    if anchor == "end":
        return x - width, x
    return x, x + width


class SharedRules(unittest.TestCase):
    def assert_inside(self, name: str, svg: str) -> None:
        root = parse(svg)
        _, _, width, height = map(float, root.attrib["viewBox"].split())
        for element in root.iter(f"{SVG}text"):
            left, right = span(element)
            y = float(element.attrib["y"])
            self.assertGreaterEqual(left, 0, f"{name}: {element.text!r}")
            self.assertLessEqual(right, width, f"{name}: {element.text!r}")
            self.assertTrue(0 < y < height, f"{name}: {element.text!r}")

    def test_the_module_returns_its_six_files(self) -> None:
        self.assertEqual(set(FILES), NAMES)

    def test_every_file_parses_and_carries_a_sentence_for_alt_text(self) -> None:
        for name, svg in FILES.items():
            root = parse(svg)
            self.assertEqual(root.get("role"), "img", name)
            self.assertGreater(len(root.get("aria-label", "")), 20, name)
            width = 320 if name.endswith("-mobile.svg") else 840
            self.assertEqual(float(root.attrib["width"]), width, name)

    def test_no_text_leaves_the_canvas(self) -> None:
        for name, svg in FILES.items():
            self.assert_inside(name, svg)

    def test_a_long_community_line_and_long_titles_stay_inside(self) -> None:
        long_title = "Replace the deprecated argument everywhere it is still read " * 4
        opened = [
            entry(
                "terraform-aws-modules/terraform-aws-dynamodb-table",
                n,
                900,
                title=long_title,
            )
            for n in range(1, 10)
        ]
        merged = [
            entry(
                "cloudposse/terraform-aws-tfstate-backend",
                n,
                443,
                "2026-03-24",
                long_title,
            )
            for n in range(1, 9)
        ]
        for name, svg in oss.render({}, context(merged, opened, LINE * 3)).items():
            self.assert_inside(name, svg)

    def test_no_dash_anywhere(self) -> None:
        sources = dict(FILES)
        sources["oss.py"] = (SCRIPTS / "cards" / "oss.py").read_text(encoding="utf-8")
        for name, content in sources.items():
            for dash in DASHES:
                self.assertNotIn(dash, content, name)

    def test_cards_are_poster_safe_and_self_contained(self) -> None:
        for name, svg in FILES.items():
            for banned in (
                'opacity="0"',
                "<set",
                "<script",
                "<image",
                "foreignObject",
                "href",
            ):
                self.assertNotIn(banned, svg, f"{name}: {banned}")
            self.assertNotIn("prefers-reduced-motion", svg, name)
            for element in parse(svg).iter(f"{SVG}animate"):
                if element.get("fill") == "freeze":
                    # an entrance ends on the element's own, finished state
                    self.assertTrue(
                        element.attrib["values"].endswith((";1", ";0")), name
                    )
                    self.assertTrue(element.attrib["keyTimes"].startswith("0;"), name)

    def test_entrances_are_over_early_and_loops_sit_on_the_page_clock(self) -> None:
        for name, svg in FILES.items():
            moving = 0
            for element in parse(svg).iter():
                if element.tag not in {f"{SVG}animate", f"{SVG}animateTransform"}:
                    continue
                moving += 1
                seconds = float(element.attrib["dur"].rstrip("s"))
                if element.get("repeatCount") == "indefinite":
                    self.assertIn(seconds, CLOCK, name)
                else:
                    self.assertLessEqual(seconds, 1.7, name)
            self.assertGreater(moving, 0, f"{name} has no motion")
            self.assertLessEqual(moving, 40, name)

    def test_text_keeps_the_size_floor(self) -> None:
        for name, svg in FILES.items():
            floor = kit.MICRO_PHONE if name.endswith("-mobile.svg") else kit.MICRO
            for element in parse(svg).iter(f"{SVG}text"):
                self.assertGreaterEqual(float(element.attrib["font-size"]), floor, name)

    def test_render_is_pure_and_repeatable(self) -> None:
        before = copy.deepcopy(CTX["oss"])
        self.assertEqual(oss.render(DATA, CTX), FILES)
        self.assertEqual(CTX["oss"], before)

    def test_empty_lists_still_draw_every_file(self) -> None:
        files = oss.render({}, context())
        self.assertEqual(set(files), NAMES)
        for name, svg in files.items():
            parse(svg)
            self.assertNotIn("more on GitHub", svg, name)


class DataRules(unittest.TestCase):
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
        self.assertEqual(oss._reach(999), "999")

    def test_list_kickers_carry_the_counts(self) -> None:
        record = CTX["oss"]
        self.assertTrue(
            any(
                t.startswith(f"{record['merged_count']} MERGED UPSTREAM")
                for t in texts(FILES["oss-merged.svg"])
            )
        )
        self.assertIn(
            f"{record['open_count']} OPEN PRS", texts(FILES["oss-review.svg"])
        )
        self.assertIn(
            f"{record['open_count']} OPEN PRS", texts(FILES["oss-review-mobile.svg"])
        )

    def test_a_commit_is_labelled_as_a_commit(self) -> None:
        url = "https://github.com/aws-ia/terraform-aws-vpc/commit/489899c7198b6d0099275e2ffee6852b98c6012b"
        self.assertEqual(oss._pr_label(url), "commit 489899c")
        self.assertEqual(oss._pr_number(url), 0)


class MergedListIsCapped(unittest.TestCase):
    """render-b-12: the desktop merged list grew by 46px with every merge."""

    def rows(self, svg: str) -> list[str]:
        return [text for text in texts(svg) if re.fullmatch(r"owner\d+/repo\d+", text)]

    def test_both_layouts_show_the_newest_six_and_one_more_row(self) -> None:
        files = oss.render({}, context(merged_rows(9)))
        newest = [f"owner{index}/repo{index}" for index in range(oss.MERGED_SHOWN)]
        self.assertEqual(oss.MERGED_SHOWN, 6)
        for name in ("oss-merged.svg", "oss-merged-mobile.svg"):
            self.assertEqual(self.rows(files[name]), newest, name)
            more = [text for text in texts(files[name]) if "more on GitHub" in text]
            self.assertEqual(len(more), 1, name)
            self.assertTrue(more[0].startswith("+3 more on GitHub"), name)

    def test_the_card_stops_growing_past_the_cap(self) -> None:
        heights = {
            count: float(
                parse(
                    oss.render({}, context(merged_rows(count)))["oss-merged.svg"]
                ).attrib["height"]
            )
            for count in (6, 7, 13, 40)
        }
        self.assertEqual(heights[7], heights[13])
        self.assertEqual(heights[13], heights[40])
        self.assertLess(heights[6], heights[7])  # no "+N more" row at exactly six

    def test_six_or_fewer_have_no_more_row(self) -> None:
        files = oss.render({}, context(merged_rows(6)))
        for name in ("oss-merged.svg", "oss-merged-mobile.svg"):
            self.assertEqual(len(self.rows(files[name])), 6, name)
            self.assertNotIn("more on GitHub", files[name], name)

    def test_the_snapshot_obeys_the_cap(self) -> None:
        dots = [
            element
            for element in parse(FILES["oss-merged.svg"]).iter(f"{SVG}circle")
            if element.get("r") == "3"
        ]
        self.assertLessEqual(len(dots), oss.MERGED_SHOWN)


class OpenNumbersAreCapped(unittest.TestCase):
    """render-b-15: every PR number was joined, sorted as text, and could reach the title."""

    def test_three_numbers_newest_first_then_a_count(self) -> None:
        opened = [entry("big/repo", n, 100) for n in (99, 1000, 5, 100, 250)]
        opened += [entry("small/repo", n, 50) for n in (7, 30, 8)]
        shown = texts(oss.render({}, context(opened=opened))["oss-review.svg"])
        self.assertIn("#1000, #250, #100 +2", shown)  # as text, "#99" would sort last
        self.assertIn("#30, #8, #7", shown)  # exactly three: no count

    def test_titles_follow_the_same_order_as_the_numbers(self) -> None:
        opened = [entry("big/repo", n, 100, title=f"Title {n}") for n in (9, 100, 20)]
        shown = texts(oss.render({}, context(opened=opened))["oss-review.svg"])
        self.assertIn("Title 100; Title 20; Title 9", shown)

    def test_the_numbers_never_reach_the_repository_name(self) -> None:
        repo = "terraform-aws-modules/terraform-aws-dynamodb-table-with-a-long-name"
        opened = [entry(repo, 50_000 + n, 100) for n in range(9)]
        root = parse(oss.render({}, context(opened=opened))["oss-review.svg"])
        title = next(e for e in root.iter(f"{SVG}text") if e.get("class") == "r")
        numbers = next(
            e for e in root.iter(f"{SVG}text") if (e.text or "").startswith("#")
        )
        self.assertEqual(numbers.text.count("#"), oss.NUMBERS_SHOWN)
        self.assertTrue(numbers.text.endswith(" +6"))
        self.assertLess(span(title)[1] + 16, span(numbers)[0])


class PhoneChipsMatchTheDesktop(unittest.TestCase):
    """phone-tests-oss-chips: the phone chips were sorted by name and dropped the stars."""

    MERGED = [
        entry("zeta/small", 1, 443, "2026-10-01"),
        entry("alpha/mid", 2, 24_152, "2026-09-01"),
        entry("Mid/big", 3, 109_397, "2026-08-01"),
        entry("alpha/mid", 4, 24_152, "2026-07-01"),
    ]
    LABELS = ["Mid/big 109.4K", "alpha/mid x2 24.2K", "zeta/small 443"]

    def chips(self, svg: str) -> list[str]:
        # the desktop writes two spaces between the parts; the phone wraps on single ones
        found = [" ".join(text.split()) for text in texts(svg)]
        return [text for text in found if text in self.LABELS]

    def test_phone_chips_are_sorted_by_stars_and_show_them(self) -> None:
        files = oss.render({}, context(self.MERGED))
        self.assertEqual(self.chips(files["oss-mobile.svg"]), self.LABELS)

    def test_both_widths_draw_the_same_chips_in_the_same_order(self) -> None:
        files = oss.render({}, context(self.MERGED))
        self.assertEqual(
            self.chips(files["oss.svg"]), self.chips(files["oss-mobile.svg"])
        )

    def test_the_snapshot_leads_with_its_most_starred_repository(self) -> None:
        merged = CTX["oss"]["merged"]
        if not merged:
            self.skipTest("no merged entries in the snapshot")
        top = max(merged, key=lambda row: row["stars"])["repo"]
        for name in ("oss.svg", "oss-mobile.svg"):
            first = next(t for t in texts(FILES[name]) if "/" in t)
            self.assertTrue(first.startswith(top[:12]), name)


class CommunityLine(unittest.TestCase):
    """Both open-PR cards end with ctx's community line, and say nothing when it is empty."""

    OPEN = [entry("big/repo", 12, 100), entry("small/repo", 7, 50)]

    def test_both_open_cards_end_with_the_line(self) -> None:
        files = oss.render({}, context(opened=self.OPEN, line=LINE))
        self.assertEqual(texts(files["oss-review.svg"])[-1], LINE)
        phone = texts(files["oss-review-mobile.svg"])
        self.assertIn("COMMUNITY IMPACT", phone)
        sentence = " ".join(phone[phone.index("COMMUNITY IMPACT") + 1 : -1])
        self.assertEqual(sentence.lower(), LINE.partition(": ")[2].lower())
        self.assertTrue(phone[-1].startswith("UPDATED "))

    def test_a_long_line_wraps_whole_on_the_desktop(self) -> None:
        files = oss.render(
            {}, context(opened=self.OPEN, line=CTX["oss"]["community_line"] or LINE * 2)
        )
        wanted = (CTX["oss"]["community_line"] or LINE * 2).split()
        shown = " ".join(texts(files["oss-review.svg"])).split()
        self.assertEqual(shown[-len(wanted) :], wanted)

    def test_an_empty_line_draws_nothing_and_no_zero(self) -> None:
        files = oss.render({}, context(opened=self.OPEN, line=""))
        for name in ("oss-review.svg", "oss-review-mobile.svg"):
            lowered = files[name].lower()
            self.assertNotIn("community", lowered, name)
            self.assertNotIn("accepted answer", lowered, name)
            self.assertIsNone(re.search(r">\s*0 ", files[name]), name)
        with_line = oss.render({}, context(opened=self.OPEN, line=LINE))
        self.assertLess(
            float(parse(files["oss-review.svg"]).attrib["height"]),
            float(parse(with_line["oss-review.svg"]).attrib["height"]),
        )

    def test_the_merged_cards_never_carry_it(self) -> None:
        files = oss.render({}, context(merged_rows(3), self.OPEN, LINE))
        for name in (
            "oss.svg",
            "oss-mobile.svg",
            "oss-merged.svg",
            "oss-merged-mobile.svg",
        ):
            self.assertNotIn("ommunity", files[name], name)

    def test_the_snapshot_cards_show_exactly_the_context_line(self) -> None:
        line = CTX["oss"]["community_line"]
        joined = " ".join(texts(FILES["oss-review.svg"]))
        if line:
            self.assertTrue(joined.endswith(line))
        else:
            self.assertNotIn("Community impact", joined)


if __name__ == "__main__":
    unittest.main()
