"""Checks for the hero card: the two files, their bounds and motion, and what each part reads from ctx.

The shared checks run on the checked-in snapshot and assert rules, never values, so a
data refresh cannot fail them. Each data rule has its own test on a changed context.
"""

from __future__ import annotations

import importlib.util
import math
import re
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405
from itertools import combinations, pairwise
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("render_svgs", SCRIPTS / "render-svgs.py")
renderer = importlib.util.module_from_spec(SPEC)
sys.modules["render_svgs"] = renderer
SPEC.loader.exec_module(renderer)
renderer.OFFLINE = True

import kit
from cards import hero

SVG = "{http://www.w3.org/2000/svg}"
DATA = renderer.load_data()
CTX = renderer.build_context(DATA)
FILES = hero.render(DATA, CTX)
DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}
MOTION = {f"{SVG}animate", f"{SVG}animateTransform", f"{SVG}animateMotion"}
MONO = {"k": 2.0, "m": kit.TRACK, "c": 0.0}  # the mono classes and their tracking
REELS = {"tag"}  # the clip windows a reel turns in
SIDE = {"hero.svg": 24, "hero-mobile.svg": 18}  # each layout's side padding
TAG = {"hero.svg": 14.5, "hero-mobile.svg": 13}  # each layout's tagline size
# where a long tagline stops shrinking
TAG_FLOOR = {"hero.svg": 12.5, "hero-mobile.svg": 11.5}
PILL = 12.5  # the availability line's size at both widths
EPSILON = 1e-6  # float noise in measures that are equal by construction
# made-up availability lines for the tests that need one: neither is his
NOW = "Now: mentoring the Zephyr guild on weekends."
LONG_NOW = (
    "Now: building a shared delivery platform for the data, product and machine "
    "learning teams in three regions"
)
TRACKING = re.compile(r"letter-spacing:\s*(-?[\d.]+)px")
TRANSLATE = re.compile(r"translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)\s*\)")
NUM = r"(-?[\d.]+)"
# the scene says what he does in plain words: no product or tool is named in it
PRODUCTS = ("TERRAFORM", "AWS", "SAGEMAKER", "KUBERNETES", "DOCKER")
# kit's flat palette, the only paints the scene may use: one blue family, ink, grey, one green
PALETTE = {
    kit.CARD,
    kit.HAIR_STRONG,
    kit.BLUE,
    kit.BLUE_EDGE,
    kit.BLUE_LIGHT,
    kit.SKY,
    kit.BLUE_TINT,
    kit.INK,
    kit.META,
    kit.GREEN,
    kit.BG,
    "none",
    "url(#dots)",
}
STRIP = 106  # the phone strip the scene had when the card was 513 tall; it never grows


def render(**changes: object) -> dict[str, ET.Element]:
    """Both files, parsed, for the snapshot context with some keys replaced."""
    files = hero.render(DATA, {**CTX, **changes})
    return {name: ET.fromstring(svg) for name, svg in files.items()}  # nosec B314


def size(root: ET.Element) -> tuple[float, float]:
    _, _, width, height = map(float, root.attrib["viewBox"].split())
    return width, height


