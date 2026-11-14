"""Checks for the career cards: experience, education and publications, at both widths.

The baseline renders the checked-in snapshot and asserts rules, never values,
so a data refresh cannot fail it. Every data-driven rule has a test built on a
small context of its own, with made-up rows (empty and long ones included).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405 - parses SVG this repo just rendered
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kit
from cards import career

SPEC = importlib.util.spec_from_file_location("render_svgs", SCRIPTS / "render-svgs.py")
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)
renderer.OFFLINE = True

SVG = "{http://www.w3.org/2000/svg}"
FILES = {
    "experience.svg",
    "experience-mobile.svg",
    "education.svg",
    "education-mobile.svg",
    "publications.svg",
    "publications-mobile.svg",
}
DESKTOP = ("experience.svg", "education.svg", "publications.svg")
LONG_DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}  # the loop lengths the page clock allows, in seconds
MONO_TRACKING = {"m": kit.TRACK, "k": 2, "c": 0}  # kit's mono classes
EDGE = 12  # no label comes closer than this to a card's edge
BOXES = {kit.CARD, kit.BLUE_TINT, kit.HAIR_FILL}  # the fills of panels, tiles and chips


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314 - our own output


def contents(svg: str) -> list[str]:
    return [element.text or "" for element in parse(svg).iter(f"{SVG}text")]


def reading(svg: str) -> str:
    """Every label in document order as one upper-case line, so a wrapped label reads whole."""
    return " ".join(" ".join(contents(svg)).upper().split())


def width_of(element: ET.Element) -> float:
    text, size = element.text or "", float(element.attrib["font-size"])
    cls = element.get("class", "")
    if cls in MONO_TRACKING:
        return kit.text_width(text, size, True, MONO_TRACKING[cls]) - MONO_TRACKING[cls]
    return kit.text_width(text, size)


def spans(svg: str) -> list[tuple[str, float, float, float, float]]:
    """Return (text, left, right, baseline, size) for every label, measured the way kit measures."""
    out = []
    for element in parse(svg).iter(f"{SVG}text"):
        width = width_of(element)
        x = float(element.attrib["x"])
        left = {"middle": x - width / 2, "end": x - width}.get(
            element.get("text-anchor", ""), x
        )
        out.append(
            (
                element.text or "",
                left,
                left + width,
                float(element.attrib["y"]),
                float(element.attrib["font-size"]),
            )
        )
    return out


def boxes(svg: str) -> list[tuple[float, float, float, float]]:
    """(x, y, width, height) of every filled panel, tile and chip."""
    return [
        tuple(float(rect.get(key)) for key in ("x", "y", "width", "height"))
        for rect in parse(svg).iter(f"{SVG}rect")
        if rect.get("fill") in BOXES
    ]


def panels(svg: str) -> list[tuple[float, float, float, float]]:
    """The panels and tiles: kit's rx 10 rectangles in the panel fills (chips are HAIR_FILL)."""
    return [
        tuple(float(rect.get(key)) for key in ("x", "y", "width", "height"))
        for rect in parse(svg).iter(f"{SVG}rect")
        if rect.get("fill") in (kit.CARD, kit.BLUE_TINT) and rect.get("rx") == "10"
    ]


def first_on(element: ET.Element) -> float:
    """When a resting-hidden highlight first reaches full opacity, in seconds."""
    animate = element.find(f"{SVG}animate")
    values = animate.get("values").split(";")
    times = [float(t) for t in animate.get("keyTimes").split(";")]
    dur = float(animate.get("dur").removesuffix("s"))
    return times[values.index("1")] * dur


def entrances_end(svg: str) -> float:
    """When the last run-once entrance finishes, in seconds."""
    return max(
        float(animate.get("dur").removesuffix("s"))
        for animate in parse(svg).iter()
        if animate.tag in (f"{SVG}animate", f"{SVG}animateTransform")
        and animate.get("repeatCount") != "indefinite"
    )


def engagement(
    client: str, role: str, when: str, ongoing: bool = False, stack: tuple = ()
) -> dict:
    """One customer engagement in the public snapshot's shape; see customers()."""
    start, _, end = when.partition(" to ")
    return {
        "when": when,
        "client": client,
        "role": role,
        "stack": list(stack),
        "kind": "customer",
        "ongoing": ongoing,
        "start": list(renderer._start_key(start)),
        "end": None if ongoing else list(renderer._start_key(end)),
    }


def customers(*rows: dict) -> list[dict]:
    """The rows as build_context hands them to the cards: numbered oldest first, each with its sector."""
    return renderer._customers(list(rows))


ROWS = [
    engagement("Retail customer", "Cloud Engineer", "Jan 2023 to Jun 2023"),
    engagement("Public sector customer", "DevOps Engineer", "Jul 2023 to Dec 2023"),
    engagement(
        "Global financial services customer",
        "DevOps Consultant",
        "Jan 2024 to Jun 2024",
    ),
    engagement(
        "Financial market infrastructure customer",
        "Senior DevOps Consultant",
        "Jul 2024 to Dec 2024",
    ),
    engagement(
        "Healthcare and life sciences customer",
        "Lead DevOps Consultant",
        "Jan 2025 to Jun 2025",
    ),
    engagement("Enterprise customer", "Platform Lead", "Jul 2025 to now", ongoing=True),
]
CUSTOMERS = customers(*ROWS)
# the label a customer engagement gets when its start month has no CUSTOMER_LABELS entry
GENERIC = engagement(renderer.GENERIC_CUSTOMER, "DevOps Consultant", "Mar 2026 to now")
LONG_SECTOR = engagement(
    "Healthcare, life sciences and public sector research customer",
    "Lead DevOps Consultant and Platform Architect",
    "Sep 2030 to Dec 2030",
    stack=("AWS Organizations", "Control Tower", "Security Hub", "Transit Gateway"),
)
STACK = (
    "Terraform",
    "Example Very Long Service Name For Chips",
    "tftest",
    "PyTest",
    "SNS",
)
EDUCATION = [
    {
        "degree": "Master of Example Studies",
        "school": "Example University",
        "city": "Pune, India",
        "when": "June 2030 to May 2032",
    },
    {
        "degree": "Bachelor of Example Studies",
        "school": "Example College",
        "city": "Nagpur, India",
        "when": "June 2027 to May 2030",
    },
]


