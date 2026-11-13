"""Checks for the page chrome cards: headers, buttons, get-this-card strips, the footer and the divider.

The file-wide checks run on the checked-in snapshot and assert rules, never
values. The checks for each fix build their own small context, so a refresh of
assets/svg/data.json cannot fail them.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405 - parses SVG this repo just rendered
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kit
import mobile_cards as mobile
from cards import chrome

SVG = "{http://www.w3.org/2000/svg}"
DASHES = (chr(0x2013), chr(0x2014))
CARD_FILE = re.compile(r"[a-z0-9][a-z0-9-]*\.svg")
TRACKING = re.compile(r"\.m\{[^}]*letter-spacing:([0-9.]+)px")
FILES: dict[str, str] = {}
CTX: dict = {}


def setUpModule() -> None:
    """Render the lane once from the offline snapshot, the way preview.py does."""
    spec = importlib.util.spec_from_file_location(
        "render_svgs", SCRIPTS / "render-svgs.py"
    )
    renderer = importlib.util.module_from_spec(spec)
    sys.modules["render_svgs"] = renderer
    spec.loader.exec_module(renderer)
    renderer.OFFLINE = True
    data = renderer.load_data()
    CTX.update(renderer.build_context(data))
    FILES.update(chrome.render(data, CTX))


def context(**changes: object) -> dict:
    """A context with only what this lane reads, shaped like build_context's."""
    ctx = {
        "headers": [
            ("experience", "01", "Experience", "where I work and what shipped"),
            ("stats", "02", "Coding Stats", "GitHub activity, LeetCode and contests"),
        ],
        "connect": [
            {"key": "linkedin", "label": "LinkedIn", "icon": "M0 0h24v24H0z"},
            {"key": "resume", "label": "Resume", "icon": None},
        ],
        "project_count": 7,
        "tools": [{"slug": "one"}, {"slug": "two"}, {"slug": "three"}],
        "get_cards": [("oss", "oss-contributions-card-action", "open-source cards")],
        "disclaimer": "Personal projects and opinions are my own.",
    }
    ctx.update(changes)
    return ctx


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314 - our own output


def texts(root: ET.Element) -> list[ET.Element]:
    return list(root.iter(f"{SVG}text"))


def content(element: ET.Element) -> str:
    """The text as a browser shows it: runs of white space collapse to one."""
    return " ".join("".join(element.itertext()).split())


def is_mono(element: ET.Element) -> bool:
    return element.get("class") == "m" or "Mono" in element.get("font-family", "")


def extent(element: ET.Element, svg: str) -> tuple[float, float]:
    """The left and right edge of a text element, measured with kit's advances."""
    size = float(element.get("font-size"))
    tracking = 0.0
    if is_mono(element):
        css = TRACKING.search(svg)
        tracking = float(
            element.get("letter-spacing") or (css.group(1) if css else kit.TRACK)
        )
    width = kit.text_width(content(element), size, is_mono(element), tracking)
    x = float(element.get("x"))
    left = {"middle": x - width / 2, "end": x - width}.get(
        element.get("text-anchor"), x
    )
    return left, left + width


def kicker_lines(svg: str) -> list[str]:
    return [content(element) for element in texts(parse(svg)) if is_mono(element)]


