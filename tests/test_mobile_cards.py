"""Regression coverage for the phone layout engine: fonts, wrapping, bounds, motion and the expiry rule."""

from __future__ import annotations

import datetime
import re
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kit
import mobile_cards as mobile

SVG = "{http://www.w3.org/2000/svg}"
LONG_REPO = "cloudposse/terraform-aws-tfstate-backend"


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314


def texts(root: ET.Element) -> list[ET.Element]:
    return list(root.iter(f"{SVG}text"))


def by_text(root: ET.Element, content: str) -> ET.Element:
    return next(element for element in texts(root) if element.text == content)


def sample_card() -> mobile.Card:
    """One card that uses every drawing call except raw()."""
    card = mobile.Card("Engine sample", kit.BLUE_LIGHT)
    card.label("merged upstream")
    card.lines("Sagar Gupta", size=30, weight=800)
    card.status("BUILDING AT AWS")
    card.metrics([("1,342", "Contributions"), ("13", "Merged upstream")])
    card.divider()
    card.chips(["Terraform", "AWS", LONG_REPO])
    card.pills([("5X CERTIFIED", kit.SKY), ("LEETCODE GUARDIAN", kit.AMBER)])
    card.row("ansible/ansible", "Fix the inventory cache key", "PR #1234")
    card.row("A pattern", metadata="2025", size=14, bullet=True, weight=500)
    return card


