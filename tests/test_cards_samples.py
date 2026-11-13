"""Checks for cards/samples.py: the three aws-samples diagram cards, desktop and phone.

Built on the checked-in snapshot through the same loader preview.py uses, so the
cards under test are the ones the README gets. The checks assert rules, never
the snapshot's values.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405 - parses SVG this repo just rendered
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
PHONE_AGENTCORE = "sample-agentcore-harness-mobile.svg"
# the titles the old renderer typed in; two of them had drifted from the portfolio
TYPED_TITLES = (
    "AgentCore Harness with Governed MCP Tools",
    "AWS Organizations Governance",
)
DASHES = (
    chr(0x2013),
    chr(0x2014),
)  # en and em dash, by code point so this file has neither


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314 - our own output


def size_of(root: ET.Element) -> tuple[float, float]:
    _, _, width, height = map(float, root.attrib["viewBox"].split())
    return width, height


def offsets(element: ET.Element) -> list[tuple[float, float]]:
    """Every translate an element can sit at: its transform, or each value an animation gives it."""
    moves = [
        child
        for child in element.findall(f"{SVG}animateTransform")
        if child.get("type") == "translate"
    ]
    if moves:
        return [
            tuple(float(n) for n in value.split())
            for value in moves[0].attrib["values"].split(";")
        ]
    transform = element.get("transform", "")
    if transform.startswith("translate("):
        x, y = (float(n) for n in transform[10:-1].replace(",", " ").split())
        return [(x, y)]
    return [(0.0, 0.0)]


def placed_texts(
    element: ET.Element, origins: list[tuple[float, float]] | None = None
) -> list[tuple[ET.Element, list[tuple[float, float]]]]:
    """Every <text> with each origin its ancestors can put it at."""
    origins = origins or [(0.0, 0.0)]
    here = [(ox + dx, oy + dy) for ox, oy in origins for dx, dy in offsets(element)]
    if element.tag == f"{SVG}text":
        return [(element, here)]
    found = []
    for child in element:
        found.extend(placed_texts(child, here))
    return found


def span(element: ET.Element, phone: bool) -> tuple[float, float]:
    """The left and right edge of a text before any translate, measured the way kit measures."""
    size = float(element.attrib["font-size"])
    family = element.get("font-family", "")
    cls = element.get("class", "")
    if cls == "l":
        width = kit.text_width(element.text or "", size, True, 0 if phone else 0.5)
    elif cls == "m":
        width = kit.text_width(element.text or "", size, True, samples.TAG_TRACK)
    elif "Mono" in family:
        width = kit.text_width(element.text or "", size, True, kit.TRACK)
    else:
        width = kit.text_width(element.text or "", size)
    x = float(element.attrib["x"])
    left = x - width / 2 if element.get("text-anchor") == "middle" else x
    return left, left + width


def with_samples(rows: list[dict]) -> dict[str, str]:
    return samples.render(DATA, {**CTX, "samples": rows})


def sample(key: str, title: str, tags: list[str] | None = None) -> dict:
    return {
        "key": key,
        "title": title,
        "url": "https://github.com/aws-samples/example",
        "date": "January 2026",
        "tags": tags or ["TERRAFORM"],
    }


def motion_of(packet: ET.Element) -> tuple[float, float, list[float], list[float]]:
    """A packet's straight path (start x, end x) with its keyPoints and keyTimes."""
    motion = packet.find(f"{SVG}animateMotion")
    start, end = (
        float(part.split()[0]) for part in motion.attrib["path"].lstrip("M").split("H")
    )
    points = [float(p) for p in motion.attrib["keyPoints"].split(";")]
    times = [float(t) for t in motion.attrib["keyTimes"].split(";")]
    return start, end, points, times


class FileTests(unittest.TestCase):
    def test_every_sample_has_a_desktop_and_a_phone_file(self) -> None:
        expected = {
            f"sample-{row['key']}{suffix}.svg"
            for row in CTX["samples"]
            for suffix in ("", "-mobile")
        }
        self.assertEqual(set(FILES), expected)
        for key in KEYS:
            self.assertIn(f"sample-{key}.svg", FILES)
            self.assertIn(f"sample-{key}-mobile.svg", FILES)

    def test_a_sample_without_a_diagram_is_left_out(self) -> None:
        files = with_samples([sample("not-drawn-yet", "Some Other Sample")])
        self.assertEqual(files, {})

    def test_every_file_is_xml_with_a_label_and_its_width(self) -> None:
        for name, svg in FILES.items():
            with self.subTest(name):
                root = parse(svg)
                width, height = size_of(root)
                self.assertEqual(width, 320 if name.endswith("-mobile.svg") else 410)
                self.assertGreater(height, 200)
                self.assertEqual(root.get("role"), "img")
                self.assertGreater(len(root.get("aria-label", "")), 40)

    def test_render_is_deterministic(self) -> None:
        self.assertEqual(samples.render(DATA, CTX), FILES)