class EveryFileTests(unittest.TestCase):
    def test_the_lane_returns_exactly_its_files(self) -> None:
        expected = {"footer.svg", "footer-mobile.svg", "divider.svg"}
        for key, _, _, _ in CTX["headers"]:
            for theme in ("dark", "light"):
                expected |= {
                    f"header-{key}-{theme}.svg",
                    f"header-{key}-{theme}-mobile.svg",
                }
        expected |= {f"connect-{button['key']}.svg" for button in CTX["connect"]}
        expected |= {"cta-community.svg", "cta-profile.svg"}
        if CTX["project_count"]:
            expected.add("cta-portfolio.svg")
        for key, _, _ in CTX["get_cards"]:
            expected |= {f"get-{key}.svg", f"get-{key}-mobile.svg"}
        self.assertEqual(set(FILES), expected)
        for name in FILES:
            self.assertRegex(name, CARD_FILE)

    def test_every_file_is_a_self_contained_labelled_svg(self) -> None:
        for name, svg in FILES.items():
            with self.subTest(file=name):
                root = parse(svg)
                self.assertEqual(root.tag, f"{SVG}svg")
                self.assertEqual(root.get("role"), "img")
                self.assertTrue(root.get("aria-label", "").strip())
                tags = {element.tag.removeprefix(SVG) for element in root.iter()}
                self.assertFalse(tags & {"script", "foreignObject", "image", "use"})
                self.assertNotIn("href", svg)
                self.assertNotIn("@import", svg)
                self.assertNotIn("prefers-reduced-motion", svg)

    def test_no_file_holds_an_en_or_em_dash(self) -> None:
        for name, svg in FILES.items():
            for dash in DASHES:
                self.assertNotIn(dash, svg, name)

    def test_no_text_leaves_the_canvas(self) -> None:
        for name, svg in FILES.items():
            root = parse(svg)
            _, _, width, height = map(float, root.get("viewBox").split())
            self.assertEqual(float(root.get("width")), width)
            for element in texts(root):
                left, right = extent(element, svg)
                size, y = float(element.get("font-size")), float(element.get("y"))
                with self.subTest(file=name, text=content(element)):
                    self.assertGreaterEqual(left, 0)
                    self.assertLessEqual(right, width)
                    self.assertGreaterEqual(y - size, 0)
                    self.assertLessEqual(y + size * 0.25, height)

    def test_phone_cards_are_320_wide_and_keep_the_side_padding(self) -> None:
        phone = {name: svg for name, svg in FILES.items() if "-mobile" in name}
        self.assertEqual(
            len(phone), len(CTX["headers"]) * 2 + len(CTX["get_cards"]) + 1
        )
        for name, svg in phone.items():
            root = parse(svg)
            self.assertEqual(float(root.get("width")), mobile.WIDTH, name)
            for element in texts(root):
                left, right = extent(element, svg)
                with self.subTest(file=name, text=content(element)):
                    self.assertGreaterEqual(left, mobile.PAD - 0.01)
                    self.assertLessEqual(right, mobile.WIDTH - mobile.PAD + 0.01)

    def test_text_is_never_smaller_than_the_floor(self) -> None:
        for name, svg in FILES.items():
            floor = kit.MICRO_PHONE if "-mobile" in name else kit.MICRO
            for element in texts(parse(svg)):
                with self.subTest(file=name, text=content(element)):
                    self.assertGreaterEqual(float(element.get("font-size")), floor)

    def test_a_still_frame_shows_the_whole_card(self) -> None:
        """Hidden at rest only: a rotating line behind the first one, or a tint that flashes."""
        for name, svg in FILES.items():
            root = parse(svg)
            parents = {child: parent for parent in root.iter() for child in parent}
            for element in root.iter():
                if element.get("opacity") != "0":
                    continue
                with self.subTest(file=name, tag=element.tag.removeprefix(SVG)):
                    loops = [
                        animate
                        for animate in element.findall(f"{SVG}animate")
                        if animate.get("attributeName") == "opacity"
                        and animate.get("repeatCount") == "indefinite"
                    ]
                    self.assertEqual(len(loops), 1)
                    if element.tag == f"{SVG}text":
                        first = next(
                            sibling
                            for sibling in parents[element]
                            if sibling.tag == f"{SVG}text"
                            and sibling.get("y") == element.get("y")
                        )
                        self.assertIsNone(first.get("opacity"))
                    else:
                        self.assertEqual(element.tag, f"{SVG}rect")
            # an entrance holds its start value, then ends on the element's own frame
            for animate in root.iter(f"{SVG}animate"):
                if animate.get("fill") == "freeze":
                    self.assertTrue(animate.get("values").endswith(";1"), name)

    def test_motion_is_smil_only_and_every_card_moves(self) -> None:
        for name, svg in FILES.items():
            with self.subTest(file=name):
                self.assertNotIn("@keyframes", svg)
                self.assertIn('repeatCount="indefinite"', svg)

    def test_rendering_is_deterministic(self) -> None:
        self.assertEqual(chrome.render({}, CTX), FILES)


