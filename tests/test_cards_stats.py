"""Checks for the stats lane: competitive, certification status and the phone twins of the vendored cards.

The shared checks run on the checked-in snapshot and on crafted contexts (empty, long, many)
and assert rules, never values, so a data refresh cannot fail them. Each rule a fix or the
new look added has its own test on a small fixture.
"""

from __future__ import annotations

import copy
import datetime
import importlib.util
import math
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
YEAR_MONTH = re.compile(r"\b(?:" + "|".join(stats.MONTHS) + r") (?:19|20)[0-9]{2}\b")
MONO_CLASSES = {"k", "m", "c"}
SANS_CLASSES = {"t", "s", "b"}
# a 1x1 transparent GIF, standing in for a Credly badge image
PIXEL = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="
TERRAFORM = "HashiCorp Certified: Terraform Associate (003)"
# the share of kit's sans measure a 600-weight line sets at: the hero's figure, fixed here
# so a module that claims a tighter one cannot wrap its names past their boxes unnoticed
SET_SANS = 0.9
# the svg-forge validator's error line for a standalone file (SV013): the phone badge card
# inlines Credly images and may pass the 50 KB warning, never this
BADGE_CARD_LIMIT = 100 * 1024
# stand-ins for Credly images: a certification's is about 8 KB, a learning badge's about 6 KB
CERT_IMAGE = "data:image/png;base64," + "A" * 8200
LEARNING_IMAGE = "data:image/png;base64," + "B" * 6000


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
            "leetcode": {
                "best_contest_rank": "63",
                "rating_history": [
                    ["2022-02-13", 1435],
                    ["2024-05-01", 1930],
                    ["2026-09-13", 2166],
                ],
            },
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


def empty() -> dict:
    """Every source missing: no stats, no contests, no badges, no certifications."""
    return context(
        coding_stats={},
        github={},
        leetcode={},
        contests=[],
        badges=[],
        updated={},
        certs={"active": [], "lapsed": [], "active_count": 0, "issuer": ""},
    )


def long() -> dict:
    """Twelve finishes with long names, seven certifications, two of them oddly named."""
    places = ["1st", "2nd", "3rd", "4th"] * 3
    contests = [
        {
            "title": f"{place} Place - A Very Long Hackathon Name That Keeps Going {n}, "
            f"Grand Finals Edition Of The Year '2{n % 10}",
            "organizer": "An Institute With A Rather Long Name Of Its Own",
            "date": f"March 20{20 + n % 6}",
        }
        for n, place in enumerate(places)
    ]
    active = [
        {
            "name": f"AWS Certified Made Up Track Number {n} - Professional",
            "expires": f"202{7 + n % 3}-0{1 + n}-15",
        }
        for n in range(6)
    ] + [
        {
            "name": "Acme Certified Kubernetes Thing With A Long Name",
            "expires": "2027-05-05",
        }
    ]
    certs = {
        "active": active,
        "lapsed": [
            {
                "name": "Acme Certified Something Long Enough To Need Clipping On A Phone And Then Some",
                "expired": "2025-01-01",
            }
        ],
        "active_count": len(active),
        "issuer": "AWS / OTHER",
    }
    github = dict(
        context()["github"],
        contributions=123456789,
        commits=987654,
        calendar=[[40] * 7] * 60,
    )
    return context(contests=contests, certs=certs, github=github)


CASES = {
    "snapshot": (DATA, CTX),
    "fixture": (snapshot(), context()),
    "empty": (snapshot(), empty()),
    "long": (snapshot({"name": "Some Certificate", "expiryDate": ""}), long()),
}


def rendered(case: str) -> dict[str, str]:
    data, ctx = CASES[case]
    return FILES if case == "snapshot" else stats.render(data, ctx)


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


def extent(element: ET.Element, fit: float = 1) -> tuple[float, float]:
    """The left and right edge of a text element, as the kit measures it (sans scaled by fit)."""
    size = float(element.attrib["font-size"])
    tracking = 2 if element.get("class") == "k" else kit.TRACK
    span = kit.text_width(element.text or "", size, is_mono(element), tracking)
    if not is_mono(element):
        span *= fit
    x = float(element.attrib["x"])
    anchor = element.get("text-anchor")
    left = x - span / 2 if anchor == "middle" else x - span if anchor == "end" else x
    return left, left + span


def boxes(root: ET.Element) -> list[tuple[float, float, float, float]]:
    """Every rect drawn inside the card, as (x, y, width, height), the frame left out."""
    width = float(root.attrib["width"])
    out = []
    for rect in root.iter(f"{SVG}rect"):
        if "width" not in rect.attrib or "x" not in rect.attrib:
            continue
        box = tuple(float(rect.attrib[key]) for key in ("x", "y", "width", "height"))
        if box[2] < width - 4:
            out.append(box)
    return out


def tile_rects(root: ET.Element) -> list[ET.Element]:
    """The stat tiles' rects: radius 10 and still (the lit border that moves is not a tile)."""
    return [
        rect
        for rect in root.iter(f"{SVG}rect")
        if rect.get("rx") == "10" and not len(rect)
    ]