class HouseRuleTests(unittest.TestCase):
    def test_no_en_or_em_dash(self) -> None:
        for name, svg in FILES.items():
            for dash in DASHES:
                with self.subTest(name):
                    self.assertNotIn(dash, svg)

    def test_self_contained(self) -> None:
        for name, svg in FILES.items():
            with self.subTest(name):
                for banned in (
                    "<script",
                    "<foreignObject",
                    "href=",
                    "<image",
                    "@import",
                ):
                    self.assertNotIn(banned, svg)

    def test_no_text_leaves_the_canvas(self) -> None:
        for name, svg in FILES.items():
            root = parse(svg)
            width, height = size_of(root)
            phone = name.endswith("-mobile.svg")
            for element, origins in placed_texts(root):
                left, right = span(element, phone)
                size = float(element.attrib["font-size"])
                y = float(element.attrib["y"])
                for ox, oy in origins:
                    with self.subTest(name, text=element.text, origin=(ox, oy)):
                        self.assertGreaterEqual(left + ox, 0)
                        self.assertLessEqual(right + ox, width)
                        self.assertGreaterEqual(y + oy - size * 0.8, 0)
                        self.assertLessEqual(y + oy, height)

    def test_hidden_marks_are_loop_states_not_entrances(self) -> None:
        """opacity="0" is allowed only on a mark its own repeating loop brings back."""
        for name, svg in FILES.items():
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
                    self.assertIn("1", loops[0].attrib["values"].split(";"))

    def test_label_sizes_stay_above_the_floor(self) -> None:
        for name, svg in FILES.items():
            for element in parse(svg).iter(f"{SVG}text"):
                with self.subTest(name, text=element.text):
                    self.assertGreaterEqual(float(element.attrib["font-size"]), 10)


class TitleTests(unittest.TestCase):
    """Fix: titles come from ctx["samples"], not from strings typed into the renderer."""

    def titles(self, svg: str, phone: bool) -> str:
        lines = [
            element.text or ""
            for element in parse(svg).iter(f"{SVG}text")
            if float(element.attrib["font-size"]) == samples.TITLE_SIZE
            and (phone or element.get("class") == "t")
        ]
        return " ".join(lines)

    def test_each_card_shows_its_portfolio_title(self) -> None:
        for row in CTX["samples"]:
            for suffix in ("", "-mobile"):
                name = f"sample-{row['key']}{suffix}.svg"
                with self.subTest(name):
                    self.assertEqual(
                        self.titles(FILES[name], bool(suffix)), row["title"]
                    )

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

    def test_tags_come_from_ctx_after_the_source(self) -> None:
        files = with_samples(
            [sample("sagemaker-mlops", "A Sample", ["Terraform", "Step Functions"])]
        )
        desktop = files["sample-sagemaker-mlops.svg"]
        self.assertIn(">AWS SAMPLES  |  TERRAFORM  |  STEP FUNCTIONS<", desktop)

    def test_tag_lines_break_only_at_a_separator(self) -> None:
        tags = ["TERRAFORM", "CONTROL TOWER", "ORGANIZATIONS", "SECURITY HUB"]
        lines = samples.tag_lines(tags, 200, 10.5, 1.4)
        self.assertGreater(len(lines), 1)
        self.assertEqual(
            samples.SEPARATOR.join(lines),
            samples.SEPARATOR.join([samples.SOURCE, *tags]),
        )
        for line in lines:
            self.assertFalse(line.startswith("|") or line.endswith("|"))

    def test_a_long_desktop_title_wraps_inside_the_margins(self) -> None:
        for row in CTX["samples"]:
            root = parse(FILES[f"sample-{row['key']}.svg"])
            for element in root.iter(f"{SVG}text"):
                if element.get("class") not in ("t", "m"):
                    continue
                left, right = span(element, False)
                with self.subTest(row["key"], text=element.text):
                    self.assertEqual(left, 20)
                    self.assertLessEqual(right, samples.DESKTOP - 20)
        long = "A Title Long Enough That It Has To Wrap Onto A Second Line"
        root = parse(with_samples([sample(KEYS[0], long)])[f"sample-{KEYS[0]}.svg"])
        lines = [e for e in root.iter(f"{SVG}text") if e.get("class") == "t"]
        self.assertGreater(len(lines), 1)
        for element in lines:
            self.assertLessEqual(span(element, False)[1], samples.DESKTOP - 20)

    def test_desktop_cards_share_one_height(self) -> None:
        heights = {
            size_of(parse(svg))[1]
            for name, svg in FILES.items()
            if not name.endswith("-mobile.svg")
        }
        self.assertEqual(len(heights), 1)
        mixed = with_samples(
            [
                sample("agentcore-harness", "Short"),
                sample(
                    "org-governance",
                    "A Title Long Enough That It Has To Wrap Onto A Second Line",
                ),
            ]
        )
        short = parse(mixed["sample-agentcore-harness.svg"])
        long = parse(mixed["sample-org-governance.svg"])
        self.assertEqual(size_of(short), size_of(long))
        # the lone line sits half a title step lower, centred in the taller foot
        baseline = next(
            float(element.attrib["y"])
            for element in short.iter(f"{SVG}text")
            if element.get("class") == "t"
        )
        self.assertEqual(baseline, samples.FOOT + 28 + samples.TITLE_STEP / 2)

    def test_one_line_titles_keep_the_committed_height(self) -> None:
        files = with_samples([sample(key, "Short") for key in KEYS])
        for key in KEYS:
            with self.subTest(key):
                self.assertEqual(size_of(parse(files[f"sample-{key}.svg"])), (410, 262))