def parents(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def chain(element: ET.Element, up: dict[ET.Element, ET.Element]) -> list[ET.Element]:
    """The element and its ancestors, nearest first."""
    out = [element]
    while out[-1] in up:
        out.append(up[out[-1]])
    return out


def shift(element: ET.Element, up: dict[ET.Element, ET.Element]) -> tuple[float, float]:
    """Where the static translate attributes on the element and its ancestors put its origin."""
    dx = dy = 0.0
    for node in chain(element, up):
        found = TRANSLATE.search(node.get("transform", ""))
        if found and "scale" not in node.get("transform", ""):
            dx, dy = dx + float(found.group(1)), dy + float(found.group(2))
    return dx, dy


def animated(element: ET.Element) -> bool:
    return any(child.tag in MOTION for child in element)


def clip_of(node: ET.Element) -> str:
    found = re.fullmatch(r"url\(#(\w+)\)", node.get("clip-path", ""))
    return found.group(1) if found else ""


def lines(root: ET.Element) -> list[dict]:
    """Every drawn line of text with its class, colour, size, absolute span and the reel it sits in.

    Widths are measured the way kit measures them; a pinned label uses its textLength.
    """
    up = parents(root)
    out = []
    for element in root.iter(f"{SVG}text"):
        cls, font = element.get("class", ""), float(element.attrib["font-size"])
        dx, dy = shift(element, up)
        nodes = chain(element, up)
        reel = next((clip_of(n) for n in nodes if clip_of(n) in REELS), "")
        rows = [span for span in element if span.tag == f"{SVG}tspan" and span.get("x")]
        for row in rows or [element]:
            content = "".join(row.itertext())
            track = 0.0
            if cls in MONO:
                own = TRACKING.search(element.get("style", ""))
                track = float(own.group(1)) if own else MONO[cls]
                width = kit.text_width(content, font, True, track)
            else:
                width = kit.text_width(content, font)
            width = float(element.get("textLength", width))
            x, y = float(row.attrib["x"]) + dx, float(row.attrib["y"]) + dy
            anchor = element.get("text-anchor", "")
            left = (
                x - width
                if anchor == "end"
                else x - width / 2
                if anchor == "middle"
                else x
            )
            out.append(
                {
                    "text": content,
                    "class": cls,
                    "fill": element.get("fill", ""),
                    "size": font,
                    "track": track,
                    "left": left,
                    "right": left + width,
                    "y": y,
                    "reel": reel,
                    "node": element,
                    "moves": any(animated(n) or n.get("opacity") == "0" for n in nodes),
                    "hidden": any(n.get("opacity") == "0" for n in nodes),
                }
            )
    return out


def window(root: ET.Element, clip: str) -> tuple[float, float, float, float]:
    """A reel's clip window as absolute (left, top, right, bottom)."""
    up = parents(root)
    holder = next(n for n in root.iter(f"{SVG}g") if clip_of(n) == clip)
    dx, dy = shift(holder, up)
    rect = next(c for c in root.iter(f"{SVG}clipPath") if c.get("id") == clip)[0]
    x, y = float(rect.attrib["x"]) + dx, float(rect.attrib["y"]) + dy
    return x, y, x + float(rect.attrib["width"]), y + float(rect.attrib["height"])


def bars(root: ET.Element) -> list[ET.Element]:
    """The tagline's blue bar: none without a tagline, else one."""
    return [
        e
        for e in root.iter(f"{SVG}rect")
        if e.get("width") == "2" and e.get("fill") == kit.BLUE
    ]


def tag_rows(root: ET.Element) -> list[dict]:
    """The tagline as drawn: the reel's rows, closing copy included, or the one line beside the bar.

    Found by place, not size, since a long line is set smaller than the rest.
    """
    found = lines(root)
    rows = [line for line in found if line["reel"] == "tag"]
    if rows or not bars(root):
        return rows
    bar = bars(root)[0]
    top = float(bar.attrib["y"])
    bottom = top + float(bar.attrib["height"])
    return [
        line
        for line in found
        if line["class"] == "s"
        and top <= line["y"] <= bottom + 1
        and line["left"] > float(bar.attrib["x"])
    ]


def tagline(root: ET.Element) -> list[str]:
    """The lines the tagline shows, in order; the reel's closing copy of the first is left out."""
    found = [line["text"] for line in tag_rows(root)]
    return found[:-1] if len(found) > 1 else found


def pill_of(root: ET.Element) -> ET.Element | None:
    """The availability pill's rect, or None when there is no line."""
    return next(
        (
            e
            for e in root.iter(f"{SVG}rect")
            if e.get("rx") == "13" and e.get("fill") == kit.CARD
        ),
        None,
    )


def pill_lines(root: ET.Element) -> list[dict]:
    """The lines of text inside the availability pill, top to bottom.

    Reel rows waiting under their window are left out: the clip hides them.
    """
    pill = pill_of(root)
    if pill is None:
        return []
    x, y, w, h = (float(pill.attrib[k]) for k in ("x", "y", "width", "height"))
    return [
        line
        for line in lines(root)
        if not line["reel"] and x < line["left"] < x + w and y < line["y"] < y + h
    ]


def panel(root: ET.Element) -> tuple[float, float, float, float]:
    """The scene panel as absolute (left, top, right, bottom): its clip, grown back to the border."""
    left, top, right, bottom = window(root, "scene")
    return left - 1, top - 1, right + 1, bottom + 1


def in_scene(element: ET.Element, up: dict[ET.Element, ET.Element]) -> bool:
    """Whether the element is drawn inside the scene panel's clip."""
    return any(clip_of(node) == "scene" for node in chain(element, up))


def scene_lines(root: ET.Element) -> list[dict]:
    """Every line of text the scene draws, each with its absolute box (left, top, right, bottom).

    The box leaves out the trailing tracking and runs from the cap height to under the baseline.
    """
    up = parents(root)
    out = []
    for line in lines(root):
        if in_scene(line["node"], up):
            font = line["size"]
            box = (
                line["left"],
                line["y"] - 0.75 * font,
                line["right"] - line["track"],
                line["y"] + 0.2 * font,
            )
            out.append({**line, "box": box})
    return out


def scene_parts(root: ET.Element, tag: str, **paint: str) -> list[ET.Element]:
    """The scene's elements of one tag whose attributes match `paint`."""
    up = parents(root)
    return [
        e
        for e in root.iter(f"{SVG}{tag}")
        if in_scene(e, up) and all(e.get(k) == v for k, v in paint.items())
    ]


def cloud(root: ET.Element) -> tuple[list[tuple[float, float, float]], tuple]:
    """The core read back from its path: absolute lobes (cx, cy, r) and base (left, top, right, bottom)."""
    up = parents(root)
    path = scene_parts(root, "path", fill=kit.BLUE)[0]  # the one blue fill in the scene
    dx, dy = shift(path, up)
    d = path.attrib["d"]
    lobes = [
        (float(x) + float(r) + dx, float(y) + dy, float(r))
        for x, y, r in re.findall(f"M{NUM} {NUM}A{NUM}", d)
    ]
    left, top, right, bottom = map(
        float, re.search(f"M{NUM} {NUM}H{NUM}V{NUM}", d).groups()
    )
    return lobes, (left + dx, top + dy, right + dx, bottom + dy)


def in_cloud(x: float, y: float, shape: tuple) -> bool:
    lobes, (left, top, right, bottom) = shape
    if left <= x <= right and top <= y <= bottom:
        return True
    return any(math.hypot(x - cx, y - cy) <= r for cx, cy, r in lobes)


def apart(box: tuple, other: tuple) -> float:
    """The clear space between two boxes (left, top, right, bottom); 0 when they touch or overlap."""
    dx = max(other[0] - box[2], box[0] - other[2], 0)
    dy = max(other[1] - box[3], box[1] - other[3], 0)
    return math.hypot(dx, dy)


def cloud_gap(box: tuple, shape: tuple) -> float:
    """The clear space between a box and the cloud, at least 0."""
    lobes, base = shape
    near = apart(box, base)
    for cx, cy, r in lobes:
        near = min(near, max(0.0, apart(box, (cx, cy, cx, cy)) - r))
    return near


def spokes(root: ET.Element) -> list[tuple[float, float, float, float]]:
    """The spokes at rest, as absolute segments from the core out to each tile's port."""
    up = parents(root)
    out = []
    for path in scene_parts(root, "path", stroke=kit.HAIR_STRONG):
        found = re.fullmatch(f"M{NUM} {NUM}L{NUM} {NUM}", path.attrib["d"])
        if found:
            dx, dy = shift(path, up)
            x0, y0, x1, y1 = map(float, found.groups())
            out.append((x0 + dx, y0 + dy, x1 + dx, y1 + dy))
    return out


def segment_gap(segment: tuple, box: tuple, shape: tuple) -> float:
    """The clear space between a box and the part of a spoke the cloud does not cover."""
    x0, y0, x1, y1 = segment
    points = [(x0 + (x1 - x0) * k / 400, y0 + (y1 - y0) * k / 400) for k in range(401)]
    return min(apart(box, (x, y, x, y)) for x, y in points if not in_cloud(x, y, shape))


def boxes(root: ET.Element, tag: str, **paint: str) -> list[tuple]:
    """Absolute boxes of the scene's rects or circles that match `paint`."""
    up = parents(root)
    out = []
    for e in scene_parts(root, tag, **paint):
        dx, dy = shift(e, up)
        if tag == "circle":
            cx, cy, r = (float(e.attrib[k]) for k in ("cx", "cy", "r"))
            out.append((cx - r + dx, cy - r + dy, cx + r + dx, cy + r + dy))
        else:
            x, y, w, h = (float(e.attrib[k]) for k in ("x", "y", "width", "height"))
            out.append((x + dx, y + dy, x + w + dx, y + h + dy))
    return out


def dash_seen(path: ET.Element, offset: float) -> float:
    """How much of a dashed path's 100 units its dashes cover at a dash offset."""
    dash, space = map(float, path.attrib["stroke-dasharray"].split())
    period, seen = dash + space, 0.0
    for k in range(-3, 4):
        start = k * period - offset
        seen += max(0.0, min(100.0, start + dash) - max(0.0, start))
    return seen


def loops(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if e.tag in MOTION and e.get("repeatCount")]


def entrances(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if e.tag in MOTION and not e.get("repeatCount")]


def ease(spline: list[float], k: float) -> float:
    """How far a keySplines curve has gone at time fraction k."""
    x1, y1, x2, y2 = spline

    def point(s: float, a: float, b: float) -> float:
        return 3 * (1 - s) ** 2 * s * a + 3 * (1 - s) * s * s * b + s**3

    low, high = 0.0, 1.0
    for _ in range(40):
        middle = (low + high) / 2
        low, high = (middle, high) if point(middle, x1, x2) < k else (low, middle)
    return point((low + high) / 2, y1, y2)


def sample(loop: ET.Element, second: float) -> list[float]:
    """A repeating animation's value at a moment, as numbers: linear, or eased by its keySplines."""
    dur = float(loop.attrib["dur"].rstrip("s"))
    at = second % dur
    times = [float(t) * dur for t in loop.attrib["keyTimes"].split(";")]
    values = [[float(n) for n in v.split()] for v in loop.attrib["values"].split(";")]
    splines = [
        [float(n) for n in spline.split()]
        for spline in loop.get("keySplines", "").split(";")
        if spline.strip()
    ]
    for index, (a, b) in enumerate(pairwise(times)):
        if a <= at <= b and b > a:
            k = (at - a) / (b - a)
            if loop.get("calcMode") == "spline":
                k = ease(splines[index], k)
            return [p + (q - p) * k for p, q in zip(values[index], values[index + 1])]
    return values[-1]


def state(
    element: ET.Element, up: dict[ET.Element, ET.Element], second: float
) -> tuple[float, float, float]:
    """(opacity, dx, dy) of an element at a moment of the loop, its ancestors' loops included.

    A loop on a translate replaces the attribute, as SMIL does. The entrances are over
    by the second second and are left out.
    """
    opacity, dx, dy = 1.0, 0.0, 0.0
    for node in chain(element, up):
        own = [c for c in node if c.tag in MOTION and c.get("repeatCount")]
        fade = next((c for c in own if c.get("attributeName") == "opacity"), None)
        move = next((c for c in own if c.get("attributeName") == "transform"), None)
        opacity *= (
            sample(fade, second)[0]
            if fade is not None
            else float(node.get("opacity", 1))
        )
        found = TRANSLATE.search(node.get("transform", ""))
        if move is not None:
            x, y = sample(move, second)
        elif found and "scale" not in node.get("transform", ""):
            x, y = float(found.group(1)), float(found.group(2))
        else:
            x = y = 0.0
        dx, dy = dx + x, dy + y
    return opacity, dx, dy


class SnapshotTests(unittest.TestCase):
    """Rules the hero keeps at both widths, on the data the page is built from.

    The subclasses below run every one of them again on a refreshed portfolio.
    """

    ctx = CTX

    @classmethod
    def setUpClass(cls):
        cls.files = hero.render(DATA, cls.ctx)

    def each(self):
        for name, svg in self.files.items():
            with self.subTest(file=name):
                yield name, svg, ET.fromstring(svg)  # nosec B314

    def test_the_module_returns_the_hero_and_its_phone_twin(self):
        self.assertEqual(set(self.files), {"hero.svg", "hero-mobile.svg"})
        for name in self.files:
            self.assertTrue(renderer.CARD_FILE.fullmatch(name), name)

    def test_every_file_is_valid_xml_with_a_sized_root(self):
        for _, _, root in self.each():
            width, height = size(root)
            self.assertEqual(root.tag, f"{SVG}svg")
            self.assertEqual(root.get("role"), "img")
            self.assertEqual(float(root.attrib["width"]), width)
            self.assertEqual(float(root.attrib["height"]), height)

    def test_the_cards_keep_their_sizes(self):
        # the widths are fixed; the heights follow the text, so only their floor and grid are rules
        desktop, phone = (size(ET.fromstring(self.files[name])) for name in SIDE)  # nosec B314
        self.assertEqual(desktop[0], 840)
        self.assertGreaterEqual(desktop[1], 320)
        self.assertEqual(desktop[1] % 8, 0)  # the card ends on the 8px grid
        self.assertEqual(phone[0], 320)

    def test_no_text_leaves_the_canvas(self):
        for name, _, root in self.each():
            width, height = size(root)
            pad = SIDE[name]
            for line in lines(root):
                if line["hidden"]:  # the core's status waiting for its turn
                    continue
                self.assertGreaterEqual(line["left"], pad - 2.01, line["text"])
                self.assertLessEqual(line["right"], width - pad + 0.01, line["text"])
                if not line["reel"]:
                    self.assertGreater(line["y"] - line["size"] * 0.75, 8, line["text"])
                    self.assertLess(line["y"], height - 12, line["text"])

    def test_a_reel_turns_inside_its_window_and_rests_on_its_first_row(self):
        for _, _, root in self.each():
            width, height = size(root)
            for clip in REELS:
                left, top, right, bottom = window(root, clip)
                self.assertTrue(0 < left < right < width and 0 < top < bottom < height)
                rows = [line for line in lines(root) if line["reel"] == clip]
                self.assertGreater(len(rows), 2)
                self.assertTrue(top < rows[0]["y"] < bottom, clip)
                self.assertEqual(rows[0]["text"], rows[-1]["text"])  # the loop closes
                pitch = rows[1]["y"] - rows[0]["y"]
                # no second row peeks in; the measures are floats, so equal may land a hair under
                self.assertGreaterEqual(pitch + EPSILON, bottom - top)
                for row in rows:
                    self.assertGreaterEqual(row["left"] + EPSILON, left, row["text"])
                    self.assertLessEqual(row["right"], right + EPSILON, row["text"])

    def test_no_dash_characters(self):
        for _, svg, _ in self.each():
            for dash in DASHES:
                self.assertNotIn(dash, svg)

    def test_entrances_are_poster_safe(self):
        for _, _, root in self.each():
            up = parents(root)
            found = entrances(root)
            self.assertTrue(found)
            for entrance in found:
                self.assertEqual(entrance.get("fill"), "freeze")
                rest = entrance.attrib["values"].split(";")[-1]
                self.assertIn(rest, {"1", "0 0"})  # it ends where the attributes rest
                self.assertNotIn("opacity", up[entrance].attrib)
                self.assertNotIn("begin", entrance.attrib)
                self.assertLessEqual(float(entrance.attrib["dur"].rstrip("s")), 1.6)

    def test_only_the_loop_s_actors_rest_hidden(self):
        # the core's BUILDING status and the proof cells waiting their turn
        for _, svg, root in self.each():
            self.assertNotIn("visibility", svg)
            self.assertNotIn("display:none", svg)
            hidden = [e for e in root.iter() if e.get("opacity") == "0"]
            for element in hidden:
                self.assertTrue(
                    any(
                        c.get("attributeName") == "opacity" and c.get("repeatCount")
                        for c in element
                    ),
                    element.tag,
                )
                words = {"".join(t.itertext()) for t in element.iter(f"{SVG}text")}
                self.assertLessEqual(words, {hero.BUILDING})

    def test_the_still_frame_holds_the_finished_hub(self):
        for _, _, root in self.each():
            still = {line["text"] for line in lines(root) if not line["moves"]}
            shown = {line["text"] for line in lines(root) if not line["hidden"]}
            for word in (*(node[0] for node in hero.NODES), hero.CORE, hero.LIVE):
                self.assertIn(word, shown)
            self.assertNotIn(hero.BUILDING, shown)
            self.assertIn(self.ctx["aws_title_long"].split(" - ")[0], " ".join(still))

    def test_every_loop_is_on_the_page_clock(self):
        for _, _, root in self.each():
            found = loops(root)
            self.assertTrue(found)  # motion stays visible at both widths
            for loop in found:
                self.assertIn(float(loop.attrib["dur"].rstrip("s")), CLOCK)
                self.assertEqual(loop.get("repeatCount"), "indefinite")
                self.assertIn(
                    loop.get("attributeName"),
                    {"opacity", "transform", "stroke-dashoffset", "r"},
                )
                times = [float(t) for t in loop.get("keyTimes", "0;1").split(";")]
                self.assertEqual((times[0], times[-1]), (0.0, 1.0))
                self.assertEqual(times, sorted(times))
                self.assertEqual(len(times), len(loop.attrib["values"].split(";")))

    def test_the_motion_budget_is_kept(self):
        for _, _, root in self.each():
            moving = [e for e in root.iter() if animated(e)]
            self.assertLessEqual(
                len(moving), 30
            )  # the contest winner had 38; the cap is 40

    def test_text_keeps_the_size_floor(self):
        for name, _, root in self.each():
            floor = kit.MICRO_PHONE if name.endswith("-mobile.svg") else kit.MICRO
            for line in lines(root):
                self.assertGreaterEqual(line["size"], floor, line["text"])

    def test_files_are_self_contained(self):
        for _, svg, _ in self.each():
            for banned in ("href", "<image", "<script", "foreignObject", "@import"):
                self.assertNotIn(banned, svg)
            self.assertEqual(svg.count("url("), svg.count("url(#"))

    def test_green_is_the_live_dot_and_the_closing_check(self):
        for _, svg, root in self.each():
            self.assertNotIn(kit.AMBER, svg)
            green = [
                e for e in root.iter() if kit.GREEN in (e.get("fill"), e.get("stroke"))
            ]
            # the pill's dot and its pulse when there is a line, then the ok that marks the hub live
            dots = 2 if self.ctx["availability"] else 0
            self.assertEqual([e.tag for e in green], [f"{SVG}circle"] * (dots + 1))
            self.assertEqual([e.get("r") for e in green[:dots]], ["3.5"] * dots)
            self.assertEqual(green[-1].get("fill"), kit.GREEN)
            self.assertNotIn("34,197,94", svg)  # no green tint behind the pill

    def test_the_name_is_drawn_once_at_display_size(self):
        for name, _, root in self.each():
            found = [line for line in lines(root) if line["text"] == hero.NAME]
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["class"], "t")
            self.assertEqual(
                found[0]["size"], 32 if name.endswith("-mobile.svg") else 56
            )
            self.assertFalse(found[0]["moves"])

    def test_the_label_is_a_summary_of_the_card(self):
        ctx = self.ctx
        for _, _, root in self.each():
            label = root.attrib["aria-label"]
            self.assertTrue(
                label.startswith(
                    f"{hero.NAME}, {ctx['aws_title_long']}, {ctx['location']}."
                )
            )
            self.assertIn(ctx["intro"], label)
            for cell in ctx["proof"]:
                self.assertIn(f"{cell['value']} {cell['label']}", label)
            if ctx["availability"]:
                self.assertIn(ctx["availability"].rstrip("."), label)

    def test_the_greeting_and_the_place_come_from_ctx(self):
        for _, _, root in self.each():
            shown = {line["text"]: line for line in lines(root)}
            self.assertEqual(shown[self.ctx["greeting"].upper()]["class"], "k")
            self.assertEqual(shown[self.ctx["location"].upper()]["class"], "m")


