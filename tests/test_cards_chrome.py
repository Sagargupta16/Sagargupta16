"""Checks for the page chrome: section headers, the connect row, call-to-action buttons, strips and the footer.

The file-wide checks run on the checked-in snapshot and assert rules, never
values. The checks for each rule build their own small context, so a refresh
of assets/svg/data.json cannot fail them.
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
from cards import chrome

SVG = "{http://www.w3.org/2000/svg}"
DASHES = (chr(0x2013), chr(0x2014))
CARD_FILE = re.compile(r"[a-z0-9][a-z0-9-]*\.svg")
CLOCK = {2.0, 3.0, 4.0, 6.0, 12.0, 24.0}  # kit's page clock
TRACKING = {"m": kit.TRACK, "k": 2.0, "c": 0.0}  # the mono classes in kit.style()
ANIMATIONS = {f"{SVG}animate", f"{SVG}animateTransform", f"{SVG}animateMotion"}
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
        "header_counts": {"experience": "4 YEARS AT ACME", "stats": ""},
        "connect": [
            {"key": "linkedin", "label": "LinkedIn", "icon": "M0 0h24v24H0z"},
            {"key": "resume", "label": "Resume", "icon": None, "primary": True},
        ],
        "project_count": 7,
        "tools": [{"slug": "one"}, {"slug": "two"}, {"slug": "three"}],
        "get_cards": [("oss", "oss-contributions-card-action", "open-source cards")],
        "disclaimer": "Personal projects and opinions are my own.",
        "location": "Springfield, Nowhere",
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


def size(element: ET.Element) -> tuple[float, float]:
    root = element
    _, _, width, height = map(float, root.get("viewBox").split())
    return width, height


def extent(element: ET.Element) -> tuple[float, float]:
    """The left and right edge of a text element: its textLength, else kit's measure."""
    font = float(element.get("font-size"))
    cls = element.get("class")
    if element.get("textLength"):
        width = float(element.get("textLength"))
    elif cls in TRACKING:
        width = (
            kit.text_width(content(element), font, True, TRACKING[cls]) - TRACKING[cls]
        )
    else:
        width = kit.text_width(content(element), font)
    x = float(element.get("x"))
    left = {"middle": x - width / 2, "end": x - width}.get(
        element.get("text-anchor"), x
    )
    return left, left + width