class PhonePacketTests(unittest.TestCase):
    """Fix: on the phone AgentCore card the moving packet must not cross the 9 TOOLS label."""

    def setUp(self) -> None:
        self.root = parse(FILES[PHONE_AGENTCORE])
        self.parents = {
            child: parent for parent in self.root.iter() for child in parent
        }
        self.windows = [
            (
                float(rect.attrib["x"]),
                float(rect.attrib["x"]) + float(rect.attrib["width"]),
            )
            for clip in self.root.iter(f"{SVG}clipPath")
            if clip.get("id") == "ac-wires"
            for rect in clip
        ]
        lane = {name for name, _, _ in samples._AC_LANE}
        self.labels = {
            element.text: span(element, True)
            for element in self.root.iter(f"{SVG}text")
            if element.text in lane
        }
        self.packets = [
            circle
            for circle in self.root.iter(f"{SVG}circle")
            if circle.find(f"{SVG}animateMotion") is not None
        ]

    def clipped(self, element: ET.Element) -> bool:
        while element in self.parents:
            element = self.parents[element]
            if element.get("clip-path") == "url(#ac-wires)":
                return True
        return False

    def test_every_packet_is_clipped_to_the_wires(self) -> None:
        self.assertEqual(len(self.packets), 2)
        self.assertEqual(len(self.windows), 3)
        for packet in self.packets:
            self.assertTrue(self.clipped(packet))

    def test_no_wire_window_reaches_a_label(self) -> None:
        self.assertEqual(
            set(self.labels), {"MCP CLIENT", "CEDAR GATE", "9 TOOLS", "HARNESS"}
        )
        for name, (left, right) in self.labels.items():
            for start, end in self.windows:
                with self.subTest(name, window=(start, end)):
                    self.assertTrue(end <= left or start >= right)

    def test_the_packet_is_never_drawn_over_9_tools(self) -> None:
        """Walk the loop: wherever a packet shows through a window, it is clear of every label."""
        tools_left, tools_right = self.labels["9 TOOLS"]
        passed_tools = []
        for packet in self.packets:
            start, end, points, times = motion_of(packet)
            radius = float(packet.attrib["r"])
            behind = False
            for step in range(1001):
                t = step / 1000
                index = max(i for i, time in enumerate(times) if time <= t)
                share = points[index]
                if index < len(times) - 1:
                    along = (t - times[index]) / (times[index + 1] - times[index])
                    share += along * (points[index + 1] - points[index])
                x = start + share * (end - start)
                behind = behind or tools_left < x < tools_right
                for window_start, window_end in self.windows:
                    seen = (max(x - radius, window_start), min(x + radius, window_end))
                    if seen[0] >= seen[1]:
                        continue
                    for name, (left, right) in self.labels.items():
                        self.assertTrue(
                            seen[1] <= left or seen[0] >= right,
                            f"packet over {name} at t={t}",
                        )
            passed_tools.append(behind)
        # the allowed call does travel past the tools box: behind it, never over it
        self.assertEqual(sorted(passed_tools), [False, True])

    def test_the_packet_rests_whole_on_each_wire(self) -> None:
        allowed = max(self.packets, key=lambda packet: len(motion_of(packet)[2]))
        start, end, points, _ = motion_of(allowed)
        radius = float(allowed.attrib["r"])
        rests = sorted({p for a, p in zip(points, points[1:]) if a == p and 0 < p < 1})
        self.assertEqual(len(rests), len(self.windows))
        for share, (window_start, window_end) in zip(rests, self.windows):
            x = start + share * (end - start)
            self.assertGreaterEqual(x - radius, window_start - 0.05)
            self.assertLessEqual(x + radius, window_end + 0.05)

    def test_the_desktop_diagram_keeps_its_committed_motion(self) -> None:
        desktop = FILES["sample-agentcore-harness.svg"]
        self.assertNotIn("clipPath", desktop)
        self.assertEqual(desktop.count("<animateMotion"), 2)


