"""Checks for the stats lane: competitive, certification status and the phone twins of the vendored cards.

The shared checks run on the checked-in snapshot and assert rules, never values, so a
data refresh cannot fail them. Each fix of the port has its own test on a small fixture.
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
import mobile_cards as mobile
from cards import stats

SVG = "{http://www.w3.org/2000/svg}"
DATA = renderer.load_data()
CTX = renderer.build_context(DATA)
FILES = stats.render(DATA, CTX)
NAMES = {
    "competitive.svg",
    "competitive-mobile.svg",
    "certs-status.svg",
    "certs-status-mobile.svg",
    "github-mobile.svg",
    "leetcode-mobile.svg",
    "certs-mobile.svg",
}
DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}
MONO_CLASSES = {"k", "m", "c"}
# a 1x1 transparent GIF, standing in for a Credly badge image
PIXEL = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="
TERRAFORM = "HashiCorp Certified: Terraform Associate (003)"


def context(**changes: object) -> dict:
    """A context shaped like build_context's, holding only what the stats cards read."""
    ctx = {
        "today": "2026-11-13",
        "certs": {
            "active": [
                {
                    "name": "AWS Certified Developer - Associate",
                    "expires": "2029-01-31",
                },
                {"name": "AWS Certified Cloud Practitioner", "expires": "2029-01-31"},
            ],
            "lapsed": [{"name": TERRAFORM, "expired": "2026-09-10"}],
            "active_count": 2,
            "issuer": "AWS",
        },
        "leetcode": {
            "badge": "Guardian",
            "rating": 2166,
            "top": 1.12,
            "contests": 107,
            "solved": 1342,
            "by_difficulty": {
                "Easy": [481, 975],
                "Medium": [693, 2146],
                "Hard": [168, 989],
            },
            "history": [1435, 1502, 1490, 1811, 2007, 1930, 2166],
        },
        "github": {
            "contributions": 8295,
            "commits": 5617,
            "prs": 2020,
            "stars": 413,
            "streak": 5,
            "longest": 126,
            "active_days": 308,
            "calendar": [
                [week % 5, 0, 3, 9, 27, 1, day]
                for week, day in zip(range(24), range(24))
            ],
            "languages": [
                ["TypeScript", 51.2, "#3178c6"],
                ["Python", 29.4, "#3572A5"],
                ["JavaScript", 11.1, "#f1e05a"],
                ["CSS", 2.3, "#663399"],
                ["C++", 1.9, "#f34b7d"],
                ["Shell", 1.2, "#89e051"],
            ],
        },
        "contests": [
            {
                "title": "1st Place - Coding Cauldron Online, Version '23",
                "organizer": "NIT Trichy",
                "date": "March 2023",
            },
            {
                "title": "Rank 1289 - Google Kick Start '22, Round E",
                "organizer": "Google",
                "date": "September 2022",
            },
            {
                "title": "Rank 1699 - Google Kick Start '22, Round B",
                "organizer": "Google",
                "date": "May 2022",
            },
            {
                "title": "3rd Place - MOTHRA, Version '21",
                "organizer": "NIT Trichy",
                "date": "October 2021",
            },
            {
                "title": "4th Place - TriNIT Hackathon",
                "organizer": "NIT Warangal",
                "date": "March 2024",
            },
        ],
        "coding_stats": {
            "leetcode": {"best_contest_rank": "63"},
            "geeksforgeeks": {"problems_solved": "500+"},
            "hackerrank": {"problem_solving": "6-Star"},
        },
        "updated": {
            "github": "2026-11-13T07:52:32+00:00",
            "leetcode": "2026-11-13T07:52:27+00:00",
        },
        "badges": [
            {"name": "AWS Certified Developer - Associate", "image": PIXEL},
            {"name": "AWS Knowledge: Architecting (Retired)", "image": PIXEL},
            {"name": "Well-Architected Proficient", "image": PIXEL},
        ],
    }
    ctx.update(changes)
    return ctx


