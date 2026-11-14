"""Checks for the community tool cards: files, bounds, motion, the preview motif by kind, and the row rules.

The shared checks run on the checked-in snapshot and assert rules, never values, so a
data refresh cannot fail them. Each rule of the layout has its own test on a small fixture.
"""

from __future__ import annotations

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
from cards import tools

SVG = "{http://www.w3.org/2000/svg}"
DATA = renderer.load_data()
CTX = renderer.build_context(DATA)
FILES = tools.render(DATA, CTX)
DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}
ANIMATIONS = {f"{SVG}animate", f"{SVG}animateTransform", f"{SVG}animateMotion"}
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


def name_of(entry: dict, phone: bool) -> str:
    return f"tool-{entry['slug']}{'-mobile' if phone else ''}.svg"


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314


def card(entry: dict, phone: bool = False) -> ET.Element:
    """Render one tool on its own and return the parsed desktop or phone card."""
    return parse(render([entry])[name_of(entry, phone)])


def size(root: ET.Element) -> tuple[float, float]:
    _, _, width, height = map(float, root.attrib["viewBox"].split())
    return width, height


def texts(root: ET.Element, cls: str = "") -> list[ET.Element]:
    return [t for t in root.iter(f"{SVG}text") if not cls or t.get("class") == cls]


def span(element: ET.Element) -> tuple[float, float]:
    """The left and right edge of a text element, measured the way kit measures."""
    font = float(element.attrib["font-size"])
    mono = element.get("class") in {"k", "m", "c"}
    # code (class c) is mono with no letter-spacing; the micro-labels are tracked
    tracking = 0 if element.get("class") == "c" else kit.TRACK
    width = kit.text_width(element.text or "", font, mono, tracking)
    if element.get("class") in {"k", "m"}:
        width -= kit.TRACK  # tracking sits between letters, not after the last
    x = float(element.attrib["x"])
    anchor = element.get("text-anchor")
    left = x - width / 2 if anchor == "middle" else x - width if anchor == "end" else x
    return left, left + width


def rects(root: ET.Element) -> list[dict]:
    out = []
    for rect in root.iter(f"{SVG}rect"):
        if "x" not in rect.attrib or "width" not in rect.attrib:
            continue
        x, y = float(rect.attrib["x"]), float(rect.attrib["y"])
        w, h = float(rect.attrib["width"]), float(rect.attrib["height"])
        out.append(
            {
                "x": x,
                "y": y,
                "right": x + w,
                "bottom": y + h,
                "rx": float(rect.get("rx", 0)),
                "h": h,
            }
        )
    return out


def chips(root: ET.Element, layout: tools.Layout) -> list[dict]:
    """Every pill under the strip as {x, y, right, bottom, text, fill}, left to right."""
    found, labels = [], texts(root, "m")
    for rect in rects(root):
        if (
            rect["y"] <= layout.cover
            or rect["h"] < 10
            or abs(rect["rx"] - rect["h"] / 2) > 0.01
        ):
            continue
        inside = [
            t
            for t in labels
            if rect["x"] <= float(t.attrib["x"]) <= rect["right"]
            and rect["y"] <= float(t.attrib["y"]) <= rect["bottom"]
        ]
        found.append(
            {
                **rect,
                "text": inside[0].text if inside else "",
                "fill": inside[0].get("fill") if inside else "",
            }
        )
    return sorted(found, key=lambda c: (c["y"], c["x"]))


def tech_row(root: ET.Element, layout: tools.Layout) -> list[dict]:
    title = layout.cover + layout.eyebrow + layout.title_gap
    return [c for c in chips(root, layout) if c["y"] > title]


def traction_row(root: ET.Element, layout: tools.Layout) -> list[dict]:
    title = layout.cover + layout.eyebrow + layout.title_gap
    return [c for c in chips(root, layout) if c["y"] < title]


def eyebrow_text(root: ET.Element, layout: tools.Layout) -> ET.Element:
    baseline = layout.cover + layout.eyebrow
    (found,) = [
        t
        for t in texts(root, "m")
        if abs(float(t.attrib["y"]) - baseline) < 0.01
        and t.get("fill") == kit.BLUE_LIGHT
    ]
    return found