class MlopsPacketTests(unittest.TestCase):
    """Fix: the SageMaker packet runs on the wires between the boxes, never over a label."""

    NAMES = ("DATA", "TRAIN", "GATE", "DEPLOY", "SERVE")

    def roots(self):
        for phone in (False, True):
            name = f"sample-sagemaker-mlops{'-mobile' if phone else ''}.svg"
            yield phone, parse(FILES[name])

    def test_the_packet_is_clipped_to_the_wires_between_the_boxes(self) -> None:
        for phone, root in self.roots():
            with self.subTest(phone=phone):
                parents = {c: p for p in root.iter() for c in p}
                (clip,) = [
                    c for c in root.iter(f"{SVG}clipPath") if c.get("id") == "ml-wires"
                ]
                self.assertEqual(len(clip), len(self.NAMES) - 1)
                packets = [
                    c
                    for c in root.iter(f"{SVG}circle")
                    if c.find(f"{SVG}animateMotion") is not None
                    and c.get("fill") == kit.INK
                ]
                self.assertEqual(len(packets), 1)
                self.assertEqual(
                    parents[packets[0]].get("clip-path"), "url(#ml-wires)"
                )

    def test_the_packet_is_never_drawn_over_a_box_label(self) -> None:
        """Walk the loop: wherever the packet shows through a window it is clear of every label."""
        for phone, root in self.roots():
            windows = [
                (
                    float(r.attrib["x"]),
                    float(r.attrib["x"]) + float(r.attrib["width"]),
                )
                for c in root.iter(f"{SVG}clipPath")
                if c.get("id") == "ml-wires"
                for r in c
            ]
            labels = {
                e.text: span(e, phone)
                for e in root.iter(f"{SVG}text")
                if e.text in self.NAMES
            }
            self.assertEqual(set(labels), set(self.NAMES))
            packet = next(
                c
                for c in root.iter(f"{SVG}circle")
                if c.find(f"{SVG}animateMotion") is not None
                and c.get("fill") == kit.INK
            )
            start, end, points, times = motion_of(packet)
            radius = float(packet.attrib["r"])
            seen_anywhere = False
            for step in range(1001):
                t = step / 1000
                index = max(i for i, time in enumerate(times) if time <= t)
                share = points[index]
                if index < len(times) - 1:
                    along = (t - times[index]) / (times[index + 1] - times[index])
                    share += along * (points[index + 1] - points[index])
                x = start + share * (end - start)
                for window_start, window_end in windows:
                    shown = (max(x - radius, window_start), min(x + radius, window_end))
                    if shown[0] >= shown[1]:
                        continue
                    seen_anywhere = True
                    for name, (left, right) in labels.items():
                        with self.subTest(phone=phone, name=name, t=t):
                            self.assertTrue(
                                shown[1] <= left or shown[0] >= right,
                                f"packet over {name} at t={t}",
                            )
            self.assertTrue(seen_anywhere)


if __name__ == "__main__":
    unittest.main()
