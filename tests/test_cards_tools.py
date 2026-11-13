"""Checks for the community tool cards: the files, their bounds and motion, and the fixes of the port.

The shared checks run on the checked-in snapshot and assert rules, never values, so a
data refresh cannot fail them. Each fix has its own test on a small fixture.
"""

from __future__ import annotations

import importlib.util
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
from cards import tools

SVG = "{http://www.w3.org/2000/svg}"
DATA = renderer.load_data()
CTX = renderer.build_context(DATA)
FILES = tools.render(DATA, CTX)
DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}
LAYOUTS = {False: tools.DESKTOP, True: tools.PHONE}


def tool(**changes: object) -> dict:
    """One entry shaped like ctx["tools"], with no traction until a test adds it."""
    base = {
        "slug": "sample-tool",
        "title": "Sample Tool",
        "summary": "Draws one thing from a short spec, and checks it before it ships.",
        "tech": ["TypeScript", "ELK", "SVG"],
        "url": "https://github.com/example/sample-tool",
        "repo": "sample-tool",
        "stars": 3,
        "kind": "CLI",
        "npm_monthly": None,
        "top": True,
    }
    return {**base, **changes}


def numbered(count: int, **changes: object) -> list[dict]:
    return [tool(slug=f"tool-{i}", title=f"Tool {i}", **changes) for i in range(count)]


def render(entries: list[dict]) -> dict[str, str]:
    return tools.render({}, {"tools": entries})


def card(entry: dict, phone: bool = False) -> ET.Element:
    """Render one tool on its own and return the parsed desktop or phone card."""
    files = render([entry])
    return ET.fromstring(files[f"tool-{entry['slug']}{'-mobile' if phone else ''}.svg"])  # nosec B314


def size(root: ET.Element) -> tuple[float, float]:
    _, _, width, height = map(float, root.attrib["viewBox"].split())
    return width, height


def texts(root: ET.Element, cls: str = "") -> list[ET.Element]:
    return [t for t in root.iter(f"{SVG}text") if not cls or t.get("class") == cls]


def span(element: ET.Element) -> tuple[float, float]:
    """The left and right edge of a text element, measured the way kit measures."""
    font = float(element.attrib["font-size"])
    mono = element.get("class") in {"k", "m", "c"}
    width = kit.text_width(element.text or "", font, mono, kit.TRACK)
    x = float(element.attrib["x"])
    left = x - width / 2 if element.get("text-anchor") == "middle" else x
    return left, left + width


def pills(root: ET.Element) -> list[dict]:
    """Every chip as {x, y, right, bottom, text, fill}; the frame and the accent bar are not chips."""
    out = []
    labels = texts(root, "m")
    for rect in list(root.iter(f"{SVG}rect"))[2:]:
        x, y = float(rect.attrib["x"]), float(rect.attrib["y"])
        right, bottom = (
            x + float(rect.attrib["width"]),
            y + float(rect.attrib["height"]),
        )
        inside = [
            t
            for t in labels
            if x <= float(t.attrib["x"]) <= right
            and y <= float(t.attrib["y"]) <= bottom
        ]
        out.append(
            {
                "x": x,
                "y": y,
                "right": right,
                "bottom": bottom,
                "text": inside[0].text if inside else "",
                "fill": inside[0].get("fill") if inside else "",
            }
        )
    return out


def tech_row(root: ET.Element) -> list[dict]:
    """The chips on the card's bottom row."""
    found = pills(root)
    lowest = max((p["y"] for p in found), default=0)
    return [p for p in found if p["y"] == lowest]


def traction_row(root: ET.Element) -> list[dict]:
    found = pills(root)
    lowest = max((p["y"] for p in found), default=0)
    return [p for p in found if p["y"] < lowest]


def heights(files: dict[str, str], phone: bool) -> list[float]:
    return [
        size(ET.fromstring(svg))[1]  # nosec B314
        for name, svg in files.items()
        if name.endswith("-mobile.svg") == phone
    ]