def heights(files: dict[str, str], phone: bool) -> list[float]:
    return [
        size(parse(svg))[1]
        for name, svg in files.items()
        if name.endswith("-mobile.svg") == phone
    ]


def loops(root: ET.Element) -> list[ET.Element]:
    return [
        e
        for e in root.iter()
        if e.tag in ANIMATIONS and e.get("repeatCount") == "indefinite"
    ]


def motif_name(root: ET.Element) -> str:
    (group,) = [
        g for g in root.iter(f"{SVG}g") if (g.get("id") or "").startswith("motif-")
    ]
    return group.get("id").removeprefix("motif-")


def each_kind() -> list[tuple[str, str]]:
    return [(kind, name) for kind, (name, _) in tools.MOTIFS.items()]


class SnapshotTests(unittest.TestCase):
    """Rules every tool card keeps, on the data the page is built from."""

    def each(self):
        for name, svg in FILES.items():
            with self.subTest(file=name):
                yield name, svg, parse(svg), LAYOUTS[name.endswith("-mobile.svg")]

    def test_one_desktop_and_one_phone_file_per_tool(self):
        expected = {
            name_of(entry, phone) for entry in CTX["tools"] for phone in (False, True)
        }
        self.assertEqual(set(FILES), expected)
        self.assertTrue(CTX["tools"], "the snapshot lists no community tools")
        for name in FILES:
            self.assertTrue(renderer.CARD_FILE.fullmatch(name), name)

    def test_every_file_is_a_270px_card(self):
        # the README gives both sources width="270", so the phone twin is 270 wide too
        for _, _, root, _ in self.each():
            width, height = size(root)
            self.assertEqual(width, tools.WIDTH)
            self.assertEqual(float(root.attrib["width"]), tools.WIDTH)
            self.assertEqual(float(root.attrib["height"]), height)
            self.assertEqual(root.get("role"), "img")

    def test_no_text_or_chip_leaves_its_area(self):
        for _, _, root, layout in self.each():
            width, height = size(root)
            for element in texts(root):
                left, right = span(element)
                baseline, font = (
                    float(element.attrib["y"]),
                    float(element.attrib["font-size"]),
                )
                if baseline <= layout.cover:  # in the strip: inside the strip's padding
                    self.assertGreaterEqual(left, layout.pad - 0.01, element.text)
                    self.assertLessEqual(right, width - layout.pad + 0.01, element.text)
                    self.assertGreaterEqual(baseline - font * 0.75, 2, element.text)
                else:  # under it: inside the card's padding, above the bottom margin
                    self.assertGreaterEqual(left, layout.pad - 0.01, element.text)
                    self.assertLessEqual(right, width - layout.pad + 0.01, element.text)
                    self.assertLess(baseline, height - 8, element.text)
            for chip in chips(root, layout):
                self.assertGreaterEqual(chip["x"], layout.pad - 0.01)
                self.assertLessEqual(chip["right"], width - layout.pad + 0.01)
                self.assertLessEqual(chip["bottom"], height - layout.bottom + 0.01)

    def test_strip_labels_sit_inside_their_boxes(self):
        # a label in the preview never spills out of the box drawn around it
        for _, _, root, layout in self.each():
            boxes = [
                r
                for r in rects(root)
                if r["bottom"] <= layout.cover
                and r["right"] - r["x"] < tools.WIDTH - 20
            ]
            for element in texts(root):
                baseline = float(element.attrib["y"])
                if baseline > layout.cover:
                    continue
                left, right = span(element)
                middle = baseline - float(element.attrib["font-size"]) * 0.36
                for box in boxes:
                    if (
                        box["x"] < (left + right) / 2 < box["right"]
                        and box["y"] < middle < box["bottom"]
                    ):
                        self.assertGreaterEqual(left, box["x"] + 2, element.text)
                        self.assertLessEqual(right, box["right"] - 2, element.text)

    def test_no_dash_characters(self):
        for _, svg, _, _ in self.each():
            for dash in DASHES:
                self.assertNotIn(dash, svg)

    def test_hidden_at_rest_means_in_transit(self):
        """Anything that rests at opacity 0 is a packet or a highlight: it carries its own repeating fade."""
        for _, _, root, _ in self.each():
            for element in root.iter():
                if element.get("opacity") != "0":
                    continue
                fades = [
                    child
                    for child in element
                    if child.tag == f"{SVG}animate"
                    and child.get("attributeName") == "opacity"
                    and child.get("repeatCount") == "indefinite"
                ]
                self.assertTrue(fades, f"<{element.tag}> rests hidden with no loop")
                self.assertGreater(
                    max(map(float, fades[0].get("values").split(";"))), 0.5
                )

    def test_packets_rest_off_their_wire(self):
        # a travelling light starts each loop where it rests, so a still frame shows no stray dash
        for _, _, root, _ in self.each():
            for path in root.iter(f"{SVG}path"):
                if path.get("pathLength") != "100":
                    continue
                (motion,) = list(path)
                self.assertEqual(motion.get("attributeName"), "stroke-dashoffset")
                rest = float(path.get("stroke-dashoffset"))
                self.assertEqual(float(motion.get("values").split(";")[0]), rest)
                self.assertGreater(rest, float(path.get("stroke-dasharray").split()[0]))

    def test_the_text_under_the_strip_rests_visible(self):
        """The eyebrow, title, summary and chips enter with kit's poster-safe entrance and end at 1."""
        for _, _, root, layout in self.each():
            parents = {child: parent for parent in root.iter() for child in parent}
            for element in texts(root):
                if float(element.attrib["y"]) <= layout.cover:
                    continue
                node = element
                while node is not None:
                    self.assertIsNone(node.get("opacity"), element.text)
                    node = parents.get(node)
            for animation in root.iter(f"{SVG}animate"):
                if (
                    animation.get("repeatCount")
                    or animation.get("attributeName") != "opacity"
                ):
                    continue
                self.assertEqual(animation.get("fill"), "freeze")
                self.assertEqual(animation.get("values").split(";")[-1], "1")

    def test_text_keeps_the_size_floor(self):
        for name, _, root, _ in self.each():
            floor = kit.MICRO_PHONE if name.endswith("-mobile.svg") else kit.MICRO
            for element in texts(root):
                self.assertGreaterEqual(float(element.attrib["font-size"]), floor)

    def test_every_card_loops_on_the_page_clock(self):
        for _, _, root, _ in self.each():
            found = loops(root)
            self.assertTrue(found, "the card has no loop: the motion must stay visible")
            for animation in found:
                self.assertEqual(float(animation.get("dur").rstrip("s")), tools.LOOP)
                self.assertIn(tools.LOOP, CLOCK)

    def test_key_times_match_their_values(self):
        for _, _, root, _ in self.each():
            for animation in root.iter():
                if animation.tag not in ANIMATIONS or not animation.get("keyTimes"):
                    continue
                times = [float(value) for value in animation.get("keyTimes").split(";")]
                values = animation.get("values").split(";")
                self.assertEqual(len(times), len(values))
                self.assertEqual((times[0], times[-1]), (0.0, 1.0))
                self.assertEqual(times, sorted(times))

    def test_loops_close_where_they_open(self):
        """A fade or a move ends each loop on its first value; a travelling dash is periodic instead."""
        for _, _, root, _ in self.each():
            for animation in loops(root):
                if animation.get("attributeName") == "stroke-dashoffset":
                    continue
                values = animation.get("values").split(";")
                self.assertEqual(values[0], values[-1], animation.attrib)

    def test_motion_budget_and_weight(self):
        for _, svg, root, _ in self.each():
            animated = {
                id(parent)
                for parent in root.iter()
                for child in parent
                if child.tag in ANIMATIONS
            }
            self.assertLessEqual(len(animated), 14)
            self.assertLessEqual(len(svg.encode("utf-8")), 30_000)

    def test_files_are_self_contained(self):
        for _, svg, _, _ in self.each():
            for banned in (
                "href",
                "<image",
                "<script",
                "foreignObject",
                "@import",
                "prefers-reduced-motion",
            ):
                self.assertNotIn(banned, svg)
            ids = re.findall(r' id="([^"]+)"', svg)
            self.assertEqual(len(ids), len(set(ids)))
            for reference in re.findall(r"url\(#([^)]+)\)", svg):
                self.assertIn(reference, ids)

    def test_blue_family_only(self):
        # amber is for LeetCode and work in review, green for live or ok: neither is a star or a tick
        for _, svg, _, _ in self.each():
            self.assertNotIn(kit.AMBER, svg)
            self.assertNotIn(kit.GREEN, svg)

    def test_the_label_says_what_the_card_shows(self):
        for entry in CTX["tools"]:
            for phone in (False, True):
                label = parse(FILES[name_of(entry, phone)]).attrib["aria-label"]
                self.assertTrue(
                    label.startswith(f"{entry['title']}: {entry['summary']}")
                )
                self.assertEqual("stars." in label, entry["stars"] >= tools.STAR_FLOOR)
                self.assertEqual("npm downloads" in label, bool(entry["npm_monthly"]))

    def test_title_and_summary_are_drawn_whole(self):
        for entry in CTX["tools"]:
            for phone in (False, True):
                root = parse(FILES[name_of(entry, phone)])
                self.assertEqual(
                    " ".join(t.text for t in texts(root, "t")),
                    " ".join(entry["title"].split()),
                )
                self.assertEqual(
                    " ".join(t.text for t in texts(root, "b")),
                    " ".join(entry["summary"].split()),
                )

    def test_the_eyebrow_is_the_kind(self):
        for entry in CTX["tools"]:
            for phone, layout in LAYOUTS.items():
                shown = eyebrow_text(parse(FILES[name_of(entry, phone)]), layout).text
                kind = " ".join(entry["kind"].upper().split())
                if shown.endswith(
                    "..."
                ):  # cut to whole words only to clear the traction chips
                    self.assertTrue(kind.startswith(shown[:-3]), shown)
                else:
                    self.assertEqual(shown, kind)

    def test_the_motif_follows_the_kind(self):
        for entry in CTX["tools"]:
            expected = tools.MOTIFS.get(entry["kind"], tools.FALLBACK)[0]
            for phone in (False, True):
                self.assertEqual(
                    motif_name(parse(FILES[name_of(entry, phone)])), expected
                )

    def test_tech_chips_keep_their_order_three_at_most(self):
        for entry in CTX["tools"]:
            for phone, layout in LAYOUTS.items():
                shown = [
                    c["text"]
                    for c in tech_row(parse(FILES[name_of(entry, phone)]), layout)
                ]
                self.assertLessEqual(len(shown), tools.TECH_SHOWN)
                self.assertEqual(shown, [t for t in entry["tech"] if t in shown])
                if entry["tech"]:
                    self.assertTrue(shown, f"{entry['slug']} shows no tech chip")

    def test_rows_on_both_pages_share_one_height_and_one_chip_line(self):
        # the profile shows the leading top tools and COMMUNITY.md the whole list,
        # so their rows are the same runs only while the top tools come first
        tops = [entry["top"] for entry in CTX["tools"]]
        self.assertEqual(tops, sorted(tops, reverse=True))
        for phone, layout in LAYOUTS.items():
            entries = CTX["tools"]
            for start in range(0, len(entries), layout.row):
                with self.subTest(phone=phone, start=start):
                    roots = [
                        parse(FILES[name_of(e, phone)])
                        for e in entries[start : start + layout.row]
                    ]
                    self.assertEqual(len({size(r)[1] for r in roots}), 1)
                    self.assertLessEqual(
                        len({c["y"] for r in roots for c in tech_row(r, layout)}), 1
                    )
                    self.assertLessEqual(
                        len({c["y"] for r in roots for c in traction_row(r, layout)}), 1
                    )

    def test_no_dead_band(self):
        # every card ends one margin under its tech chips, and the run's lowest
        # summary line sits one fixed gap above them
        for phone, layout in LAYOUTS.items():
            entries = CTX["tools"]
            for _, run in tools.runs(entries, layout):
                lowest = max(tools.text_block(e, layout).last for e in run)
                for entry in run:
                    with self.subTest(phone=phone, slug=entry["slug"]):
                        root = parse(FILES[name_of(entry, phone)])
                        row = tech_row(root, layout)
                        if not row:
                            continue
                        self.assertAlmostEqual(
                            row[0]["y"] - lowest, layout.drop, places=1
                        )
                        self.assertLess(
                            size(root)[1] - row[0]["bottom"] - layout.bottom, 1
                        )