class LongerLineTests(SnapshotTests):
    """The snapshot rules again, with an availability line that wraps the pill at both widths."""

    ctx = {**CTX, "availability": LONG_NOW}

    def test_the_line_wraps_the_pill(self):
        for name, _, root in self.each():
            self.assertGreater(len(pill_lines(root)), 1, name)


class LongerIntroTests(SnapshotTests):
    """The snapshot rules again, with one more sentence in the intro."""

    ctx = {
        **CTX,
        "intro": CTX["intro"]
        + " A second sentence, made up for this test, runs the intro onto another line.",
    }


class NoLineTests(SnapshotTests):
    """The snapshot rules again, with no availability line."""

    ctx = {**CTX, "availability": ""}


class SceneTests(unittest.TestCase):
    """The hub's rules: it keeps its panel, nothing in it collides at any moment of the loop,
    it says his work in plain words and kit's flat palette, and it rests on the finished, live hub.

    The subclass runs every one of them again in the taller desktop panel a longer intro makes.
    """

    ctx = CTX

    @classmethod
    def setUpClass(cls):
        files = hero.render(DATA, cls.ctx)
        cls.roots = {name: ET.fromstring(svg) for name, svg in files.items()}  # nosec B314

    def each(self):
        for name, root in self.roots.items():
            with self.subTest(file=name):
                yield name, root

    def moments(self) -> list[float]:
        return [step / 20 for step in range(round(kit.T * 20))]

    def test_the_panel_keeps_its_box(self):
        # desktop: right of the left column, filling the height above the proof row
        root = self.roots["hero.svg"]
        left, top, right, bottom = panel(root)
        self.assertEqual((left, top, right), (464, 24, 816))
        up = parents(root)
        cells = [
            e
            for e in root.iter(f"{SVG}rect")
            if e.get("rx") == "10" and e.get("fill") == kit.CARD and not in_scene(e, up)
        ]
        self.assertEqual(bottom, float(cells[0].attrib["y"]) - 16)
        # phone: the strip between the pill and the intro, never taller than it was
        _, top, _, bottom = panel(self.roots["hero-mobile.svg"])
        self.assertEqual(bottom - top, STRIP)

    def test_every_scene_label_sits_inside_the_panel(self):
        for _, root in self.each():
            left, top, right, bottom = panel(root)
            found = scene_lines(root)
            self.assertTrue(found)
            for line in found:
                x0, y0, x1, y1 = line["box"]
                self.assertGreaterEqual(x0, left + 6, line["text"])
                self.assertLessEqual(x1, right - 6, line["text"])
                self.assertGreaterEqual(y0, top + 6, line["text"])
                self.assertLessEqual(y1, bottom - 6, line["text"])

    def test_no_two_scene_labels_overlap_at_any_moment(self):
        """Walk the loop: wherever two different labels can both be seen, their boxes are apart.

        A tile's word is drawn twice, grey and then lit in ink over it, so a word on its own
        copy is one label. BUILDING and LIVE share a place, so they must never show together.
        """
        for name, root in self.each():
            up = parents(root)
            found = scene_lines(root)
            for second in self.moments():
                seen = {
                    (line["text"], line["box"])
                    for line in found
                    if state(line["node"], up, second)[0] > 0.001
                }
                for (a, box_a), (b, box_b) in combinations(sorted(seen), 2):
                    self.assertGreater(apart(box_a, box_b), 2, (name, second, a, b))

    def test_labels_and_marks_keep_clear_of_the_spokes_and_the_cloud(self):
        for name, root in self.each():
            shape, found = cloud(root), spokes(root)
            marks = [(line["text"], line["box"]) for line in scene_lines(root)]
            marks += [("ok", box) for box in boxes(root, "circle", fill=kit.GREEN)]
            for text, box in marks:
                for segment in found:
                    self.assertGreaterEqual(
                        segment_gap(segment, box, shape), 6, (name, text)
                    )
                if text != hero.CORE:
                    self.assertGreaterEqual(cloud_gap(box, shape), 6, (name, text))
            tiles = boxes(root, "rect", rx="7", fill=kit.CARD)
            self.assertEqual(len(tiles), len(hero.NODES))
            for tile, other in combinations(tiles, 2):
                self.assertGreater(apart(tile, other), 8, name)
            for tile in tiles:
                self.assertGreaterEqual(cloud_gap(tile, shape), 12, name)

    def test_every_spoke_shows_a_readable_run(self):
        # the length of line between the cloud and the port's dot, where the signal is seen
        for name, root in self.each():
            shape, found = cloud(root), spokes(root)
            ports = boxes(root, "circle", fill=kit.BLUE_LIGHT)
            self.assertEqual(len(found), len(hero.NODES))
            for x0, y0, x1, y1 in found:
                port = next(
                    (b[2] - b[0]) / 2
                    for b in ports
                    if abs((b[0] + b[2]) / 2 - x1) < 0.01
                    and abs((b[1] + b[3]) / 2 - y1) < 0.01
                )
                length, run = math.hypot(x1 - x0, y1 - y0), 0.0
                for k in range(400):
                    x = x0 + (x1 - x0) * (k + 0.5) / 400
                    y = y0 + (y1 - y0) * (k + 0.5) / 400
                    if not in_cloud(x, y, shape) and math.hypot(x1 - x, y1 - y) > port:
                        run += length / 400
                self.assertGreaterEqual(run, 24, (name, x1, y1))

    def test_the_core_word_has_room_in_its_cloud(self):
        for name, root in self.each():
            shape = cloud(root)
            word = next(line for line in scene_lines(root) if line["text"] == hero.CORE)
            x0, y0, x1, y1 = word["box"]
            row = (y0 + y1) / 2
            span = [
                x / 10
                for x in range(round(x0 - 60) * 10, round(x1 + 60) * 10)
                if in_cloud(x / 10, row, shape)
            ]
            self.assertGreaterEqual(x0 - min(span), 10, name)
            self.assertGreaterEqual(max(span) - x1, 10, name)

    def test_the_status_sits_midway_between_the_lower_spokes(self):
        for name, root in self.each():
            lower = sorted(spokes(root), key=lambda s: s[3])[-2:]  # to the bottom row
            words = {line["text"]: line["box"] for line in scene_lines(root)}
            (ok,) = boxes(root, "circle", fill=kit.GREEN)
            y = (ok[1] + ok[3]) / 2
            across = [x0 + (x1 - x0) * (y - y0) / (y1 - y0) for x0, y0, x1, y1 in lower]
            middle = sum(across) / 2
            # the ok and LIVE as one group; a centred word also sets its trailing
            # tracking, so BUILDING sits half of that to the left
            live = (ok[0] + words[hero.LIVE][2]) / 2
            building = (words[hero.BUILDING][0] + words[hero.BUILDING][2]) / 2
            self.assertAlmostEqual(live, middle, delta=0.5, msg=name)
            self.assertAlmostEqual(building, middle, delta=1, msg=name)

    def test_the_still_frame_is_the_finished_live_hub(self):
        for name, root in self.each():
            found = scene_lines(root)
            shown = {line["text"] for line in found if not line["hidden"]}
            lit = {line["text"] for line in found if line["fill"] == kit.INK}
            for word, *_ in hero.NODES:
                self.assertIn(word, shown & lit, name)
            self.assertIn(hero.LIVE, shown, name)
            self.assertEqual(
                {line["text"] for line in found if line["hidden"]}, {hero.BUILDING}
            )
            # every lit spoke is drawn whole, and every signal is off the end of its spoke
            for path in scene_parts(root, "path", stroke=kit.BLUE_EDGE):
                self.assertEqual(path.get("stroke-dashoffset"), "0", name)
            heads = scene_parts(root, "path", stroke=kit.SKY)
            self.assertEqual(len(heads), len(hero.NODES))
            for head in heads:
                offset = float(head.attrib["stroke-dashoffset"])
                self.assertEqual(dash_seen(head, offset), 0, name)

    def test_the_loop_ends_on_the_still_frame(self):
        # at its first and its last moment every loop in the scene draws what its attributes do
        for name, root in self.each():
            up = parents(root)
            found = [e for e in loops(root) if in_scene(e, up)]
            self.assertTrue(found)
            for loop in found:
                target, dur = up[loop], float(loop.attrib["dur"].rstrip("s"))
                edges = (sample(loop, 0)[0], sample(loop, dur - 0.001)[0])
                if loop.attrib["attributeName"] == "opacity":
                    rest = float(target.get("opacity", 1))
                    for value in edges:
                        self.assertAlmostEqual(value, rest, delta=0.01, msg=name)
                else:
                    self.assertEqual(loop.attrib["attributeName"], "stroke-dashoffset")
                    rest = dash_seen(target, float(target.attrib["stroke-dashoffset"]))
                    for value in edges:
                        self.assertAlmostEqual(
                            dash_seen(target, value), rest, delta=0.01, msg=name
                        )

    def test_the_capabilities_light_in_order_and_only_then_the_core_goes_live(self):
        """Walk the loop: the hub powers down, reads BUILDING, lights down the left side and
        then down the right, and LIVE never shows brighter than the dimmest capability."""
        for name, root in self.each():
            up = parents(root)
            found = scene_lines(root)
            words = [node[0] for node in hero.NODES]
            lit = {
                line["text"]: line["node"]
                for line in found
                if line["fill"] == kit.INK and line["text"] in words
            }
            live = next(line["node"] for line in found if line["text"] == hero.LIVE)
            building = next(
                line["node"] for line in found if line["text"] == hero.BUILDING
            )
            first, dark, reads, finished = {}, None, False, 0
            for second in self.moments():
                level = {word: state(node, up, second)[0] for word, node in lit.items()}
                shows = state(live, up, second)[0]
                self.assertLessEqual(shows, min(level.values()) + 0.01, (name, second))
                if max(level.values()) < 0.01:
                    dark = second if dark is None else dark
                    reads |= state(building, up, second)[0] > 0.99
                if dark is not None:
                    for word, value in level.items():
                        if value > 0.5:
                            first.setdefault(word, second)
                finished += shows > 0.99
            self.assertIsNotNone(dark, name)
            self.assertTrue(reads, name)  # the dark hub reads BUILDING
            order = sorted(first, key=first.get)
            self.assertEqual(order, words, name)
            sides = [side for _, _, side, _ in hero.NODES]
            self.assertEqual(sides, sorted(sides))  # the left side lights first
            # the finished, live hub holds for a third of the loop or more
            self.assertGreaterEqual(finished / 20, kit.T / 3, name)

    def test_the_scene_is_flat_and_in_kit_s_palette(self):
        for name, root in self.each():
            up = parents(root)
            inside = [e for e in root.iter() if in_scene(e, up) and e.tag not in MOTION]
            paints = {e.get(k) for e in inside for k in ("fill", "stroke")} - {None}
            self.assertLessEqual(paints, PALETTE, name)
            # the one ok; the pill's dot is the card's other green
            green = [e for e in inside if kit.GREEN in (e.get("fill"), e.get("stroke"))]
            self.assertEqual(len(green), 1, name)
            for e in inside:
                self.assertNotIn(
                    e.tag.split("}")[1], {"linearGradient", "radialGradient", "filter"}
                )
                self.assertNotIn("filter", e.attrib)

    def test_the_scene_names_no_product_and_shows_no_figure(self):
        for name, root in self.each():
            said = " ".join(line["text"] for line in scene_lines(root)).upper()
            for product in PRODUCTS:
                self.assertNotIn(product, said, name)
            self.assertIsNone(re.search(r"\d", said), said)

    def test_the_scene_moves_one_part_for_each_thing_that_happens(self):
        # each capability: its lit spoke, its signal and its tile; the core: its two states;
        # and the panel's entrance. About 12 to 20 moving parts.
        for name, root in self.each():
            up = parents(root)
            moving = [e for e in root.iter() if in_scene(e, up) and animated(e)]
            self.assertEqual(len(moving), 3 * len(hero.NODES) + 3, name)

    def test_the_desktop_panel_has_its_title_and_the_phone_strip_none(self):
        desktop, phone = (
            [line["text"] for line in scene_lines(self.roots[n])] for n in SIDE
        )
        self.assertIn(hero.TITLE, desktop)
        self.assertNotIn(hero.TITLE, phone)

    def test_the_alt_text_ends_on_one_sentence_about_the_scene(self):
        for name, root in self.each():
            label = root.attrib["aria-label"]
            sentence = label[label.rfind("The diagram is ") :]
            self.assertTrue(sentence.startswith("The diagram is "), name)
            self.assertTrue(sentence.endswith("live."), sentence)
            self.assertNotIn(". ", sentence)  # one sentence
            for _, said, _, _ in hero.NODES:
                self.assertIn(said, sentence)
            for product in PRODUCTS:
                self.assertNotIn(product.lower(), sentence.lower())