def snapshot(*extra: dict) -> dict:
    """The part of data.json the lane reads beside the context: the raw certification list."""
    return {
        "portfolio": {
            "certifications": [
                {
                    "name": "AWS Certified Developer - Associate",
                    "expiryDate": "2029-01-31",
                },
                {
                    "name": "AWS Certified Cloud Practitioner",
                    "expiryDate": "2029-01-31",
                },
                {"name": TERRAFORM, "expiryDate": "2026-09-10"},
                *extra,
            ]
        }
    }


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314 - the lane's own output


def texts(root: ET.Element) -> list[ET.Element]:
    return list(root.iter(f"{SVG}text"))


def contents(root: ET.Element) -> list[str]:
    return [element.text or "" for element in texts(root)]


def is_mono(element: ET.Element) -> bool:
    return (
        element.get("class") in MONO_CLASSES or element.get("font-family") == kit.MONO
    )


def extent(element: ET.Element) -> tuple[float, float]:
    """The left and right edge of a text element, as the kit measures it."""
    size = float(element.attrib["font-size"])
    tracking = 2 if element.get("class") == "k" else kit.TRACK
    span = kit.text_width(element.text or "", size, is_mono(element), tracking)
    x = float(element.attrib["x"])
    anchor = element.get("text-anchor")
    left = x - span / 2 if anchor == "middle" else x - span if anchor == "end" else x
    return left, left + span


def tiles(root: ET.Element) -> list[tuple[float, float, float, float]]:
    """The stat tiles of a card as (x, y, width, height)."""
    return [
        tuple(float(rect.attrib[key]) for key in ("x", "y", "width", "height"))
        for rect in root.iter(f"{SVG}rect")
        if rect.get("rx") == "10"
    ]


def tile_texts(root: ET.Element) -> list[ET.Element]:
    boxes = tiles(root)
    return [
        element
        for element in texts(root)
        if any(
            x <= float(element.attrib["x"]) <= x + w
            and y <= float(element.attrib["y"]) <= y + h
            for x, y, w, h in boxes
        )
    ]