class CardEngineTests(unittest.TestCase):
    def assert_bounds(self, svg: str) -> None:
        root = parse(svg)
        _, _, width, height = map(float, root.attrib["viewBox"].split())
        self.assertEqual(width, mobile.WIDTH)
        for element in texts(root):
            size = float(element.attrib["font-size"])
            x, y = float(element.attrib["x"]), float(element.attrib["y"])
            span = mobile.text_width(
                element.text or "", size, "font-family" in element.attrib
            )
            left = x - span / 2 if element.get("text-anchor") == "middle" else x
            with self.subTest(text=element.text):
                self.assertGreaterEqual(left, mobile.PAD - 0.01)
                self.assertLessEqual(left + span, width - mobile.PAD + 0.01)
                self.assertGreaterEqual(y - size, 0)
                self.assertLessEqual(y + size * 0.25, height)

    def test_mono_labels_carry_the_mono_stack_and_no_css_rule_overrides_it(
        self,
    ) -> None:
        svg = sample_card().finish()
        root = parse(svg)
        self.assertEqual(root.get("font-family"), kit.SANS)
        mono = (
            "MERGED UPSTREAM",
            "BUILDING AT AWS",
            "CONTRIBUTIONS",
            "Terraform",
            "5X CERTIFIED",
            "PR #1234",
            "2025",
        )
        for content in mono:
            with self.subTest(label=content):
                element = by_text(root, content)
                self.assertEqual(element.get("font-family"), kit.MONO)
                self.assertEqual(element.get("letter-spacing"), f"{kit.TRACK:g}")
        for content in ("Sagar Gupta", "1,342", "ansible/ansible"):
            with self.subTest(sans=content):
                self.assertIsNone(by_text(root, content).get("font-family"))
        # author CSS beats a font-family attribute, so no rule may select text elements
        style = "".join(element.text or "" for element in root.iter(f"{SVG}style"))
        self.assertNotRegex(style, r"(^|[},\s])text\s*[,{:\[]")
        self.assertIn("tabular-nums", style)

    def test_micro_labels_sit_at_the_phone_floor(self) -> None:
        root = parse(sample_card().finish())
        self.assertEqual(mobile.MICRO, kit.MICRO_PHONE)
        for element in texts(root):
            if "font-family" in element.attrib:
                self.assertGreaterEqual(
                    float(element.attrib["font-size"]), kit.MICRO_PHONE
                )

    def test_metrics_never_split_a_word(self) -> None:
        items = [
            ("1,234,567", "Contributions"),
            ("57", "Pull requests"),
            ("308", "Active days"),
        ]
        card = mobile.Card("Tiles")
        card.metrics(items, 3)
        svg = card.finish()
        root = parse(svg)
        words = {
            word for value, label in items for word in (value, *label.upper().split())
        }
        for element in texts(root):
            for word in (element.text or "").split():
                self.assertIn(word, words)
        # three tiles this wide cannot hold the words, so the row took fewer columns
        tiles = [
            float(rect.attrib["width"])
            for rect in root.iter(f"{SVG}rect")
            if rect.get("rx") == "10"
        ]
        self.assertEqual(len(tiles), 3)
        self.assertTrue(all(width > 100 for width in tiles), tiles)
        self.assert_bounds(svg)

    def test_metrics_keep_three_columns_when_every_word_fits(self) -> None:
        card = mobile.Card("Tiles")
        card.metrics([("941", "Commits"), ("57", "PRs"), ("308", "Days")], 3)
        root = parse(card.finish())
        tiles = {
            rect.attrib["x"]
            for rect in root.iter(f"{SVG}rect")
            if rect.get("rx") == "10"
        }
        self.assertEqual(len(tiles), 3)

    def test_metrics_shrink_a_long_numeral_before_dropping_a_column(self) -> None:
        card = mobile.Card("Tiles")
        card.metrics([("1,234,567,890", "Views"), ("2", "Stars")])
        root = parse(card.finish())
        numeral = by_text(root, "1,234,567,890")
        self.assertLess(float(numeral.attrib["font-size"]), mobile.VALUE_SIZES[2])
        self.assertGreaterEqual(float(numeral.attrib["font-size"]), mobile.VALUE_FLOOR)

    def test_chips_are_centred_in_their_pills(self) -> None:
        card = mobile.Card("Chips")
        shown = card.chips(["Terraform", "AWS", LONG_REPO])
        self.assertEqual(shown, 3)
        svg = card.finish()
        root = parse(svg)
        pill, checked = None, 0
        for element in root.iter():
            if element.tag == f"{SVG}rect" and element.get("fill") == kit.HAIR_FILL:
                pill = element
            elif element.tag == f"{SVG}text" and pill is not None:
                x, width = float(pill.attrib["x"]), float(pill.attrib["width"])
                self.assertEqual(element.get("text-anchor"), "middle")
                self.assertAlmostEqual(
                    float(element.attrib["x"]), x + width / 2, places=3
                )
                span = mobile.text_width(element.text, mobile.MICRO, True)
                self.assertLessEqual(span, width)
                self.assertLessEqual(x + width, mobile.WIDTH - mobile.PAD + 0.01)
                checked += 1
        # the long repository name wraps inside its own pill
        self.assertEqual(checked, 4)
        self.assert_bounds(svg)

    def test_chips_stop_at_max_rows_and_report_what_they_drew(self) -> None:
        labels = [f"repository-{index:02d}" for index in range(12)]
        card = mobile.Card("Chips")
        shown = card.chips(labels, max_rows=2)
        self.assertLess(shown, len(labels))
        drawn = [element.text for element in texts(parse(card.finish()))]
        self.assertEqual(drawn, labels[:shown])

    def test_pills_and_status_stay_inside_the_column(self) -> None:
        card = mobile.Card("Pills")
        card.pills(
            [
                ("5X CERTIFIED", kit.SKY),
                ("2+ YEARS AT AWS", kit.GREEN),
                ("LEETCODE GUARDIAN", kit.AMBER),
                (
                    "A LABEL THAT IS FAR TOO LONG FOR ONE ROW OF THE CARD",
                    kit.BLUE_LIGHT,
                ),
            ]
        )
        card.status("OPEN TO BUILDING LANDING ZONES AND MLOPS PLATFORMS AT AWS")
        svg = card.finish()
        self.assert_bounds(svg)
        for rect in parse(svg).iter(f"{SVG}rect"):
            right = float(rect.attrib["x"]) + float(rect.attrib["width"])
            self.assertLessEqual(right, mobile.WIDTH)

    def test_one_fact_has_the_desktop_colour(self) -> None:
        svg = sample_card().finish()
        self.assertIn(f'stroke="{kit.HAIR_STRONG}"', svg)
        self.assertIn(kit.GREEN, svg)
        for retired in ("#26343d", "#4ade80", "#fbbf24", "#b1bfcc"):
            self.assertNotIn(retired, svg)

    def test_finish_has_no_shine_and_every_loop_is_on_the_page_clock(self) -> None:
        card = sample_card()
        for index in range(30):
            card.lines(f"Row {index}")
        svg = card.finish()
        for banned in ("shine", "linearGradient", "skewX", "prefers-reduced-motion"):
            self.assertNotIn(banned, svg)
        root = parse(svg)
        bar = next(rect for rect in root.iter(f"{SVG}rect") if rect.get("width") == "3")
        pulse = bar.find(f"{SVG}animate")
        self.assertEqual(
            (pulse.get("dur"), pulse.get("repeatCount")), ("3s", "indefinite")
        )
        loops = entrances = 0
        for element in root.iter():
            if element.get("repeatCount") == "indefinite":
                self.assertIn(
                    float(element.attrib["dur"].rstrip("s")), (2, 3, 4, 6, 12, 24)
                )
                loops += 1
            elif element.get("fill") == "freeze":
                self.assertLessEqual(float(element.attrib["dur"].rstrip("s")), 1.61)
                self.assertEqual(element.attrib["keyTimes"].split(";")[0], "0")
                self.assertEqual(element.attrib["keyTimes"].split(";")[-1], "1")
                entrances += 1
        self.assertGreater(loops, 0)
        self.assertGreater(entrances, 30)

    def test_card_is_poster_safe_and_self_contained(self) -> None:
        name = 'Open source: 13 merged & 2 "open" <pull requests>'
        card = sample_card()
        card.name = name
        svg = card.finish(attrs={"data-active-certifications": 5})
        root = parse(svg)
        self.assertEqual(root.get("aria-label"), name)
        self.assertEqual(root.get("role"), "img")
        self.assertEqual(root.get("data-active-certifications"), "5")
        # the finished frame is the rest state: nothing waits hidden for its entrance
        self.assertNotIn('opacity="0"', svg)
        self.assertNotIn('stroke-dashoffset="1"', svg)
        self.assertIn("<animate", svg)
        for banned in (
            "<script",
            "foreignObject",
            'href="http',
            "@import",
            "@font-face",
        ):
            self.assertNotIn(banned, svg)

    def test_lines_balance_the_last_line(self) -> None:
        text, size = "Publications, Talks and Recognition", 20
        plain = kit.wrap_text(text, mobile.CONTENT_WIDTH, size, False, kit.TRACK)
        self.assertEqual(plain[-1], "Recognition")
        card = mobile.Card("Header")
        card.lines(text, size=size, weight=800)
        drawn = [element.text for element in texts(parse(card.finish()))]
        self.assertEqual(drawn, ["Publications, Talks", "and Recognition"])

    def test_balancing_never_widens_a_line_past_its_width(self) -> None:
        text = "AWS interoperability certificates"
        lines = mobile.wrap_text(text, 180, mobile.MICRO, True)
        self.assertEqual(lines, ["AWS interoperability", "certificates"])
        for line in lines:
            self.assertLessEqual(mobile.text_width(line, mobile.MICRO, True), 180)

    def test_raw_places_a_block_at_the_cursor_and_advances(self) -> None:
        card = mobile.Card("Raw")
        self.assertEqual(card.width, 320)
        card.label("before")
        top = card.y
        card.raw(kit.text(mobile.PAD, 14, "DRAWN BY HAND", mobile.MICRO, cls="m"), 40)
        self.assertEqual(card.y, top + 40)
        card.label("after")
        svg = card.finish()
        root = parse(svg)
        placed = next(
            group
            for group in root.iter(f"{SVG}g")
            if group.get("transform") == f"translate(0 {top:g})"
        )
        self.assertEqual(placed.find(f"{SVG}text").text, "DRAWN BY HAND")
        # kit's text classes are defined in the card, so a raw block can use them
        self.assertIn(".m{", svg)
        after = by_text(root, "AFTER")
        self.assertGreater(float(after.attrib["y"]), top + 40)

    def test_block_groups_calls_into_one_entrance(self) -> None:
        loose, grouped = mobile.Card("Loose"), mobile.Card("Grouped")
        for index in range(4):
            loose.lines(f"Line {index}")
        with grouped.block():
            for index in range(4):
                grouped.lines(f"Line {index}")
        entrances = [
            card.finish().count("<animateTransform") for card in (loose, grouped)
        ]
        self.assertEqual(entrances, [4, 1])
        self.assertEqual(loose.y, grouped.y)

    def test_long_content_grows_the_card_instead_of_truncating(self) -> None:
        long_title = "WWW " * 30 + "unbroken-" * 24 + " & <complete>"
        tall, short = mobile.Card("Long"), mobile.Card("Short")
        tall.row(long_title, metadata="2026", bullet=True)
        short.row("Short", metadata="2026", bullet=True)
        svg = tall.finish()
        self.assert_bounds(svg)
        drawn = "".join((element.text or "") for element in texts(parse(svg)))
        self.assertIn("".join(long_title.split()), "".join(drawn.split()))
        heights = [
            float(parse(card).attrib["height"]) for card in (svg, short.finish())
        ]
        self.assertGreater(heights[0], heights[1] + 150)

    def test_sample_card_text_stays_inside_the_column(self) -> None:
        self.assert_bounds(sample_card().finish())

    def test_cert_status_boundaries(self) -> None:
        today = datetime.date(2026, 10, 14)
        cases = (
            ({"expiryDate": "2026-10-14"}, ("active", "Valid through 2026-10-14")),
            ({"expiryDate": "2026-10-13"}, ("expired", "Expired 2026-10-13")),
            ({"expiryDate": "2027-01-01"}, ("active", "Valid through 2027-01-01")),
            ({}, ("unknown", "Expiry not recorded")),
            ({"expiryDate": None}, ("unknown", "Expiry not recorded")),
            ({"expiryDate": "N/A"}, ("unknown", "Expiry not recorded")),
            (
                {"expiryDate": "2029-01-31T00:00:00Z"},
                ("unknown", "Expiry not recorded"),
            ),
        )
        for certificate, expected in cases:
            with self.subTest(certificate=certificate):
                self.assertEqual(mobile.cert_status(certificate, today), expected)

    def test_engine_holds_no_card_and_reads_nothing(self) -> None:
        source = (SCRIPTS / "mobile_cards.py").read_text(encoding="utf-8")
        self.assertFalse(hasattr(mobile, "render_mobile_cards"))
        self.assertIsNone(re.search(r"\bopen\(|read_text|read_bytes|urlopen", source))