class RuleTests(unittest.TestCase):
    """The layout's rules on small fixtures, including empty and long inputs."""

    def test_star_chip_from_ten_stars(self):
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                quiet = card(tool(stars=tools.STAR_FLOOR - 1), phone)
                self.assertEqual(
                    [p for p in quiet.iter(f"{SVG}path") if p.get("fill") == kit.SKY],
                    [],
                )
                self.assertEqual(traction_row(quiet, layout), [])
                self.assertNotIn("stars.", quiet.attrib["aria-label"])

                starred = card(tool(stars=tools.STAR_FLOOR), phone)
                stars = [
                    p for p in starred.iter(f"{SVG}path") if p.get("fill") == kit.SKY
                ]
                self.assertEqual(len(stars), 1)
                (chip,) = traction_row(starred, layout)
                self.assertEqual(chip["text"], "10")
                self.assertEqual(chip["fill"], kit.SKY)
                self.assertTrue(starred.attrib["aria-label"].endswith(" 10 stars."))

    def test_star_count_is_exact(self):
        (chip,) = traction_row(card(tool(stars=1234)), tools.DESKTOP)
        self.assertEqual(chip["text"], "1,234")

    def test_npm_chip_shows_the_exact_monthly_count(self):
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                self.assertEqual(traction_row(card(tool(), phone), layout), [])
                root = card(tool(npm_monthly=1793), phone)
                (chip,) = traction_row(root, layout)
                # 1,793 and not 1.8K: a rounded figure would exceed the live one
                self.assertEqual(chip["text"], "1,793/MO NPM")
                self.assertTrue(
                    root.attrib["aria-label"].endswith(" 1,793 npm downloads a month.")
                )

    def test_traction_chips_end_the_eyebrow_row(self):
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                root = card(tool(stars=88, npm_monthly=2070), phone)
                star, npm = traction_row(root, layout)
                self.assertEqual([star["text"], npm["text"]], ["88", "2,070/MO NPM"])
                self.assertEqual(star["y"], npm["y"])
                self.assertAlmostEqual(npm["right"], tools.WIDTH - layout.pad, places=1)
                self.assertAlmostEqual(
                    npm["x"], star["right"] + tools.CHIP_GAP, places=1
                )
                # centred on the eyebrow's letters, clear of the strip above and the title below
                eyebrow = eyebrow_text(root, layout)
                middle = float(eyebrow.attrib["y"]) - layout.micro * 0.36
                self.assertAlmostEqual(
                    (star["y"] + star["bottom"]) / 2, middle, places=1
                )
                self.assertGreaterEqual(star["y"], layout.cover + 8)
                title = (
                    float(texts(root, "t")[0].attrib["y"]) - layout.title_size * 0.72
                )
                self.assertGreaterEqual(title - star["bottom"], 4)
                self.assertLessEqual(
                    span(eyebrow)[1], star["x"] - tools.KIND_GAP + 0.01
                )
                # one chip alone still ends at the margin
                (alone,) = traction_row(card(tool(npm_monthly=1793), phone), layout)
                self.assertAlmostEqual(
                    alone["right"], tools.WIDTH - layout.pad, places=1
                )

    def test_a_long_kind_gives_way_to_the_traction_chips(self):
        long = "Claude Code Plugin Marketplace Bundle"
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                root = card(tool(kind=long, stars=12345, npm_monthly=1793), phone)
                shown = eyebrow_text(root, layout).text
                self.assertTrue(shown.endswith("..."))
                self.assertTrue(long.upper().startswith(shown[:-3]))
                self.assertNotIn(" ...", shown)  # cut after a whole word
                star, _ = traction_row(root, layout)
                self.assertLessEqual(
                    span(eyebrow_text(root, layout))[1],
                    star["x"] - tools.KIND_GAP + 0.01,
                )
                # chips that leave no room for a single letter take the row alone
                crowded = card(tool(kind=long, stars=12345, npm_monthly=1234567), phone)
                for element in texts(crowded, "m"):
                    if (
                        abs(
                            float(element.attrib["y"]) - (layout.cover + layout.eyebrow)
                        )
                        < 0.01
                    ):
                        self.assertNotEqual(element.get("fill"), kit.BLUE_LIGHT)
                self.assertEqual(len(traction_row(crowded, layout)), 2)
                # with no chips beside it, a kind that fits is shown whole
                self.assertEqual(
                    eyebrow_text(card(tool(kind="mcp  server"), phone), layout).text,
                    "MCP SERVER",
                )

    def test_a_chip_that_does_not_fit_is_passed_over(self):
        long = ["Plugin Marketplace", "GitHub GraphQL API", "SVG", "YAML"]
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                shown = [
                    c["text"] for c in tech_row(card(tool(tech=long), phone), layout)
                ]
                self.assertEqual(
                    shown, ["Plugin Marketplace", "SVG", "YAML"][: len(shown)]
                )
                self.assertNotIn("GitHub GraphQL API", shown)
                many = [f"Tech{i}" for i in range(10)]
                self.assertEqual(
                    [c["text"] for c in tech_row(card(tool(tech=many), phone), layout)],
                    many[:3],
                )
                wide = ["A" * 60, "Go"]
                self.assertEqual(
                    [c["text"] for c in tech_row(card(tool(tech=wide), phone), layout)],
                    ["Go"],
                )
                # the pilot's fix: the stars live on the eyebrow row, so the tech row
                # has the full width whether or not a star is drawn (orrery kept SVG)
                trio = ["TypeScript", "ELK", "SVG"]
                for stars in (7, 88):
                    root = card(tool(stars=stars, tech=trio), phone)
                    self.assertEqual([c["text"] for c in tech_row(root, layout)], trio)

    def test_a_tall_card_sets_its_runs_height_and_no_other(self):
        """A run is the desktop grid of top tools, or a row of the rest, or a phone row."""
        long = " ".join(["Reads a long list of inputs and writes them out again."] * 4)
        plain = (
            heights(render(numbered(1)), False)[0],
            heights(render(numbered(1)), True)[0],
        )
        for index in (
            4,
            7,
        ):  # a top tool in the grid's second row, then one of the rest
            entries = numbered(6) + numbered(4, top=False)
            entries = [dict(e, slug=f"tool-{i}") for i, e in enumerate(entries)]
            entries[index] = dict(
                entries[index], slug="tall", summary=long, stars=88, title="Tall Tool"
            )
            files = render(entries)
            for phone, layout in LAYOUTS.items():
                with self.subTest(index=index, phone=phone):
                    tall = [size(parse(files[name_of(e, phone)]))[1] for e in entries]
                    (start, run), *_ = [
                        (s, r)
                        for s, r in tools.runs(entries, layout)
                        if entries[index] in r
                    ]
                    if not phone and index < 6:
                        self.assertEqual(len(run), 6)  # every top tool, three a row
                    else:
                        self.assertEqual(start, index - index % layout.row)
                    row = tall[start : start + len(run)]
                    self.assertEqual(len(set(row)), 1)
                    self.assertGreater(row[0], plain[phone])
                    rest = tall[:start] + tall[start + len(run) :]
                    self.assertEqual(set(rest), {plain[phone]})
                    # every card of the taller run ends on its tech chips, one margin above the edge
                    for entry in run:
                        root = parse(files[name_of(entry, phone)])
                        bottoms = {c["bottom"] for c in tech_row(root, layout)}
                        self.assertEqual(len(bottoms), 1)
                        self.assertLess(
                            size(root)[1] - bottoms.pop() - layout.bottom, 1
                        )

    def test_the_desktop_grid_of_top_tools_is_one_height(self):
        """The profile's three rows end level, and a top count short of a whole row
        takes the next tool into the grid's run, so COMMUNITY.md's mixed row matches."""
        long = " ".join(["Reads many inputs."] * 8)
        entries = numbered(8) + numbered(4, top=False)
        entries = [dict(e, slug=f"tool-{i}") for i, e in enumerate(entries)]
        entries[1] = dict(entries[1], summary=long)
        (first, grid), *rest = tools.runs(entries, tools.DESKTOP)
        self.assertEqual((first, len(grid)), (0, 9))
        self.assertEqual([len(run) for _, run in rest], [3])
        files = render(entries)
        self.assertEqual(
            len({size(parse(files[name_of(e, False)]))[1] for e in grid}), 1
        )
        self.assertEqual(
            len(
                {
                    c["y"]
                    for e in grid
                    for c in tech_row(parse(files[name_of(e, False)]), tools.DESKTOP)
                }
            ),
            1,
        )
        # the phone keeps its two-up rows
        self.assertEqual(
            [len(run) for _, run in tools.runs(entries, tools.PHONE)], [2] * 6
        )

    def test_a_short_card_beside_a_tall_one_only_takes_the_difference(self):
        short, long = "Draws one thing.", " ".join(["Reads many inputs."] * 8)
        entries = [
            tool(slug="a", title="A", summary=short, stars=50),
            tool(slug="b", title="B", summary=long, npm_monthly=2070),
            tool(slug="c", title="C", summary=short),
        ]
        files = render(entries)
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                blocks = {e["slug"]: tools.text_block(e, layout) for e in entries}
                tops = set()
                for entry in entries[
                    : layout.row
                ]:  # the first run: a, b and on desktop c
                    root = parse(files[name_of(entry, phone)])
                    (top,) = {c["y"] for c in tech_row(root, layout)}
                    tops.add(top)
                    self.assertAlmostEqual(
                        top, blocks["b"].last + layout.drop, places=1
                    )
                self.assertEqual(len(tops), 1)

    def test_a_tool_without_tech_or_traction_ends_under_its_text(self):
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                root = card(tool(tech=[], stars=0), phone)
                self.assertEqual(chips(root, layout), [])
                self.assertNotIn("Built with", root.attrib["aria-label"])
                last = max(float(t.attrib["y"]) for t in texts(root, "b"))
                self.assertLessEqual(
                    size(root)[1] - last, layout.bottom + layout.body_size
                )

    def test_empty_and_missing_inputs_still_draw(self):
        self.assertEqual(render([]), {})
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                root = card(
                    tool(summary="", kind="", tech=[], stars=None, npm_monthly=0), phone
                )
                self.assertEqual(motif_name(root), tools.FALLBACK[0])
                self.assertEqual(texts(root, "b"), [])
                self.assertEqual(chips(root, layout), [])
                self.assertGreater(size(root)[1], layout.cover)

    def test_a_long_single_token_stays_inside_the_card(self):
        for title in ("oss-contributions-card-action", "x" * 30):
            for phone, layout in LAYOUTS.items():
                with self.subTest(title=title, phone=phone):
                    root = card(
                        tool(title=title, summary=f"Wraps {title}/{title} safely."),
                        phone,
                    )
                    for element in texts(root):
                        left, right = span(element)
                        self.assertGreaterEqual(left, layout.pad - 0.01, element.text)
                        self.assertLessEqual(
                            right, tools.WIDTH - layout.pad + 0.01, element.text
                        )
                    # nothing is dropped: the pieces rejoin to the token
                    self.assertEqual("".join(t.text for t in texts(root, "t")), title)

    def test_a_long_token_breaks_after_a_separator(self):
        pieces = tools.wrap("oss-contributions-card-action", 150, 18)
        self.assertGreater(len(pieces), 1)
        self.assertEqual("".join(pieces), "oss-contributions-card-action")
        for piece in pieces[:-1]:
            self.assertTrue(piece.endswith("-"), pieces)

    def test_a_lone_last_word_takes_one_word_with_it(self):
        lines = tools.wrap(
            "one two three four five six seven eight nine ten elevens", 120, 13
        )
        self.assertIn(" ", lines[-1])
        for line in lines:
            self.assertLessEqual(kit.text_width(line, 13), 120)

    def test_every_kind_draws_its_motif(self):
        for kind, name in [*each_kind(), ("Something New", tools.FALLBACK[0])]:
            for phone in (False, True):
                with self.subTest(kind=kind, phone=phone):
                    root = card(tool(kind=kind), phone)
                    self.assertEqual(motif_name(root), name)
                    group = next(
                        g
                        for g in root.iter(f"{SVG}g")
                        if g.get("id") == f"motif-{name}"
                    )
                    self.assertTrue(loops(group), f"{name} has no loop")
                    animated = {
                        id(p) for p in group.iter() for c in p if c.tag in ANIMATIONS
                    }
                    self.assertLessEqual(len(animated), 12)

    def test_two_tools_of_one_kind_never_share_a_cover(self):
        """The run, the tool call, the slash command and the check list each carry the
        tool's own name, so a row of one kind never repeats a picture."""
        named = {"run", "call", "slash", "checks"}
        for kind, name in each_kind():
            if name not in named:
                continue
            entries = [
                tool(slug="acme-lint", kind=kind),
                tool(slug="acme-cost-optimizer", kind=kind),
            ]
            files = render(entries)
            for phone, layout in LAYOUTS.items():
                with self.subTest(kind=kind, phone=phone):
                    covers = []
                    for entry in entries:
                        root = parse(files[name_of(entry, phone)])
                        group = next(
                            g
                            for g in root.iter(f"{SVG}g")
                            if g.get("id") == f"motif-{name}"
                        )
                        words = "".join(t.text or "" for t in group.iter(f"{SVG}text"))
                        # a name broken over lines still reads whole, in order
                        self.assertIn(entry["slug"], words)
                        covers.append(
                            re.sub(r' begin="[^"]*"', "", ET.tostring(group, "unicode"))
                        )
                    self.assertNotEqual(*covers)

    def test_a_long_name_breaks_after_a_hyphen_or_is_cut_to_fit(self):
        lines = tools._name_lines("bedrock-multi-model-mcp", 90, kit.MICRO)
        self.assertEqual("".join(lines), "bedrock-multi-model-mcp")
        self.assertTrue(all(line.endswith("-") for line in lines[:-1]))
        self.assertTrue(all(tools._code(line, kit.MICRO) <= 90 for line in lines))
        for phone in (False, True):
            root = card(tool(slug="x" * 80, kind="Claude Code plugin"), phone)
            group = next(
                g for g in root.iter(f"{SVG}g") if g.get("id") == "motif-slash"
            )
            (command,) = [
                t
                for t in group.iter(f"{SVG}text")
                if t.get("class") == "c" and t.text != "/"
            ]
            self.assertTrue(command.text.endswith("..."))

    def test_each_motif_rests_on_its_finished_frame(self):
        # what the loop clears and rebuilds rests shown; only transit marks rest hidden
        for kind, name in each_kind():
            root = card(tool(kind=kind))
            group = next(
                g for g in root.iter(f"{SVG}g") if g.get("id") == f"motif-{name}"
            )
            for element in group.iter():
                fades = [
                    c
                    for c in element
                    if c.tag == f"{SVG}animate" and c.get("attributeName") == "opacity"
                ]
                for fade in fades:
                    values = [float(v) for v in fade.get("values").split(";")]
                    resting = float(element.get("opacity", 1))
                    self.assertEqual(values[0], resting, name)
                    if resting == 1:
                        self.assertEqual(values[-1], 1, name)

    def test_neighbours_take_turns(self):
        files = render(numbered(6))
        for phone, layout in LAYOUTS.items():
            with self.subTest(phone=phone):
                starts = []
                for entry in numbered(6)[: layout.row]:
                    begins = {
                        a.get("begin", "0s")
                        for a in loops(parse(files[name_of(entry, phone)]))
                    }
                    self.assertEqual(len(begins), 1)
                    starts.append(float(begins.pop().rstrip("s")))
                step = tools.LOOP / layout.row
                self.assertEqual(starts, [k * step for k in range(layout.row)])

    def test_text_is_escaped(self):
        entry = tool(
            title="R&D <kit>", summary='Reads "a & b" <c>.', tech=["C&C"], kind="A&B"
        )
        for phone, layout in LAYOUTS.items():
            root = card(entry, phone)
            self.assertEqual(root.attrib["aria-label"].split(":")[0], "R&D <kit>")
            self.assertEqual(texts(root, "t")[0].text, "R&D <kit>")
            self.assertEqual(tech_row(root, layout)[0]["text"], "C&C")
            self.assertEqual(eyebrow_text(root, layout).text, "A&B")

    def test_render_is_deterministic(self):
        self.assertEqual(tools.render(DATA, CTX), FILES)


if __name__ == "__main__":
    unittest.main()