class SharedRules(unittest.TestCase):
    def test_the_lane_writes_exactly_its_files(self) -> None:
        self.assertEqual(set(FILES), NAMES)
        self.assertEqual(set(stats.render(snapshot(), context())), NAMES)

    def test_every_file_parses_and_says_what_it_shows(self) -> None:
        for name, svg in FILES.items():
            with self.subTest(file=name):
                root = parse(svg)
                self.assertEqual(root.get("role"), "img")
                self.assertGreater(len(root.get("aria-label", "")), 20)
                width = 320 if name.endswith("-mobile.svg") else 840
                self.assertEqual(float(root.attrib["width"]), width)
                self.assertEqual(
                    root.attrib["viewBox"],
                    f"0 0 {root.attrib['width']} {root.attrib['height']}",
                )

    def test_no_text_leaves_the_canvas(self) -> None:
        for files in (FILES, stats.render(snapshot(), context())):
            for name, svg in files.items():
                root = parse(svg)
                _, _, width, height = map(float, root.attrib["viewBox"].split())
                margin = mobile.PAD if name.endswith("-mobile.svg") else 16
                for element in texts(root):
                    size = float(element.attrib["font-size"])
                    y = float(element.attrib["y"])
                    left, right = extent(element)
                    with self.subTest(file=name, text=element.text):
                        self.assertGreaterEqual(left, margin - 0.01)
                        self.assertLessEqual(right, width - margin + 0.01)
                        self.assertGreaterEqual(y - size, 0)
                        self.assertLessEqual(y + size * 0.25, height)

    def test_no_en_or_em_dash_and_nothing_external(self) -> None:
        for name, svg in FILES.items():
            with self.subTest(file=name):
                for dash in DASHES:
                    self.assertNotIn(dash, svg)
                self.assertNotIn("<script", svg)
                self.assertNotIn("foreignObject", svg)
                for href in re.findall(r'href="([^"]*)"', svg):
                    self.assertTrue(href.startswith(("data:", "#")), href[:40])

    def test_a_still_render_shows_the_whole_card(self) -> None:
        """Poster-safe: nothing rests hidden, and every run-once animation ends on the resting value."""
        rest = {"opacity": "1", "stroke-dashoffset": "0"}
        for name, svg in FILES.items():
            root = parse(svg)
            with self.subTest(file=name):
                self.assertNotIn('opacity="0"', svg)
                self.assertNotIn("visibility", svg)
            for parent in root.iter():
                for animation in parent:
                    if animation.tag not in (f"{SVG}animate", f"{SVG}animateTransform"):
                        continue
                    if animation.get("repeatCount") == "indefinite":
                        continue
                    last = animation.attrib["values"].split(";")[-1]
                    with self.subTest(
                        file=name, attribute=animation.get("attributeName")
                    ):
                        self.assertEqual(animation.get("fill"), "freeze")
                        self.assertIsNone(animation.get("begin"))
                        if animation.tag.endswith("animateTransform"):
                            identity = (
                                "1 1" if animation.get("type") == "scale" else "0 0"
                            )
                            self.assertEqual(last, identity)
                            self.assertIsNone(parent.get("transform"))
                        else:
                            name_ = animation.attrib["attributeName"]
                            self.assertEqual(last, rest[name_])
                            self.assertEqual(
                                parent.get(name_, rest[name_]), rest[name_]
                            )

    def test_every_loop_is_on_the_page_clock(self) -> None:
        for name, svg in FILES.items():
            for dur in re.findall(
                r'dur="([0-9.]+)s"[^>]*repeatCount="indefinite"', svg
            ):
                with self.subTest(file=name, dur=dur):
                    self.assertIn(float(dur), CLOCK)

    def test_motion_stays_inside_the_budget(self) -> None:
        for name, svg in FILES.items():
            root = parse(svg)
            animated = sum(
                1
                for parent in root.iter()
                if any(child.tag.startswith(f"{SVG}animate") for child in parent)
            )
            with self.subTest(file=name):
                self.assertLessEqual(animated, 40)

    def test_text_never_drops_below_the_floor(self) -> None:
        for name, svg in FILES.items():
            phone = name.endswith("-mobile.svg")
            for element in texts(parse(svg)):
                size = float(element.attrib["font-size"])
                with self.subTest(file=name, text=element.text):
                    self.assertGreaterEqual(size, kit.MICRO)
                    if phone and is_mono(element):
                        self.assertGreaterEqual(size, kit.MICRO_PHONE)

    def test_render_is_pure(self) -> None:
        data, ctx = snapshot(), context()
        before = copy.deepcopy((data, ctx))
        self.assertEqual(stats.render(data, ctx), stats.render(data, ctx))
        self.assertEqual((data, ctx), before)

    def test_missing_figures_show_a_placeholder_not_a_bare_mark(self) -> None:
        files = stats.render(
            snapshot(), context(coding_stats={}, github={}, leetcode={}, contests=[])
        )
        for name in ("competitive.svg", "competitive-mobile.svg"):
            words = contents(parse(files[name]))
            with self.subTest(file=name):
                self.assertNotIn("#", words)
                self.assertEqual(words.count(stats.MISSING), 3)