def tiles(root: ET.Element) -> list[tuple[float, float, float, float]]:
    """The stat tiles of a card as (x, y, width, height)."""
    return [
        tuple(float(rect.attrib[key]) for key in ("x", "y", "width", "height"))
        for rect in tile_rects(root)
    ]


def tile_texts(root: ET.Element) -> list[ET.Element]:
    found = tiles(root)
    return [
        element
        for element in texts(root)
        if any(
            x <= float(element.attrib["x"]) <= x + w
            and y <= float(element.attrib["y"]) <= y + h
            for x, y, w, h in found
        )
    ]


def image_bytes(root: ET.Element) -> int:
    """How much of a card is inlined images."""
    return sum(len(i.get("href") or "") for i in root.iter(f"{SVG}image"))


def cell_dates(words: list[str]) -> list[str]:
    """The expiry month each certification cell shows, in drawing order (the eyebrow skipped)."""
    return [
        found.group()
        for word in words
        if "NEXT" not in word and (found := YEAR_MONTH.search(word))
    ]


def counted(root: ET.Element) -> list[int]:
    """The badges a card counts in its +N lines rather than draws."""
    return [int(n) for n in re.findall(r"\+([0-9]+) ", " ".join(contents(root)))]


def loops(svg: str) -> list[ET.Element]:
    return [
        animation
        for animation in parse(svg).iter()
        if animation.tag.startswith(f"{SVG}animate")
        and animation.get("repeatCount") == "indefinite"
    ]