class TallerPanelSceneTests(SceneTests):
    """The scene rules again, in the taller desktop panel a longer intro makes."""

    ctx = {**CTX, "intro": CTX["intro"] + " " + CTX["intro"]}


class RoleTests(unittest.TestCase):
    """The role line is static, whole and exact, and a wrapped line never starts with the hyphen."""

    def test_the_desktop_role_is_one_exact_static_line(self):
        root = render()["hero.svg"]
        found = [line for line in lines(root) if line["text"] == CTX["aws_title_long"]]
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["moves"])
        self.assertEqual(found[0]["fill"], kit.INK)

    def test_the_phone_role_wraps_without_losing_a_character(self):
        root = render()["hero-mobile.svg"]
        role = [
            line
            for line in lines(root)
            if line["class"] == "s" and line["fill"] == kit.INK and not line["moves"]
        ]
        self.assertEqual(" ".join(line["text"] for line in role), CTX["aws_title_long"])
        for line in role:
            self.assertFalse(line["text"].startswith("-"), line["text"])

    def test_a_changed_title_is_drawn_as_given(self):
        title = "Principal Consultant - Platform & Reliability at AWS"
        for name, root in render(aws_title_long=title).items():
            role = [
                line["text"]
                for line in lines(root)
                if line["class"] == "s"
                and line["fill"] == kit.INK
                and not line["moves"]
            ]
            self.assertEqual(" ".join(role), title, name)

    def test_no_wrapped_line_starts_with_the_hyphen_at_any_width(self):
        title = CTX["aws_title_long"]
        for width in range(90, 420, 6):
            wrapped = hero._role_lines(title, width, 14.5)
            self.assertEqual(" ".join(wrapped).replace(" ", ""), title.replace(" ", ""))
            for line in wrapped:
                self.assertFalse(line.startswith("-"), (width, wrapped))