class SnapshotTests(unittest.TestCase):
    """Rules every tool card keeps, on the data the page is built from."""

    def each(self):
        for name, svg in FILES.items():
            with self.subTest(file=name):
                yield name, svg, ET.fromstring(svg)  # nosec B314

    def test_one_desktop_and_one_phone_file_per_tool(self):
        expected = {
            f"tool-{entry['slug']}{suffix}.svg"
            for entry in CTX["tools"]
            for suffix in ("", "-mobile")
        }
        self.assertEqual(set(FILES), expected)
        self.assertTrue(CTX["tools"], "the snapshot lists no community tools")
        for name in FILES:
            self.assertTrue(renderer.CARD_FILE.fullmatch(name), name)

    def test_every_file_is_a_270px_card(self):
        for _, _, root in self.each():
            width, height = size(root)
            self.assertEqual(width, tools.WIDTH)
            self.assertEqual(float(root.attrib["width"]), tools.WIDTH)
            self.assertEqual(float(root.attrib["height"]), height)
            self.assertGreaterEqual(height, tools.MIN_HEIGHT)
            self.assertEqual(root.get("role"), "img")

    def test_no_text_or_chip_leaves_the_canvas(self):
        for _, _, root in self.each():
            width, height = size(root)
            for element in texts(root):
                left, right = span(element)
                self.assertGreaterEqual(left, tools.PAD - 0.01, element.text)
                self.assertLessEqual(right, width, element.text)
                self.assertLess(float(element.attrib["y"]), height - 8, element.text)
            for pill in pills(root):
                self.assertGreaterEqual(pill["x"], tools.PAD)
                self.assertLessEqual(pill["right"], width - tools.PAD + 0.01)
                self.assertLessEqual(pill["bottom"], height - 12)

    def test_no_dash_characters(self):
        for _, svg, _ in self.each():
            for dash in DASHES:
                self.assertNotIn(dash, svg)

    def test_the_still_frame_is_the_whole_card(self):
        # nothing rests hidden, so there is no entrance to make poster-safe
        for _, svg, _ in self.each():
            self.assertNotIn('opacity="0"', svg)
            self.assertNotIn("visibility", svg)

    def test_text_keeps_the_size_floor(self):
        for name, _, root in self.each():
            floor = kit.MICRO_PHONE if name.endswith("-mobile.svg") else kit.MICRO
            for element in texts(root):
                self.assertGreaterEqual(float(element.attrib["font-size"]), floor)

    def test_one_loop_on_the_page_clock(self):
        for _, _, root in self.each():
            loops = [
                e
                for e in root.iter()
                if e.tag
                in {f"{SVG}animate", f"{SVG}animateTransform", f"{SVG}animateMotion"}
            ]
            self.assertEqual(
                len(loops), 1
            )  # the accent bar's pulse: the motion stays visible
            self.assertEqual(loops[0].get("attributeName"), "opacity")
            self.assertIn(float(loops[0].attrib["dur"].rstrip("s")), CLOCK)
            self.assertEqual(loops[0].get("repeatCount"), "indefinite")

    def test_files_are_self_contained(self):
        for _, svg, _ in self.each():
            for banned in (
                "href",
                "<image",
                "<script",
                "foreignObject",
                "@import",
                "url(",
            ):
                self.assertNotIn(banned, svg)

    def test_blue_family_only(self):
        # amber is for LeetCode and work in review, green for live or ok: neither is a star
        for _, svg, _ in self.each():
            self.assertNotIn(kit.AMBER, svg)
            self.assertNotIn(kit.GREEN, svg)

    def test_the_label_says_what_the_card_shows(self):
        for entry in CTX["tools"]:
            for suffix in ("", "-mobile"):
                root = ET.fromstring(FILES[f"tool-{entry['slug']}{suffix}.svg"])  # nosec B314
                label = root.attrib["aria-label"]
                self.assertTrue(
                    label.startswith(f"{entry['title']}: {entry['summary']}")
                )
                self.assertEqual("stars." in label, entry["stars"] >= tools.STAR_FLOOR)
                self.assertEqual("npm downloads" in label, bool(entry["npm_monthly"]))

    def test_title_and_summary_are_drawn_whole(self):
        for entry in CTX["tools"]:
            for phone, suffix in ((False, ""), (True, "-mobile")):
                root = ET.fromstring(FILES[f"tool-{entry['slug']}{suffix}.svg"])  # nosec B314
                self.assertEqual(
                    " ".join(t.text for t in texts(root, "t")),
                    " ".join(entry["title"].split()),
                )
                self.assertEqual(
                    " ".join(t.text for t in texts(root, "b")),
                    " ".join(entry["summary"].split()),
                )

    def test_at_most_three_tech_chips_in_order(self):
        for entry in CTX["tools"]:
            for suffix in ("", "-mobile"):
                root = ET.fromstring(FILES[f"tool-{entry['slug']}{suffix}.svg"])  # nosec B314
                shown = [p["text"] for p in tech_row(root)]
                self.assertLessEqual(len(shown), tools.TECH_SHOWN)
                self.assertEqual(shown, entry["tech"][: len(shown)])
                if entry["tech"]:
                    self.assertTrue(shown, f"{entry['slug']} shows no tech chip")

    def test_rows_on_both_pages_share_one_height(self):
        # the profile shows the leading top tools and COMMUNITY.md the whole list,
        # so their rows are the same runs only while the top tools come first
        tops = [entry["top"] for entry in CTX["tools"]]
        self.assertEqual(tops, sorted(tops, reverse=True))
        for phone, layout in LAYOUTS.items():
            tall = heights(FILES, phone)
            for start in range(0, len(tall), layout.row):
                self.assertEqual(len(set(tall[start : start + layout.row])), 1)


