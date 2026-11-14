"""Checks for cards/samples.py: the three aws-samples diagram cards, desktop and phone.

Built on the checked-in snapshot through the same loader preview.py uses, so the
cards under test are the ones the README gets, plus crafted samples for the
parts that come from ctx (title, date, tags). The rule checks run on both, and
the diagram checks on the crafted three, so a portfolio that drops or renames a
sample cannot break them. The checks assert rules, never the snapshot's values.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405 - parses SVG this repo just rendered
from itertools import pairwise
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kit
from cards import samples

SPEC = importlib.util.spec_from_file_location("render_svgs", SCRIPTS / "render-svgs.py")
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)
renderer.OFFLINE = True
DATA = renderer.load_data()
CTX = renderer.build_context(DATA)
FILES = samples.render(DATA, CTX)

SVG = "{http://www.w3.org/2000/svg}"
KEYS = ("agentcore-harness", "org-governance", "sagemaker-mlops")
LEAD = "agentcore-harness"
PAIR = ("org-governance", "sagemaker-mlops")
ANIMATIONS = (f"{SVG}animate", f"{SVG}animateTransform", f"{SVG}animateMotion")
CLOCK = {2, 3, 4, 6, 12, 24}
# the titles the old renderer typed in; two of them had drifted from the portfolio
TYPED_TITLES = (
    "AgentCore Harness with Governed MCP Tools",
    "AWS Organizations Governance",
)
DASHES = (
    chr(0x2013),
    chr(0x2014),
)  # en and em dash, by code point so this file has neither
LONG = "A Title Long Enough That It Has To Wrap Onto A Second Line Of The Card"
# wider than the lead card's 792px column at its 20px title size
LONGER = f"{LONG} Even On The Full Width Lead Card At The Top Of The Section"
# where green (an ok state) and amber (work waiting on a person) may appear
GREEN_NODES = {"gateway", "release-eval", "release-prod", "gate", "approve", "serve"}
AMBER_NODES = {"approve"}
# plan.md rule 14, typed here so a change to kit cannot lower them unseen
FLOOR_DESKTOP, FLOOR_PHONE = 10.5, 11.5


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314 - our own output


def size_of(root: ET.Element) -> tuple[float, float]:
    _, _, width, height = map(float, root.attrib["viewBox"].split())
    return width, height


def phone(name: str) -> bool:
    return name.endswith("-mobile.svg")


def with_samples(rows: list[dict]) -> dict[str, str]:
    return samples.render(DATA, {**CTX, "samples": rows})


def sample(
    key: str, title: str = "Short", tags=None, date: str = "January 2026"
) -> dict:
    return {
        "key": key,
        "title": title,
        "url": "https://github.com/aws-samples/example",
        "date": date,
        "tags": ["TERRAFORM"] if tags is None else tags,
    }


# every diagram, whatever the snapshot holds today
DRAWN = with_samples([sample(key) for key in KEYS])
# what the rule checks run on: the README's cards and the crafted three
CARDS = [*FILES.items(), *DRAWN.items()]


def parents_of(root: ET.Element) -> dict:
    return {child: parent for parent in root.iter() for child in parent}


def ancestors(element: ET.Element, parents: dict):
    while element in parents:
        element = parents[element]
        yield element


def shown_at_rest(element: ET.Element, parents: dict) -> bool:
    """True when nothing from the element up holds opacity 0: a still render shows it."""
    return all(e.get("opacity") != "0" for e in (element, *ancestors(element, parents)))


# ---------------------------------------------------------------- geometry
def static_offset(element: ET.Element, parents: dict) -> tuple[float, float]:
    """The sum of the plain translate() transforms above an element."""
    dx = dy = 0.0
    for e in (element, *ancestors(element, parents)):
        transform = e.get("transform", "")
        if transform.startswith("translate(") and "scale" not in transform:
            x, y = (float(n) for n in transform[10:-1].replace(",", " ").split())
            dx, dy = dx + x, dy + y
    return dx, dy


def entrance_offsets(element: ET.Element, parents: dict) -> list[tuple[float, float]]:
    """Every extra shift an entrance can give an element on its way in."""
    shifts = [(0.0, 0.0)]
    for e in (element, *ancestors(element, parents)):
        for move in e.findall(f"{SVG}animateTransform"):
            if move.get("type") == "translate":
                for value in move.attrib["values"].split(";"):
                    x, y = (float(n) for n in value.split())
                    shifts.append((x, y))
    return shifts


def text_content(element: ET.Element) -> str:
    return "".join(element.itertext())


def text_box(element: ET.Element) -> tuple[float, float, float, float]:
    """A text's box (left, top, right, bottom) before transforms, measured the way kit measures."""
    size = float(element.attrib["font-size"])
    content = text_content(element)
    cls = element.get("class", "")
    if cls == "m":
        width = kit.text_width(content, size, True, kit.TRACK) - kit.TRACK
    elif cls == "c":
        width = kit.text_width(content, size, True)
    else:
        width = kit.text_width(content, size)
    x, y = float(element.attrib["x"]), float(element.attrib["y"])
    anchor = element.get("text-anchor")
    left = x - width / 2 if anchor == "middle" else x - width if anchor == "end" else x
    return left, y - 0.75 * size, left + width, y + 0.2 * size