class ProofTests(unittest.TestCase):
    """The proof row is the ctx cells, in order, and nothing else."""

    def cells(self, root: ET.Element) -> list[tuple[str, str]]:
        found = lines(root)
        values = [line for line in found if line["class"] == "n"]
        out = []
        for value in values:
            label = [
                line["text"]
                for line in found
                if line["class"] == "m"
                and line["fill"] == kit.META
                and abs(line["left"] - value["left"]) < 0.01
                and 0 < line["y"] - value["y"] < 40
            ]
            out.append((value["text"], " ".join(label)))
        return out

    def test_the_snapshot_cells_are_shown_in_order(self):
        expected = [(c["value"], c["label"].upper()) for c in CTX["proof"]]
        for name, root in render().items():
            self.assertEqual(self.cells(root), expected, name)

    def test_changed_cells_are_shown_as_given(self):
        proof = [
            {"value": "7", "label": "first thing"},
            {"value": "41k", "label": "a second and longer label"},
        ]
        for name, root in render(proof=proof).items():
            self.assertEqual(
                self.cells(root),
                [
                    ("7", "FIRST THING"),
                    ("41k", "A SECOND AND LONGER LABEL"),
                ],
                name,
            )

    def test_one_cell_is_lit_at_rest_and_the_light_moves(self):
        for name, root in render().items():
            lit = [
                e
                for e in root.iter(f"{SVG}rect")
                if e.get("fill") == kit.BLUE_TINT and e.get("rx") == "10"
            ]
            resting = [e for e in lit if e.get("opacity") != "0"]
            self.assertEqual(len(resting), 1, name)
            for cell in lit:
                self.assertTrue(animated(cell), name)

    def test_the_phone_cells_are_one_height_in_an_even_grid(self):
        root = render()["hero-mobile.svg"]
        tiles = [
            e
            for e in root.iter(f"{SVG}rect")
            if e.get("rx") == "10" and e.get("fill") == kit.CARD
        ]
        tiles = [
            e for e in tiles if float(e.attrib["width"]) < 200
        ]  # not the scene panel
        self.assertEqual(len(tiles), len(CTX["proof"][:4]))
        self.assertEqual(len({e.attrib["height"] for e in tiles}), 1)
        tops = sorted({float(e.attrib["y"]) for e in tiles})
        self.assertEqual(len(tops), 2)
        self.assertEqual(tops[1] - tops[0], float(tiles[0].attrib["height"]) + 8)
        # the longest label still ends inside its cell
        bottom = tops[1] + float(tiles[0].attrib["height"])
        labels = [
            line["y"]
            for line in lines(root)
            if line["class"] == "m" and line["fill"] == kit.META and line["y"] > tops[1]
        ]
        self.assertLessEqual(max(labels), bottom - 4)

    def test_no_cells_means_no_row_and_a_shorter_card(self):
        full, bare = render(), render(proof=[])
        for name in SIDE:
            self.assertEqual(self.cells(bare[name]), [])
            self.assertLess(size(bare[name])[1], size(full[name])[1])

    def test_a_single_cell_is_lit_without_a_loop(self):
        for name, root in render(proof=CTX["proof"][:1]).items():
            lit = [e for e in root.iter(f"{SVG}rect") if e.get("fill") == kit.BLUE_TINT]
            self.assertFalse(
                [e for e in lit if e.get("rx") == "10" and animated(e)], name
            )