class FixTests(unittest.TestCase):
    """One test per fix of the port."""

    def test_star_chip_from_ten_stars(self):
        for phone in (False, True):
            with self.subTest(phone=phone):
                quiet = card(tool(stars=tools.STAR_FLOOR - 1), phone)
                self.assertIsNone(quiet.find(f"{SVG}path"))
                self.assertEqual(traction_row(quiet), [])
                self.assertNotIn("stars.", quiet.attrib["aria-label"])

                starred = card(tool(stars=tools.STAR_FLOOR), phone)
                star = starred.find(f"{SVG}path")
                self.assertIsNotNone(star)
                self.assertEqual(star.get("fill"), kit.SKY)
                (chip,) = traction_row(starred)
                self.assertEqual(chip["text"], "10")
                self.assertEqual(chip["fill"], kit.SKY)
                self.assertTrue(starred.attrib["aria-label"].endswith(" 10 stars."))

    def test_star_count_is_exact(self):
        (chip,) = traction_row(card(tool(stars=1234)))
        self.assertEqual(chip["text"], "1,234")

    def test_npm_chip_shows_the_exact_monthly_count(self):
        for phone in (False, True):
            with self.subTest(phone=phone):
                self.assertEqual(traction_row(card(tool(), phone)), [])
                root = card(tool(npm_monthly=1793), phone)
                (chip,) = traction_row(root)
                # 1,793 and not 1.8K: a rounded figure would exceed the live one
                self.assertEqual(chip["text"], "1,793/MO NPM")
                self.assertTrue(
                    root.attrib["aria-label"].endswith(" 1,793 npm downloads a month.")
                )

    def test_traction_chips_use_the_space_under_the_summary(self):
        for phone in LAYOUTS:
            with self.subTest(phone=phone):
                plain = card(tool(), phone)
                root = card(tool(stars=88, npm_monthly=2070), phone)
                last = max(float(t.attrib["y"]) for t in texts(root, "b"))
                star, npm = traction_row(root)
                self.assertEqual([star["text"], npm["text"]], ["88", "2,070/MO NPM"])
                self.assertEqual(star["y"], npm["y"])
                self.assertGreaterEqual(star["y"], last + 10)  # clear of the last line
                (tech_top,) = {p["y"] for p in tech_row(root)}
                self.assertGreaterEqual(tech_top - star["bottom"], 10)
                self.assertLessEqual(npm["right"], tools.WIDTH - tools.PAD)
                # the chips took dead space: the card is no taller, the tech row has not moved
                self.assertEqual(size(root), size(plain))
                self.assertEqual(tech_row(root), tech_row(plain))

    def test_star_takes_room_only_when_it_is_drawn(self):
        # the old row kept 56px free for a star on every card and stopped at 178px,
        # so orrery (7 stars, none drawn) lost SVG, its third chip, by 2px
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                trio = ["TypeScript", "ELK", "SVG"]
                root = card(tool(stars=7, tech=trio), phone)
                self.assertEqual([p["text"] for p in tech_row(root)], trio)
                # a row that needs the freed room is whole with a star and without one
                names = ["TypeScript", "MCP Protocol"]
                widths = sum(
                    kit.chip_width(n, layout.chip_size, tools.CHIP_PAD) for n in names
                )
                self.assertGreater(widths + tools.CHIP_GAP, tools.WIDTH - 92)
                for stars in (7, 88):
                    root = card(tool(stars=stars, tech=names), phone)
                    self.assertEqual([p["text"] for p in tech_row(root)], names)
                    self.assertLessEqual(
                        max(p["right"] for p in tech_row(root)),
                        tools.WIDTH - tools.PAD,
                    )
                # and in the traction row the npm chip starts at the margin unless a star precedes it
                (alone,) = traction_row(card(tool(npm_monthly=1793), phone))
                self.assertEqual(alone["x"], tools.PAD)
                star, npm = traction_row(card(tool(stars=88, npm_monthly=1793), phone))
                self.assertEqual(star["x"], tools.PAD)
                self.assertAlmostEqual(
                    npm["x"], star["right"] + tools.CHIP_GAP, places=1
                )

    def test_a_chip_that_does_not_fit_is_left_out_whole(self):
        long = ["Plugin Marketplace", "GitHub GraphQL API", "SVG"]
        for phone in (False, True):
            root = card(tool(tech=long), phone)
            self.assertEqual([p["text"] for p in tech_row(root)], long[:1])

    def test_cards_in_a_row_keep_one_height(self):
        long = " ".join(["Reads a long list of inputs and writes them out again."] * 4)
        entries = numbered(7)
        entries[4] = tool(slug="tall", title="Tall Tool", summary=long, stars=88)
        files = render(entries)
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                tall = heights(files, phone)
                start = 4 - 4 % layout.row
                row = tall[start : start + layout.row]
                self.assertEqual(len(set(row)), 1)
                self.assertGreater(row[0], tools.MIN_HEIGHT)
                rest = tall[:start] + tall[start + layout.row :]
                self.assertEqual(set(rest), {tools.MIN_HEIGHT})
                # the taller row still ends on its tech chips, 12px above the edge
                for name, svg in files.items():
                    if name.endswith("-mobile.svg") != phone:
                        continue
                    root = ET.fromstring(svg)  # nosec B314
                    self.assertEqual(
                        {p["bottom"] for p in tech_row(root)}, {size(root)[1] - 12}
                    )

    def test_a_tall_card_keeps_its_rows_apart(self):
        long = " ".join(["Reads a long list of inputs and writes them out again."] * 4)
        for phone in (False, True):
            root = card(tool(summary=long, stars=88, npm_monthly=2070), phone)
            last = max(float(t.attrib["y"]) for t in texts(root, "b"))
            (traction_top,) = {p["y"] for p in traction_row(root)}
            (traction_bottom,) = {p["bottom"] for p in traction_row(root)}
            (tech_top,) = {p["y"] for p in tech_row(root)}
            self.assertGreaterEqual(traction_top, last + 10)
            self.assertGreaterEqual(tech_top, traction_bottom + 10)

    def test_a_long_single_token_stays_inside_the_card(self):
        for title in ("oss-contributions-card-action", "x" * 30):
            for phone in (False, True):
                with self.subTest(title=title, phone=phone):
                    root = card(
                        tool(title=title, summary=f"Wraps {title}/{title} safely."), phone
                    )
                    width, _ = size(root)
                    for element in texts(root):
                        left, right = span(element)
                        self.assertGreaterEqual(left, tools.PAD - 0.01, element.text)
                        self.assertLessEqual(right, width, element.text)
                    # nothing is dropped: the pieces rejoin to the token
                    self.assertEqual("".join(t.text for t in texts(root, "t")), title)

    def test_a_long_token_breaks_after_a_separator(self):
        self.assertEqual(
            tools.wrap("oss-contributions-card-action", 24, 18),
            ["oss-contributions-card-", "action"],
        )

    def test_traction_chips_share_one_height_across_a_row(self):
        short, long = "Draws one thing.", " ".join(["Reads many inputs."] * 8)
        entries = [
            tool(slug="a", title="A", summary=short, stars=50),
            tool(slug="b", title="B", summary=long, stars=60, npm_monthly=2070),
            tool(slug="c", title="C", summary=short, stars=0, npm_monthly=900),
            tool(slug="d", title="D", summary=short, stars=70),
        ]
        files = render(entries)
        for phone, layout in LAYOUTS.items():
            for start in range(0, len(entries), layout.row):
                with self.subTest(phone=phone, start=start):
                    ys = {
                        p["y"]
                        for entry in entries[start : start + layout.row]
                        for p in traction_row(
                            ET.fromstring(  # nosec B314
                                files[f"tool-{entry['slug']}{'-mobile' if phone else ''}.svg"]
                            )
                        )
                    }
                    self.assertEqual(len(ys), 1)

    def test_a_tool_without_tech_or_traction_still_draws(self):
        for phone in (False, True):
            root = card(tool(tech=[], stars=0), phone)
            self.assertEqual(pills(root), [])
            self.assertNotIn("Built with", root.attrib["aria-label"])

    def test_text_is_escaped(self):
        entry = tool(title="R&D <kit>", summary='Reads "a & b" <c>.', tech=["C&C"])
        for phone in (False, True):
            root = card(entry, phone)
            self.assertEqual(root.attrib["aria-label"].split(":")[0], "R&D <kit>")
            self.assertEqual(texts(root, "t")[0].text, "R&D <kit>")
            self.assertEqual(tech_row(root)[0]["text"], "C&C")

    def test_render_is_deterministic(self):
        self.assertEqual(tools.render(DATA, CTX), FILES)


if __name__ == "__main__":
    unittest.main()