def placed(box, offset) -> tuple[float, float, float, float]:
    dx, dy = offset
    return box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy


def rect_box(element: ET.Element) -> tuple[float, float, float, float]:
    x, y = float(element.get("x", 0)), float(element.get("y", 0))
    return x, y, x + float(element.attrib["width"]), y + float(element.attrib["height"])


def overlap(a, b) -> bool:
    """True when two boxes share some area (touching edges do not count)."""
    return (
        min(a[2], b[2]) - max(a[0], b[0]) > 0.01
        and min(a[3], b[3]) - max(a[1], b[1]) > 0.01
    )


def inside(inner, outer, margin: float = 0) -> bool:
    return (
        inner[0] >= outer[0] + margin - 0.01
        and inner[1] >= outer[1] + margin - 0.01
        and inner[2] <= outer[2] - margin + 0.01
        and inner[3] <= outer[3] - margin + 0.01
    )


def nodes(root: ET.Element) -> dict[str, ET.Element]:
    return {g.get("data-node"): g for g in root.iter(f"{SVG}g") if g.get("data-node")}


def tile(node: ET.Element) -> tuple[float, float, float, float]:
    return rect_box(node.find(f"{SVG}rect"))


def windows(root: ET.Element, key: str) -> list[tuple[float, float, float, float]]:
    (clip,) = [c for c in root.iter(f"{SVG}clipPath") if c.get("id") == f"wires-{key}"]
    return [rect_box(r) for r in clip]


def key_of(name: str) -> str:
    return name.removeprefix("sample-").removesuffix(".svg").removesuffix("-mobile")


def packets(root: ET.Element) -> list[ET.Element]:
    return [
        c
        for c in root.iter(f"{SVG}circle")
        if c.find(f"{SVG}animateMotion") is not None
    ]


def points_of(path: str) -> list[tuple[float, float]]:
    """The corners of a straight-run path, M x y L x y ..."""
    return [
        tuple(float(n) for n in part.split()) for part in path.lstrip("M").split("L")
    ]


def route_of(packet: ET.Element) -> list[tuple[float, float]]:
    return points_of(packet.find(f"{SVG}animateMotion").attrib["path"])


def wires(root: ET.Element) -> list[list[tuple[float, float]]]:
    return [
        points_of(p.attrib["d"])
        for p in root.iter(f"{SVG}path")
        if p.get("stroke") == samples.WIRE
    ]


def holds(box, point) -> bool:
    """True when a point lies in a box (left, top, right, bottom), its edge included."""
    x, y = point
    return box[0] - 0.01 <= x <= box[2] + 0.01 and box[1] - 0.01 <= y <= box[3] + 0.01


def on_edge(point, box) -> bool:
    x, y = point
    return (
        holds(box, point)
        and min(abs(x - box[0]), abs(x - box[2]), abs(y - box[1]), abs(y - box[3]))
        < 0.01
    )


def track(values: list[float], times: list[float], t: float) -> float:
    """A linear animation's value at share t of its loop."""
    for (t0, v0), (t1, v1) in pairwise(zip(times, values)):
        if t0 <= t <= t1:
            return v0 if t1 == t0 else v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return values[-1]


def position(route: list[tuple[float, float]], share: float) -> tuple[float, float]:
    lengths = [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in pairwise(route)]
    goal, run = share * sum(lengths), 0.0
    for (a, b), length in zip(pairwise(route), lengths):
        if run + length >= goal - 1e-9:
            k = 0 if length == 0 else (goal - run) / length
            return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
        run += length
    return route[-1]


def numbers(text: str) -> list[float]:
    return [float(v) for v in text.split(";")]


# ---------------------------------------------------------------- files
class FileTests(unittest.TestCase):
    def test_every_sample_has_a_desktop_and_a_phone_file(self) -> None:
        expected = {
            f"sample-{row['key']}{suffix}.svg"
            for row in CTX["samples"]
            if row["key"] in samples.DIAGRAMS
            for suffix in ("", "-mobile")
        }
        self.assertEqual(set(FILES), expected)

    def test_a_sample_without_a_diagram_is_left_out(self) -> None:
        self.assertEqual(
            with_samples([sample("not-drawn-yet", "Some Other Sample")]), {}
        )
        self.assertEqual(with_samples([]), {})
        self.assertEqual(
            samples.render(DATA, {k: v for k, v in CTX.items() if k != "samples"}), {}
        )

    def test_widths_and_heights(self) -> None:
        files = with_samples([sample(key) for key in KEYS])
        for name, svg in files.items():
            root = parse(svg)
            width, height = size_of(root)
            with self.subTest(name):
                if phone(name):
                    self.assertEqual(width, samples.PHONE)
                    self.assertLess(height, 520)
                elif key_of(name) == LEAD:
                    self.assertEqual(width, samples.WIDE)
                    self.assertTrue(260 <= height <= 340, height)
                else:
                    self.assertEqual(width, samples.HALF)
                self.assertEqual(root.get("width"), f"{width:g}")
                self.assertEqual(root.get("height"), f"{height:g}")

    def test_the_label_is_a_sentence_about_the_sample(self) -> None:
        for name, svg in FILES.items():
            root = parse(svg)
            title = next(
                row["title"] for row in CTX["samples"] if row["key"] == key_of(name)
            )
            label = root.get("aria-label", "")
            with self.subTest(name):
                self.assertEqual(root.get("role"), "img")
                self.assertTrue(label.startswith(title))
                self.assertIn("published as a solution under aws-samples", label)
                self.assertNotIn("published by AWS", label)
                self.assertGreater(len(label), 120)

    def test_render_is_deterministic(self) -> None:
        self.assertEqual(samples.render(DATA, CTX), FILES)