class AvailabilityTests(unittest.TestCase):
    """The pill shows the line as written behind the card's only green, and goes when it is empty."""

    def test_the_line_is_drawn_in_his_own_casing(self):
        for name, root in render().items():
            words = " ".join(line["text"] for line in pill_lines(root))
            self.assertEqual(words, CTX["availability"], name)
            for line in pill_lines(root):
                self.assertEqual((line["class"], line["size"]), ("s", PILL), name)

    def test_an_empty_line_removes_the_pill_and_its_green(self):
        full, bare = (
            hero.render(DATA, {**CTX, "availability": NOW}),
            hero.render(DATA, {**CTX, "availability": ""}),
        )
        for name in SIDE:
            self.assertEqual(full[name].count(kit.GREEN), 3)
            self.assertEqual(bare[name].count(kit.GREEN), 1)  # the closing check stays
            root = ET.fromstring(bare[name])  # nosec B314
            with_line = ET.fromstring(full[name])  # nosec B314
            self.assertTrue(pill_lines(with_line), name)
            self.assertIsNone(pill_of(root), name)
            self.assertLessEqual(size(root)[1], size(with_line)[1])
            # the alt text says the line with the pill and drops it, and only it, without
            line = NOW.rstrip(".") + "."
            self.assertIn(line, with_line.attrib["aria-label"])
            self.assertNotIn(NOW.rstrip("."), root.attrib["aria-label"])
            self.assertEqual(
                root.attrib["aria-label"],
                with_line.attrib["aria-label"].replace(f" {line}", ""),
                name,
            )

    def test_the_layout_closes_up_without_the_pill(self):
        for name, root in render(availability="").items():
            found = lines(root)
            intro = min(line["y"] for line in found if line["class"] == "b")
            above = max(
                line["y"]
                for line in found
                if line["y"] < intro and not line["reel"] and line["left"] < 60
            )
            self.assertLessEqual(intro - above, 70, name)

    def test_the_slack_is_shared_when_the_left_column_ends_short(self):
        # desktop: with no pill the block under the kicker is centred above the proof row.
        # A short made-up intro keeps the left column short of the proof row either way.
        short = {"intro": "A short made-up intro for the layout.", "intro_keywords": []}
        full = render(availability=NOW, **short)["hero.svg"]
        bare = render(availability="", **short)["hero.svg"]

        def marks(root: ET.Element) -> tuple[float, float, float]:
            found = lines(root)
            name = next(line["y"] for line in found if line["text"] == hero.NAME)
            intro = max(line["y"] for line in found if line["class"] == "b")
            value = min(line["y"] for line in found if line["class"] == "n")
            return name, intro, value

        (name, intro, value), (low, last, same) = marks(full), marks(bare)
        self.assertEqual(value, same)  # the proof row stays where it is
        drop = low - name
        self.assertGreater(drop, 0)
        # what the name moved down by is what is left under the intro
        self.assertAlmostEqual((same - last) - (value - intro), drop, delta=1)

    def test_the_desktop_pill_is_cut_to_its_line(self):
        root = render(availability=NOW)["hero.svg"]  # a line short enough for one row
        line = pill_lines(root)[0]
        length = float(line["node"].attrib["textLength"])
        pill = pill_of(root)
        left, wide = float(pill.attrib["x"]), float(pill.attrib["width"])
        dot = next(e for e in root.iter(f"{SVG}circle") if e.get("fill") == kit.GREEN)
        before = float(dot.attrib["cx"]) - float(dot.attrib["r"]) - left
        after = left + wide - (line["left"] + length)
        self.assertAlmostEqual(before, after, delta=1.5)  # even padding on both sides

    def test_a_long_line_wraps_inside_the_pill(self):
        long_line = CTX["availability"] + " and a second programme that runs beside it"
        for name, root in render(availability=long_line).items():
            width, _ = size(root)
            for line in lines(root):
                self.assertLessEqual(
                    line["right"], width - SIDE[name] + 0.01, line["text"]
                )