class SharedRules(unittest.TestCase):
    def test_the_lane_writes_exactly_its_files(self) -> None:
        for case in CASES:
            with self.subTest(case=case):
                self.assertEqual(set(rendered(case)), NAMES)

    def test_every_file_parses_and_says_what_it_shows(self) -> None:
        for case in CASES:
            for name, svg in rendered(case).items():
                with self.subTest(case=case, file=name):
                    root = parse(svg)
                    self.assertEqual(root.get("role"), "img")
                    self.assertGreater(len(root.get("aria-label", "")), 20)
                    width = 320 if name.endswith("-mobile.svg") else 840
                    self.assertEqual(float(root.attrib["width"]), width)
                    self.assertEqual(
                        root.attrib["viewBox"],
                        f"0 0 {root.attrib['width']} {root.attrib['height']}",
                    )

    def test_every_card_is_the_flat_surface_with_no_accent_bar(self) -> None:
        """The new look: kit's frame on BG first, and none of the old engine's left accent bar."""
        for case in CASES:
            for name, svg in rendered(case).items():
                root = parse(svg)
                with self.subTest(case=case, file=name):
                    # the root's first rect (the clip sits inside defs) is kit's surface
                    surface = root.findall(f"{SVG}rect")[0]
                    self.assertEqual(surface.get("fill"), kit.BG)
                    self.assertEqual(surface.get("stroke"), kit.HAIR)
                    self.assertNotIn('width="3" height="26"', svg)
                    self.assertNotIn("linearGradient", svg)
                    self.assertNotIn("skewX", svg)

    def test_no_text_leaves_the_canvas(self) -> None:
        for case in CASES:
            for name, svg in rendered(case).items():
                root = parse(svg)
                _, _, width, height = map(float, root.attrib["viewBox"].split())
                margin = stats.PHONE_PAD if name.endswith("-mobile.svg") else stats.PAD
                for element in texts(root):
                    size = float(element.attrib["font-size"])
                    y = float(element.attrib["y"])
                    left, right = extent(element)
                    with self.subTest(case=case, file=name, text=element.text):
                        self.assertGreaterEqual(left, margin - 0.01)
                        self.assertLessEqual(right, width - margin + 0.01)
                        self.assertGreaterEqual(y - size, 0)
                        self.assertLessEqual(y + size * 0.25, height)

    def test_every_label_stays_inside_its_box(self) -> None:
        """A text that starts in a tile, cell, row or pill ends inside it too, at kit's measure.

        Sans text is measured at SET_SANS of kit's deliberately wide measure, the share a
        600-weight line really sets at (the hero's figure); mono text is measured exactly.
        """
        for case in CASES:
            for name, svg in rendered(case).items():
                root = parse(svg)
                found = boxes(root)
                for element in texts(root):
                    x, y = float(element.attrib["x"]), float(element.attrib["y"])
                    holders = [
                        (bw * bh, bx, bw)
                        for bx, by, bw, bh in found
                        if bx <= x <= bx + bw and by <= y <= by + bh
                    ]
                    if not holders:
                        continue
                    _, bx, bw = min(holders)
                    left, right = extent(element, SET_SANS)
                    with self.subTest(case=case, file=name, text=element.text):
                        self.assertGreaterEqual(left, bx - 0.01)
                        self.assertLessEqual(right, bx + bw + 0.01)

    def test_no_en_or_em_dash_and_nothing_external(self) -> None:
        for case in CASES:
            for name, svg in rendered(case).items():
                with self.subTest(case=case, file=name):
                    for dash in DASHES:
                        self.assertNotIn(dash, svg)
                    self.assertNotIn("<script", svg)
                    self.assertNotIn("foreignObject", svg)
                    self.assertNotIn("prefers-reduced-motion", svg)
                    for href in re.findall(r'href="([^"]*)"', svg):
                        self.assertTrue(href.startswith(("data:", "#")), href[:40])

    def test_a_still_render_shows_the_whole_card(self) -> None:
        """Poster-safe: nothing rests hidden, and every run-once animation ends on the resting value."""
        rest = {"opacity": "1", "stroke-dashoffset": "0"}
        for case in CASES:
            for name, svg in rendered(case).items():
                root = parse(svg)
                with self.subTest(case=case, file=name):
                    self.assertNotIn('opacity="0"', svg)
                    self.assertNotIn("visibility", svg)
                for parent in root.iter():
                    for animation in parent:
                        if animation.tag not in (
                            f"{SVG}animate",
                            f"{SVG}animateTransform",
                        ):
                            continue
                        if animation.get("repeatCount") == "indefinite":
                            continue
                        last = animation.attrib["values"].split(";")[-1]
                        with self.subTest(
                            case=case,
                            file=name,
                            attribute=animation.get("attributeName"),
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

    def test_a_loop_opens_on_what_the_still_render_shows(self) -> None:
        """Loops that fade start visible, and loops that move start at the element's own place."""
        for case in CASES:
            for name, svg in rendered(case).items():
                for animation in loops(svg):
                    first = animation.attrib["values"].split(";")[0]
                    with self.subTest(case=case, file=name, values=first):
                        if animation.get("attributeName") == "opacity":
                            self.assertNotEqual(float(first), 0)
                        if animation.get("type") == "translate":
                            self.assertEqual(first, "0 0")

    def test_every_loop_is_on_the_page_clock(self) -> None:
        for case in CASES:
            for name, svg in rendered(case).items():
                for animation in loops(svg):
                    dur = float(animation.attrib["dur"].removesuffix("s"))
                    begin = float((animation.get("begin") or "0s").removesuffix("s"))
                    with self.subTest(case=case, file=name, dur=dur):
                        self.assertIn(dur, CLOCK)
                        # a loop that waits for its turn still starts inside one turn of its clock
                        self.assertLess(begin, dur)

    def test_motion_stays_inside_the_budget(self) -> None:
        for case in CASES:
            for name, svg in rendered(case).items():
                root = parse(svg)
                animated = sum(
                    1
                    for parent in root.iter()
                    if any(child.tag.startswith(f"{SVG}animate") for child in parent)
                )
                with self.subTest(case=case, file=name):
                    self.assertLessEqual(animated, 40)
                    # and every card with something to show keeps moving after its entrance
                    if case != "empty":
                        self.assertTrue(loops(svg))

    def test_text_never_drops_below_the_floor(self) -> None:
        for case in CASES:
            for name, svg in rendered(case).items():
                phone = name.endswith("-mobile.svg")
                for element in texts(parse(svg)):
                    size = float(element.attrib["font-size"])
                    with self.subTest(case=case, file=name, text=element.text):
                        self.assertGreaterEqual(size, kit.MICRO)
                        if phone and is_mono(element):
                            self.assertGreaterEqual(size, kit.MICRO_PHONE)

    def test_render_is_pure(self) -> None:
        for case in ("fixture", "long"):
            data, ctx = CASES[case]
            before = copy.deepcopy((data, ctx))
            with self.subTest(case=case):
                self.assertEqual(stats.render(data, ctx), stats.render(data, ctx))
                self.assertEqual((data, ctx), before)

    def test_missing_figures_show_a_placeholder_not_a_bare_mark(self) -> None:
        files = rendered("empty")
        for name in ("competitive.svg", "competitive-mobile.svg"):
            words = contents(parse(files[name]))
            with self.subTest(file=name):
                self.assertNotIn("#", words)
                self.assertEqual(words.count(stats.MISSING), 3)

    def test_every_card_stays_under_the_size_budget(self) -> None:
        """30 KB a card; the phone badge card inlines its images and keeps under the 100 KB error line."""
        for case in CASES:
            for name, svg in rendered(case).items():
                size = len(svg.encode("utf-8"))
                with self.subTest(case=case, file=name):
                    self.assertLess(
                        size,
                        BADGE_CARD_LIMIT if name == "certs-mobile.svg" else 30 * 1024,
                    )


class Colour(unittest.TestCase):
    def test_green_is_only_the_active_mark(self) -> None:
        for case in CASES:
            for name, svg in rendered(case).items():
                with self.subTest(case=case, file=name):
                    if not name.startswith("certs-status") or "0 ACTIVE" in svg:
                        self.assertNotIn(kit.GREEN, svg)
                        continue
                    # the live dot (its ring and its fill) and the count beside it
                    self.assertEqual(svg.count(kit.GREEN), 3)
                    mark = [e for e in texts(parse(svg)) if e.get("fill") == kit.GREEN]
                    self.assertEqual(len(mark), 1)
                    self.assertTrue(mark[0].text.endswith(" ACTIVE"))

    def test_amber_on_the_competitive_card_stays_on_the_leetcode_tile(self) -> None:
        for case in ("snapshot", "fixture", "long"):
            for name in ("competitive.svg", "competitive-mobile.svg"):
                root = parse(rendered(case)[name])
                lead = [
                    r for r in tile_rects(root) if r.get("stroke") == stats.AMBER_EDGE
                ]
                self.assertEqual(len(lead), 1)
                x, y, w, h = (
                    float(lead[0].attrib[key]) for key in ("x", "y", "width", "height")
                )
                for element in root.iter():
                    if kit.AMBER not in (element.get("fill"), element.get("stroke")):
                        continue
                    with self.subTest(case=case, file=name, text=element.text):
                        self.assertTrue(
                            x <= float(element.attrib["x"]) <= x + w
                            and y <= float(element.attrib["y"]) <= y + h
                        )

    def test_the_leetcode_twin_keeps_amber_and_leaves_red_and_green_out(self) -> None:
        for case in CASES:
            svg = rendered(case)["leetcode-mobile.svg"]
            with self.subTest(case=case):
                self.assertNotIn("#f87171", svg)
                self.assertNotIn(kit.GREEN, svg)
                self.assertIn(kit.AMBER, svg)


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
            with self.subTest(empty=name):
                self.assertEqual(
                    parse(rendered("empty")[name]).get("data-active-certifications"),
                    "0",
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
                self.assertIn(
                    f"Previously earned: {TERRAFORM}. Expired 2026-09-10.", label
                )
                # every active certification is named in full, with its expiry
                self.assertIn(
                    "AWS Certified Developer - Associate until 2029-01-31", label
                )

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
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            root = parse(files[name])
            words = contents(root)
            with self.subTest(file=name):
                self.assertEqual(root.get("data-active-certifications"), "2")
                self.assertIn("EXPIRY NOT RECORDED", words)
                self.assertIn("Some Certificate", words)
                self.assertIn(
                    "Expiry not recorded: Some Certificate.", root.get("aria-label")
                )
                self.assertIn("2 ACTIVE", words)

    def test_github_tiles_are_two_columns_of_whole_words_under_the_window_label(
        self,
    ) -> None:
        github = dict(context()["github"], contributions=1234567)
        root = parse(
            stats.render(snapshot(), context(github=github))["github-mobile.svg"]
        )
        found = tiles(root)
        self.assertEqual(len(found), len(stats.GITHUB_TILES))
        self.assertEqual(len({x for x, *_ in found}), 2)
        allowed = {"1,234,567", "5,617", "2,020", "308", "5", "126"} | {
            word for _, label in stats.GITHUB_TILES for word in label.upper().split()
        }
        inside = tile_texts(root)
        self.assertGreaterEqual(len(inside), 2 * len(found))
        for element in inside:
            for word in (element.text or "").split():
                with self.subTest(word=word):
                    self.assertIn(word, allowed)
        # the rolling figures sit under the label that says so
        label = next(e for e in texts(root) if "PAST 12 MONTHS" in (e.text or ""))
        self.assertTrue(is_mono(label))
        self.assertLess(float(label.attrib["y"]), min(y for _, y, *_ in found))
        # stars are a lifetime total, so they sit outside the tiles, in a line of their own
        self.assertIn("413 total stars", contents(root))

    def test_retired_badges_are_left_out_of_the_phone_grid(self) -> None:
        root = parse(stats.render(snapshot(), context())["certs-mobile.svg"])
        drawn = [
            g.find(f"{SVG}title").text
            for g in root.iter(f"{SVG}g")
            if g.find(f"{SVG}image") is not None and g.find(f"{SVG}title") is not None
        ]
        self.assertEqual(len(list(root.iter(f"{SVG}image"))), 2)
        self.assertFalse([name for name in drawn if "Retired" in name])
        self.assertNotIn("Retired", " ".join(contents(root)))

    def test_the_phone_badge_counts_equal_the_gallery_counts(self) -> None:
        """The desktop gallery counts every badge it shows, retired ones too, so the phone
        card counts the same badges even though its grid leaves the retired ones out."""
        root = parse(stats.render(snapshot(), context())["certs-mobile.svg"])
        words = " ".join(contents(root))
        self.assertIn("3 CREDLY BADGES", words)
        self.assertIn("1 INDUSTRY CERTIFICATIONS", words)
        self.assertIn("2 LEARNING AND PARTNER BADGES", words)
        self.assertIn("+1 MORE ON CREDLY", words)
        self.assertTrue(root.get("aria-label").startswith("3 Credly badges: "))
        # the live card: the eyebrow, the two headings and drawn plus +N all count the
        # gallery, which is every imaged badge the renderer read from the Credly card
        gallery = [b for b in CTX["badges"] if b.get("image")]
        if gallery:
            live = parse(FILES["certs-mobile.svg"])
            words = " ".join(contents(live))
            self.assertIn(f"{len(gallery)} CREDLY BADGES", words)
            headings = re.findall(
                r"([0-9]+) (?:INDUSTRY CERTIFICATIONS|LEARNING AND PARTNER BADGES)",
                words,
            )
            self.assertEqual(sum(map(int, headings)), len(gallery))
            drawn = len(list(live.iter(f"{SVG}image")))
            self.assertEqual(drawn + sum(counted(live)), len(gallery))
            self.assertTrue(
                live.get("aria-label").startswith(f"{len(gallery)} Credly badges: ")
            )

    def test_retired_badges_are_left_out_of_the_list_drawn_without_images(self) -> None:
        badges = [dict(badge, image=None) for badge in context()["badges"]]
        svg = stats.render(snapshot(), context(badges=badges))["certs-mobile.svg"]
        words = " ".join(contents(parse(svg)))
        self.assertIn("ACTIVE CERTIFICATIONS", words)
        self.assertIn("Well-Architected Proficient", words)
        self.assertNotIn("Retired", svg)

    def test_the_finishes_are_called_top_finishes_not_a_podium(self) -> None:
        files = stats.render(snapshot(), context())
        for name in ("competitive.svg", "competitive-mobile.svg"):
            words = contents(parse(files[name]))
            with self.subTest(file=name):
                self.assertIn("TOP FINISHES", words)
                # the list keeps its 4th place, which is why it is not a podium
                self.assertIn("4TH", words)
                self.assertIn("TriNIT Hackathon", words)
        for name, svg in {**files, **FILES}.items():
            with self.subTest(file=name):
                self.assertNotIn("podium", svg.lower())

    def test_the_kick_start_tile_is_read_from_the_contests_on_both_layouts(
        self,
    ) -> None:
        files = stats.render(snapshot(), context())
        # the better of the two rounds in the list, with the same figure and words at both widths
        self.assertEqual(stats.kick_start(context()["contests"]), (1289, "22", "E"))
        for name in ("competitive.svg", "competitive-mobile.svg"):
            words = contents(parse(files[name]))
            with self.subTest(file=name):
                for expected in ("KICK START '22", "#1289", "ROUND E RANK"):
                    self.assertIn(expected, words)
        # a different result in the data changes both cards
        contests = [
            {"title": "Rank 77 - Google Kick Start '23, Round H", "date": "2023"}
        ]
        files = stats.render(snapshot(), context(contests=contests))
        for name in ("competitive.svg", "competitive-mobile.svg"):
            words = contents(parse(files[name]))
            with self.subTest(file=name):
                for expected in ("KICK START '23", "#77", "ROUND H RANK"):
                    self.assertIn(expected, words)
                self.assertNotIn("#1289", words)
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
        long_ = [["Jupyter Notebook", 62.3, "#DA5B0B"], *short[:5]]
        for languages, columns in ((short, 2), (long_, 1)):
            entries = self.legend(languages)
            self.assertEqual(len(entries), len(languages))
            rows: dict[str, list[tuple[float, float]]] = {}
            for element in entries:
                left, right = extent(element)
                self.assertLessEqual(right, stats.PHONE - stats.PHONE_PAD)
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


class Competitive(unittest.TestCase):
    def test_a_finish_splits_into_place_event_and_edition(self) -> None:
        self.assertEqual(
            stats.finish(
                {
                    "title": "1st Place - Acme Quiz, QZX '22",
                    "organizer": "Acme College",
                    "date": "June 2022",
                }
            ),
            {
                "place": "1ST",
                "event": "Acme Quiz",
                "edition": "QZX '22",
                "host": "Acme College",
            },
        )
        # no year in the title: the edition says when, from the date, in the '24 form the
        # other rows and the alt text use
        self.assertEqual(
            stats.finish({"title": "4th Place - Acme Hackathon", "date": "March 2024"})[
                "edition"
            ],
            "'24",
        )
        self.assertEqual(
            stats.finish({"title": "2nd Place - Acme Cup, Finals", "date": "May 2021"})[
                "edition"
            ],
            "Finals '21",
        )

    def test_the_ledger_lists_every_finish_up_to_its_cap(self) -> None:
        for name in ("competitive.svg", "competitive-mobile.svg"):
            words = contents(parse(stats.render(snapshot(), context())[name]))
            places = [w for w in words if re.fullmatch("[1-4](ST|ND|RD|TH)", w)]
            with self.subTest(file=name):
                self.assertEqual(
                    len(places), len(stats.top_finishes(context()["contests"]))
                )
            words = contents(parse(rendered("long")[name]))
            places = [w for w in words if re.fullmatch("[1-4](ST|ND|RD|TH)", w)]
            with self.subTest(file=name, case="long"):
                self.assertEqual(len(places), stats.LEDGER_CAP - 1)
                self.assertIn(f"+{12 - stats.LEDGER_CAP + 1} MORE", words)
        # the desktop header tallies the places, in the order the ledger lists them
        words = contents(parse(stats.render(snapshot(), context())["competitive.svg"]))
        self.assertIn("1X 1ST  1X 3RD  1X 4TH", words)

    def test_the_eyebrow_dates_the_record_from_the_contests(self) -> None:
        words = contents(parse(stats.render(snapshot(), context())["competitive.svg"]))
        self.assertIn("COMPETITIVE PROGRAMMING  |  SINCE 2021", words)
        words = contents(parse(rendered("empty")["competitive.svg"]))
        self.assertIn("COMPETITIVE PROGRAMMING", words)

    def test_the_lit_row_visits_every_finish_once_a_loop(self) -> None:
        for name in ("competitive.svg", "competitive-mobile.svg"):
            svg = stats.render(snapshot(), context())[name]
            moves = [a for a in loops(svg) if a.get("type") == "translate"]
            with self.subTest(file=name):
                self.assertEqual(len(moves), 1)
                rows = {v.split()[1] for v in moves[0].attrib["values"].split(";")}
                self.assertEqual(
                    len(rows), len(stats.top_finishes(context()["contests"]))
                )
                self.assertEqual(moves[0].attrib["dur"], "12s")


class Certifications(unittest.TestCase):
    TODAY = datetime.date(2026, 11, 13)

    def test_the_share_left_comes_from_the_expiry_and_the_issuer_validity(self) -> None:
        half = stats._validity(
            {"name": "AWS Certified Acme - Associate", "expires": "2028-05-13"},
            self.TODAY,
            "AWS Certified ",
        )
        self.assertEqual(half["name"], "Acme")
        self.assertEqual(half["level"], "ASSOCIATE")
        self.assertEqual((half["left"], half["unit"]), ("18", "MO"))
        self.assertAlmostEqual(half["share"], 0.5, places=2)
        soon = stats._validity(
            {"name": "AWS Certified Acme", "expires": "2026-11-23"}, self.TODAY, ""
        )
        self.assertEqual((soon["left"], soon["unit"]), ("10", "DAYS"))
        # an issuer with no known validity, and an expiry that is not a date, draw no ring
        other = stats._validity(
            {"name": "Acme Certified Thing", "expires": "2027-05-13"}, self.TODAY, ""
        )
        self.assertIsNone(other["share"])
        self.assertEqual(other["left"], "6")
        missing = stats._validity(
            {"name": "AWS Certified Acme", "expires": "soon"}, self.TODAY, ""
        )
        self.assertIsNone(missing["share"])
        self.assertEqual((missing["left"], missing["until"]), ("", ""))
        leap = stats._validity(
            {"name": "AWS Certified Acme", "expires": "2028-02-29"}, self.TODAY, ""
        )
        self.assertGreater(leap["share"], 0)

    def ring_arcs(self, svg: str) -> list[float]:
        """The share each validity ring's arc draws, from its dash against its circumference."""
        out = []
        for circle in parse(svg).iter(f"{SVG}circle"):
            if circle.get("stroke") == kit.BLUE_EDGE and circle.get("stroke-dasharray"):
                arc, around = map(float, circle.attrib["stroke-dasharray"].split())
                out.append(arc / around)
        return out

    def test_each_active_certification_gets_a_cell_and_a_ring_for_what_is_left(
        self,
    ) -> None:
        ctx = context()
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            svg = stats.render(snapshot(), ctx)[name]
            words = contents(parse(svg))
            arcs = self.ring_arcs(svg)
            with self.subTest(file=name):
                self.assertEqual(len(arcs), len(ctx["certs"]["active"]))
                # 2029-01-31 from 2026-11-13: 26 months left of a three-year validity
                self.assertEqual(words.count("26"), 2)
                for share in arcs:
                    self.assertAlmostEqual(share, 810 / 1096, places=2)
                self.assertIn("Developer", words)
                self.assertIn("ASSOCIATE", " ".join(words))
        # a certification with no known validity is drawn with no ring, not a guessed one
        ctx = context(
            certs=dict(
                context()["certs"],
                active=[
                    *context()["certs"]["active"],
                    {"name": "Acme Certified Thing", "expires": "2027-05-13"},
                ],
                active_count=3,
            )
        )
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            svg = stats.render(snapshot(), ctx)[name]
            with self.subTest(file=name, case="unknown validity"):
                self.assertEqual(len(self.ring_arcs(svg)), 2)
                self.assertIn("Acme Certified Thing", contents(parse(svg)))

    def test_a_light_runs_each_ring_in_turn_on_the_clock(self) -> None:
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            svg = stats.render(snapshot(), context())[name]
            lights = [
                a for a in loops(svg) if a.get("attributeName") == "stroke-dashoffset"
            ]
            begins = sorted(float(a.attrib["begin"].removesuffix("s")) for a in lights)
            with self.subTest(file=name):
                self.assertEqual(len(lights), 2)
                self.assertAlmostEqual(begins[1] - begins[0], stats.T / 2, places=1)

    def test_the_eyebrow_names_the_next_expiry(self) -> None:
        words = contents(parse(stats.render(snapshot(), context())["certs-status.svg"]))
        self.assertIn("AWS CERTIFIED  |  VALIDITY LEFT  |  NEXT EXPIRY JAN 2029", words)
        # the phone's line under the issuer says what the rings show, and the next expiry
        phone = contents(
            parse(stats.render(snapshot(), context())["certs-status-mobile.svg"])
        )
        line = next(w for w in phone if w.startswith("VALIDITY LEFT"))
        self.assertIn("JAN 2029", line)
        for case in CASES:
            words = contents(parse(rendered(case)["certs-status-mobile.svg"]))
            with self.subTest(case=case):
                self.assertTrue(any(w.startswith("VALIDITY LEFT") for w in words))

    def test_the_cells_run_soonest_expiry_first(self) -> None:
        """The first cell is the expiry the eyebrow names, whatever order the portfolio lists."""
        active = [
            {"name": "AWS Certified Developer - Associate", "expires": "2029-01-31"},
            {"name": "Acme Certified Thing", "expires": ""},
            {"name": "AWS Certified Cloud Practitioner", "expires": "2027-07-14"},
        ]
        ctx = context(certs=dict(context()["certs"], active=active, active_count=3))
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            root = parse(stats.render(snapshot(), ctx)[name])
            words = contents(root)
            with self.subTest(file=name):
                self.assertEqual(cell_dates(words), ["JUL 2027", "JAN 2029"])
                self.assertIn("JUL 2027", next(w for w in words if "NEXT" in w))
                label = root.get("aria-label")
                self.assertLess(
                    label.index("Cloud Practitioner"), label.index("Developer")
                )
                self.assertLess(
                    label.index("Developer"), label.index("Acme Certified Thing")
                )
        # the live cards open on the next expiry too
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            words = contents(parse(FILES[name]))
            dates = cell_dates(words)
            if dates:
                with self.subTest(live=name):
                    self.assertTrue(
                        next(w for w in words if "NEXT" in w).endswith(dates[0])
                    )

    def test_the_lapsed_certifications_are_one_caption_line_each(self) -> None:
        words = contents(parse(stats.render(snapshot(), context())["certs-status.svg"]))
        self.assertEqual(words.count("PREVIOUSLY EARNED"), 1)
        self.assertIn(TERRAFORM, words)
        self.assertIn("EXPIRED 2026-09-10", words)
        long_words = contents(parse(rendered("long")["certs-status.svg"]))
        self.assertTrue(any(w.endswith("...") for w in long_words))

    def test_the_phone_badge_grid_keeps_to_its_byte_budget(self) -> None:
        big = "data:image/webp;base64," + "A" * 6000
        badges = [{"name": f"Acme Badge {n}", "image": big} for n in range(30)]
        badges[0]["name"] = "AWS Certified Developer - Associate"
        root = parse(
            svg := stats.render(snapshot(), context(badges=badges))["certs-mobile.svg"]
        )
        drawn = len(list(root.iter(f"{SVG}image")))
        self.assertLess(len(svg.encode("utf-8")), BADGE_CARD_LIMIT)
        self.assertLessEqual(image_bytes(root), stats.IMAGE_BUDGET)
        self.assertEqual(drawn + sum(counted(root)), 30)
        self.assertIn("30 CREDLY BADGES", contents(root))
        # the certification shows, on its own tile, ahead of one row of learning badges
        self.assertIn("1 INDUSTRY CERTIFICATIONS", contents(root))
        self.assertEqual(drawn - 1, stats.BADGE_ROW)

    def badge_card(self, certs: int, learning: int) -> tuple[str, ET.Element]:
        """The phone badge card for `certs` active certifications with Credly-sized images
        (about 8 KB, the size of his largest) and `learning` learning badges (about 6 KB)."""
        names = [f"AWS Certified Acme Track {n} - Associate" for n in range(certs)]
        badges = [{"name": name, "image": CERT_IMAGE} for name in names] + [
            {"name": f"Acme Knowledge {n} - Training Badge", "image": LEARNING_IMAGE}
            for n in range(learning)
        ]
        active = [{"name": name, "expires": "2029-01-31"} for name in names]
        ctx = context(
            badges=badges,
            certs=dict(context()["certs"], active=active, active_count=certs),
        )
        svg = stats.render(snapshot(), ctx)["certs-mobile.svg"]
        return svg, parse(svg)

    def test_more_certifications_never_push_the_badge_card_past_its_budget(
        self,
    ) -> None:
        """The next certification he earns cannot stop the daily job: certification images
        are held to the budget too, in whole rows, and what does not fit is counted."""
        for certs in (5, 6, 7, 12, 20):
            svg, root = self.badge_card(certs, 15)
            images = [i.get("href") for i in root.iter(f"{SVG}image")]
            shown = images.count(CERT_IMAGE)
            notes = " ".join(contents(root))
            with self.subTest(certs=certs):
                self.assertLess(len(svg.encode("utf-8")), BADGE_CARD_LIMIT)
                self.assertLessEqual(image_bytes(root), stats.IMAGE_BUDGET)
                self.assertEqual(len(images) + sum(counted(root)), certs + 15)
                self.assertIn(f"{certs} INDUSTRY CERTIFICATIONS", contents(root))
                if shown < certs:
                    # cut in whole rows, counted on their own line, and no learning badge
                    # takes a place a certification could not have
                    self.assertEqual(shown % stats.CERT_ROW, 0)
                    self.assertIn(f"+{certs - shown} MORE CERTIFICATIONS", notes)
                    self.assertNotIn(LEARNING_IMAGE, images)
        # seven certifications at about 8 KB each all show
        _, root = self.badge_card(7, 15)
        hrefs = [i.get("href") for i in root.iter(f"{SVG}image")]
        self.assertEqual(hrefs.count(CERT_IMAGE), 7)

    def test_the_phone_shows_one_row_of_the_most_relevant_learning_badges(
        self,
    ) -> None:
        """Picked by name, not by Credly's order: partner, ambassador, then accreditations."""
        learning = [
            "Acme Knowledge: Serverless - Training Badge",
            "Acme Well-Architected Proficient",
            "Acme Cloud 101 - Training Badge",
            "Claude Partner Badge - Claude Code",
            "Acme AI Foundational (L100) Accreditation",
            "Acme Storage - Training Badge",
            "Acme Lifecycle Ambassador Foundational (L100)",
            "Acme Generative AI Technical Intermediate (L200)",
        ]
        badges = [{"name": "AWS Certified Developer - Associate", "image": PIXEL}] + [
            {"name": name, "image": PIXEL} for name in learning
        ]
        root = parse(
            stats.render(snapshot(), context(badges=badges))["certs-mobile.svg"]
        )
        drawn = [
            g.find(f"{SVG}title").text
            for g in root.iter(f"{SVG}g")
            if g.find(f"{SVG}image") is not None and g.find(f"{SVG}title") is not None
        ]
        self.assertEqual(
            drawn[1:],
            [
                "Claude Partner Badge - Claude Code",
                "Acme Lifecycle Ambassador Foundational (L100)",
                "Acme Generative AI Technical Intermediate (L200)",
                "Acme AI Foundational (L100) Accreditation",
                "Acme Well-Architected Proficient",
            ],
        )
        words = contents(root)
        self.assertIn("8 LEARNING AND PARTNER BADGES", words)
        self.assertIn("+3 MORE ON CREDLY", " ".join(words))


class PhoneTwins(unittest.TestCase):
    def test_the_heatmap_scan_rests_on_this_week_and_the_ripple_on_the_busiest_day(
        self,
    ) -> None:
        ctx = context()
        weeks = ctx["github"]["calendar"][-stats.WEEKS :]
        root = parse(stats.render(snapshot(), ctx)["github-mobile.svg"])
        cells = [
            r for r in root.iter(f"{SVG}rect") if r.get("width") == str(stats.CELL)
        ]
        self.assertEqual(len(cells), sum(len(week) for week in weeks))
        last_x = stats.PHONE_PAD + (len(weeks) - 1) * stats.PITCH
        scan = next(
            p for p in root.iter(f"{SVG}path") if p.get("stroke") == kit.BLUE_LIGHT
        )
        self.assertAlmostEqual(
            float(re.match(r"M([0-9.]+)", scan.attrib["d"]).group(1)),
            last_x - 2.5 + 4,
            places=1,
        )
        _, column, row = max(
            (count, c, r)
            for c, week in enumerate(weeks)
            for r, count in enumerate(week)
        )
        ripple = next(
            g
            for g in root.iter(f"{SVG}g")
            if (g.get("transform") or "").startswith("translate(")
        )
        cx, cy = map(float, ripple.attrib["transform"][10:-1].split())
        top = min(float(c.attrib["y"]) for c in cells)
        self.assertEqual(cx, stats.PHONE_PAD + column * stats.PITCH + stats.CELL / 2)
        self.assertEqual(cy, top + row * stats.PITCH + stats.CELL / 2)

    def test_the_heatmap_enters_as_one_clip_not_a_column_at_a_time(self) -> None:
        svg = stats.render(snapshot(), context())["github-mobile.svg"]
        self.assertIn('clip-path="url(#weeks)"', svg)
        self.assertEqual(svg.count('<clipPath id="weeks">'), 1)

    def test_the_rating_line_says_its_climb_and_its_years(self) -> None:
        words = contents(
            parse(stats.render(snapshot(), context())["leetcode-mobile.svg"])
        )
        self.assertIn("+731 SINCE 2022", words)
        self.assertIn("2022", words)
        self.assertIn("2026", words)
        ctx = context(leetcode=dict(context()["leetcode"], history=[1500, 1400, 1450]))
        words = contents(parse(stats.render(snapshot(), ctx)["leetcode-mobile.svg"]))
        self.assertIn("-50 SINCE 2022", words)

    def test_the_rating_light_runs_on_the_six_second_clock(self) -> None:
        svg = stats.render(snapshot(), context())["leetcode-mobile.svg"]
        lights = [
            a for a in loops(svg) if a.get("attributeName") == "stroke-dashoffset"
        ]
        self.assertEqual([a.attrib["dur"] for a in lights], ["6s"])

    def test_a_long_figure_steps_its_numeral_down_inside_the_tile(self) -> None:
        root = parse(rendered("long")["github-mobile.svg"])
        value = next(e for e in texts(root) if e.text == "123,456,789")
        self.assertLess(float(value.attrib["font-size"]), 22)
        self.assertGreaterEqual(float(value.attrib["font-size"]), stats.VALUE_FLOOR)


if __name__ == "__main__":
    unittest.main()