# ---------------------------------------------------------------- house rules
class HouseRuleTests(unittest.TestCase):
    def test_no_en_or_em_dash(self) -> None:
        for name, svg in CARDS:
            for dash in DASHES:
                with self.subTest(name):
                    self.assertNotIn(dash, svg)
        source = (SCRIPTS / "cards" / "samples.py").read_text(encoding="utf-8")
        for dash in DASHES:
            self.assertNotIn(dash, source)

    def test_self_contained_and_flat(self) -> None:
        for name, svg in CARDS:
            with self.subTest(name):
                for banned in (
                    "<script",
                    "<foreignObject",
                    "href=",
                    "<image",
                    "@import",
                    "Gradient",
                    "<filter",
                    "blur",
                ):
                    self.assertNotIn(banned, svg)

    def test_no_text_leaves_the_canvas(self) -> None:
        for name, svg in CARDS:
            root = parse(svg)
            width, height = size_of(root)
            parents = parents_of(root)
            for element in root.iter(f"{SVG}text"):
                box = placed(text_box(element), static_offset(element, parents))
                for shift in entrance_offsets(element, parents):
                    left, top, right, bottom = placed(box, shift)
                    with self.subTest(name, text=text_content(element), shift=shift):
                        self.assertGreaterEqual(left, 0)
                        self.assertLessEqual(right, width)
                        self.assertGreaterEqual(top, 0)
                        self.assertLessEqual(bottom, height)

    def test_text_stays_above_the_floor(self) -> None:
        """Phone labels at 11.5px show at about 11px on a 309px column, above the 10.4px the brief asks."""
        for name, svg in CARDS:
            floor = FLOOR_PHONE if phone(name) else FLOOR_DESKTOP
            for element in parse(svg).iter(f"{SVG}text"):
                with self.subTest(name, text=text_content(element)):
                    self.assertGreaterEqual(float(element.attrib["font-size"]), floor)

    def test_hidden_marks_are_loop_states_not_entrances(self) -> None:
        """opacity="0" is allowed only on a mark its own repeating loop brings back."""
        for name, svg in CARDS:
            for element in parse(svg).iter():
                if element.get("opacity") != "0":
                    continue
                loops = [
                    child
                    for child in element.findall(f"{SVG}animate")
                    if child.get("attributeName") == "opacity"
                ]
                with self.subTest(name, tag=element.tag):
                    self.assertEqual(len(loops), 1)
                    self.assertEqual(loops[0].get("repeatCount"), "indefinite")
                    self.assertIsNone(loops[0].get("begin"))
                    self.assertIn(1.0, numbers(loops[0].attrib["values"]))

    def test_loops_keep_the_page_clock(self) -> None:
        for name, svg in CARDS:
            for element in parse(svg).iter():
                if (
                    element.tag not in ANIMATIONS
                    or element.get("repeatCount") != "indefinite"
                ):
                    continue
                with self.subTest(name, tag=element.tag):
                    self.assertIn(float(element.attrib["dur"].rstrip("s")), CLOCK)
                    self.assertIsNone(element.get("begin"))
                    if element.get("keyTimes"):
                        times = numbers(element.attrib["keyTimes"])
                        self.assertEqual((times[0], times[-1]), (0, 1))
                        self.assertEqual(times, sorted(times))

    def test_loops_open_and_close_on_the_rest_frame(self) -> None:
        """A browser at 0 s and at every seam shows what a still render shows.

        A mark of the finished state opens and closes its loop shown, a mark
        in transit opens and closes it hidden. The live dot's widening ring is
        the one pulse that does neither.
        """
        for name, svg in CARDS:
            for element in parse(svg).iter():
                fades = [
                    a
                    for a in element.findall(f"{SVG}animate")
                    if a.get("attributeName") == "opacity"
                    and a.get("repeatCount") == "indefinite"
                ]
                pulse = any(
                    a.get("attributeName") == "r"
                    for a in element.findall(f"{SVG}animate")
                )
                if not fades or pulse:
                    continue
                values = numbers(fades[0].attrib["values"])
                rest = 0.0 if element.get("opacity") == "0" else 1.0
                with self.subTest(name, tag=element.tag, values=values):
                    self.assertEqual((values[0], values[-1]), (rest, rest))

    def test_entrances_are_poster_safe(self) -> None:
        """Every animation that runs once holds its start value until its turn and freezes on the rest value."""
        for name, svg in CARDS:
            for element in parse(svg).iter():
                if (
                    element.tag not in ANIMATIONS
                    or element.get("repeatCount") == "indefinite"
                ):
                    continue
                values = element.attrib["values"].split(";")
                with self.subTest(name, tag=element.tag, values=values):
                    self.assertEqual(element.get("fill"), "freeze")
                    self.assertEqual(values[0], values[1])
                    self.assertIn(values[-1], ("1", "0 0", "0"))

    def test_green_and_amber_mean_one_thing(self) -> None:
        for name, svg in CARDS:
            root = parse(svg)
            parents = parents_of(root)
            for element in root.iter():
                colours = {element.get("fill"), element.get("stroke")}
                for colour, allowed in (
                    (kit.GREEN, GREEN_NODES),
                    (kit.AMBER, AMBER_NODES),
                ):
                    if colour not in colours:
                        continue
                    node = next(
                        (
                            a.get("data-node")
                            for a in ancestors(element, parents)
                            if a.get("data-node")
                        ),
                        None,
                    )
                    with self.subTest(name, colour=colour, node=node):
                        self.assertIn(node, allowed)
            if key_of(name) != "sagemaker-mlops":
                self.assertNotIn(kit.AMBER, svg)


