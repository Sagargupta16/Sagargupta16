"""Checks for the stack card: four lanes of tool tiles at both widths, lit one lane at a time.

The baseline renders the checked-in snapshot and asserts rules, never values,
so a refreshed icon cache cannot fail it. The layout rules each have a test
on crafted lanes: no glyphs, long names, many tools, long lane names, none.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405 - parses SVG this repo just rendered
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kit
from cards import stack

SPEC = importlib.util.spec_from_file_location("render_svgs", SCRIPTS / "render-svgs.py")
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)
renderer.OFFLINE = True

SVG = "{http://www.w3.org/2000/svg}"
LONG_DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}  # the loop lengths the page clock allows, in seconds
ANIMATIONS = (f"{SVG}animate", f"{SVG}animateTransform")
MONO = {"m": kit.TRACK, "k": 2.0, "c": 0.0, "g": 0.0}  # mono classes and their tracking
ICONS = json.loads((ROOT / "assets" / "svg" / "icons.json").read_text(encoding="utf-8"))


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314 - our own output


def size_of(svg: str) -> tuple[float, float]:
    _, _, width, height = map(float, parse(svg).attrib["viewBox"].split())
    return width, height


def lit_layers(root: ET.Element) -> list[ET.Element]:
    """The groups that rest hidden and light a lane: opacity 0 with a repeating fade."""
    return [
        group
        for group in root.iter(f"{SVG}g")
        if group.get("opacity") == "0"
        and any(child.get("repeatCount") == "indefinite" for child in group)
    ]


def spans(svg: str) -> list[dict]:
    """Every label with its box as kit measures it, reading size, class and anchor from its groups.

    A label under a static transform would not sit where its x and y say, so
    the walk refuses one.
    """
    root = parse(svg)
    lit = {id(element) for layer in lit_layers(root) for element in layer.iter()}
    out = []

    def walk(element: ET.Element, inherited: dict) -> None:
        if "transform" in element.attrib and element.tag != f"{SVG}rect":
            raise AssertionError(f"a static transform on <{element.tag}>")
        here = dict(inherited)
        for key in ("font-size", "class", "text-anchor", "fill"):
            if element.get(key):
                here[key] = element.get(key)
        if element.tag == f"{SVG}text":
            text, size = element.text or "", float(here["font-size"])
            cls = here.get("class", "b")
            mono = cls in MONO
            width = kit.text_width(text, size, mono, MONO.get(cls, 0))
            if mono and text:
                width -= MONO[cls]
            x, y = float(element.attrib["x"]), float(element.attrib["y"])
            anchor = here.get("text-anchor")
            left = (
                x - width / 2
                if anchor == "middle"
                else x - width
                if anchor == "end"
                else x
            )
            out.append(
                {
                    "text": text,
                    "left": left,
                    "right": left + width,
                    "top": y - size * 0.72,
                    "baseline": y,
                    "size": size,
                    "class": cls,
                    "fill": here.get("fill"),
                    "lit": id(element) in lit,
                    # a tile's parts take their class from their group; a lane number has its own
                    "grouped": element.get("class") is None,
                }
            )
        for child in element:
            walk(child, here)

    walk(root, {})
    return out


def rects(svg: str, fill: str, stroke: str) -> list[tuple[float, float, float, float]]:
    """(x, y, right, bottom) of every rect drawn in a group with this fill and stroke."""
    out = []
    for group in parse(svg).iter(f"{SVG}g"):
        if group.get("fill") != fill or group.get("stroke") != stroke:
            continue
        for rect in group.iter(f"{SVG}rect"):
            x, y = float(rect.get("x")), float(rect.get("y"))
            out.append(
                (x, y, x + float(rect.get("width")), y + float(rect.get("height")))
            )
    return out


def inside(span: dict, box: tuple, margin: float = 0) -> bool:
    x, y, right, bottom = box
    return (
        span["left"] >= x + margin - 0.01
        and span["right"] <= right - margin + 0.01
        and span["top"] >= y - 0.01
        and span["baseline"] <= bottom + 0.01
    )


def tile_names(svg: str) -> list[dict]:
    return [s for s in spans(svg) if s["class"] == "s" and not s["lit"]]


def monograms(svg: str) -> list[dict]:
    """The letters drawn at rest in place of a missing glyph."""
    return [
        s for s in spans(svg) if s["class"] == "g" and s["grouped"] and not s["lit"]
    ]


def timeline(animation: ET.Element) -> list[tuple[float, str]]:
    dur = float(animation.get("dur").rstrip("s"))
    times = [float(t) * dur for t in animation.get("keyTimes").split(";")]
    return list(zip(times, animation.get("values").split(";")))


def no_icons(slug: str) -> None:
    return None


LONG = " ".join(["An Extremely Long Tool Name That Could Never Fit One Tile"] * 3)


class OfflineCards(unittest.TestCase):
    """Both files from the checked-in snapshot."""

    @classmethod
    def setUpClass(cls) -> None:
        data = renderer.load_data()
        cls.ctx = renderer.build_context(data)
        cls.files = stack.render(data, cls.ctx)
        cls.again = stack.render(data, cls.ctx)

    def test_file_names(self) -> None:
        self.assertEqual(set(self.files), {"stack.svg", "stack-mobile.svg"})
        for name in self.files:
            self.assertRegex(name, renderer.CARD_FILE)
            self.assertNotIn(name, renderer.RESERVED_FILES)

    def test_ai_stack_is_a_lane_not_a_file(self) -> None:
        self.assertFalse(any(name.startswith("ai-stack") for name in self.files))
        self.assertIn("AI and agents", [lane for lane, _ in stack.LANES])

    def test_render_is_deterministic(self) -> None:
        self.assertEqual(self.files, self.again)

    def test_widths(self) -> None:
        self.assertEqual(size_of(self.files["stack.svg"])[0], 840)
        self.assertEqual(size_of(self.files["stack-mobile.svg"])[0], 320)

    def test_every_file_parses_and_is_labelled(self) -> None:
        for name, svg in self.files.items():
            root = parse(svg)
            self.assertEqual(root.tag, f"{SVG}svg", name)
            self.assertEqual(root.get("role"), "img", name)
            self.assertGreater(len(root.get("aria-label", "")), 20, name)

    def test_the_label_names_every_tool_in_words(self) -> None:
        """The alt text lists real names lane by lane, never a Simple Icons slug."""
        slugs = {slug for _, tools in stack.LANES for _, slug, _ in tools if slug}
        for name, svg in self.files.items():
            label = parse(svg).get("aria-label")
            for lane, tools in stack.LANES:
                self.assertIn(f"{lane}: ", label, name)
                for tool, _, full in tools:
                    self.assertIn(full or tool, label, name)
            for slug in slugs:
                if slug not in {
                    tool.lower() for _, tools in stack.LANES for tool, _, _ in tools
                }:
                    self.assertNotIn(slug, label, name)

    def test_curated_list(self) -> None:
        """Four lanes; the tools he does not use stay off the card."""
        self.assertEqual(
            [lane for lane, _ in stack.LANES],
            ["Cloud and IaC", "CI/CD and platform", "AI and agents", "Apps and data"],
        )
        names = {tool for _, tools in stack.LANES for tool, _, _ in tools}
        self.assertEqual(len(names), sum(len(tools) for _, tools in stack.LANES))
        for dropped in (
            "Unity",
            "R",
            "C#",
            "Java",
            "Figma",
            "Postman",
            "Redux",
            "Material UI",
            "Jenkins",
            "GitLab",
            "Kubernetes",
            "ChatGPT",
            "Gemini",
        ):
            self.assertNotIn(dropped, names)
        for _, tools in stack.LANES:
            for _, slug, _ in tools:
                if slug:
                    self.assertIn(slug, renderer.ICON_SLUGS, slug)

    def test_eyebrow_counts_the_lanes(self) -> None:
        total = sum(len(tools) for _, tools in stack.LANES)
        for name, svg in self.files.items():
            shown = [s["text"] for s in spans(svg)]
            self.assertIn(f"{total} TOOLS IN {len(stack.LANES)} LANES", shown, name)

    def test_desktop_shows_every_tool(self) -> None:
        shown = [s["text"] for s in tile_names(self.files["stack.svg"])]
        self.assertEqual(
            shown, [tool for _, tools in stack.LANES for tool, _, _ in tools]
        )

    def test_phone_caps_each_lane_and_counts_the_rest(self) -> None:
        svg = self.files["stack-mobile.svg"]
        shown = [s["text"] for s in tile_names(svg)]
        counts = [
            int(s["text"][1:])
            for s in spans(svg)
            if re.fullmatch(r"\+\d+", s["text"]) and not s["lit"]
        ]
        expected, more = [], []
        for _, tools in stack.LANES:
            rows, hidden = stack.arrange(
                list(tools), self.phone_room(), stack.Layout(True), stack.PHONE_ROWS
            )
            self.assertLessEqual(len(rows), stack.PHONE_ROWS)
            kept = [tile["name"] for row in rows for tile in row if not tile["more"]]
            self.assertEqual(kept, [tool for tool, _, _ in tools][: len(kept)])
            self.assertEqual(len(kept) + hidden, len(tools))
            expected += kept
            if hidden:
                more.append(hidden)
        self.assertEqual(shown, expected)
        self.assertEqual(counts, more)

    @staticmethod
    def phone_room() -> float:
        size = stack.Layout(True)
        return size.w - size.pad - size.inset - (size.pad + size.inset)

    def test_no_text_leaves_the_canvas(self) -> None:
        for name, svg in self.files.items():
            width, height = size_of(svg)
            for span in spans(svg):
                self.assertGreaterEqual(span["left"], 0, f"{name}: {span['text']!r}")
                self.assertLessEqual(span["right"], width, f"{name}: {span['text']!r}")
                self.assertGreaterEqual(span["top"], 0, f"{name}: {span['text']!r}")
                self.assertLessEqual(
                    span["baseline"], height, f"{name}: {span['text']!r}"
                )

    def test_text_floor(self) -> None:
        for name, svg in self.files.items():
            floor = kit.MICRO_PHONE if name.endswith("-mobile.svg") else kit.MICRO
            for span in spans(svg):
                self.assertGreaterEqual(
                    span["size"], floor, f"{name}: {span['text']!r}"
                )

    def test_names_sit_inside_their_tiles(self) -> None:
        for name, svg in self.files.items():
            tiles = rects(svg, kit.BG, kit.HAIR_STRONG)
            for span in tile_names(svg):
                self.assertTrue(
                    any(inside(span, tile, 4) for tile in tiles),
                    f"{name}: {span['text']!r} is not inside a tile",
                )

    def test_monograms_sit_inside_their_boxes(self) -> None:
        for name, svg in self.files.items():
            boxes = rects(svg, "none", stack.ICON)
            letters = monograms(svg)
            self.assertTrue(letters, name)
            self.assertEqual(len(letters), len(boxes), name)
            for span in letters:
                self.assertTrue(
                    any(inside(span, box, 1) for box in boxes),
                    f"{name}: {span['text']!r}",
                )

    def test_tiles_keep_inside_their_lane(self) -> None:
        for name, svg in self.files.items():
            panels = rects_of_panels(svg)
            for tile in rects(svg, kit.BG, kit.HAIR_STRONG):
                self.assertTrue(
                    any(
                        tile[0] >= p[0] + 4
                        and tile[2] <= p[2] - 4
                        and tile[1] >= p[1] + 4
                        and tile[3] <= p[3] - 4
                        for p in panels
                    ),
                    f"{name}: tile {tile} leaves its lane",
                )

    def test_lane_labels_sit_left_of_the_tiles_on_the_desktop(self) -> None:
        svg = self.files["stack.svg"]
        first_tile = min(tile[0] for tile in rects(svg, kit.BG, kit.HAIR_STRONG))
        panels = rects_of_panels(svg)
        lanes = {lane.upper() for lane, _ in stack.LANES}
        words = {word for lane in lanes for word in lane.split()}
        labels = [
            s
            for s in spans(svg)
            if s["class"] == "m" and set(s["text"].split()) <= words and s["text"]
        ]
        self.assertTrue(labels)
        for span in labels:
            self.assertLessEqual(span["right"], first_tile - 8, span["text"])
            self.assertTrue(any(inside(span, p, 4) for p in panels), span["text"])

    def test_one_glyph_per_tool_drawn_once(self) -> None:
        """Each glyph's path is defined once and placed with <use>; a tool with no glyph gets a monogram."""
        for name, svg in self.files.items():
            root = parse(svg)
            defined = {
                path.get("id") for path in root.iter(f"{SVG}path") if path.get("id")
            }
            uses = [use.get("href") for use in root.iter(f"{SVG}use")]
            self.assertTrue(uses, name)
            for href in uses:
                self.assertTrue(href.startswith("#"), name)
                self.assertIn(href[1:], defined, name)
            slugs = {
                slug
                for _, tools in stack.LANES
                for _, slug, _ in tools
                if slug and self.ctx["icon"](slug)
            }
            self.assertEqual(len(defined), len(slugs), name)

    def test_no_long_dash_no_green_no_amber(self) -> None:
        for name, svg in self.files.items():
            for dash in LONG_DASHES:
                self.assertNotIn(dash, svg, name)
            self.assertNotIn(kit.AMBER, svg, name)
            self.assertNotIn(kit.GREEN, svg, name)

    def test_self_contained(self) -> None:
        for name, svg in self.files.items():
            for banned in (
                "<script",
                "<foreignObject",
                "<image",
                "@import",
                "prefers-reduced-motion",
                "url(http",
            ):
                self.assertNotIn(banned, svg, f"{name}: {banned}")
            for href in re.findall(r'href="([^"]*)"', svg):
                self.assertTrue(href.startswith("#"), f"{name}: {href}")

    def test_ids_are_unique(self) -> None:
        for name, svg in self.files.items():
            ids = re.findall(r' id="([^"]+)"', svg)
            self.assertEqual(len(ids), len(set(ids)), name)
            for reference in re.findall(r"url\(#([^)]+)\)", svg):
                self.assertIn(reference, ids, name)

    def test_weight_and_motion_budget(self) -> None:
        """Glyphs as paths, not raster: well under the validator's 50 KB warning line."""
        for name, svg in self.files.items():
            self.assertLess(len(svg.encode("utf-8")), 48_000, name)
            animated = {
                id(parent)
                for parent in parse(svg).iter()
                for child in parent
                if child.tag in ANIMATIONS
            }
            self.assertLessEqual(len(animated), 40, name)

    def test_hidden_at_rest_means_lit_in_turn(self) -> None:
        """Anything at opacity 0 is a lane's lit layer: it carries its own repeating fade up to full."""
        for name, svg in self.files.items():
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
                self.assertTrue(
                    fades, f"{name}: <{element.tag}> rests hidden with no loop"
                )
                self.assertEqual(
                    max(float(v) for v in fades[0].get("values").split(";")), 1.0, name
                )

    def test_the_poster_shows_everything_a_lit_layer_shows(self) -> None:
        """A lit layer only recolours: each of its labels repeats one drawn at rest in the same place."""
        for name, svg in self.files.items():
            rest = {
                (s["text"], round(s["left"], 1), s["baseline"])
                for s in spans(svg)
                if not s["lit"]
            }
            for span in spans(svg):
                if span["lit"]:
                    self.assertIn(
                        (span["text"], round(span["left"], 1), span["baseline"]),
                        rest,
                        name,
                    )

    def test_entrances_are_poster_safe(self) -> None:
        """Content enters with kit's held entrance: no opacity attribute at rest, and it ends at 1."""
        for name, svg in self.files.items():
            root = parse(svg)
            parents = {child: parent for parent in root.iter() for child in parent}
            lit = {
                id(element) for layer in lit_layers(root) for element in layer.iter()
            }
            for element in root.iter(f"{SVG}text"):
                if id(element) in lit:
                    continue
                node = element
                while node is not None:
                    self.assertIsNone(node.get("opacity"), f"{name}: {element.text!r}")
                    node = parents.get(node)
            for animation in root.iter(f"{SVG}animate"):
                if animation.get("repeatCount"):
                    continue
                self.assertEqual(animation.get("fill"), "freeze", name)
                if animation.get("attributeName") == "opacity":
                    self.assertEqual(animation.get("values").split(";")[-1], "1", name)

    def test_loops_run_on_the_page_clock(self) -> None:
        for name, svg in self.files.items():
            for animation in parse(svg).iter():
                if (
                    animation.tag in ANIMATIONS
                    and animation.get("repeatCount") == "indefinite"
                ):
                    self.assertIn(float(animation.get("dur").rstrip("s")), CLOCK, name)

    def test_key_times_match_their_values(self) -> None:
        for name, svg in self.files.items():
            for animation in parse(svg).iter():
                if animation.tag not in ANIMATIONS or not animation.get("keyTimes"):
                    continue
                times = [float(value) for value in animation.get("keyTimes").split(";")]
                self.assertEqual(
                    len(times), len(animation.get("values").split(";")), name
                )
                self.assertEqual((times[0], times[-1]), (0.0, 1.0), name)
                self.assertEqual(times, sorted(times), name)

    def test_loops_close_where_they_open(self) -> None:
        """A fade or a move ends each loop on its first value; the rail's dash is periodic instead."""
        for name, svg in self.files.items():
            for animation in parse(svg).iter():
                if (
                    animation.tag not in ANIMATIONS
                    or animation.get("repeatCount") != "indefinite"
                ):
                    continue
                if animation.get("attributeName") == "stroke-dashoffset":
                    continue
                values = animation.get("values").split(";")
                self.assertEqual(values[0], values[-1], f"{name}: {animation.attrib}")

    def test_lanes_light_in_turn(self) -> None:
        """Each lane is lit in its own slot of the 12 s loop, in order, and never two at once."""
        for name, svg in self.files.items():
            windows = []
            for layer in lit_layers(parse(svg)):
                fade = next(
                    child for child in layer if child.get("attributeName") == "opacity"
                )
                lit = [t for t, v in timeline(fade) if float(v) == 1]
                windows.append((min(lit), max(lit)))
            self.assertEqual(len(windows), len(stack.LANES), name)
            slot = kit.T / len(windows)
            for index, (start, end) in enumerate(windows):
                self.assertGreaterEqual(start, index * slot, name)
                self.assertLessEqual(end, (index + 1) * slot, name)
                self.assertGreater(end - start, slot / 2, name)

    def test_each_sweep_runs_left_to_right(self) -> None:
        for name, svg in self.files.items():
            root = parse(svg)
            clips = {
                clip.get("id"): clip
                for clip in root.iter(f"{SVG}clipPath")
                if clip.get("id", "").startswith("sweep")
            }
            self.assertEqual(len(clips), len(stack.LANES), name)
            for clip in clips.values():
                move = next(clip.iter(f"{SVG}animateTransform"))
                xs = [float(value.split()[0]) for _, value in timeline(move)]
                self.assertLess(xs[0], 0, name)
                self.assertEqual(max(xs), 0, name)
                peak = xs.index(0)
                self.assertEqual(xs[: peak + 1], sorted(xs[: peak + 1]), name)

    def test_the_rail_only_runs_down(self) -> None:
        """On the desktop the line reaches each lane as it lights: its dash offset only ever falls."""
        root = parse(self.files["stack.svg"])
        rails = [
            animation
            for animation in root.iter(f"{SVG}animate")
            if animation.get("attributeName") == "stroke-dashoffset"
            and animation.get("repeatCount")
        ]
        self.assertEqual(len(rails), 1)
        offsets = [float(value) for _, value in timeline(rails[0])]
        self.assertEqual(offsets, sorted(offsets, reverse=True))
        self.assertEqual((offsets[0], offsets[-1]), (1.0, -1.0))
        phone = parse(self.files["stack-mobile.svg"])
        self.assertFalse(
            [
                a
                for a in phone.iter(f"{SVG}animate")
                if a.get("attributeName") == "stroke-dashoffset"
                and a.get("repeatCount")
            ]
        )