class Fixes(unittest.TestCase):
    def test_status_cards_carry_the_active_count_on_the_root(self) -> None:
        """validate-readme.py requires data-active-certifications on both status cards."""
        files = stats.render(snapshot(), context())
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            root = parse(files[name])
            with self.subTest(file=name):
                self.assertEqual(root.get("data-active-certifications"), "2")
                self.assertIn("2 active AWS certifications", root.get("aria-label"))
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            with self.subTest(snapshot=name):
                self.assertEqual(
                    parse(FILES[name]).get("data-active-certifications"),
                    str(CTX["certs"]["active_count"]),
                )
        self.assertNotIn("data-active-certifications", files["certs-mobile.svg"])

    def test_the_status_alt_text_is_sentences_that_keep_the_lapsed_cert_apart(
        self,
    ) -> None:
        files = stats.render(snapshot(), context())
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            label = parse(files[name]).get("aria-label")
            with self.subTest(file=name):
                self.assertTrue(label.startswith("2 active AWS certifications. "))
                self.assertNotIn(".;", label)
                self.assertNotIn("; ", label)
                self.assertNotIn("..", label)
                self.assertTrue(label.endswith("."))
                self.assertIn(f"Previously earned: {TERRAFORM}. Expired 2026-09-10.", label)

    def test_the_phone_github_card_keeps_the_follower_count_beside_the_stars(
        self,
    ) -> None:
        def render(**github: object):
            ctx = context(github=dict(context()["github"], **github))
            return parse(stats.render(snapshot(), ctx)["github-mobile.svg"])

        root = render(followers=120)
        line = f"413 total stars {stats.DOT} 120 followers"
        self.assertIn(line, contents(root))
        self.assertIn(line, root.get("aria-label"))
        for missing in (0, None):
            root = render(followers=missing)
            with self.subTest(followers=missing):
                self.assertNotIn("followers", " ".join(contents(root)))
                self.assertNotIn("followers", root.get("aria-label"))
                self.assertIn("413 total stars", contents(root))
        root = render(followers=120, stars=0)
        self.assertIn("120 followers", contents(root))
        self.assertEqual(len(tiles(root)), len(stats.GITHUB_TILES))

    def test_a_certification_without_an_expiry_is_named_and_never_counted(self) -> None:
        data = snapshot({"name": "Some Certificate", "expiryDate": ""})
        files = stats.render(data, context())
        desktop = parse(files["certs-status.svg"])
        self.assertEqual(desktop.get("data-active-certifications"), "2")
        self.assertIn("Expiry not recorded: Some Certificate.", contents(desktop))
        phone = contents(parse(files["certs-status-mobile.svg"]))
        self.assertIn("EXPIRY NOT RECORDED", phone)
        self.assertIn("UNRECORDED", " ".join(phone))

    def test_github_tiles_are_two_columns_of_whole_words_under_the_window_label(
        self,
    ) -> None:
        github = dict(context()["github"], contributions=1234567)
        root = parse(
            stats.render(snapshot(), context(github=github))["github-mobile.svg"]
        )
        boxes = tiles(root)
        self.assertEqual(len(boxes), len(stats.GITHUB_TILES))
        self.assertEqual(len({x for x, *_ in boxes}), 2)
        allowed = {"1,234,567", "5,617", "2,020", "308", "5", "126"} | {
            word for _, label in stats.GITHUB_TILES for word in label.upper().split()
        }
        inside = tile_texts(root)
        self.assertGreaterEqual(len(inside), 2 * len(boxes))
        for element in inside:
            for word in (element.text or "").split():
                with self.subTest(word=word):
                    self.assertIn(word, allowed)
        # the rolling figures sit under the label that says so
        label = next(e for e in texts(root) if e.text == "PAST 12 MONTHS")
        self.assertTrue(is_mono(label))
        self.assertLess(float(label.attrib["y"]), min(y for _, y, *_ in boxes))
        # stars are a lifetime total, so they sit outside the tiles, in a line of their own
        self.assertIn("413 total stars", contents(root))

    def test_retired_badges_are_left_out_of_the_phone_grid(self) -> None:
        svg = stats.render(snapshot(), context())["certs-mobile.svg"]
        root = parse(svg)
        self.assertEqual(len(list(root.iter(f"{SVG}image"))), 2)
        self.assertIn("2 CREDLY BADGES", contents(root))
        self.assertNotIn("Retired", svg)
        self.assertNotIn("Retired", root.get("aria-label"))
        # the live card: one image per badge that is not retired, counted the same way
        current = [b for b in CTX["badges"] if "retired" not in b["name"].lower()]
        live = parse(FILES["certs-mobile.svg"])
        if all(badge["image"] for badge in current) and current:
            self.assertEqual(len(list(live.iter(f"{SVG}image"))), len(current))
            self.assertIn(f"{len(current)} CREDLY BADGES", contents(live))
        self.assertNotIn("(Retired)", FILES["certs-mobile.svg"])

    def test_retired_badges_are_left_out_of_the_list_drawn_without_images(self) -> None:
        badges = [dict(badge, image=None) for badge in context()["badges"]]
        svg = stats.render(snapshot(), context(badges=badges))["certs-mobile.svg"]
        words = " ".join(contents(parse(svg)))
        self.assertIn("ACTIVE CERTIFICATIONS", words)
        self.assertIn("Well-Architected Proficient", words)
        self.assertNotIn("Retired", svg)

    def test_the_finishes_are_called_top_finishes_not_a_podium(self) -> None:
        files = stats.render(snapshot(), context())
        phone = parse(files["competitive-mobile.svg"])
        words = contents(phone)
        self.assertIn("TOP FINISHES", words)
        # the list keeps its 4th place, which is why it is not a podium
        self.assertIn("4th Place - TriNIT Hackathon", words)
        self.assertTrue(
            any(
                text.startswith("4TH")
                for text in contents(parse(files["competitive.svg"]))
            )
        )
        for name, svg in {**files, **FILES}.items():
            with self.subTest(file=name):
                self.assertNotIn("podium", svg.lower())

    def test_the_kick_start_tile_is_read_from_the_contests_on_both_layouts(
        self,
    ) -> None:
        files = stats.render(snapshot(), context())
        # the better of the two rounds in the list, with the same figure at both widths
        self.assertEqual(stats.kick_start(context()["contests"]), (1289, "22", "E"))
        desktop = contents(parse(files["competitive.svg"]))
        for expected in ("KICK START '22", "#1289", "ROUND E RANK"):
            self.assertIn(expected, desktop)
        phone = contents(parse(files["competitive-mobile.svg"]))
        self.assertIn("#1289", phone)
        self.assertIn("KICK START 2022 ROUND E", " ".join(phone))
        # a different result in the data changes both cards
        contests = [
            {"title": "Rank 77 - Google Kick Start '23, Round H", "date": "2023"}
        ]
        files = stats.render(snapshot(), context(contests=contests))
        desktop = contents(parse(files["competitive.svg"]))
        for expected in ("KICK START '23", "#77", "ROUND H RANK"):
            self.assertIn(expected, desktop)
        self.assertNotIn("#1289", desktop)
        phone = contents(parse(files["competitive-mobile.svg"]))
        self.assertIn("#77", phone)
        self.assertIn("KICK START 2023 ROUND H", " ".join(phone))
        # and no Kick Start result means no tile, on either card
        files = stats.render(snapshot(), context(contests=[]))
        for name in ("competitive.svg", "competitive-mobile.svg"):
            root = parse(files[name])
            with self.subTest(file=name):
                self.assertEqual(len(tiles(root)), 3)
                self.assertNotIn("KICK", " ".join(contents(root)))

    def legend(self, languages: list[list]) -> list[ET.Element]:
        github = dict(context()["github"], languages=languages)
        root = parse(
            stats.render(snapshot(), context(github=github))["github-mobile.svg"]
        )
        return [e for e in texts(root) if (e.text or "").endswith("%")]

    def test_the_language_legend_cannot_overlap_when_a_name_is_long(self) -> None:
        short = context()["github"]["languages"]
        long = [["Jupyter Notebook", 62.3, "#DA5B0B"], *short[:5]]
        for languages, columns in ((short, 2), (long, 1)):
            entries = self.legend(languages)
            self.assertEqual(len(entries), len(languages))
            rows: dict[str, list[tuple[float, float]]] = {}
            for element in entries:
                left, right = extent(element)
                self.assertLessEqual(right, mobile.WIDTH - mobile.PAD)
                rows.setdefault(element.attrib["y"], []).append((left, right))
            with self.subTest(columns=columns):
                self.assertEqual(max(len(row) for row in rows.values()), columns)
                for row in rows.values():
                    row.sort()
                    for (_, right), (left, _) in zip(row, row[1:]):
                        # the next entry's dot sits 15px before its text
                        self.assertLessEqual(right, left - 15)

    def test_a_dark_language_colour_is_lifted_to_three_to_one(self) -> None:
        svg = stats.render(snapshot(), context())["github-mobile.svg"]
        self.assertNotIn("#663399", svg)
        floor = stats._luminance(kit.BG) + 0.05
        for _, _, color in context()["github"]["languages"]:
            lifted = stats._legible(color)
            with self.subTest(color=color):
                self.assertGreaterEqual((stats._luminance(lifted) + 0.05) / floor, 3)
                self.assertIn(lifted, svg)
        # a colour that already passes is kept as GitHub gives it
        self.assertEqual(stats._legible("#3178c6"), "#3178c6")


if __name__ == "__main__":
    unittest.main()