# ---------------------------------------------------------------- packets
class PacketTests(unittest.TestCase):
    """Packets ride the wires, clipped to windows that never reach a label or a tile."""

    def files(self):
        for name, svg in CARDS:
            root = parse(svg)
            yield name, root, windows(root, key_of(name))

    def test_every_packet_is_clipped_to_the_wires(self) -> None:
        for name, root, found in self.files():
            parents = parents_of(root)
            moving = packets(root)
            with self.subTest(name):
                self.assertGreaterEqual(len(moving), 2)
                self.assertTrue(found)
                for packet in moving:
                    clips = [a.get("clip-path") for a in ancestors(packet, parents)]
                    self.assertIn(f"url(#wires-{key_of(name)})", clips)
                    self.assertEqual(packet.get("opacity"), "0")

    def test_no_window_reaches_a_label(self) -> None:
        for name, root, found in self.files():
            parents = parents_of(root)
            for element in root.iter(f"{SVG}text"):
                box = placed(text_box(element), static_offset(element, parents))
                for window in found:
                    with self.subTest(name, text=text_content(element), window=window):
                        self.assertFalse(overlap(box, window))

    def test_no_window_reaches_into_a_tile(self) -> None:
        """So a packet is seen leaving one tile and arriving at the next, never over one."""
        for name, root, found in self.files():
            for key, node in nodes(root).items():
                for window in found:
                    with self.subTest(name, node=key, window=window):
                        self.assertFalse(overlap(tile(node), window))

    def test_routes_are_straight_runs(self) -> None:
        for name, root, _ in self.files():
            for packet in packets(root):
                for a, b in pairwise(route_of(packet)):
                    with self.subTest(name, segment=(a, b)):
                        self.assertTrue(a[0] == b[0] or a[1] == b[1])

    def test_every_packet_is_seen_on_a_wire(self) -> None:
        """Walk the loop: each packet shows through some window while it is visible."""
        for name, root, found in self.files():
            for packet in packets(root):
                motion = packet.find(f"{SVG}animateMotion")
                fade = packet.find(f"{SVG}animate")
                route = route_of(packet)
                radius = float(packet.attrib["r"])
                seen = False
                for step in range(1201):
                    t = step / 1200
                    if (
                        track(
                            numbers(fade.attrib["values"]),
                            numbers(fade.attrib["keyTimes"]),
                            t,
                        )
                        <= 0
                    ):
                        continue
                    share = track(
                        numbers(motion.attrib["keyPoints"]),
                        numbers(motion.attrib["keyTimes"]),
                        t,
                    )
                    x, y = position(route, share)
                    circle = (x - radius, y - radius, x + radius, y + radius)
                    seen = seen or any(overlap(circle, window) for window in found)
                with self.subTest(name, route=route):
                    self.assertTrue(seen)