class TaglineTests(unittest.TestCase):
    """The rotating lines are ctx["hero_lines"], in order, and the first is the rest frame."""

    def assert_fitted(
        self, root: ET.Element, name: str, given: list[str]
    ) -> list[dict]:
        """The rows are the given lines in order, each at the largest size from the tagline's
        own down to the floor that fits the window, and a line that does not fit even at the
        floor ends on its last whole word that does. Returns the rows."""
        given = [line for line in given if line][:4]
        rows = tag_rows(root)
        rows = rows[:-1] if len(rows) > 1 else rows
        self.assertEqual(len(rows), len(given), name)
        if len(rows) < 2:
            return rows
        right = window(root, "tag")[2]
        for row, line in zip(rows, given):
            room = right - row["left"]
            self.assertLessEqual(row["right"], right + EPSILON, row["text"])
            self.assertTrue(TAG_FLOOR[name] <= row["size"] <= TAG[name], row["text"])
            if row["text"] == line:
                if row["size"] < TAG[name]:  # it shrank no more than it had to
                    wider = kit.text_width(line, row["size"] + 0.5)
                    self.assertGreater(wider, room + EPSILON, row["text"])
                continue
            self.assertEqual(row["size"], TAG_FLOOR[name], row["text"])
            self.assertTrue(line.startswith(row["text"]), row["text"])
            self.assertIn(line[len(row["text"])], " ,;:")  # never cut inside a word
            more = " ".join(line.split()[: len(row["text"].split()) + 1])
            self.assertGreater(kit.text_width(more, row["size"]), room + EPSILON, more)
        return rows

    def test_the_snapshot_lines_take_turns_in_order(self):
        for name, root in render().items():
            self.assert_fitted(root, name, CTX["hero_lines"])

    def test_a_long_line_steps_down_and_never_loses_half_a_word(self):
        given = [  # made up, and measured by kit against the two windows
            "A first line that fits.",
            # fits the desktop; fits the phone only below its tagline size
            "Small teams ship one tested change at a time.",
            # fits the desktop only below its tagline size; too long for the phone floor
            "Small teams ship their stacks one tested change at a time.",
            # too long for either floor
            "Shared modules, tested pipelines, reviewed changes and audited "
            "releases, for every team in every region.",
        ]
        for name, root in render(hero_lines=given).items():
            rows = self.assert_fitted(root, name, given)
            self.assertEqual(
                rows[0]["size"], TAG[name], name
            )  # a line that fits keeps the size
            stepped = [
                r
                for r, g in zip(rows, given)
                if r["text"] == g and r["size"] < TAG[name]
            ]
            cut = [r for r, g in zip(rows, given) if r["text"] != g]
            self.assertTrue(stepped and cut, name)  # the lines above test both ways out

    def test_changed_lines_are_shown_as_given(self):
        given = ["First line, as written.", "Second line & more."]
        for name, root in render(hero_lines=given).items():
            self.assertEqual(tagline(root), given, name)
            turns = [
                e
                for e in loops(root)
                if e.tag == f"{SVG}animateTransform"
                and e.attrib["values"].startswith("0 0;0 0;0 -")
            ]
            self.assertTrue(turns, name)

    def test_the_proof_light_moves_between_the_tagline_and_the_scene_beats(self):
        # four lines turn on the 3 s beat; the snapshot may hold fewer
        root = render(hero_lines=["One.", "Two.", "Three.", "Four."])["hero.svg"]
        holder = next(n for n in root.iter(f"{SVG}g") if clip_of(n) == "tag")
        reel = next(e for e in holder.iter(f"{SVG}animateTransform"))
        lit = next(
            e
            for e in root.iter(f"{SVG}rect")
            if e.get("fill") == kit.BLUE_TINT and e.get("rx") == "10"
        )
        slide = next(e for e in lit if e.tag == f"{SVG}animateTransform")

        def turns(loop: ET.Element) -> set[float]:
            dur = float(loop.attrib["dur"].rstrip("s"))
            times = [float(t) * dur for t in loop.attrib["keyTimes"].split(";")]
            values = loop.attrib["values"].split(";")
            return {
                round(b, 2)
                for a, b, v, w in zip(times, times[1:], values, values[1:])
                if v != w
            }

        self.assertEqual(turns(reel), {3.0, 6.0, 9.0, 12.0})
        self.assertEqual(float(slide.attrib["dur"].rstrip("s")), 24)  # 6 s a cell
        # the light only changes in two quiet stretches of the scene's loop: in the pause
        # between the hub's two sides, and while the finished hub holds
        start = hero.PROOF_AT - 0.35
        quiet = [(start, hero.PROOF_AT), (start + kit.T / 2, hero.PROOF_AT + kit.T / 2)]
        for turn in turns(slide):
            at = turn % kit.T
            self.assertTrue(any(a <= at <= b + 0.01 for a, b in quiet), turn)
        # the hub powering down, each signal leaving and landing, and the core going live
        beats = {
            hero.REST,
            *hero.LEAVES,
            *(leave + hero.RUN for leave in hero.LEAVES),
            hero.DONE,
        }
        busy = {*beats, *(turn % kit.T for turn in turns(reel))}
        for a, b in quiet:
            self.assertFalse([at for at in busy if a - 0.1 <= at <= b + 0.1])
            self.assertTrue(
                all(abs(b - at) >= 0.5 for at in busy)
            )  # where a move lands

    def test_one_line_is_static_and_none_leaves_no_marker(self):
        one = render(hero_lines=["Only this."])
        none = render(hero_lines=[])
        for name in SIDE:
            self.assertEqual(tagline(one[name]), ["Only this."])
            self.assertFalse(
                [n for n in one[name].iter(f"{SVG}g") if clip_of(n) == "tag"]
            )
            self.assertEqual(tagline(none[name]), [])
            self.assertEqual(len(bars(one[name])), 1)
            self.assertEqual(bars(none[name]), [])

    def test_the_bar_is_the_accent_and_the_lines_are_ink_at_both_widths(self):
        for name, root in render().items():
            self.assertEqual(len(bars(root)), 1, name)
            shown = tag_rows(root)
            self.assertTrue(shown, name)
            for line in shown:
                self.assertEqual(line["fill"], kit.INK, name)
            words = [
                line
                for line in lines(root)
                if line["fill"] == kit.BLUE_LIGHT and line["class"] in {"s", "b", "t"}
            ]
            self.assertEqual(words, [], name)  # the keywords are the only blue words

    def test_the_phone_pill_clears_the_tagline(self):
        root = render(availability=NOW)["hero-mobile.svg"]
        pill = pill_of(root)
        base = tag_rows(root)[0]["y"]
        self.assertGreaterEqual(float(pill.attrib["y"]) - base, 16)