class LookTests(unittest.TestCase):
    def test_headers_come_as_a_dark_and_light_pair_at_both_widths(self) -> None:
        for key, _, title, _ in CTX["headers"]:
            for suffix in ("", "-mobile"):
                dark = FILES[f"header-{key}-dark{suffix}.svg"]
                light = FILES[f"header-{key}-light{suffix}.svg"]
                with self.subTest(header=key, phone=bool(suffix)):
                    self.assertEqual(parse(dark).get("aria-label"), title)
                    self.assertIn(kit.BLUE_LIGHT, dark)
                    self.assertIn(kit.INK, dark)
                    # the light page gets the deeper blue and dark ink: #60a5fa is 2.5:1 on white
                    self.assertIn(chrome.LIGHT_KICKER, light)
                    self.assertNotIn(kit.BLUE_LIGHT, light)
                    self.assertNotIn(kit.INK, light)
                    # no surface is drawn: the page shows through
                    self.assertNotIn(kit.BG, dark)
                    self.assertNotIn(kit.CARD, dark)

    def test_the_footer_keeps_its_lines_and_the_disclaimer_at_both_widths(self) -> None:
        disclaimer = CTX["disclaimer"]
        self.assertTrue(disclaimer)
        wide = [content(element) for element in texts(parse(FILES["footer.svg"]))]
        self.assertIn(disclaimer, wide)
        for line in chrome.FOOTER_LINES:
            self.assertIn(line, wide)
        phone = " ".join(
            content(element) for element in texts(parse(FILES["footer-mobile.svg"]))
        )
        self.assertIn(disclaimer, phone)
        for name in ("footer.svg", "footer-mobile.svg"):
            self.assertIn(disclaimer, parse(FILES[name]).get("aria-label"))

    def test_each_strip_names_its_card_and_its_action_without_overlap(self) -> None:
        for key, repo, card in CTX["get_cards"]:
            svg = FILES[f"get-{key}.svg"]
            root = parse(svg)
            ask, link = texts(root)
            with self.subTest(strip=key):
                self.assertEqual(
                    root.get("aria-label"),
                    f"Get the {card} for your own profile: Sagargupta16/{repo}",
                )
                self.assertIn(card.upper(), content(ask))
                self.assertIn(f"SAGARGUPTA16/{repo.upper()}", content(link))
                self.assertLess(extent(ask, svg)[1] + 16, extent(link, svg)[0])
                phone = texts(parse(FILES[f"get-{key}-mobile.svg"]))
                self.assertEqual(len(phone), 2)  # two lines, as on the live page
                self.assertIn(card, content(phone[0]))

    def test_connect_buttons_flash_in_turn(self) -> None:
        begins = []
        for button in CTX["connect"]:
            root = parse(FILES[f"connect-{button['key']}.svg"])
            self.assertEqual(root.get("aria-label"), button["label"])
            self.assertEqual(content(texts(root)[0]), button["label"].upper())
            begins.append(float(root.find(f".//{SVG}animate").get("begin")[:-1]))
        self.assertEqual(begins, [index * 0.5 for index in range(len(begins))])