# ---------------------------------------------------------------- tiles and their labels
class TileTests(unittest.TestCase):
    def test_labels_sit_inside_their_tiles(self) -> None:
        for name, svg in CARDS:
            root = parse(svg)
            parents = parents_of(root)
            for key, node in nodes(root).items():
                for element in node.iter(f"{SVG}text"):
                    box = placed(text_box(element), static_offset(element, parents))
                    with self.subTest(name, node=key, text=text_content(element)):
                        self.assertTrue(inside(box, tile(node), 2))

    def test_labels_in_a_tile_do_not_collide(self) -> None:
        """Two texts may share space only as two states of one mark, set at the same anchor."""
        for name, svg in CARDS:
            root = parse(svg)
            for key, node in nodes(root).items():
                texts = {
                    (e.get("x"), e.get("y"), text_content(e)): text_box(e)
                    for e in node.iter(f"{SVG}text")
                }
                for (a, box_a), (b, box_b) in (
                    (p, q)
                    for i, p in enumerate(texts.items())
                    for q in list(texts.items())[i + 1 :]
                ):
                    if a[:2] == b[:2]:
                        continue
                    with self.subTest(name, node=key, texts=(a[2], b[2])):
                        self.assertFalse(overlap(box_a, box_b))

    def test_marks_in_a_tile_keep_clear_of_its_labels(self) -> None:
        """A rect or ring either holds a label whole (a chip) or keeps off it (pips, bars, glyphs)."""
        for name, svg in CARDS:
            root = parse(svg)
            parents = parents_of(root)
            for key, node in nodes(root).items():
                labels = [
                    (text_content(e), placed(text_box(e), static_offset(e, parents)))
                    for e in node.iter(f"{SVG}text")
                ]
                shapes = []
                for e in node.iter(f"{SVG}rect"):
                    shapes.append(placed(rect_box(e), static_offset(e, parents)))
                for e in node.iter(f"{SVG}circle"):
                    if e.get("cx") is None:
                        continue
                    cx, cy, r = (float(e.get(k)) for k in ("cx", "cy", "r"))
                    shapes.append((cx - r, cy - r, cx + r, cy + r))
                for shape in shapes:
                    for text, box in labels:
                        if inside(box, shape):
                            continue
                        with self.subTest(name, node=key, text=text, shape=shape):
                            self.assertFalse(overlap(box, shape))

    def test_a_beat_tints_the_tile_under_its_labels(self) -> None:
        """A tile's lit overlay is painted before its labels, so no beat veils a name."""
        for name, svg in CARDS:
            for key, node in nodes(parse(svg)).items():
                box = tile(node)
                order = list(node)
                lit = [
                    i
                    for i, child in enumerate(order)
                    if child.get("opacity") == "0"
                    and any(
                        r.get("fill") == kit.BLUE_TINT and rect_box(r) == box
                        for r in child.findall(f"{SVG}rect")
                    )
                ]
                texts = [
                    i
                    for i, child in enumerate(order)
                    if child.tag == f"{SVG}text"
                    or child.find(f".//{SVG}text") is not None
                ]
                if not lit:
                    continue
                with self.subTest(name, node=key):
                    self.assertLess(max(lit), min(texts))