def box(element: ET.Element) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) of a text element, from its extent, baseline and size."""
    left, right = extent(element)
    font, y = float(element.get("font-size")), float(element.get("y"))
    return left, y - font * 0.75, right, y + font * 0.25


def rect_box(element: ET.Element) -> tuple[float, float, float, float]:
    x, y = float(element.get("x")), float(element.get("y"))
    return x, y, x + float(element.get("width")), y + float(element.get("height"))


def overlaps(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def inside(inner: tuple, outer: tuple, margin: float = 0) -> bool:
    return (
        inner[0] >= outer[0] + margin
        and inner[1] >= outer[1]
        and inner[2] <= outer[2] - margin
        and inner[3] <= outer[3]
    )


def loops(root: ET.Element) -> list[ET.Element]:
    return [
        animation
        for animation in root.iter()
        if animation.tag in ANIMATIONS and animation.get("repeatCount") == "indefinite"
    ]


def header_parts(
    svg: str | ET.Element,
) -> tuple[list[str], list[str], ET.Element | None]:
    """(kicker lines, title lines, the datum's text or None) of a header file or its root."""
    found = texts(parse(svg) if isinstance(svg, str) else svg)
    titles = [content(t) for t in found if t.get("class") == "t"]
    datum = next((t for t in found if t.get("text-anchor") == "middle"), None)
    kicker = [
        content(t)
        for t in found
        if t.get("class") in ("k", "m") and t.get("text-anchor") != "middle"
    ]
    return kicker, titles, datum


class EveryFileTests(unittest.TestCase):
    def test_the_lane_returns_exactly_its_files(self) -> None:
        expected = {"footer.svg", "footer-mobile.svg"}
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
        # the headers own the section break now: no divider image is drawn
        self.assertNotIn("divider.svg", FILES)
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

    def test_the_sizes_are_the_ones_the_page_lays_out(self) -> None:
        for name, svg in FILES.items():
            root = parse(svg)
            width, height = size(root)
            with self.subTest(file=name):
                self.assertEqual(float(root.get("width")), width)
                self.assertEqual(float(root.get("height")), height)
                phone = name.endswith("-mobile.svg")
                if name.startswith("connect-"):
                    self.assertEqual((width, height), (128, 40))
                elif name.startswith("cta-"):
                    self.assertEqual((width, height), (250, 44))
                elif name.startswith("get-"):
                    self.assertEqual((width, height), (320, 60) if phone else (840, 36))
                elif name.startswith("header-"):
                    self.assertEqual(width, 320 if phone else 840)
                    self.assertTrue(64 <= height <= 140, height)
                else:  # the footer
                    self.assertEqual(width, 320 if phone else 840)
                    self.assertTrue(130 <= height <= 200, height)

    def test_no_text_leaves_the_canvas(self) -> None:
        for name, svg in FILES.items():
            root = parse(svg)
            width, height = size(root)
            for element in texts(root):
                left, top, right, bottom = box(element)
                with self.subTest(file=name, text=content(element)):
                    self.assertGreaterEqual(left, 0)
                    self.assertLessEqual(right, width)
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(bottom, height)

    def test_framed_cards_keep_their_side_padding(self) -> None:
        """Strips and the footer have a surface, so their text keeps clear of its border."""
        for name, svg in FILES.items():
            if not name.startswith(("get-", "footer")):
                continue
            root = parse(svg)
            width, _ = size(root)
            for element in texts(root):
                left, right = extent(element)
                with self.subTest(file=name, text=content(element)):
                    self.assertGreaterEqual(left, 16 - 0.01)
                    self.assertLessEqual(right, width - 16 + 0.01)

    def test_text_is_never_smaller_than_the_floor(self) -> None:
        """Buttons have no phone twin: the README shows them at 128 and 250px on a phone too."""
        for name, svg in FILES.items():
            phone = "-mobile" in name or name.startswith(("connect-", "cta-"))
            floor = kit.MICRO_PHONE if phone else kit.MICRO
            for element in texts(parse(svg)):
                with self.subTest(file=name, text=content(element)):
                    self.assertGreaterEqual(float(element.get("font-size")), floor)

    def test_a_still_frame_shows_the_whole_card(self) -> None:
        """Hidden at rest only: a rotating line behind the first one, or a light that comes and goes."""
        for name, svg in FILES.items():
            root = parse(svg)
            parents = {child: parent for parent in root.iter() for child in parent}
            for element in root.iter():
                if element.get("opacity") != "0":
                    continue
                with self.subTest(file=name, tag=element.tag.removeprefix(SVG)):
                    fades = [
                        animate
                        for animate in element.findall(f"{SVG}animate")
                        if animate.get("attributeName") == "opacity"
                        and animate.get("repeatCount") == "indefinite"
                    ]
                    self.assertEqual(len(fades), 1)
                    if element.tag == f"{SVG}text":
                        first = next(
                            sibling
                            for sibling in parents[element]
                            if sibling.tag == f"{SVG}text"
                            and sibling.get("y") == element.get("y")
                        )
                        self.assertIsNone(first.get("opacity"))
                    else:
                        # a decoration that lights: it holds no text and has no fill of its own
                        self.assertIn(element.tag, (f"{SVG}rect", f"{SVG}circle"))
                        self.assertFalse(list(element.iter(f"{SVG}text")))
            # an entrance holds its start value, then ends on the element's own frame
            for animate in root.iter(f"{SVG}animate"):
                if animate.get("fill") == "freeze":
                    self.assertTrue(animate.get("values").endswith(";1"), name)

    def test_motion_is_smil_on_the_page_clock_and_every_card_moves(self) -> None:
        for name, svg in FILES.items():
            root = parse(svg)
            repeating = loops(root)
            with self.subTest(file=name):
                self.assertNotIn("@keyframes", svg)
                self.assertTrue(repeating)
                for animation in repeating:
                    self.assertIn(float(animation.get("dur").rstrip("s")), CLOCK)
                # one meaningful motion, not a light show: kit's budget is 40 at most
                moving = {
                    parents
                    for parents in root.iter()
                    if any(c.tag in ANIMATIONS for c in parents)
                }
                self.assertLessEqual(len(moving), 40)

    def test_smil_lists_line_up(self) -> None:
        """A keyTimes list that does not match its values is dropped, and the element never moves."""
        for name, svg in FILES.items():
            for animation in parse(svg).iter():
                if animation.tag not in ANIMATIONS or not animation.get("keyTimes"):
                    continue
                times = [float(t) for t in animation.get("keyTimes").split(";")]
                values = animation.get("values").split(";")
                with self.subTest(file=name, values=animation.get("values")):
                    self.assertEqual(len(times), len(values))
                    self.assertEqual(times[0], 0)
                    self.assertEqual(times[-1], 1)
                    self.assertEqual(times, sorted(times))
                    if animation.get("keySplines"):
                        splines = animation.get("keySplines").split(";")
                        self.assertEqual(len(splines), len(times) - 1)

    def test_rendering_is_deterministic(self) -> None:
        self.assertEqual(chrome.render({}, CTX), FILES)


class HeaderTests(unittest.TestCase):
    def test_headers_come_as_a_dark_and_light_pair_at_both_widths(self) -> None:
        for key, _, title, _ in CTX["headers"]:
            for suffix in ("", "-mobile"):
                dark = FILES[f"header-{key}-dark{suffix}.svg"]
                light = FILES[f"header-{key}-light{suffix}.svg"]
                datum = CTX["header_counts"].get(key) or ""
                label = f"{title}: {datum}" if datum else title
                with self.subTest(header=key, phone=bool(suffix)):
                    self.assertEqual(parse(dark).get("aria-label"), label)
                    self.assertEqual(parse(light).get("aria-label"), label)
                    self.assertIn(kit.BLUE_LIGHT, dark)
                    self.assertIn(kit.INK, dark)
                    # the light page gets the deeper blue and dark ink: #60a5fa is 2.5:1 on white
                    self.assertIn(chrome.LIGHT_KICKER, light)
                    self.assertNotIn(kit.BLUE_LIGHT, light)
                    self.assertNotIn(kit.INK, light)
                    # no surface is drawn: the page shows through
                    self.assertNotIn(kit.BG, dark)
                    self.assertNotIn(kit.CARD, dark)
                    self.assertNotIn(kit.GREEN, dark + light)

    def test_each_header_keeps_its_clear_space_on_top(self) -> None:
        """The header owns the break between sections: nothing above CLEAR."""
        self.assertEqual(chrome.CLEAR, 12)
        files = dict(FILES)
        files.update(
            chrome.render(
                {}, context(header_counts={"experience": "13 MERGED UPSTREAM"})
            )
        )
        for name, svg in files.items():
            if not name.startswith("header-"):
                continue
            root = parse(svg)
            with self.subTest(file=name):
                for element in texts(root):
                    self.assertGreaterEqual(box(element)[1], chrome.CLEAR)
                for element in root.iter(f"{SVG}rect"):
                    self.assertGreaterEqual(float(element.get("y")), chrome.CLEAR)

    def test_header_copy_comes_from_the_context_escaped(self) -> None:
        headers = [
            ("alpha", "07", "Alpha & Beta", "first <draft> of it"),
            ("gamma", "12", "Gamma", "second one"),
        ]
        files = chrome.render({}, context(headers=headers, header_counts={}))
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
                for suffix in ("", "-mobile"):
                    lines, titles, datum = header_parts(
                        files[f"header-{key}-{theme}{suffix}.svg"]
                    )
                    self.assertEqual(" ".join(lines), kicker)
                    self.assertEqual(" ".join(titles), title)
                    self.assertIsNone(datum)
        # and the live page draws what build_context hands over, nothing typed here
        for key, number, title, subtitle in CTX["headers"]:
            lines, titles, _ = header_parts(FILES[f"header-{key}-dark.svg"])
            self.assertEqual(lines, [chrome.kicker_text(number, subtitle)])
            self.assertEqual(titles, [title])

    def test_the_section_number_is_the_blue_part_of_the_kicker(self) -> None:
        for theme, blue in (("dark", kit.BLUE_LIGHT), ("light", chrome.LIGHT_KICKER)):
            root = parse(
                chrome.render_header("03", "Open Source", "merged work", theme)
            )
            first = texts(root)[0]
            number = first.find(f"{SVG}tspan")
            self.assertEqual((number.text, number.get("fill")), ("03", blue))
            self.assertEqual(first.get("fill"), chrome.INKS[theme]["meta"])

    def test_the_datum_sits_in_its_chip_clear_of_the_title_and_kicker(self) -> None:
        cases = [
            ("01", "Experience", "where I work", "4 YEARS AT ACME"),
            (
                "05",
                "Publications, Talks and Recognition",
                "reviews, talks",
                "3 QZX SAMPLES + 18 PROJECTS",
            ),
            (
                "09",
                "A Very Long Section Title That Wraps On A Phone",
                "short",
                "120 MERGED UPSTREAM",
            ),
            (
                "02",
                "Community and Developer Tools",
                "open tools anyone can use and more of them",
                "20 TOOLS",
            ),
            ("04", "Certifications", "verified on Credly", "5 ACTIVE"),
            # too wide for a chip beside the title, so it moves up beside the kicker
            ("04", "Certifications and Badges", "verified on Credly", "5 ACTIVE"),
            (
                "04",
                "Certifications, Badges and the Credentials Earned Since 2021",
                "on Credly",
                "5 ACTIVE",
            ),
        ]
        beside_kicker = {320.0: 0, 840.0: 0}
        for number, title, subtitle, datum in cases:
            for render in (chrome.render_header, chrome.render_header_phone):
                for theme in chrome.THEMES:
                    svg = render(number, title, subtitle, theme, datum)
                    root = parse(svg)
                    width, _ = size(root)
                    lines, titles, label = header_parts(root)
                    chip = next(
                        r for r in root.iter(f"{SVG}rect") if r.get("opacity") != "0"
                    )
                    first_title = next(t for t in texts(root) if t.get("class") == "t")
                    with self.subTest(title=title, width=width, theme=theme):
                        self.assertEqual(content(label), datum)
                        self.assertTrue(inside(box(label), rect_box(chip), 6))
                        # beside the kicker too, the chip stays out of the break above
                        self.assertGreaterEqual(rect_box(chip)[1], chrome.CLEAR)
                        self.assertLessEqual(rect_box(chip)[2], width)
                        self.assertGreaterEqual(rect_box(chip)[0], 0)
                        for element in texts(root):
                            if element is not label:
                                self.assertFalse(
                                    overlaps(box(element), rect_box(chip)),
                                    content(element),
                                )
                        # every count reads in the ink, the words in the muted fill
                        self.assertEqual(label.get("fill"), chrome.INKS[theme]["meta"])
                        inked = [
                            run.text
                            for run in label.iter(f"{SVG}tspan")
                            if run.get("fill") == chrome.INKS[theme]["ink"]
                        ]
                        counts = [w for w in datum.split() if re.search("[0-9]", w)]
                        self.assertEqual(inked, counts)
                        # beside the kicker the chip is slimmer, its text on the kicker's
                        # baseline and clear of the title's capitals below
                        if rect_box(chip)[3] <= box(first_title)[1]:
                            beside_kicker[width] += 1
                            kicker_line = texts(root)[0]
                            self.assertEqual(
                                float(label.get("y")), float(kicker_line.get("y"))
                            )
                            self.assertEqual(
                                float(chip.get("height")), chrome.KICKER_CHIP_H
                            )
                            self.assertLessEqual(
                                rect_box(chip)[3] + 5, box(first_title)[1]
                            )
        # the crafted titles reach that branch at both widths
        self.assertTrue(all(beside_kicker.values()), beside_kicker)

    def test_the_label_carries_the_datum_whole_and_the_chip_shows_it_upper_case(
        self,
    ) -> None:
        """The aria-label is the README's alt text, so it reads the datum as ctx wrote it."""
        datum = "3 QZX samples + 120 projects + 40 community tools and more"
        for render in (chrome.render_header, chrome.render_header_phone):
            root = parse(render("02", "Featured Projects", "built", "dark", datum))
            _, _, label = header_parts(root)
            with self.subTest(width=size(root)[0]):
                self.assertEqual(root.get("aria-label"), f"Featured Projects: {datum}")
                shown = content(label)
                self.assertEqual(shown, shown.upper())
                self.assertTrue(datum.upper().startswith(shown.removesuffix("...")))
        root = parse(chrome.render_header("02", "Featured Projects", "built", "dark"))
        self.assertEqual(root.get("aria-label"), "Featured Projects")

    def test_a_datum_too_wide_for_the_phone_is_cut_at_a_word(self) -> None:
        datum = "3 SAMPLES + 120 PROJECTS + 40 COMMUNITY TOOLS AND MORE"
        root = parse(
            chrome.render_header_phone("02", "Projects", "built", "dark", datum)
        )
        _, _, label = header_parts(
            chrome.render_header_phone("02", "Projects", "built", "dark", datum)
        )
        shown = content(label)
        self.assertTrue(shown.endswith("..."))
        self.assertTrue(datum.startswith(shown.removesuffix("...")))
        chip = next(r for r in root.iter(f"{SVG}rect") if r.get("opacity") != "0")
        self.assertLessEqual(rect_box(chip)[2], 320)

    def test_the_datum_follows_header_counts_and_is_left_out_when_empty(self) -> None:
        for key, _, _, _ in CTX["headers"]:
            datum = CTX["header_counts"].get(key) or ""
            for suffix in ("", "-mobile"):
                _, _, label = header_parts(FILES[f"header-{key}-dark{suffix}.svg"])
                with self.subTest(header=key, phone=bool(suffix)):
                    if datum:
                        self.assertTrue(
                            datum.upper().startswith(content(label).removesuffix("..."))
                        )
                    else:
                        self.assertIsNone(label)
        files = chrome.render({}, context(header_counts={}))
        for name, svg in files.items():
            if name.startswith("header-"):
                self.assertIsNone(header_parts(svg)[2], name)
                self.assertNotIn("<rect", svg, name)

    def test_a_light_crosses_the_rule_every_6_s_and_lights_the_chip_as_it_passes(
        self,
    ) -> None:
        for render in (chrome.render_header, chrome.render_header_phone):
            root = parse(render("01", "Experience", "where", "dark", "4 YEARS AT ACME"))
            light = next(
                p
                for p in root.iter(f"{SVG}path")
                if p.find(f"{SVG}animate") is not None
            )
            move = light.find(f"{SVG}animate")
            self.assertEqual(move.get("attributeName"), "stroke-dashoffset")
            self.assertEqual(move.get("dur"), "6s")
            # 2 s of travel, 4 s of rest
            self.assertEqual(move.get("keyTimes"), "0;0.333;1")
            dash = float(light.get("stroke-dasharray").split()[0])
            values = [float(v) for v in move.get("values").split(";")]
            self.assertEqual(values, [dash, -100, -100])
            # at rest the light is off the rule's start, so a still frame shows the plain rule
            self.assertEqual(float(light.get("stroke-dashoffset")), dash)
            flash = next(r for r in root.iter(f"{SVG}rect") if r.get("opacity") == "0")
            fade = flash.find(f"{SVG}animate")
            self.assertEqual(fade.get("dur"), "6s")
            on = [
                float(t) * 6
                for t, v in zip(
                    fade.get("keyTimes").split(";"), fade.get("values").split(";")
                )
                if v == "1"
            ]
            self.assertTrue(on and max(on) <= chrome.RULE_TRAVEL + 0.5)

    def test_phone_header_kickers_and_titles_are_balanced(self) -> None:
        """The live stats header used to leave CONTESTS alone on its second line."""
        files = chrome.render({}, context())
        for theme in ("dark", "light"):
            lines, _, _ = header_parts(files[f"header-stats-{theme}-mobile.svg"])
            self.assertEqual(lines, ["02 / GITHUB ACTIVITY, LEETCODE", "AND CONTESTS"])
        for key, number, title, subtitle in CTX["headers"]:
            wrapped = kit.balance(
                kit.wrap_text(
                    chrome.kicker_text(number, subtitle),
                    318,
                    kit.MICRO_PHONE,
                    True,
                    kit.TRACK,
                )
            )
            titles = kit.balance(kit.wrap_text(title, 318, 22))
            for theme in ("dark", "light"):
                lines, shown, _ = header_parts(
                    FILES[f"header-{key}-{theme}-mobile.svg"]
                )
                with self.subTest(header=key, theme=theme):
                    self.assertEqual(lines, wrapped)
                    self.assertEqual(shown, titles)
                    for block in (lines, shown):
                        if len(block) > 1:
                            self.assertIn(" ", block[-1])

    def test_a_header_with_no_number_or_no_subtitle_still_reads(self) -> None:
        self.assertEqual(chrome.kicker_text("", "where I studied"), "WHERE I STUDIED")
        self.assertEqual(chrome.kicker_text("09", ""), "09")
        root = parse(chrome.render_header("09", "Education", "", "dark"))
        self.assertEqual(content(texts(root)[0]), "09")


class ConnectTests(unittest.TestCase):
    def test_the_buttons_light_in_turn_on_one_6_s_clock(self) -> None:
        begins = []
        for index, button in enumerate(CTX["connect"]):
            root = parse(FILES[f"connect-{button['key']}.svg"])
            self.assertEqual(root.get("aria-label"), button["label"])
            self.assertEqual(content(texts(root)[0]), button["label"].upper())
            moving = loops(root)
            self.assertEqual(len(moving), 1)
            self.assertEqual(moving[0].get("dur"), "6s")
            begins.append(float((moving[0].get("begin") or "0s")[:-1]))
        self.assertEqual(begins, [index * 1.5 for index in range(len(begins))])

    def test_resume_is_the_primary_and_a_light_circles_it(self) -> None:
        primary = [b for b in CTX["connect"] if b.get("primary")]
        self.assertEqual([b["key"] for b in primary], ["resume"])
        svg = FILES["connect-resume.svg"]
        root = parse(svg)
        self.assertIn(f'fill="{kit.BLUE}"', svg)
        self.assertEqual(texts(root)[0].get("fill"), chrome.WHITE)
        light = next(
            p for p in root.iter(f"{SVG}path") if p.find(f"{SVG}animate") is not None
        )
        dash, gap = map(float, light.get("stroke-dasharray").split())
        self.assertEqual(dash + gap, float(light.get("pathLength")))
        start, end = map(float, light.find(f"{SVG}animate").get("values").split(";"))
        self.assertEqual(start - end, 100)  # once round per loop, without a gap
        self.assertEqual(float(light.get("stroke-dashoffset")), start)
        for button in CTX["connect"]:
            if not button.get("primary"):
                other = FILES[f"connect-{button['key']}.svg"]
                self.assertNotIn(f'fill="{kit.BLUE}"', other)
                # lit the way the hero lights a proof cell
                self.assertIn(kit.BLUE_TINT, other)

    def test_label_and_icon_sit_inside_the_button(self) -> None:
        labels = ["LinkedIn", "Resume", "Email", "Portfolio", "Newsletter"]
        for label in labels:
            for icon in (None, "M0 0h24v24H0z"):
                for primary in (False, True):
                    root = parse(chrome.render_connect_button(label, icon, 0, primary))
                    word = texts(root)[0]
                    left, _, right, _ = box(word)
                    with self.subTest(label=label, icon=bool(icon), primary=primary):
                        self.assertGreaterEqual(left, 10)
                        self.assertLessEqual(right, 128 - 10)
                        # the icon and the word are centred as one group
                        start = left - (chrome.ICON + chrome.ICON_GAP if icon else 0)
                        self.assertAlmostEqual(start, 128 - right, delta=0.6)

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


class CtaTests(unittest.TestCase):
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
        live = chrome.cta_labels(CTX)
        self.assertEqual(
            live["cta-community"], f"See all {len(CTX['tools'])} community tools"
        )
        if CTX["project_count"]:
            self.assertEqual(
                live["cta-portfolio"], f"View all {CTX['project_count']} projects"
            )

    def test_every_cta_is_outlined_with_an_arrow_that_nudges_every_3_s(self) -> None:
        for name in ("cta-portfolio.svg", "cta-community.svg", "cta-profile.svg"):
            svg = chrome.render({}, context())[name]
            root = parse(svg)
            with self.subTest(file=name):
                self.assertNotIn(f'fill="{kit.BLUE}"', svg)
                nudge = root.find(f".//{SVG}animateTransform")
                self.assertEqual(nudge.get("dur"), "3s")
                shifts = {float(v.split()[0]) for v in nudge.get("values").split(";")}
                self.assertEqual(max(abs(s) for s in shifts), chrome.NUDGE)
                arrow = next(p for p in root.iter(f"{SVG}path"))
                word = texts(root)[0]
                left, _, right, _ = box(word)
                x = float(re.search(r"translate\(([0-9.]+)", svg).group(1))
                if name == "cta-profile.svg":
                    # back points left: the arrow sits before the label and nudges left
                    self.assertEqual(arrow.get("transform"), "scale(-1 1)")
                    self.assertLess(x, left)
                    self.assertLess(min(shifts), 0)
                else:
                    self.assertIsNone(arrow.get("transform"))
                    self.assertGreater(x, right)
                    self.assertGreater(max(shifts), 0)

    def test_a_long_count_still_fits_at_the_phone_floor(self) -> None:
        """No phone twin: at 250px on a phone the label keeps 11.5px; the tracking gives way instead."""
        for tools, projects in ((20, 49), (999, 9876), (9999, 9999)):
            files = chrome.render(
                {},
                context(
                    project_count=projects,
                    tools=[{"slug": str(i)} for i in range(tools)],
                ),
            )
            for name in ("cta-portfolio.svg", "cta-community.svg", "cta-profile.svg"):
                svg = files[name]
                root = parse(svg)
                word = texts(root)[0]
                left, _, right, _ = box(word)
                # the arrow's span, its nudge included: it points right, or left on cta-profile
                at = float(re.search(r"translate\(([0-9.]+)", svg).group(1))
                if name == "cta-profile.svg":
                    arrow = (at - chrome.ARROW_W - chrome.NUDGE, at)
                    clear = left - arrow[1]
                else:
                    arrow = (at, at + chrome.ARROW_W + chrome.NUDGE)
                    clear = arrow[0] - right
                with self.subTest(file=name, tools=tools, projects=projects):
                    self.assertEqual(float(word.get("font-size")), kit.MICRO_PHONE)
                    self.assertGreaterEqual(min(left, arrow[0]), 12)
                    self.assertLessEqual(max(right, arrow[1]), 250 - 12)
                    self.assertGreaterEqual(clear, min(chrome.CTA_GAPS))

    def test_the_portfolio_cta_is_skipped_when_the_count_is_unknown(self) -> None:
        for count in (0, None):
            files = chrome.render({}, context(project_count=count))
            self.assertNotIn("cta-portfolio.svg", files)
            self.assertIn("cta-community.svg", files)
            self.assertIn("cta-profile.svg", files)
            for svg in files.values():
                self.assertNotIn("PROJECTS", svg)


class StripTests(unittest.TestCase):
    def test_each_strip_names_its_action_without_overlap(self) -> None:
        for key, repo, card in CTX["get_cards"]:
            for suffix in ("", "-mobile"):
                root = parse(FILES[f"get-{key}{suffix}.svg"])
                ask, link = texts(root)
                with self.subTest(strip=key, phone=bool(suffix)):
                    self.assertEqual(
                        root.get("aria-label"),
                        f"Get the {card} for your own profile: Sagargupta16/{repo}",
                    )
                    self.assertEqual(content(ask), chrome.strip_ask(card))
                    self.assertTrue(content(link).endswith(repo))
                    self.assertEqual(link.get("fill"), kit.BLUE_LIGHT)
                    self.assertFalse(overlaps(box(ask), box(link)))
                    if suffix:  # two lines on the phone
                        self.assertGreater(float(link.get("y")), float(ask.get("y")))
                    else:
                        self.assertLess(extent(ask)[1] + chrome.GAP, extent(link)[0])
                    self.assertNotIn(kit.GREEN, FILES[f"get-{key}{suffix}.svg"])

    def test_the_ask_says_this_card_or_these_cards(self) -> None:
        self.assertEqual(
            chrome.strip_ask("GitHub stats card"), "GET THIS CARD FOR YOUR PROFILE"
        )
        self.assertEqual(
            chrome.strip_ask("open-source cards"), "GET THESE CARDS FOR YOUR PROFILE"
        )

    def test_a_light_runs_the_leader_and_the_arrow_nudges_as_it_lands(self) -> None:
        root = parse(chrome.render_get_this_card("acme-card-action", "QZX card"))
        light = next(
            p for p in root.iter(f"{SVG}path") if p.find(f"{SVG}animate") is not None
        )
        move = light.find(f"{SVG}animate")
        self.assertEqual((move.get("dur"), move.get("keyTimes")), ("6s", "0;0.333;1"))
        nudge = root.find(f".//{SVG}animateTransform")
        self.assertEqual(nudge.get("dur"), "6s")
        times = [float(t) * 6 for t in nudge.get("keyTimes").split(";")]
        values = nudge.get("values").split(";")
        moved = next(i for i, v in enumerate(values) if v != "0 0")
        # the arrow sets off as the light reaches the end of the leader, and is back by 3 s
        self.assertAlmostEqual(times[moved - 1], chrome.STRIP_TRAVEL, delta=0.01)
        self.assertEqual(values[moved], f"{chrome.NUDGE} 0")
        back = next(i for i in range(moved, len(values)) if values[i] == "0 0")
        self.assertLessEqual(times[back], chrome.STRIP_TRAVEL + 1)

    def test_a_long_repository_falls_back_to_its_name_then_is_cut(self) -> None:
        long_repo = (
            "a-very-long-community-card-generator-action-for-profiles-and-more-of-it"
        )
        for repo in ("x", "oss-contributions-card-action", long_repo, long_repo * 3):
            for render, width in (
                (chrome.render_get_this_card, 840),
                (chrome.render_get_this_card_phone, 320),
            ):
                svg = render(repo, "QZX cards")
                root = parse(svg)
                ask, link = texts(root)
                shown = content(link)
                with self.subTest(repo=repo[:20], width=width):
                    self.assertIn(
                        shown,
                        (f"Sagargupta16/{repo}", repo)
                        if not shown.endswith("...")
                        else (shown,),
                    )
                    if shown.endswith("..."):
                        self.assertTrue(repo.startswith(shown.removesuffix("...")))
                    self.assertLessEqual(
                        extent(link)[1], width - 16 - chrome.ARROW_W - 10 + 0.01
                    )
                    self.assertFalse(overlaps(box(ask), box(link)))
        # the short ones keep the owner on the wide strip
        self.assertEqual(
            content(texts(parse(chrome.render_get_this_card("x", "QZX card")))[1]),
            "Sagargupta16/x",
        )

    def test_the_phone_strips_all_show_the_bare_repository(self) -> None:
        """One form for every phone strip, short name or long: they sit one under another."""
        for repo in ("x", "acme-card-action", "oss-contributions-card-action"):
            root = parse(chrome.render_get_this_card_phone(repo, "QZX card"))
            self.assertEqual(content(texts(root)[1]), repo)
            self.assertIn(f"Sagargupta16/{repo}", root.get("aria-label"))
        for key, repo, _ in CTX["get_cards"]:
            shown = content(texts(parse(FILES[f"get-{key}-mobile.svg"]))[1])
            with self.subTest(strip=key):
                self.assertNotIn("/", shown)
                self.assertTrue(repo.startswith(shown.removesuffix("...")))


class FooterTests(unittest.TestCase):
    def test_the_footer_keeps_its_lines_and_the_disclaimer_at_both_widths(self) -> None:
        disclaimer = CTX["disclaimer"]
        self.assertTrue(disclaimer)
        for name in ("footer.svg", "footer-mobile.svg"):
            root = parse(FILES[name])
            shown = [content(element) for element in texts(root)]
            with self.subTest(file=name):
                for line in chrome.FOOTER_LINES:
                    self.assertIn(line, shown)
                self.assertIn(disclaimer, " ".join(shown))
                self.assertIn(disclaimer, root.get("aria-label"))
                for line in chrome.FOOTER_LINES:
                    self.assertIn(line, root.get("aria-label"))
        sizes = {
            float(t.get("font-size"))
            for t in texts(parse(FILES["footer.svg"]))
            if content(t) in disclaimer
        }
        self.assertEqual(sizes, {11.0})

    def test_the_comet_and_its_dot_ride_one_normalised_path(self) -> None:
        """render-a-08: the dash ran at 255 px/s and the dot at 211 px/s, so they separated."""
        for name in ("footer.svg", "footer-mobile.svg"):
            root = parse(FILES[name])
            self.assertIsNone(root.find(f".//{SVG}animateMotion"))
            track, tail, dot = [
                p
                for p in root.iter(f"{SVG}path")
                if p.get("d", "").startswith("M") and "C" in p.get("d")
            ]
            with self.subTest(file=name):
                self.assertIsNone(track.get("pathLength"))
                units = float(tail.get("pathLength"))
                self.assertEqual(units, chrome.WAVE_UNITS)
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
                for attribute in (
                    "attributeName",
                    "dur",
                    "begin",
                    "keyTimes",
                    "repeatCount",
                ):
                    self.assertEqual(
                        moves[0].get(attribute), moves[1].get(attribute), attribute
                    )
                self.assertEqual(moves[0].get("attributeName"), "stroke-dashoffset")
                # a dash starts at minus its offset: the tail's far end is the head, the dot's start is the head
                tail_offsets = [float(v) for v in moves[0].get("values").split(";")]
                dot_offsets = [float(v) for v in moves[1].get("values").split(";")]
                heads = [tail_length - offset for offset in tail_offsets]
                self.assertEqual(heads, [-offset for offset in dot_offsets])
                # in at the first stop, gone only once the tail has left the end, then a rest
                self.assertEqual(heads, [0, units + tail_length, units + tail_length])
                # the still frame holds them together too, the head arriving at the end node
                rest = tail_length - float(tail.get("stroke-dashoffset"))
                self.assertEqual(rest, -float(dot.get("stroke-dashoffset")))
                self.assertTrue(units * 0.9 <= rest < units)

    def test_a_stop_for_each_section_lights_in_order_as_the_comet_passes(self) -> None:
        for name in ("footer.svg", "footer-mobile.svg"):
            root = parse(FILES[name])
            lit = [
                c
                for c in root.iter(f"{SVG}circle")
                if c.get("fill") == kit.BLUE_LIGHT
                and c.find(f"{SVG}animate") is not None
            ]
            numbers = [number for _, number, _, _ in CTX["headers"]]
            with self.subTest(file=name):
                self.assertEqual(len(lit), len(numbers))
                xs = [float(c.get("cx")) for c in lit]
                self.assertEqual(xs, sorted(xs))
                ons = []
                for stop in lit:
                    fade = stop.find(f"{SVG}animate")
                    self.assertEqual(fade.get("dur"), "12s")
                    pairs = list(
                        zip(
                            fade.get("keyTimes").split(";"),
                            fade.get("values").split(";"),
                        )
                    )
                    ons.append(next(float(t) * 12 for t, v in pairs if v == "1"))
                    # a still frame shows every stop lit: the finished route
                    self.assertIsNone(stop.get("opacity"))
                self.assertEqual(ons, sorted(ons))
                self.assertLessEqual(ons[-1], chrome.COMET_TRAVEL)
                labels = [content(t) for t in texts(root) if content(t) in numbers]
                self.assertEqual(labels, numbers)

    def test_the_end_node_rings_when_the_comet_lands(self) -> None:
        root = parse(FILES["footer.svg"])
        ring = next(c for c in root.iter(f"{SVG}circle") if c.get("opacity") == "0")
        fade = [
            a
            for a in ring.findall(f"{SVG}animate")
            if a.get("attributeName") == "opacity"
        ][0]
        pairs = list(
            zip(fade.get("keyTimes").split(";"), fade.get("values").split(";"))
        )
        peak = next(float(t) * 12 for t, v in pairs if float(v) > 0)
        tail = parse(FILES["footer.svg"]).iter(f"{SVG}path")
        comet = [p for p in tail if p.get("pathLength")][0]
        tail_units = float(comet.get("stroke-dasharray").split()[0])
        land = (
            chrome.COMET_TRAVEL * chrome.WAVE_UNITS / (chrome.WAVE_UNITS + tail_units)
        )
        self.assertAlmostEqual(peak, land, delta=0.05)

    def test_the_route_follows_the_headers_including_none_and_many(self) -> None:
        for count in (0, 1, 2, 9, 14, 30):
            headers = [
                (f"k{i}", f"{i + 1:02d}", f"Title {i}", "sub") for i in range(count)
            ]
            for render in (chrome.render_footer, chrome.render_footer_phone):
                svg = render(context(headers=headers))
                root = parse(svg)
                width, _ = size(root)
                stops = [
                    c
                    for c in root.iter(f"{SVG}circle")
                    if c.get("fill") == kit.BLUE_LIGHT
                    and c.find(f"{SVG}animate") is not None
                ]
                labels = [t for t in texts(root) if t.get("text-anchor") == "middle"]
                with self.subTest(count=count, width=width):
                    self.assertEqual(len(stops), count)
                    # labels show only where they have room, and never touch
                    self.assertIn(len(labels), (0, count))
                    for a, b in zip(labels, labels[1:]):
                        self.assertLess(extent(a)[1] + 4, extent(b)[0])
                    moving = {
                        p for p in root.iter() if any(c.tag in ANIMATIONS for c in p)
                    }
                    if count <= 9:
                        self.assertLessEqual(len(moving), 16)

    def test_the_eyebrow_is_the_name_alone(self) -> None:
        """The hero shows the place and the stop labels count the sections: neither is said twice."""
        for render in (chrome.render_footer, chrome.render_footer_phone):
            svg = render(context(location="Springfield, Nowhere"))
            root = parse(svg)
            top = [content(t) for t in texts(root) if float(t.get("y")) < 40]
            with self.subTest(width=size(root)[0]):
                self.assertEqual(top, ["SAGAR GUPTA"])
                self.assertNotIn("SPRINGFIELD", svg.upper())
                self.assertNotIn("SECTIONS", svg)

    def test_an_empty_disclaimer_leaves_no_gap(self) -> None:
        full = parse(chrome.render_footer(context()))
        empty = parse(chrome.render_footer(context(disclaimer="")))
        self.assertLess(size(empty)[1], size(full)[1])
        self.assertTrue(empty.get("aria-label").endswith("sagargupta.online."))


if __name__ == "__main__":
    unittest.main()
