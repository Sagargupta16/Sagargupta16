"""Checks for the hero card: the two files, their bounds and motion, and what each part reads from ctx.

The shared checks run on the checked-in snapshot and assert rules, never values, so a
data refresh cannot fail them. Each data rule has its own test on a changed context.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405
from itertools import pairwise
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
REELS = {"tag", "run"}  # the clip windows a reel turns in
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


def stage_labels(root: ET.Element) -> list[dict]:
    """The three stage labels and the accounts label, left to right, without their trailing tracking."""
    names = (*hero.STAGES, hero.TARGET)
    found = {line["text"]: line for line in lines(root) if line["text"] in names}
    return [
        {**found[name], "right": found[name]["right"] - found[name]["track"]}
        for name in names
    ]


def cells(root: ET.Element) -> list[tuple[float, float]]:
    """The account cells' absolute (left, right) spans."""
    up = parents(root)
    out = []
    for rect in root.iter(f"{SVG}rect"):
        if rect.get("rx") == "3":
            x = float(rect.attrib["x"]) + shift(rect, up)[0]
            out.append((x, x + float(rect.attrib["width"])))
    return out


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
                if line["hidden"]:  # a change waiting outside the panel for its turn
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
        # a travelling change, the gate's flash and the proof cells waiting their turn
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
                self.assertLessEqual(words, {hero.PASSED, hero.HELD})

    def test_the_still_frame_holds_the_finished_run(self):
        for _, _, root in self.each():
            still = {line["text"] for line in lines(root) if not line["moves"]}
            resting = [line["text"] for line in lines(root) if line["reel"] == "run"]
            self.assertEqual(resting[0], hero.APPLIED)
            shown = {line["text"] for line in lines(root)}
            for word in (*hero.STAGES, hero.TARGET, hero.DENIED, hero.HELD):
                self.assertIn(word, shown)
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

    def test_the_scene_beats_sit_on_one_grid(self):
        beats = [
            hero.DOCK[0],
            hero.DOCK[1],
            hero.DOCK[2],
            hero.DENY,
            hero.ROLLOUT,
            hero.DONE,
        ]
        for beat in beats:
            self.assertEqual(beat % hero.BEAT, 0, beat)
        self.assertGreaterEqual(hero.REWIND, 2.5)  # the finished frame holds this long
        self.assertLess(hero.REWIND + hero.WIPE, hero.DOCK[0])

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
            # the pill's dot and its pulse when there is a line, then the check that closes the run
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
    """The scene's layout rules: whole account columns, evenly spaced labels, and the fork."""

    def test_the_account_columns_are_whole_and_inside_the_panel(self):
        for name, root in render().items():
            _, _, right, _ = panel(root)
            spans = cells(root)
            measures = hero.PHONE if name.endswith("-mobile.svg") else hero.DESKTOP
            # every cell is drawn at rest and again in its ready state
            self.assertEqual(len(spans), 2 * measures["columns"] * measures["rows"])
            self.assertEqual(len({left for left, _ in spans}), measures["columns"])
            self.assertLessEqual(max(r for _, r in spans), right - 12, name)

    def test_the_label_and_the_check_sit_on_the_middle_of_the_whole_block(self):
        for root in render().values():
            spans = cells(root)
            middle = (min(left for left, _ in spans) + max(r for _, r in spans)) / 2
            label = stage_labels(root)[-1]
            self.assertAlmostEqual(
                (label["left"] + label["right"]) / 2, middle, delta=1
            )
            up = parents(root)
            check = next(
                e
                for e in root.iter(f"{SVG}circle")
                if e.get("fill") == kit.GREEN and e.get("r") != "3.5"
            )
            self.assertAlmostEqual(
                float(check.attrib["cx"]) + shift(check, up)[0], middle, delta=0.5
            )

    def test_the_stage_labels_are_evenly_spaced_and_clear_of_the_edge(self):
        for name, root in render().items():
            left, _, right, _ = panel(root)
            labels = stage_labels(root)
            gaps = [b["left"] - a["right"] for a, b in pairwise(labels)]
            self.assertGreaterEqual(min(gaps), 16, (name, gaps))
            self.assertLess(max(gaps) - min(gaps), 0.5, (name, gaps))
            self.assertGreaterEqual(labels[0]["left"], left + 8, name)
            self.assertLessEqual(labels[-1]["right"], right - 12, name)
            self.assertEqual(len({label["y"] for label in labels}), 1)

    def test_the_denied_change_rests_off_the_rail_under_the_fork(self):
        for name, root in render().items():
            labels = stage_labels(root)
            held = next(
                line
                for line in lines(root)
                if line["text"] == hero.HELD and not line["hidden"]
            )
            middle = (held["left"] + held["right"]) / 2
            # between the guardrails and the apply stage, below the label row
            self.assertTrue(
                labels[1]["right"] - 20 < middle < labels[2]["left"] + 20, name
            )
            self.assertGreater(held["y"], labels[0]["y"] + 10, name)
            denied = next(line for line in lines(root) if line["text"] == hero.DENIED)
            self.assertAlmostEqual(denied["y"], held["y"], delta=1)  # one result line
            self.assertGreater(denied["left"], held["right"])
            # the status rows never reach the slot
            _, _, edge, _ = window(root, "run")
            self.assertLess(edge, held["left"] - 4, name)

    def test_a_change_never_covers_a_stage_label(self):
        """Walk the loop: wherever a change can be seen, its chip is clear of every stage label.

        The gap between two labels is narrower than a chip, so the denied change has to be
        out of sight while it drops from the rail to its slot.
        """
        for name, root in render().items():
            up = parents(root)
            boxes = [
                (
                    label["left"],
                    label["y"] - label["size"] * 0.75,
                    label["right"],
                    label["y"] + label["size"] * 0.25,
                )
                for label in stage_labels(root)
            ]
            faces = {}
            for text in root.iter(f"{SVG}text"):
                if "".join(text.itertext()) in (hero.PASSED, hero.HELD):
                    chip = next(e for e in up[text] if e.tag == f"{SVG}rect")
                    faces.setdefault("".join(text.itertext()), []).append(chip)
            # the first change, and the second's travelling and held faces
            self.assertEqual(
                {k: len(v) for k, v in faces.items()}, {hero.PASSED: 1, hero.HELD: 2}
            )

            def seen(chip: ET.Element, second: float) -> tuple[float, tuple]:
                opacity, dx, dy = state(chip, up, second)
                x, y = float(chip.attrib["x"]) + dx, float(chip.attrib["y"]) + dy
                w, h = float(chip.attrib["width"]), float(chip.attrib["height"])
                return opacity, (x, y, x + w, y + h)

            for label, chips in faces.items():
                for chip in chips:
                    for step in range(round(kit.T * 100)):
                        opacity, (x0, y0, x1, y1) = seen(chip, step / 100)
                        if opacity <= 0.001:
                            continue
                        for left, top, right, bottom in boxes:
                            covers = (
                                x0 < right and left < x1 and y0 < bottom and top < y1
                            )
                            self.assertFalse(covers, (name, label, step / 100))
            # the story still reads: the change is seen knocking at the gate, then held in its slot
            travelling, held = faces[hero.HELD][1], faces[hero.HELD][0]
            gate = stage_labels(root)[1]
            opacity, (x0, _, x1, _) = seen(travelling, hero.DENY)
            self.assertGreater(opacity, 0.9, name)
            self.assertAlmostEqual(
                (x0 + x1) / 2, (gate["left"] + gate["right"]) / 2, delta=1
            )
            for second in (hero.LAND + 0.3, 0.0):
                opacity, (_, y0, _, _) = seen(held, second)
                self.assertGreater(opacity, 0.9, (name, second))
                self.assertGreater(
                    y0, max(bottom for *_, bottom in boxes), (name, second)
                )

    def test_the_gate_takes_no_done_mark_and_the_denied_mark_is_an_outline(self):
        for name, root in render().items():
            ticks = [
                e for e in root.iter(f"{SVG}circle") if e.get("fill") == kit.BLUE_EDGE
            ]
            self.assertEqual(len(ticks), 2, name)  # plan and apply
            discs = [e for e in root.iter(f"{SVG}circle") if e.get("fill") == kit.INK]
            self.assertEqual(discs, [], name)

    def test_the_title_names_the_run_and_the_panel_says_landing_zone_nowhere(self):
        desktop, phone = render()["hero.svg"], render()["hero-mobile.svg"]
        shown = [line["text"] for line in lines(desktop)]
        self.assertIn(hero.TITLE, shown)
        for root in (desktop, phone):
            mono = [line["text"] for line in lines(root) if line["class"] in MONO]
            self.assertFalse([text for text in mono if "LANDING" in text])


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
        # the light only changes in two quiet stretches of the scene's loop: while a change
        # waits in the guardrails, and just after the run has closed
        start = hero.PROOF_AT - 0.35
        quiet = [(start, hero.PROOF_AT), (start + kit.T / 2, hero.PROOF_AT + kit.T / 2)]
        for turn in turns(slide):
            at = turn % kit.T
            self.assertTrue(any(a <= at <= b + 0.01 for a, b in quiet), turn)
        beats = {*hero.DOCK, hero.DENY, hero.ROLLOUT, hero.DONE}
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