class SharedRuleTests(unittest.TestCase):
    """The tables render-svgs.py writes from and validate-readme.py accepts exactly."""

    def test_every_customer_label_is_generic_and_keyed_by_start_month(self) -> None:
        # the validator accepts these labels as they are, so this is the guard on them
        labels = {**mobile.CUSTOMER_LABELS, "no entry": mobile.GENERIC_CUSTOMER}
        for month, label in labels.items():
            with self.subTest(month=month):
                self.assertTrue(label.endswith(" customer"), label)
        for month in mobile.CUSTOMER_LABELS:
            # the renderer looks a label up by the portfolio's 'Oct 2024' start text
            self.assertRegex(month, r"^[A-Z][a-z]{2} \d{4}$")

    def test_programs_and_customers_never_share_a_label(self) -> None:
        customers = {*mobile.CUSTOMER_LABELS.values(), mobile.GENERIC_CUSTOMER}
        self.assertTrue(customers.isdisjoint(mobile.PROGRAMS.values()))
        for key in mobile.PROGRAMS:
            self.assertEqual(key, key.lower())  # matched against the lower-cased name

    def test_cert_issuer(self) -> None:
        cases = {
            "AWS Certified Developer - Associate": "AWS",
            "HashiCorp Certified: Terraform Associate (003)": "TERRAFORM",
            "Certified Kubernetes Administrator": "OTHER",
        }
        for name, issuer in cases.items():
            with self.subTest(name=name):
                self.assertEqual(mobile.cert_issuer(name), issuer)


if __name__ == "__main__":
    unittest.main()