def shown(row: dict) -> list[str]:
    """What a row must show on both layouts: its number, its bracketed sector if any, role and dates."""
    sector = [f"({row['sector']})"] if row["sector"] else []
    return [row["title"], *sector, row["role"], row["when"]]


class CareerCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = renderer.load_data()
        with contextlib.redirect_stdout(io.StringIO()):
            cls.ctx = renderer.build_context(cls.data)
        cls.files = career.render(cls.data, cls.ctx)

    def render(self, **changes: object) -> dict[str, str]:
        return career.render(self.data, {**self.ctx, **changes})

    def assert_inside(self, name: str, svg: str) -> None:
        """Every label sits on the canvas and keeps EDGE clear of its sides."""
        _, _, width, height = map(float, parse(svg).attrib["viewBox"].split())
        for text, left, right, baseline, size in spans(svg):
            with self.subTest(file=name, text=text):
                self.assertGreaterEqual(left, EDGE)
                self.assertLessEqual(right, width - EDGE)
                self.assertGreaterEqual(baseline - size, 0)
                self.assertLessEqual(baseline + size * 0.25, height - 8)

    def assert_no_collisions(self, name: str, svg: str) -> None:
        """No two labels on one baseline may run into each other."""
        rows: dict[float, list[tuple[float, float, str]]] = {}
        for text, left, right, baseline, _ in spans(svg):
            rows.setdefault(baseline, []).append((left, right, text))
        for baseline, row in rows.items():
            row.sort()
            for (_, right, first), (left, _, second) in zip(row, row[1:]):
                with self.subTest(file=name, y=baseline, pair=(first, second)):
                    self.assertLessEqual(right, left)

    def assert_in_boxes(self, name: str, svg: str) -> None:
        """A label that starts inside a panel, tile or chip stays inside it, clear of its edges."""
        found = boxes(svg)
        for text, left, right, baseline, size in spans(svg):
            middle = (left + right) / 2
            mid_y = baseline - size * 0.35
            holding = [
                (w * h, (x, y, w, h))
                for x, y, w, h in found
                if x <= middle <= x + w and y <= mid_y <= y + h
            ]
            if not holding:
                continue
            x, y, w, h = min(holding)[1]
            inset = 6 if h <= 24 else 10  # a chip pads its label less than a panel
            with self.subTest(file=name, text=text):
                self.assertGreaterEqual(left, x + inset)
                self.assertLessEqual(right, x + w - inset)
                self.assertGreaterEqual(baseline - size * 0.75, y + 3)
                self.assertLessEqual(baseline + size * 0.25, y + h - 3)

    def assert_sound(self, files: dict[str, str]) -> None:
        for name, svg in files.items():
            parse(svg)
            self.assert_inside(name, svg)
            self.assert_no_collisions(name, svg)
            self.assert_in_boxes(name, svg)

    # ------------------------------------------------------------ every file
    def test_the_module_returns_its_six_files(self) -> None:
        self.assertEqual(set(self.files), FILES)

    def test_every_file_parses_at_its_width_with_a_sentence_for_alt_text(self) -> None:
        for name, svg in self.files.items():
            with self.subTest(file=name):
                root = parse(svg)
                self.assertEqual(root.get("role"), "img")
                self.assertGreater(len(root.get("aria-label", "")), 40)
                self.assertEqual(
                    root.get("width"), "320" if name.endswith("-mobile.svg") else "840"
                )

    def test_a_phone_twin_carries_its_desktop_cards_label(self) -> None:
        for name in ("experience", "education", "publications"):
            with self.subTest(card=name):
                self.assertEqual(
                    parse(self.files[f"{name}.svg"]).get("aria-label"),
                    parse(self.files[f"{name}-mobile.svg"]).get("aria-label"),
                )

    def test_no_text_leaves_the_canvas_or_crowds_its_edge(self) -> None:
        for name, svg in self.files.items():
            self.assert_inside(name, svg)

    def test_labels_on_one_line_never_touch(self) -> None:
        for name, svg in self.files.items():
            self.assert_no_collisions(name, svg)

    def test_every_label_stays_inside_its_panel_tile_or_chip(self) -> None:
        for name, svg in self.files.items():
            self.assert_in_boxes(name, svg)

    def test_no_en_or_em_dash_in_the_cards_or_the_module(self) -> None:
        sources = dict(self.files)
        sources["career.py"] = Path(career.__file__).read_text(encoding="utf-8")
        for name, text in sources.items():
            for dash in LONG_DASHES:
                with self.subTest(file=name, dash=hex(ord(dash))):
                    self.assertNotIn(dash, text)

    def test_every_card_is_poster_safe(self) -> None:
        for name, svg in self.files.items():
            root = parse(svg)
            with self.subTest(file=name):
                self.assertNotIn("prefers-reduced-motion", svg)
                # an entrance holds its start value from 0 s and freezes on the
                # element's own, finished state
                for animate in root.iter(f"{SVG}animate"):
                    if animate.get("repeatCount") == "indefinite":
                        continue
                    self.assertEqual(animate.get("fill"), "freeze")
                    if animate.get("attributeName") == "opacity":
                        self.assertTrue(animate.get("values", "").endswith(";1"))
            # only a highlight rests hidden: it holds no text and a loop lights it
            for element in root.iter():
                if element.get("opacity") != "0":
                    continue
                with self.subTest(file=name, element=element.tag):
                    self.assertFalse(list(element.iter(f"{SVG}text")))
                    self.assertTrue(
                        any(
                            child.get("repeatCount") == "indefinite"
                            for child in element
                        )
                    )

    def test_every_entrance_runs_once_and_is_over_by_about_1_6_s(self) -> None:
        for name, svg in self.files.items():
            with self.subTest(file=name):
                self.assertLessEqual(entrances_end(svg), 1.7)

    def test_every_loop_runs_on_the_page_clock(self) -> None:
        for name, svg in self.files.items():
            root = parse(svg)
            loops = [
                element.get("dur", "")
                for element in root.iter()
                if element.get("repeatCount") == "indefinite"
            ]
            loops += re.findall(r"animation:\w+ ([\d.]+s)", svg)
            with self.subTest(file=name):
                self.assertTrue(loops)  # every card moves
            for dur in loops:
                with self.subTest(file=name, dur=dur):
                    self.assertIn(float(dur.removesuffix("s")), CLOCK)

    def test_every_card_keeps_the_motion_budget(self) -> None:
        for name, svg in self.files.items():
            root = parse(svg)
            moving = {
                id(parent)
                for parent in root.iter()
                for child in parent
                if child.tag in (f"{SVG}animate", f"{SVG}animateTransform")
            }
            with self.subTest(file=name):
                self.assertLessEqual(len(moving), 40)

    def test_text_sizes_keep_the_floor(self) -> None:
        for name, svg in self.files.items():
            phone = name.endswith("-mobile.svg")
            for element in parse(svg).iter(f"{SVG}text"):
                size = float(element.attrib["font-size"])
                mono = element.get("class") in MONO_TRACKING
                floor = (kit.MICRO_PHONE if mono else 13) if phone else kit.MICRO
                with self.subTest(file=name, text=element.text):
                    self.assertGreaterEqual(size, floor)

    def test_each_eyebrow_carries_data_not_the_section_name(self) -> None:
        words = {
            "experience": ("CAREER", "EXPERIENCE"),
            "education": ("EDUCATION",),
            "publications": ("PUBLICATIONS", "RECOGNITION"),
        }
        for name, svg in self.files.items():
            eyebrow = contents(svg)[0].upper()
            with self.subTest(file=name, eyebrow=eyebrow):
                self.assertRegex(eyebrow, r"\d")
                for word in words[name.split("-")[0].removesuffix(".svg")]:
                    self.assertNotIn(word, eyebrow)

    def test_rendering_is_deterministic(self) -> None:
        self.assertEqual(career.render(self.data, self.ctx), self.files)

    # ------------------------------------------------------------ the snapshot's rules
    def test_both_layouts_show_the_snapshots_newest_engagements(self) -> None:
        rows = self.ctx["engagements"][-career.ENGAGEMENTS_SHOWN :]
        self.assertTrue(rows)
        for name in ("experience.svg", "experience-mobile.svg"):
            text = reading(self.files[name])
            for row in rows:
                with self.subTest(file=name, when=row["when"]):
                    for fact in shown(row):
                        self.assertIn(fact.upper(), text)
                    # the table label is only ever shown as the bracketed sector
                    if row["sector"]:
                        self.assertNotIn(row["client"].upper(), text)

    def test_a_program_in_the_data_never_reaches_the_cards(self) -> None:
        pf = self.data["portfolio"]
        program = {
            "name": "Example Pipeline (SME Program)",
            "date": "Jun 2031 - Aug 2031",
        }
        data = {
            **self.data,
            "portfolio": {**pf, "engagements": [*pf["engagements"], program]},
        }
        with contextlib.redirect_stdout(io.StringIO()):
            ctx = renderer.build_context(data)
        self.assertEqual({row["kind"] for row in ctx["engagements"]}, {"customer"})
        files = career.render(data, ctx)
        for name in ("experience.svg", "experience-mobile.svg"):
            text = reading(files[name])
            label = parse(files[name]).get("aria-label").upper()
            for gone in ("EXAMPLE PIPELINE", "SME", *renderer.PROGRAMS.values()):
                with self.subTest(file=name, text=gone):
                    self.assertNotIn(gone.upper(), text)
                    self.assertNotIn(gone.upper(), label)

    # ------------------------------------------------------------ experience: rows from the context
    def test_engagements_come_from_the_context_on_both_layouts(self) -> None:
        rows = customers(
            engagement("Telecom customer", "Release Manager", "Mar 2031 to Sep 2031"),
            engagement(
                "Energy customer", "Platform Lead", "Oct 2031 to now", ongoing=True
            ),
        )
        files = self.render(engagements=rows)
        for name in ("experience.svg", "experience-mobile.svg"):
            text = reading(files[name])
            with self.subTest(file=name):
                for row in rows:
                    for fact in shown(row):
                        self.assertIn(fact.upper(), text)
                # nothing typed into the module may stand in for a row
                self.assertNotIn("TERRAFORM MODULE LIBRARY", text)
                self.assertNotIn("ENTERPRISE", text)
                self.assertIn(
                    "Customer 1 (Telecom), Release Manager (Mar 2031 to Sep 2031)",
                    parse(files[name]).get("aria-label"),
                )
        self.assert_sound(files)

    def test_the_alt_text_names_each_row_by_number_and_sector(self) -> None:
        rows = customers(*ROWS[:2], GENERIC)
        label = parse(self.render(engagements=rows)["experience.svg"]).get("aria-label")
        self.assertTrue(
            label.endswith(
                ". Customer engagements at AWS: "
                "Customer 1 (Retail), Cloud Engineer (Jan 2023 to Jun 2023); "
                "Customer 2 (Public sector), DevOps Engineer (Jul 2023 to Dec 2023); "
                "Customer 3, DevOps Consultant (Mar 2026 to now)"
            ),
            label,
        )

    def test_the_eyebrow_counts_every_engagement_and_the_span(self) -> None:
        for count in (1, 3, 6):
            files = self.render(engagements=customers(*ROWS[:count]))
            noun = "ENGAGEMENT" if count == 1 else "ENGAGEMENTS"
            first = self.ctx["milestones"][0]["year"]
            for name in ("experience.svg", "experience-mobile.svg"):
                eyebrow = contents(files[name])[0]
                with self.subTest(file=name, rows=count):
                    self.assertTrue(eyebrow.startswith(f"{first} TO NOW | {count} "))
                    self.assertTrue(eyebrow.endswith(f"{noun} AT AWS"))
            self.assertEqual(
                contents(files["experience.svg"])[0],
                f"{first} TO NOW | {count} CUSTOMER {noun} AT AWS",
            )

    def test_the_phone_lists_engagements_newest_first(self) -> None:
        for rows in (CUSTOMERS[:3], CUSTOMERS[2:]):
            text = reading(self.render(engagements=rows)["experience-mobile.svg"])
            order = [text.index(row["title"].upper()) for row in rows]
            with self.subTest(rows=len(rows), ongoing=rows[-1]["ongoing"]):
                self.assertEqual(order, sorted(order, reverse=True))

    def test_the_phone_opens_on_the_current_role_and_the_ongoing_engagement(
        self,
    ) -> None:
        rows = CUSTOMERS[2:]
        svg = self.render(engagements=rows)["experience-mobile.svg"]
        texts = contents(svg)
        current = self.ctx["milestones"][-1]
        ongoing = rows[-1]
        self.assertEqual(texts[1], f"{current['year']}  FULL TIME")
        self.assertLess(texts.index(ongoing["title"]), texts.index(rows[-2]["title"]))
        # the NOW panel is the first panel, and the ongoing row sits inside it
        now = panels(svg)[0]
        baseline = next(s[3] for s in spans(svg) if s[0] == ongoing["title"])
        self.assertTrue(now[1] < baseline < now[1] + now[3])

    def test_a_sector_sits_right_under_its_title_and_the_role_follows(self) -> None:
        rows = customers(ROWS[0], ROWS[1], ROWS[5])
        for name in ("experience.svg", "experience-mobile.svg"):
            texts = contents(self.render(engagements=rows)[name])
            for row in rows:
                with self.subTest(file=name, title=row["title"]):
                    at = texts.index(row["title"])
                    self.assertEqual(texts[at + 1], f"({row['sector']})")
                    self.assertEqual(texts[at + 2], f"{row['role']}, AWS".upper())

    def test_a_row_with_the_generic_label_draws_no_bracket_line(self) -> None:
        def brackets(svg: str) -> list[str]:
            return [t for t in contents(svg) if t.startswith("(") and t.endswith(")")]

        rows = customers(ROWS[0], GENERIC)
        files = self.render(engagements=rows)
        career_only = self.render(engagements=[])  # a milestone may wrap a bracket too
        for name in ("experience.svg", "experience-mobile.svg"):
            texts = contents(files[name])
            with self.subTest(file=name):
                rest = brackets(career_only[name])
                self.assertEqual(
                    [b for b in brackets(files[name]) if b not in rest], ["(Retail)"]
                )
                self.assertIn("Customer 2", texts)
                for text in texts:
                    self.assertNotIn("(AWS)", text)
                    self.assertNotIn("AWS CUSTOMER", text.upper())

    def test_no_engagements_leaves_no_empty_heading(self) -> None:
        files = self.render(engagements=[])
        for name in ("experience.svg", "experience-mobile.svg"):
            with self.subTest(file=name):
                self.assertNotIn("ENGAGEMENTS", reading(files[name]))
                self.assert_inside(name, files[name])
                self.assertFalse(
                    [p for p in panels(files[name]) if name == "experience.svg"]
                )
        self.assert_sound(files)

    def test_the_heading_names_customer_engagements(self) -> None:
        files = self.render(engagements=CUSTOMERS[:3])
        for name in ("experience.svg", "experience-mobile.svg"):
            with self.subTest(file=name):
                self.assertIn("CUSTOMER ENGAGEMENTS", contents(files[name]))
        self.assertIn(
            ". Customer engagements at AWS: Customer 1 (Retail), Cloud Engineer",
            parse(files["experience.svg"]).get("aria-label"),
        )

    def test_every_role_says_it_was_held_at_aws(self) -> None:
        for name in ("experience.svg", "experience-mobile.svg"):
            text = reading(self.render(engagements=CUSTOMERS[:3])[name])
            for row in CUSTOMERS[:3]:
                with self.subTest(file=name, role=row["role"]):
                    self.assertIn(f"{row['role']}, AWS".upper(), text)

    # ------------------------------------------------------------ experience: the newest four
    def test_both_layouts_keep_the_newest_four_and_never_renumber_them(self) -> None:
        for count in (5, 6):
            files = self.render(engagements=customers(*ROWS[:count]))
            for name in ("experience.svg", "experience-mobile.svg"):
                titles = {
                    t for t in contents(files[name]) if re.fullmatch(r"Customer \d+", t)
                }
                with self.subTest(file=name, rows=count):
                    # the newest four keep the numbers counted over every row
                    self.assertEqual(
                        titles, {f"Customer {n}" for n in range(count - 3, count + 1)}
                    )
            self.assertIn(
                f"CUSTOMER ENGAGEMENTS, NEWEST 4 OF {count}",
                contents(files["experience.svg"]),
            )
            self.assertIn(
                f"+{count - 4} EARLIER", contents(files["experience-mobile.svg"])
            )
            stops = [
                circle
                for circle in parse(files["experience.svg"]).iter(f"{SVG}circle")
                if circle.get("r") == str(career.STOP_R)
            ]
            self.assertEqual(len(stops), len(self.ctx["milestones"]) + 4)
            self.assertEqual(len(panels(files["experience.svg"])), 4)
            self.assert_sound(files)

    def test_a_full_rail_of_long_labels_never_collides_or_leaves_the_card(self) -> None:
        for count in (1, 2, 3, 4, 5):
            for extra in ([], [GENERIC]):
                rows = customers(*extra, *[LONG_SECTOR] * count)
                with self.subTest(rows=count, generic=bool(extra)):
                    self.assert_sound(self.render(engagements=rows))

    def test_a_sector_wraps_to_the_width_of_its_panel(self) -> None:
        sector = "(Financial market infrastructure)"
        three = contents(
            self.render(engagements=customers(ROWS[0], ROWS[3], ROWS[5]))[
                "experience.svg"
            ]
        )
        four = contents(
            self.render(engagements=customers(ROWS[0], ROWS[1], ROWS[3], ROWS[5]))[
                "experience.svg"
            ]
        )
        # three panels hold the sector on one line; four narrower ones do not
        self.assertIn(sector, three)
        self.assertNotIn(sector, four)
        self.assertIn("infrastructure)", four)

    def test_engagement_panels_share_one_height_and_fill_the_width(self) -> None:
        for count in (2, 3, 4):
            rows = customers(*ROWS[: count - 1], LONG_SECTOR)
            boxes_ = panels(self.render(engagements=rows)["experience.svg"])
            with self.subTest(rows=count):
                self.assertEqual(len(boxes_), count)
                self.assertEqual(len({h for _, _, _, h in boxes_}), 1)
                self.assertEqual(min(x for x, _, _, _ in boxes_), 24)
                self.assertAlmostEqual(
                    max(x + w for x, _, w, _ in boxes_), 816, delta=1
                )

    def test_every_role_starts_at_one_y_whatever_its_sector(self) -> None:
        # oldest first: a short sector, one that wraps, a short one, and none at all
        rows = customers(ROWS[0], ROWS[3], ROWS[5], GENERIC)
        root = parse(self.render(engagements=rows)["experience.svg"])
        sub_y = max(
            float(c.get("cy"))
            for c in root.iter(f"{SVG}circle")
            if c.get("r") == str(career.STOP_R)
        )

        def lines(cls: str) -> dict[float, list[float]]:
            """The baselines under the engagement rail in one class, by stop."""
            out: dict[float, list[float]] = {}
            for element in root.iter(f"{SVG}text"):
                y = float(element.get("y"))
                if y > sub_y and element.get("class") == cls:
                    if element.get("fill") == kit.META:
                        out.setdefault(float(element.get("x")), []).append(y)
            return out

        roles, sectors = lines("m"), lines("b")
        self.assertEqual(len(roles), len(rows))
        self.assertEqual(len({min(ys) for ys in roles.values()}), 1)
        # the generic row draws no sector, and the others take different line counts
        self.assertEqual(len(sectors), len(rows) - 1)
        self.assertGreater(len({len(ys) for ys in sectors.values()}), 1)
        role_top = min(min(ys) for ys in roles.values()) - kit.MICRO * 0.75
        for x, ys in sectors.items():
            with self.subTest(x=x):
                self.assertLess(max(ys) + career.SECTOR * 0.25, role_top)

    def test_a_long_role_wraps_and_the_card_grows_for_it(self) -> None:
        long = engagement(
            "Retail customer",
            "Lead DevOps Consultant and Platform Architect",
            "Sep 2030 to Dec 2030",
        )
        short = self.render(engagements=CUSTOMERS[-4:])["experience.svg"]
        tall = self.render(engagements=customers(*ROWS[-3:], long))["experience.svg"]
        role = f"{long['role']}, AWS".upper()
        self.assertNotIn(role, contents(tall))
        self.assertIn(role, reading(tall))
        self.assertGreater(
            float(parse(tall).get("height")), float(parse(short).get("height"))
        )

    # ------------------------------------------------------------ experience: stack chips
    def test_stack_chips_come_from_the_engagement_in_order_and_at_most_three(
        self,
    ) -> None:
        rows = customers(
            engagement(
                "Retail customer", "Cloud Engineer", "Jan 2023 to Jun 2023", stack=STACK
            ),
            engagement(
                "Public sector customer", "Platform Lead", "Jul 2023 to now", True
            ),
        )
        files = self.render(engagements=rows)
        for name in ("experience.svg", "experience-mobile.svg"):
            chips = [
                t
                for t in contents(files[name])
                if t in STACK or t in ("Terraform", "tftest", "PyTest", "SNS")
            ]
            with self.subTest(file=name):
                if name == "experience.svg":
                    # names in the stack's order; one too wide for the panel is passed over
                    self.assertEqual(chips, ["Terraform", "tftest", "PyTest"])
                else:
                    # the phone draws chips for the ongoing engagement only, which has none
                    self.assertEqual(chips, [])
            self.assert_in_boxes(name, files[name])

    def test_the_ongoing_engagement_gets_its_chips_on_the_phone(self) -> None:
        rows = customers(
            engagement(
                "Retail customer", "Platform Lead", "Jul 2023 to now", True, STACK
            ),
        )
        texts = contents(self.render(engagements=rows)["experience-mobile.svg"])
        chips = [t for t in texts if t in STACK]
        self.assertTrue(1 <= len(chips) <= 3)
        self.assertEqual(chips, [s for s in STACK if s in chips])

    # ------------------------------------------------------------ experience: live and the run
    def test_green_marks_only_the_current_role_and_the_ongoing_engagement(self) -> None:
        for rows, live in ((CUSTOMERS[2:], 2), (CUSTOMERS[:3], 1)):
            files = self.render(engagements=rows)
            for name in ("experience.svg", "experience-mobile.svg"):
                root = parse(files[name])
                green = [
                    t.text
                    for t in root.iter(f"{SVG}text")
                    if t.get("fill") == kit.GREEN
                ]
                wanted = [f"{self.ctx['milestones'][-1]['year']}  FULL TIME"]
                if live == 2:
                    wanted.append(rows[-1]["when"].upper())
                with self.subTest(file=name, live=live):
                    self.assertEqual(sorted(green), sorted(wanted))

    def test_a_live_dot_enters_with_its_stop(self) -> None:
        files = self.render(engagements=[*CUSTOMERS[:2], CUSTOMERS[5]])
        root = parse(files["experience.svg"])
        parents = {child: parent for parent in root.iter() for child in parent}
        pulses = [
            c
            for c in root.iter(f"{SVG}circle")
            if any(a.get("attributeName") == "r" for a in c)
        ]
        # the current role and the one ongoing engagement, and no other stop
        self.assertEqual(len(pulses), 2)
        self.assertEqual({ring.get("stroke") for ring in pulses}, {kit.GREEN})
        for ring in pulses:
            group = parents[ring]
            self.assertEqual(group.tag, f"{SVG}g")
            entrance = group[0]
            self.assertEqual(entrance.get("attributeName"), "opacity")
            self.assertTrue(entrance.get("values").startswith("0;0;"))
            self.assertGreater(float(entrance.get("keyTimes").split(";")[1]), 0)
            # the stop's labels sit in the same group, so they enter together
            self.assertTrue(list(group.iter(f"{SVG}text")))

    def test_an_engagement_that_ended_is_not_drawn_live(self) -> None:
        root = parse(self.render(engagements=CUSTOMERS[:3])["experience.svg"])
        pulses = [
            c
            for c in root.iter(f"{SVG}circle")
            if any(a.get("attributeName") == "r" for a in c)
        ]
        self.assertEqual(len(pulses), 1)  # the current role only
        self.assertEqual(pulses[0].get("cy"), str(career.RAIL_Y))

    def test_the_run_travels_the_rails_in_order_and_lights_each_panel_in_turn(
        self,
    ) -> None:
        for count in (2, 3, 4):
            rows = customers(*ROWS[-count:])
            svg = self.render(engagements=rows)["experience.svg"]
            root = parse(svg)
            beams = [p for p in root.iter(f"{SVG}path") if p.get("pathLength") == "100"]
            starts, ends = [], []
            for beam in beams:
                animate = beam.find(f"{SVG}animate")
                begin = float(animate.get("begin", "0s").removesuffix("s"))
                travel = float(animate.get("keyTimes").split(";")[1])
                starts.append(begin)
                ends.append(
                    begin + travel * float(animate.get("dur").removesuffix("s"))
                )
            with self.subTest(rows=count):
                # along the milestone rail, down and back along the bracket, through the engagements
                self.assertEqual(len(beams), 3)
                self.assertEqual(starts, sorted(starts))
                # the light leaves once every entrance is over
                self.assertGreaterEqual(starts[0], entrances_end(svg))
                for end, start in zip(ends, starts[1:]):
                    self.assertAlmostEqual(end, start, places=2)
                self.assertLess(ends[-1], 12)
                lights = sorted(
                    (float(r.get("x")), first_on(r))
                    for r in root.iter(f"{SVG}rect")
                    if r.get("opacity") == "0" and r.get("stroke") == kit.SKY
                )
                self.assertEqual(len(lights), count)
                times = [at for _, at in lights]
                self.assertEqual(times, sorted(times))
                self.assertGreaterEqual(times[0], starts[2])
                self.assertLess(times[-1], 12)

    def test_the_phone_light_climbs_the_rail_into_the_now_panel(self) -> None:
        svg = self.render(engagements=CUSTOMERS[2:])["experience-mobile.svg"]
        root = parse(svg)
        beam = next(p for p in root.iter(f"{SVG}path") if p.get("pathLength") == "100")
        _, bottom, top = map(
            float, re.match(r"M([\d.]+) ([\d.]+)V([\d.]+)", beam.get("d")).groups()
        )
        self.assertGreater(bottom, top)  # it runs up, oldest to newest
        now = panels(svg)[0]
        self.assertAlmostEqual(top, now[1] + now[3], delta=0.5)
        light = next(r for r in root.iter(f"{SVG}rect") if r.get("opacity") == "0")
        self.assertEqual(float(light.get("y")), now[1])

    # ------------------------------------------------------------ experience: the rails
    def test_milestones_come_from_the_context(self) -> None:
        milestones = [
            {
                "year": "2030",
                "what": "Diploma",
                "where": "Example Institute",
                "city": "Pune, India",
                "kind": "study",
                "current": False,
            },
            {
                "year": "2033",
                "what": "Principal Platform Engineer",
                "where": "Example Cloud",
                "city": "Pune, India",
                "kind": "work",
                "current": True,
            },
        ]
        files = self.render(milestones=milestones)
        for name in ("experience.svg", "experience-mobile.svg"):
            text = reading(files[name])
            with self.subTest(file=name):
                for stop in milestones:
                    for key in ("year", "what", "where", "city"):
                        self.assertIn(stop[key].upper(), text)
                self.assertNotIn("NIT WARANGAL", text)
                self.assertTrue(contents(files[name])[0].startswith("2030 TO NOW"))
        self.assertIn("2033  FULL TIME", contents(files["experience.svg"]))
        self.assertNotIn("2030  FULL TIME", contents(files["experience.svg"]))
        self.assert_sound(files)

    def test_a_long_milestone_rail_wraps_its_titles_and_keeps_its_labels_apart(
        self,
    ) -> None:
        milestones = [
            {
                "year": str(2020 + n),
                "what": f"Example Senior Platform Engineering Role Number {n}",
                "where": "Example Organisation",
                "city": "Example City, India",
                "kind": "work",
                "current": n == 5,
            }
            for n in range(6)
        ]
        files = self.render(milestones=milestones)
        self.assert_sound(files)
        # the titles wrap rather than shrink below the type scale
        self.assertNotIn(milestones[0]["what"], contents(files["experience.svg"]))

    def test_the_outer_stops_keep_their_labels_on_the_cards_padding(self) -> None:
        texts = spans(self.files["experience.svg"])
        rail = [s for s in texts if s[3] < 200]  # the milestone rail's labels
        self.assertAlmostEqual(min(left for _, left, _, _, _ in rail), 24, delta=0.5)
        self.assertAlmostEqual(max(right for _, _, right, _, _ in rail), 816, delta=0.5)

    def test_no_bracket_tick_runs_through_a_label(self) -> None:
        for rows in (CUSTOMERS[:2], CUSTOMERS[:4], customers(*ROWS[:3], GENERIC)):
            svg = self.render(engagements=rows)["experience.svg"]
            ticks = [
                path
                for path in parse(svg).iter(f"{SVG}path")
                if path.get("stroke") == kit.HAIR_STRONG
                and "stroke-width" not in path.attrib
            ]
            self.assertEqual(len(ticks), 1)
            segments = [
                tuple(map(float, match))
                for match in re.findall(
                    r"M([\d.]+) ([\d.]+)V([\d.]+)", ticks[0].get("d")
                )
            ]
            self.assertEqual(len(segments), len(rows))
            for x, top, bottom in segments:
                self.assertGreater(bottom, top)  # still a tick down from the bracket
                for text, left, right, baseline, size in spans(svg):
                    if left <= x <= right:
                        with self.subTest(text=text, x=x):
                            glyph_top = baseline - size * 0.75
                            self.assertFalse(
                                top < baseline and bottom > glyph_top,
                                f"tick at x={x:g} ({top:g} to {bottom:g}) crosses {text!r}",
                            )

    def test_the_bracket_starts_below_the_current_roles_city(self) -> None:
        root = parse(self.files["experience.svg"])
        bracket = next(
            p for p in root.iter(f"{SVG}path") if p.get("stroke-dasharray") == "3 4"
        )
        start = float(re.match(r"M[\d.]+ ([\d.]+)V", bracket.get("d")).group(1))
        city = self.ctx["milestones"][-1]["city"].upper()
        baseline = max(
            y
            for text, _, _, y, _ in spans(self.files["experience.svg"])
            if text == city
        )
        self.assertGreater(start, baseline)

    # ------------------------------------------------------------ publications
    def test_panels_come_from_the_context(self) -> None:
        groups = [
            ("REVIEWS", [("Reviewed a design guide", "2031")]),
            ("TALKS", [("Spoke about release trains", "2032")]),
            ("PROGRAMS", [("Mentor of the year", "2033"), ("Guild lead", "2031")]),
        ]
        files = self.render(recognition=groups)
        for name in ("publications.svg", "publications-mobile.svg"):
            labels = contents(files[name])
            with self.subTest(file=name):
                wanted = [
                    entry
                    for title, items in groups
                    for entry in (title, *(part for item in items for part in item))
                ]
                found = [label for label in labels if label in wanted]
                # every title and row, in the context's order
                self.assertEqual(found, wanted)
                self.assertNotIn("AMBASSADOR", reading(files[name]))
                self.assertEqual(labels[0], "2031 TO 2033 | 4 ENTRIES")
        label = parse(files["publications.svg"]).get("aria-label")
        self.assertIn("Mentor of the year (2033)", label)
        self.assert_sound(files)

    def test_a_single_group_spans_the_card_and_none_leaves_only_the_eyebrow(
        self,
    ) -> None:
        one = self.render(recognition=[("TALKS", [("One talk", "2031")])])
        self.assertEqual([w for _, _, w, _ in panels(one["publications.svg"])], [792])
        self.assertEqual(
            [w for _, _, w, _ in panels(one["publications-mobile.svg"])], [288]
        )
        for name, svg in self.render(recognition=[]).items():
            if name.startswith("publications"):
                with self.subTest(file=name):
                    self.assertFalse(panels(svg))
                    self.assertEqual(contents(svg), ["0 ENTRIES"])

    def test_the_panels_fill_the_width_and_every_column_ends_on_one_line(self) -> None:
        many = [
            (
                "REVIEWS",
                [
                    (
                        "Reviewed a guide for multi-account landing zones and their guardrails",
                        "2031",
                    )
                ],
            ),
            (
                "TALKS",
                [
                    ("Spoke about release trains", "2032"),
                    ("Spoke about drift", "2032-2033"),
                ],
            ),
            (
                "PROGRAMS",
                [
                    (f"Example recognition {n} with a longer title", "2033")
                    for n in range(9)
                ],
            ),
        ]
        small = [
            ("A", [("one", "2031")]),
            ("B", [("two", "2032")]),
            ("C", [("three", "2031")]),
        ]
        for groups in (many, small, many[:2], [*small, ("D", [("four", "2030")])]):
            files = self.render(recognition=groups)
            svg = files["publications.svg"]
            found = panels(svg)
            with self.subTest(groups=len(groups), items=sum(len(i) for _, i in groups)):
                self.assertEqual(len(found), len(groups))
                self.assertEqual(min(x for x, _, _, _ in found), 24)
                self.assertAlmostEqual(max(x + w for x, _, w, _ in found), 816, delta=1)
                bottoms: dict[float, float] = {}
                for x, y, _, h in found:
                    bottoms[x] = max(bottoms.get(x, 0), y + h)
                self.assertEqual(len({round(b, 1) for b in bottoms.values()}), 1)
                self.assert_sound(files)

    def test_one_lit_border_steps_from_panel_to_panel(self) -> None:
        for name, svg in self.files.items():
            if not name.startswith("publications"):
                continue
            root = parse(svg)
            found = panels(svg)
            lit = [
                r
                for r in root.iter(f"{SVG}rect")
                if r.get("fill") == "none" and r.get("stroke") == kit.BLUE_EDGE
            ]
            with self.subTest(file=name):
                self.assertEqual(len(lit), len(found))
                # the first is lit at rest, the others rest hidden
                self.assertEqual([r.get("opacity") for r in lit].count(None), 1)
                starts = [first_on(r) for r in lit[1:]]
                self.assertEqual(starts, sorted(starts))

    def test_a_long_item_wraps_only_its_first_line_round_the_year(self) -> None:
        text = "Peer reviewer for a long example guidance series on multi-account platform patterns"
        svg = self.render(
            recognition=[
                ("REVIEWS", [(text, "2025-2026")]),
                ("TALKS", [("One talk", "2031")]),
            ]
        )["publications-mobile.svg"]
        lines = [s for s in spans(svg) if s[0] and s[0] in text and len(s[0]) > 8]
        year = next(s for s in spans(svg) if s[0] == "2025-2026")
        self.assertGreater(len(lines), 1)
        self.assertEqual(" ".join(s[0] for s in lines), text)
        self.assertEqual(lines[0][3], year[3])  # the year rides the first line
        self.assertLess(lines[0][2], year[1])
        self.assertGreater(
            max(s[2] for s in lines[1:]), year[1]
        )  # the rest use the full width

    # ------------------------------------------------------------ education
    def test_education_comes_from_the_context(self) -> None:
        files = self.render(education=EDUCATION)
        for name in ("education.svg", "education-mobile.svg"):
            text = reading(files[name])
            with self.subTest(file=name):
                for row in EDUCATION:
                    for fact in (
                        row["degree"],
                        row["school"],
                        row["city"],
                        row["when"],
                    ):
                        self.assertIn(fact.upper(), text)
                # the degree, dates, school and city only: no grade, no division
                self.assertNotIn("CGPA", text)
                self.assertNotIn("DISTINCTION", text)
                self.assertNotIn("WARANGAL", text)
                self.assertEqual(contents(files[name])[0], "2 DEGREES | 2027 TO 2032")
        self.assertEqual(
            parse(files["education.svg"]).get("aria-label"),
            "Education: Master of Example Studies, Example University, Pune, India, "
            "June 2030 to May 2032; Bachelor of Example Studies, "
            "Example College, Nagpur, India, June 2027 to May 2030",
        )
        self.assert_sound(files)

    def test_the_degrees_sit_side_by_side_oldest_first_and_newest_first_on_the_phone(
        self,
    ) -> None:
        files = self.render(education=EDUCATION)
        desktop = panels(files["education.svg"])
        self.assertEqual(len(desktop), 2)
        self.assertEqual(len({y for _, y, _, _ in desktop}), 1)  # one row
        texts = contents(files["education.svg"])
        self.assertLess(
            texts.index("Bachelor of Example Studies"),
            texts.index("Master of Example Studies"),
        )
        phone = contents(files["education-mobile.svg"])
        self.assertLess(
            phone.index("Master of Example Studies"),
            phone.index("Bachelor of Example Studies"),
        )

    def test_a_long_degree_wraps_and_its_tile_grows_with_its_neighbour(self) -> None:
        long = {
            **EDUCATION[0],
            "degree": "Master of Example Studies in Distributed Platform Engineering and Applied Research",
            "school": "Example Institute of Technology and Applied Research",
            "city": "Thiruvananthapuram, India",
        }
        short = panels(self.render(education=EDUCATION)["education.svg"])
        files = self.render(education=[long, EDUCATION[1]])
        tall = panels(files["education.svg"])
        self.assertGreater(tall[0][3], short[0][3])
        self.assertEqual(len({h for _, _, _, h in tall}), 1)
        self.assertNotIn(long["degree"], contents(files["education.svg"]))
        self.assertIn(long["degree"].upper(), reading(files["education.svg"]))
        self.assert_sound(files)

    def test_no_degrees_leaves_a_card_that_still_parses(self) -> None:
        files = self.render(education=[])
        for name in ("education.svg", "education-mobile.svg"):
            with self.subTest(file=name):
                self.assertFalse(panels(files[name]))
                self.assertEqual(contents(files[name]), ["0 DEGREES"])

    def test_the_education_light_crosses_the_degrees_in_the_order_they_were_taken(
        self,
    ) -> None:
        degrees = ("Bachelor of Example Studies", "Master of Example Studies")
        for name in ("education.svg", "education-mobile.svg"):
            svg = self.render(education=EDUCATION)[name]
            lights = [
                r for r in parse(svg).iter(f"{SVG}rect") if r.get("opacity") == "0"
            ]
            lit = {}
            for text, left, _, baseline, _ in spans(svg):
                if text not in degrees:
                    continue
                for light in lights:
                    x, y = float(light.get("x")), float(light.get("y"))
                    w, h = float(light.get("width")), float(light.get("height"))
                    if x <= left <= x + w and y <= baseline <= y + h:
                        lit[text] = first_on(light)
            with self.subTest(file=name):
                self.assertEqual(len(lights), 2)
                self.assertLess(lit[degrees[0]], lit[degrees[1]])

    def test_the_education_phone_card_never_starts_or_ends_a_line_on_a_dot(
        self,
    ) -> None:
        rows = [
            {
                "degree": "Master of Example Studies",
                "school": "Example Institute of Technology and Applied Research",
                "city": "Pune, India",
                "when": "June 2030 to May 2032",
            },
            *self.ctx["education"],
        ]
        for school in ("Example University", "Devi Ahilya Vishwavidyalaya (DAVV)"):
            rows.append({**rows[0], "school": school, "city": "Indore, India"})
        files = self.render(education=rows)
        for line in contents(files["education-mobile.svg"]):
            with self.subTest(line=line):
                self.assertFalse(line.rstrip().endswith(career.DOT))
                self.assertFalse(line.lstrip().startswith(career.DOT))
                self.assertNotIn(career.JOIN, line)
                self.assertNotIn("CGPA", line)
        self.assert_sound(files)


if __name__ == "__main__":
    unittest.main()