def rects_of_panels(svg: str) -> list[tuple[float, float, float, float]]:
    """The lane panels: the rects with the panels' corner radius."""
    out = []
    for rect in parse(svg).iter(f"{SVG}rect"):
        if rect.get("rx") == "10" and rect.get("fill") == kit.CARD:
            x, y = float(rect.get("x")), float(rect.get("y"))
            out.append(
                (x, y, x + float(rect.get("width")), y + float(rect.get("height")))
            )
    return out


class CraftedLanes(unittest.TestCase):
    """The layout and the motion on inputs the snapshot does not have."""

    def test_render_reads_only_the_icon_callable(self) -> None:
        files = stack.render({}, {"icon": no_icons})
        self.assertEqual(set(files), {"stack.svg", "stack-mobile.svg"})
        self.assertEqual(stack.render({}, {}), files)

    def test_a_tool_with_no_glyph_gets_a_monogram(self) -> None:
        total = sum(len(tools) for _, tools in stack.LANES)
        for svg in stack.render({}, {"icon": no_icons}).values():
            root = parse(svg)
            self.assertFalse(list(root.iter(f"{SVG}use")))
            letters = monograms(svg)
            names = tile_names(svg)
            self.assertEqual(len(letters), len(names))
            self.assertLessEqual(len(names), total)
            for letter, name in zip(letters, names):
                self.assertEqual(letter["text"], stack.monogram(name["text"]))

    def test_monogram(self) -> None:
        self.assertEqual(stack.monogram("SageMaker"), "SM")
        self.assertEqual(stack.monogram("Amazon Q"), "AQ")
        self.assertEqual(stack.monogram("Kiro"), "K")
        self.assertEqual(stack.monogram("C++"), "C")
        self.assertEqual(stack.monogram("next.js"), "NJ")
        self.assertEqual(stack.monogram(""), "?")

    def test_long_names_and_many_tools_stay_in_their_tiles(self) -> None:
        tools = [(f"Tool {k}", None, None) for k in range(30)] + [
            (LONG, "terraform", None)
        ]
        lanes = [("Cloud and IaC", tools), ("AI and agents", [("Kiro", None, None)])]
        for phone in (False, True):
            svg = stack._card(lanes, ICONS.get, phone)
            width, height = size_of(svg)
            tiles = rects(svg, kit.BG, kit.HAIR_STRONG)
            for tile in tiles:
                self.assertGreaterEqual(tile[0], 0)
                self.assertLessEqual(tile[2], width)
                self.assertLessEqual(tile[3], height)
            for span in tile_names(svg):
                self.assertTrue(
                    any(inside(span, tile, 4) for tile in tiles), span["text"]
                )
            for span in spans(svg):
                self.assertLessEqual(span["right"], width, span["text"])
            shown = [s["text"] for s in tile_names(svg)]
            if phone:
                more = [
                    s["text"]
                    for s in spans(svg)
                    if re.fullmatch(r"\+\d+", s["text"]) and not s["lit"]
                ]
                self.assertEqual(len(more), 1)
                self.assertEqual(
                    len([n for n in shown if n.startswith("Tool")]) + int(more[0][1:]),
                    31,
                )
            else:
                cut = [name for name in shown if name.endswith("...")]
                self.assertEqual(len(cut), 1)
                self.assertTrue(LONG.startswith(cut[0][:-3]))
                self.assertEqual(len(shown), 32)

    def test_a_long_lane_name_wraps_inside_its_lane(self) -> None:
        name = "Observability, incident response and every on-call runbook"
        lanes = [
            (name, [("Linux", "linux", None)]),
            ("Apps and data", [("Go", "go", None)]),
        ]
        for phone in (False, True):
            svg = stack._card(lanes, ICONS.get, phone)
            panels = rects_of_panels(svg)
            words = set(name.upper().split())
            lines = [
                s
                for s in spans(svg)
                if s["class"] == "m" and s["text"] and set(s["text"].split()) <= words
            ]
            self.assertGreater(len(lines), 1)
            self.assertEqual(" ".join(s["text"] for s in lines), name.upper())
            for span in lines:
                self.assertTrue(any(inside(span, p, 4) for p in panels), span["text"])
            if not phone:
                first_tile = min(
                    tile[0] for tile in rects(svg, kit.BG, kit.HAIR_STRONG)
                )
                for span in lines:
                    self.assertLessEqual(span["right"], first_tile, span["text"])

    def test_rows_are_balanced_flush_and_in_order(self) -> None:
        size = stack.Layout(False)
        tools = [tool for _, lane in stack.LANES for tool in lane]
        for room in (300, 420, 640):
            rows, hidden = stack.arrange(tools, room, size)
            self.assertEqual(hidden, 0)
            self.assertEqual(
                [t["name"] for row in rows for t in row], [name for name, _, _ in tools]
            )
            for row in rows:
                right = row[-1]["x"] + row[-1]["w"]
                self.assertLessEqual(right, room + 0.01)
                if (
                    right < room - 0.01
                ):  # short of flush only when every tile is at its stretch limit
                    for tile in row:
                        natural = size.tile_width(tile["name"])
                        self.assertAlmostEqual(
                            tile["w"], natural * stack.STRETCH, delta=0.01
                        )

    def test_a_sparse_row_does_not_stretch_without_limit(self) -> None:
        size = stack.Layout(False)
        rows, _ = stack.arrange([("Go", "go", None)], 600, size)
        self.assertLessEqual(
            rows[0][0]["w"], size.tile_width("Go") * stack.STRETCH + 0.01
        )

    def test_no_lanes_still_draws_a_card(self) -> None:
        for phone in (False, True):
            svg = stack._card([("Empty", [])], ICONS.get, phone)
            root = parse(svg)
            self.assertIn("0 tools in 0 lanes", root.get("aria-label"))
            self.assertFalse(list(root.iter(f"{SVG}clipPath"))[1:])
            self.assertFalse(lit_layers(root))

    def test_one_lane_and_eight_lanes_keep_the_clock(self) -> None:
        for count in (1, 8):
            lanes = [
                (f"Lane {k}", [("Docker", "docker", None), ("Bash", None, None)])
                for k in range(count)
            ]
            for phone in (False, True):
                svg = stack._card(lanes, ICONS.get, phone)
                root = parse(svg)
                self.assertEqual(len(lit_layers(root)), count)
                for animation in root.iter():
                    if animation.tag not in ANIMATIONS or not animation.get("keyTimes"):
                        continue
                    times = [float(t) for t in animation.get("keyTimes").split(";")]
                    self.assertEqual(times, sorted(times))
                    self.assertEqual(
                        len(times), len(animation.get("values").split(";"))
                    )
                    if animation.get("repeatCount"):
                        self.assertIn(float(animation.get("dur").rstrip("s")), CLOCK)
                rails = [
                    a
                    for a in root.iter(f"{SVG}animate")
                    if a.get("attributeName") == "stroke-dashoffset"
                    and a.get("repeatCount")
                ]
                self.assertEqual(len(rails), 1 if count > 1 and not phone else 0)

    def test_names_are_escaped(self) -> None:
        svg = stack._card(
            [("R&D <lab>", [("A&B <c>", None, "A&B <c> full")])], no_icons, False
        )
        root = parse(svg)
        self.assertIn("A&B <c> full", root.get("aria-label"))
        self.assertIn("A&B <c>", [s["text"] for s in tile_names(svg)])