# ---------------------------------------------------------------- what each diagram says
class DiagramTests(unittest.TestCase):
    """On the crafted three (DRAWN), so these hold whichever samples the portfolio lists."""

    def texts(self, name: str, at_rest: bool = False) -> set[str]:
        root = parse(DRAWN[name])
        parents = parents_of(root)
        return {
            text_content(e)
            for e in root.iter(f"{SVG}text")
            if not at_rest or shown_at_rest(e, parents)
        }

    def both(self, key: str):
        for suffix in ("", "-mobile"):
            yield f"sample-{key}{suffix}.svg"

    def test_agentcore_draws_both_lanes(self) -> None:
        for name in self.both(LEAD):
            texts = self.texts(name)
            with self.subTest(name):
                for label in (
                    *samples._CLIENTS,
                    "GATEWAY",
                    "9 TOOLS",
                    "HARNESS",
                    *samples._HARNESS,
                    samples._TOOL,
                    *(stage for stage, _ in samples._RELEASE),
                ):
                    self.assertIn(label, texts)
                lanes = {t.split()[0]: t for t in texts if "  |  " in t}
                self.assertTrue({"REQUEST", "RELEASE"} <= set(lanes))
                # the clients column is what makes the calls MCP calls
                self.assertIn("MCP", lanes["REQUEST"])

    def test_agentcore_poster_shows_the_call_allowed(self) -> None:
        """At rest the gateway reads ALLOW over CEDAR POLICY; DENY and what was asked exist only in their beat."""
        for name in self.both(LEAD):
            root = parse(DRAWN[name])
            parents = parents_of(root)
            gateway = nodes(root)["gateway"]
            words = {
                text_content(e): shown_at_rest(e, parents)
                for e in gateway.iter(f"{SVG}text")
            }

            def beat(word: str) -> tuple[str, str]:
                (text,) = [
                    e for e in gateway.iter(f"{SVG}text") if text_content(e) == word
                ]
                fade = parents[text].find(f"{SVG}animate")
                return fade.attrib["values"], fade.attrib["keyTimes"]

            with self.subTest(name):
                self.assertTrue(words["ALLOW"])
                self.assertTrue(words["CEDAR POLICY"])
                self.assertFalse(words["DENY"])
                self.assertFalse(words[samples._UNLISTED])
                # the caption says what was refused exactly while DENY shows
                self.assertEqual(beat(samples._UNLISTED), beat("DENY"))
        self.assertIn("PASS", self.texts(f"sample-{LEAD}.svg", at_rest=True))

    def test_agentcore_gateway_captions_swap_in_sequence(self) -> None:
        """CEDAR POLICY and the refused tool share one line, so they take turns: one is
        fully gone before the other starts to show, on the way in and on the way back."""

        def curve(fade: ET.Element) -> list[tuple[float, float]]:
            values = [float(v) for v in fade.attrib["values"].split(";")]
            times = [float(t) for t in fade.attrib["keyTimes"].split(";")]
            return list(zip(times, values))

        def at(points: list[tuple[float, float]], t: float) -> float:
            for (t0, v0), (t1, v1) in zip(points, points[1:]):
                if t0 <= t <= t1:
                    return v0 if t1 == t0 else v0 + (v1 - v0) * (t - t0) / (t1 - t0)
            return points[-1][1]

        for name in self.both(LEAD):
            root = parse(DRAWN[name])
            parents = parents_of(root)
            gateway = nodes(root)["gateway"]
            fades = {
                text_content(e): curve(parents[e].find(f"{SVG}animate"))
                for e in gateway.iter(f"{SVG}text")
                if text_content(e) in ("CEDAR POLICY", samples._UNLISTED)
            }
            policy, refused = fades["CEDAR POLICY"], fades[samples._UNLISTED]
            with self.subTest(name):
                self.assertTrue(any(v == 0 for _, v in policy))
                self.assertTrue(any(v == 1 for _, v in refused))
                for step in range(1201):
                    t = step / 1200
                    self.assertEqual(min(at(policy, t), at(refused, t)), 0, t)

    def test_agentcore_both_calls_leave_one_client(self) -> None:
        """The policy refuses a tool, not a client: the refused and the allowed call start in one client, the one that lights."""
        for name in self.both(LEAD):
            root = parse(DRAWN[name])
            found = nodes(root)
            clients = {k: tile(n) for k, n in found.items() if k.startswith("client-")}
            starts = [
                key
                for packet in packets(root)
                for key, box in clients.items()
                if holds(box, route_of(packet)[0])
            ]
            lit = {
                key
                for key in clients
                if any(g.get("opacity") == "0" for g in found[key].iter(f"{SVG}g"))
            }
            with self.subTest(name):
                self.assertEqual(len(clients), len(samples._CLIENTS))
                self.assertEqual(len(starts), 2)
                self.assertEqual(set(starts), lit)
                self.assertEqual(len(lit), 1)
        label = parse(DRAWN[f"sample-{LEAD}.svg"]).get("aria-label", "")
        self.assertIn("tool it does not list", label)

    def test_agentcore_draws_nine_tools(self) -> None:
        for name in self.both(LEAD):
            tools = nodes(parse(DRAWN[name]))["tools"]
            pips = [
                g
                for g in tools.iter(f"{SVG}g")
                if g.get("transform", "").startswith("translate")
            ]
            with self.subTest(name):
                self.assertEqual(len(pips[0].findall(f"{SVG}rect")), 9)
                self.assertEqual(len(pips[1].findall(f"{SVG}rect")), 1)

    def test_org_tree_names_every_ou(self) -> None:
        for name in self.both("org-governance"):
            with self.subTest(name):
                self.assertTrue(set(samples._OUS.values()) <= self.texts(name))

    def test_org_poster_shows_the_policies_where_they_attach(self) -> None:
        """SCP and RCP attached to Workloads, inherited (dashed) below it, delegated admin on Security."""
        for name in self.both("org-governance"):
            root = parse(DRAWN[name])
            parents = parents_of(root)
            found = nodes(root)
            for key in (*samples._OUS, "mgmt"):
                chips = {}
                for rect in found[key].iter(f"{SVG}rect"):
                    label = next(
                        (
                            text_content(e)
                            for e in parents[rect]
                            if e.tag == f"{SVG}text"
                        ),
                        None,
                    )
                    if (
                        label
                        and shown_at_rest(rect, parents)
                        and rect is not found[key][0]
                    ):
                        chips[label] = rect.get("stroke-dasharray") is not None
                with self.subTest(name, node=key):
                    if key == "workloads":
                        self.assertEqual(chips, {"SCP": False, "RCP": False})
                    elif key in ("production", "non-production"):
                        self.assertEqual(chips, {"SCP": True, "RCP": True})
                    elif key == "security":
                        self.assertEqual(chips, {samples._ADMIN: False})
                    else:
                        self.assertEqual(chips, {})

    def test_org_governance_leaves_the_management_account(self) -> None:
        """The sample runs in the management account: it sits on a wire to ROOT, and every trip through ROOT starts in it."""
        for name in self.both("org-governance"):
            root = parse(DRAWN[name])
            found = nodes(root)
            mgmt, top = tile(found["mgmt"]), tile(found["root"])
            trips = [route_of(p) for p in packets(root)]
            through_root = [r for r in trips if any(holds(top, p) for p in r)]
            ends = {
                key
                for r in through_root
                for key in samples._OUS
                if key != "root" and holds(tile(found[key]), r[-1])
            }
            with self.subTest(name):
                self.assertEqual(
                    [text_content(e) for e in found["mgmt"].iter(f"{SVG}text")],
                    [samples._MGMT],
                )
                self.assertTrue(
                    any(
                        on_edge(w[0], mgmt) and on_edge(w[-1], top) for w in wires(root)
                    )
                )
                # the two policies and the delegation, each from the management account
                self.assertEqual(len(through_root), len(samples._POLICIES) + 1)
                for route in through_root:
                    self.assertTrue(holds(mgmt, route[0]))
                self.assertEqual(ends, {"workloads", "security"})
                self.assertIn("management account", root.get("aria-label", ""))

    def test_mlops_draws_the_loop_with_its_approval(self) -> None:
        for name in self.both("sagemaker-mlops"):
            root = parse(DRAWN[name])
            found = nodes(root)
            with self.subTest(name):
                self.assertEqual(
                    set(found),
                    {"data", "train", "gate", "approve", "deploy", "serve", "monitor"},
                )
                self.assertIn(samples._DRIFT, self.texts(name))
                # the dashed wire is the retrain path: it ends on TRAIN's bottom edge
                dashed = [
                    p
                    for p in root.iter(f"{SVG}path")
                    if p.get("stroke-dasharray") == "4 4"
                    and p.get("d", "").startswith("M")
                ]
                self.assertEqual(len(dashed), 1)
                end = tuple(
                    float(n) for n in dashed[0].attrib["d"].split("L")[-1].split()
                )
                x, y, w, h = (
                    float(found["train"][0].get(k))
                    for k in ("x", "y", "width", "height")
                )
                self.assertEqual(end, (x + w / 2, y + h))
                # amber is the waiting state only: hidden at rest, the poster shows the approval
                parents = parents_of(root)
                for element in found["approve"].iter():
                    if kit.AMBER in (element.get("stroke"), element.get("fill")):
                        self.assertFalse(shown_at_rest(element, parents))