class FixTests(unittest.TestCase):
    def test_the_footer_comet_and_its_dot_ride_one_normalised_path(self) -> None:
        """render-a-08: the dash ran at 255 px/s and the dot at 211 px/s, so they separated."""
        root = parse(FILES["footer.svg"])
        self.assertIsNone(root.find(f".//{SVG}animateMotion"))
        self.assertIsNone(root.find(f".//{SVG}circle"))
        track, tail, dot = root.findall(f"{SVG}path")
        self.assertIsNone(track.get("pathLength"))
        units = float(tail.get("pathLength"))
        for stroke in (tail, dot):
            self.assertEqual(stroke.get("d"), track.get("d"))
            self.assertEqual(float(stroke.get("pathLength")), units)
            self.assertEqual(stroke.get("stroke-linecap"), "round")
        tail_length, tail_gap = map(float, tail.get("stroke-dasharray").split())
        dot_length, dot_gap = map(float, dot.get("stroke-dasharray").split())
        self.assertLess(dot_length, 1)  # drawn as its round cap
        # one dash on the wave at a time, however far the offset runs
        self.assertGreaterEqual(min(tail_gap, dot_gap), units + tail_length)
        moves = [stroke.find(f"{SVG}animate") for stroke in (tail, dot)]
        for name in ("attributeName", "dur", "begin", "keyTimes", "repeatCount"):
            self.assertEqual(moves[0].get(name), moves[1].get(name), name)
        self.assertEqual(moves[0].get("attributeName"), "stroke-dashoffset")
        # a dash starts at minus its offset: the tail's far end is the head, the dot's start is the head
        tail_offsets = [float(v) for v in moves[0].get("values").split(";")]
        dot_offsets = [float(v) for v in moves[1].get("values").split(";")]
        heads = [tail_length - offset for offset in tail_offsets]
        self.assertEqual(heads, [-offset for offset in dot_offsets])
        # in at the left edge, and gone only once the tail has left on the right
        self.assertEqual(heads, [0, units + tail_length])
        # the still frame holds them together too, both on the card
        rest = tail_length - float(tail.get("stroke-dashoffset"))
        self.assertEqual(rest, -float(dot.get("stroke-dashoffset")))
        self.assertTrue(tail_length <= rest <= units)

    def test_connect_labels_are_xml_escaped(self) -> None:
        """render-b-22: a label with & or < used to break the file."""
        label = 'Q&A <x> "y"'
        for icon in (None, "M0 0h24v24H0z"):
            root = parse(chrome.render_connect_button(label, icon, 0))
            self.assertEqual(root.get("aria-label"), label)
            self.assertEqual(content(texts(root)[0]), label.upper())
        files = chrome.render({}, context(connect=[{"key": "qa", "label": label}]))
        self.assertEqual(
            content(texts(parse(files["connect-qa.svg"]))[0]), label.upper()
        )

    def test_header_numbers_and_subtitles_come_from_the_context(self) -> None:
        headers = [
            ("alpha", "07", "Alpha & Beta", "first <draft> of it"),
            ("gamma", "12", "Gamma", "second one"),
        ]
        files = chrome.render({}, context(headers=headers))
        self.assertEqual(
            sorted(name for name in files if name.startswith("header-")),
            sorted(
                f"header-{key}-{theme}{suffix}.svg"
                for key in ("alpha", "gamma")
                for theme in ("dark", "light")
                for suffix in ("", "-mobile")
            ),
        )
        for key, number, title, subtitle in headers:
            kicker = f"{number} / {subtitle.upper()}"
            for theme in ("dark", "light"):
                wide = parse(files[f"header-{key}-{theme}.svg"])
                self.assertEqual(
                    [content(element) for element in texts(wide)], [kicker, title]
                )
                phone = files[f"header-{key}-{theme}-mobile.svg"]
                self.assertEqual(" ".join(kicker_lines(phone)), kicker)
        # and the live page draws what build_context hands over, nothing typed here
        for key, number, title, subtitle in CTX["headers"]:
            wide = parse(FILES[f"header-{key}-dark.svg"])
            self.assertEqual(
                [content(element) for element in texts(wide)],
                [f"{number} / {subtitle.upper()}", title],
            )

    def test_cta_labels_count_from_the_context(self) -> None:
        files = chrome.render({}, context())
        labels = {
            name: content(texts(parse(files[name]))[0])
            for name in ("cta-portfolio.svg", "cta-community.svg", "cta-profile.svg")
        }
        self.assertEqual(
            labels,
            {
                "cta-portfolio.svg": "VIEW ALL 7 PROJECTS",
                "cta-community.svg": "SEE ALL 3 COMMUNITY TOOLS",
                "cta-profile.svg": "BACK TO PROFILE",
            },
        )
        self.assertEqual(
            parse(files["cta-portfolio.svg"]).get("aria-label"), "View all 7 projects"
        )
        # only the portfolio button is filled
        self.assertIn(f'fill="{kit.BLUE}"', files["cta-portfolio.svg"])
        self.assertNotIn(f'fill="{kit.BLUE}"', files["cta-community.svg"])
        live = chrome.cta_labels(CTX)
        self.assertEqual(
            live["cta-community"][0], f"See all {len(CTX['tools'])} community tools"
        )
        if CTX["project_count"]:
            self.assertEqual(
                live["cta-portfolio"][0], f"View all {CTX['project_count']} projects"
            )

    def test_the_portfolio_cta_is_skipped_when_the_count_is_unknown(self) -> None:
        for count in (0, None):
            files = chrome.render({}, context(project_count=count))
            self.assertNotIn("cta-portfolio.svg", files)
            self.assertIn("cta-community.svg", files)
            self.assertIn("cta-profile.svg", files)
            for svg in files.values():
                self.assertNotIn("PROJECTS", svg)

    def test_phone_header_kickers_are_balanced(self) -> None:
        """The live stats header left CONTESTS alone on its second line."""
        files = chrome.render({}, context())
        for theme in ("dark", "light"):
            self.assertEqual(
                kicker_lines(files[f"header-stats-{theme}-mobile.svg"]),
                ["02 / GITHUB ACTIVITY, LEETCODE", "AND CONTESTS"],
            )
        for key, number, _, subtitle in CTX["headers"]:
            kicker = f"{number} / {subtitle.upper()}"
            wrapped = kit.wrap_text(
                kicker, mobile.CONTENT_WIDTH, mobile.MICRO, True, kit.TRACK
            )
            for theme in ("dark", "light"):
                svg = FILES[f"header-{key}-{theme}-mobile.svg"]
                lines = kicker_lines(svg)
                with self.subTest(header=key, theme=theme):
                    self.assertEqual(lines, kit.balance(wrapped))
                    if len(lines) > 1:
                        self.assertIn(" ", lines[-1])
                    # mono by attribute, with no CSS rule that would override it
                    self.assertNotIn("text{", svg)
                    self.assertEqual(parse(svg).get("font-family"), kit.SANS)


if __name__ == "__main__":
    unittest.main()