class TightPaths(unittest.TestCase):
    """The glyph minifier keeps every point within half a tenth of where it was."""

    @staticmethod
    def segments(d: str, scale: float = 1.0) -> list[tuple[str, list[float]]]:
        """Absolute segments, H and V written as L, every length scaled; an arc's angle and flags kept."""
        out, x, y = [], 0.0, 0.0
        for command, a in stack.absolute(d):
            if command == "H":
                command, a = "L", [a[0], y / scale]
            elif command == "V":
                command, a = "L", [x / scale, a[0]]
            if command == "A":
                numbers = [
                    a[0] * scale,
                    a[1] * scale,
                    *a[2:5],
                    a[5] * scale,
                    a[6] * scale,
                ]
            else:
                numbers = [value * scale for value in a]
            out.append((command, numbers))
            if command == "Z":
                x, y = next(n for c, n in reversed(out) if c == "M")[:2]
            elif numbers:
                x, y = numbers[-2], numbers[-1]
        return out

    def check(self, d: str, scale: float = 1.0) -> None:
        before = self.segments(d, scale)
        after = self.segments(stack.tight(d, scale))
        self.assertEqual([c for c, _ in before], [c for c, _ in after])
        for (command, a), (_, b) in zip(before, after):
            self.assertEqual(len(a), len(b), command)
            for k, (want, got) in enumerate(zip(a, b)):
                self.assertAlmostEqual(want, got, delta=0.051, msg=f"{command} {k}")

    def test_every_lane_glyph(self) -> None:
        for _, tools in stack.LANES:
            for _, slug, _ in tools:
                if slug:
                    with self.subTest(slug=slug):
                        self.check(ICONS[slug], 16 / 24)
                        self.assertLess(
                            len(stack.tight(ICONS[slug], 16 / 24)), len(ICONS[slug])
                        )

    def test_compact_arcs_implicit_repeats_and_closed_subpaths(self) -> None:
        self.check(
            "M1 1a1 1 0 01.5.5l1 1 2 2h3v-2zm2 2c1 1 2 2 3 3s1 1 2 2q1 1 2 2t1 1Z"
        )
        self.check("M0 0L10.25 0 10.25 10.75 0 10.75z", 2 / 3)
        self.check("m5 5 1 1 1 1z m-1-1h2", 0.5)


if __name__ == "__main__":
    unittest.main()