class IntroTests(unittest.TestCase):
    """The intro is the ctx sentence, whole, with its keyword phrases in the light blue."""

    def test_the_sentence_is_drawn_whole(self):
        for name, root in render().items():
            body = [line["text"] for line in lines(root) if line["class"] == "b"]
            self.assertEqual(" ".join(body), " ".join(CTX["intro"].split()), name)

    def test_the_keywords_are_accented_and_nothing_else_is(self):
        for name, root in render().items():
            accented = "".join(
                "".join(span.itertext())
                for span in root.iter(f"{SVG}tspan")
                if span.get("fill") == kit.BLUE_LIGHT
            )
            plain = "".join(CTX["intro_keywords"]).replace(" ", "")
            self.assertEqual(accented.replace(" ", ""), plain, name)

    def test_a_keyword_phrase_stays_on_one_line(self):
        whole = [
            keyword for keyword in CTX["intro_keywords"] if keyword in CTX["intro"]
        ]
        split = {}
        for name, root in render().items():
            body = [line["text"] for line in lines(root) if line["class"] == "b"]
            split[name] = [k for k in whole if not any(k in row for row in body)]
        self.assertEqual(split["hero.svg"], [])
        self.assertLessEqual(
            len(split["hero-mobile.svg"]), 1
        )  # only where a line would be left short

    def test_the_unit_wrap_keeps_every_word_at_any_width(self):
        intro, keywords = CTX["intro"], CTX["intro_keywords"]
        for width in range(120, 520, 12):
            rows = hero._wrap_units(intro, keywords, width, 13.5)
            self.assertEqual(" ".join(rows), " ".join(intro.split()), width)
            for row in rows:
                if " " in row:  # a single long word is kit's to split
                    self.assertLessEqual(kit.text_width(row, 13.5), width, row)
                self.assertNotIn(hero.JOIN, row)

    def test_a_longer_intro_grows_the_card_instead_of_crowding_it(self):
        longer = CTX["intro"] + " " + CTX["intro"]
        usual, grown = render(), render(intro=longer)
        for name in SIDE:
            self.assertGreater(size(grown[name])[1], size(usual[name])[1])
            found = lines(grown[name])
            last = max(line["y"] for line in found if line["class"] == "b")
            first_value = min(line["y"] for line in found if line["class"] == "n")
            self.assertGreater(first_value - last, 24, name)
            height = size(grown[name])[1]
            for line in found:
                if not line["reel"]:
                    self.assertLess(line["y"], height - 12, line["text"])

    def test_markup_in_the_data_is_escaped(self):
        risky = 'Builds <fast> & "safe" things.'
        files = hero.render(
            DATA,
            {
                **CTX,
                "intro": risky,
                "intro_keywords": ["<fast>"],
                "hero_lines": ["A & B", "C < D"],
                "availability": "Now: R&D <lab>",
                "greeting": "Hi & hello",
            },
        )
        for name, svg in files.items():
            root = ET.fromstring(svg)  # nosec B314
            body = [line["text"] for line in lines(root) if line["class"] == "b"]
            self.assertEqual(" ".join(body), risky, name)


if __name__ == "__main__":
    unittest.main()