# ---------------------------------------------------------------- the foot: what comes from ctx
class FootTests(unittest.TestCase):
    def titles(self, svg: str) -> list[ET.Element]:
        return [e for e in parse(svg).iter(f"{SVG}text") if e.get("class") == "t"]

    def foot_texts(self, name: str, svg: str) -> list[ET.Element]:
        cover = samples.DIAGRAMS[key_of(name)][4 if phone(name) else 3]
        return [
            e for e in parse(svg).iter(f"{SVG}text") if float(e.attrib["y"]) > cover
        ]

    def test_each_card_shows_its_portfolio_title(self) -> None:
        for row in CTX["samples"]:
            if row["key"] not in samples.DIAGRAMS:
                continue  # a sample with no diagram yet draws no card
            for suffix in ("", "-mobile"):
                name = f"sample-{row['key']}{suffix}.svg"
                with self.subTest(name):
                    shown = " ".join(text_content(e) for e in self.titles(FILES[name]))
                    self.assertEqual(shown, row["title"])

    def test_a_changed_title_reaches_both_layouts(self) -> None:
        files = with_samples([sample("org-governance", "Landing Zone Guardrails")])
        self.assertEqual(len(files), 2)
        for name, svg in files.items():
            with self.subTest(name):
                self.assertIn("Landing Zone Guardrails", svg)
                for typed in TYPED_TITLES:
                    self.assertNotIn(f">{typed}<", svg)

    def test_a_title_is_escaped(self) -> None:
        files = with_samples([sample("sagemaker-mlops", "Train & Deploy <fast>")])
        for name, svg in files.items():
            with self.subTest(name):
                self.assertIn("Train &amp; Deploy &lt;fast&gt;", svg)
                parse(svg)

    def test_the_eyebrow_carries_the_source_and_the_month(self) -> None:
        for date, expected in (
            ("October 2026", "AWS-SAMPLES  |  OCT 2026"),
            ("", "AWS-SAMPLES"),
            ("Q3 2026", "AWS-SAMPLES  |  Q3 2026"),
        ):
            files = with_samples([sample(key, date=date) for key in KEYS])
            for name, svg in files.items():
                eyebrows = [
                    text_content(e)
                    for e in self.foot_texts(name, svg)
                    if text_content(e).startswith("AWS-")
                ]
                with self.subTest(name, date=date):
                    self.assertEqual(eyebrows, [expected])

    def test_tags_come_from_ctx_in_order(self) -> None:
        files = with_samples(
            [sample(key, tags=["Terraform", "Step Functions"]) for key in KEYS]
        )
        for name, svg in files.items():
            chips = [
                text_content(e)
                for e in self.foot_texts(name, svg)
                if e.get("class") == "m" and e.get("text-anchor") == "middle"
            ]
            with self.subTest(name):
                self.assertEqual(chips, ["TERRAFORM", "STEP FUNCTIONS"])

    def test_no_tags_draw_no_chips(self) -> None:
        tagged = with_samples([sample(LEAD)])
        bare = with_samples([sample(LEAD, tags=[])])
        for name in bare:
            with self.subTest(name):
                chips = [
                    e
                    for e in self.foot_texts(name, bare[name])
                    if e.get("text-anchor") == "middle"
                ]
                self.assertEqual(chips, [])
                if phone(name):
                    self.assertLess(
                        size_of(parse(bare[name]))[1], size_of(parse(tagged[name]))[1]
                    )

    def test_many_tags_end_in_a_count_inside_the_margins(self) -> None:
        tags = [f"TAG NUMBER {i}" for i in range(12)]
        files = with_samples([sample(key, tags=tags) for key in KEYS])
        for name, svg in files.items():
            width = size_of(parse(svg))[0]
            margin = 16 if phone(name) else 24
            chips = [
                e
                for e in self.foot_texts(name, svg)
                if e.get("text-anchor") == "middle"
            ]
            labels = [text_content(e) for e in chips]
            with self.subTest(name):
                self.assertTrue(labels[-1].startswith("+"))
                self.assertEqual(int(labels[-1][1:]), len(tags) - len(labels) + 1)
                self.assertEqual(labels[:-1], tags[: len(labels) - 1])
                for e in chips:
                    self.assertLessEqual(text_box(e)[2], width - margin)

    def test_a_long_title_wraps_inside_the_margins(self) -> None:
        files = {
            **with_samples([sample(key, LONG) for key in KEYS]),
            f"sample-{LEAD}.svg": with_samples([sample(LEAD, LONGER)])[
                f"sample-{LEAD}.svg"
            ],
        }
        for name, svg in files.items():
            width = size_of(parse(svg))[0]
            margin = 16 if phone(name) else 24
            lines = self.titles(svg)
            title = LONGER if name == f"sample-{LEAD}.svg" else LONG
            with self.subTest(name):
                self.assertGreater(len(lines), 1)
                self.assertEqual(" ".join(text_content(e) for e in lines), title)
                for e in lines:
                    left, _, right, _ = text_box(e)
                    self.assertEqual(left, margin)
                    self.assertLessEqual(right, width - margin)

    def test_a_very_long_title_is_cut_at_three_lines(self) -> None:
        title = " ".join([LONG] * 4)
        for name, svg in with_samples([sample(key, title) for key in PAIR]).items():
            lines = [text_content(e) for e in self.titles(svg)]
            with self.subTest(name):
                self.assertEqual(len(lines), samples.TITLE_ROWS)
                self.assertTrue(lines[-1].endswith("..."))

    def test_the_lead_title_shares_its_row_with_the_chips_when_both_fit(self) -> None:
        for title, inline in (("Short", True), (LONG, False), (LONGER, False)):
            svg = with_samples([sample(LEAD, title, ["TERRAFORM", "AGENTCORE"])])[
                f"sample-{LEAD}.svg"
            ]
            name = f"sample-{LEAD}.svg"
            lines = self.titles(svg)
            chips = [
                e
                for e in self.foot_texts(name, svg)
                if e.get("text-anchor") == "middle"
            ]
            last = max(float(e.attrib["y"]) for e in lines)
            with self.subTest(title=title):
                self.assertEqual(len(chips), 2)
                for chip in chips:
                    if inline:
                        self.assertGreater(
                            text_box(chip)[0], text_box(lines[0])[2] + 16
                        )
                        self.assertLess(abs(float(chip.attrib["y"]) - last), 12)
                    else:
                        self.assertGreater(text_box(chip)[1], last)

    def test_the_two_up_cards_share_one_height_and_chip_row(self) -> None:
        for rows in (
            [sample(PAIR[0], "Short"), sample(PAIR[1], LONG)],
            [sample(PAIR[0], LONG, tags=[]), sample(PAIR[1], "Short")],
        ):
            files = with_samples(rows)
            pair = [parse(files[f"sample-{key}.svg"]) for key in PAIR]
            with self.subTest(rows=[r["title"] for r in rows]):
                self.assertEqual(size_of(pair[0]), size_of(pair[1]))
            chip_rows = {
                float(e.attrib["y"])
                for name in (f"sample-{key}.svg" for key in PAIR)
                for e in self.foot_texts(name, files[name])
                if e.get("text-anchor") == "middle"
            }
            self.assertLessEqual(len(chip_rows), 1)

    def test_the_lead_card_stands_alone(self) -> None:
        """Its height follows its own foot, not the two-up pair's."""
        files = with_samples(
            [sample(LEAD), sample(PAIR[0], LONG), sample(PAIR[1], LONG)]
        )
        alone = with_samples([sample(LEAD)])
        self.assertEqual(files[f"sample-{LEAD}.svg"], alone[f"sample-{LEAD}.svg"])


if __name__ == "__main__":
    unittest.main()
