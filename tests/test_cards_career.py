"""Checks for the career cards: experience, education and publications, at both widths.

The baseline renders the checked-in snapshot and asserts rules, never values,
so a data refresh cannot fail it. The fixes each have a test built on a small
context of its own.
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
LONG_DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}  # the loop lengths the page clock allows, in seconds
MONO_TRACKING = {"m": kit.TRACK, "k": 2, "c": 0}  # kit's mono classes


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314 - our own output


def contents(svg: str) -> list[str]:
    return [element.text or "" for element in parse(svg).iter(f"{SVG}text")]


def reading(svg: str) -> str:
    """Every label in document order as one upper-case line, so a wrapped label reads whole."""
    return " ".join(" ".join(contents(svg)).upper().split())


def spans(svg: str) -> list[tuple[str, float, float, float, float]]:
    """Return (text, left, right, baseline, size) for every label, measured the way kit measures."""
    out = []
    for element in parse(svg).iter(f"{SVG}text"):
        text, size = element.text or "", float(element.attrib["font-size"])
        cls = element.get("class", "")
        if "font-family" in element.attrib:  # the phone engine's mono labels
            width = kit.text_width(text, size, True, kit.TRACK)
        elif cls in MONO_TRACKING:
            width = kit.text_width(text, size, True, MONO_TRACKING[cls])
        else:
            width = kit.text_width(text, size)
        x = float(element.attrib["x"])
        left = {"middle": x - width / 2, "end": x - width}.get(
            element.get("text-anchor", ""), x
        )
        out.append((text, left, left + width, float(element.attrib["y"]), size))
    return out


def engagement(client: str, role: str, when: str, ongoing: bool = False) -> dict:
    """One customer engagement in the public snapshot's shape; see customers()."""
    start, _, end = when.partition(" to ")
    return {
        "when": when,
        "client": client,
        "role": role,
        "stack": [],
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
)


def shown(row: dict) -> list[str]:
    """What a row must show on both layouts: its number, its bracketed sector if any, role and dates."""
    sector = [f"({row['sector']})"] if row["sector"] else []
    return [row["title"], *sector, row["role"], row["when"]]


class CareerCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = renderer.load_data()
        cls.ctx = renderer.build_context(cls.data)
        cls.files = career.render(cls.data, cls.ctx)

    def render(self, **changes: object) -> dict[str, str]:
        return career.render(self.data, {**self.ctx, **changes})

    def assert_inside(self, name: str, svg: str) -> None:
        _, _, width, height = map(float, parse(svg).attrib["viewBox"].split())
        for text, left, right, baseline, size in spans(svg):
            with self.subTest(file=name, text=text):
                self.assertGreaterEqual(left, 0)
                self.assertLessEqual(right, width)
                self.assertGreaterEqual(baseline - size, 0)
                self.assertLessEqual(baseline + size * 0.25, height)

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

    def test_no_text_leaves_the_canvas(self) -> None:
        for name, svg in self.files.items():
            self.assert_inside(name, svg)

    def test_desktop_labels_on_one_line_never_touch(self) -> None:
        for name in ("experience.svg", "education.svg", "publications.svg"):
            self.assert_no_collisions(name, self.files[name])

    def test_no_en_or_em_dash_in_the_cards_or_the_module(self) -> None:
        sources = dict(self.files)
        sources["career.py"] = Path(career.__file__).read_text(encoding="utf-8")
        for name, text in sources.items():
            for dash in LONG_DASHES:
                with self.subTest(file=name, dash=hex(ord(dash))):
                    self.assertNotIn(dash, text)

    def test_every_card_is_poster_safe(self) -> None:
        for name, svg in self.files.items():
            with self.subTest(file=name):
                # nothing rests hidden: an entrance holds its start value from 0 s
                # and freezes on the element's own, finished state
                self.assertNotIn('opacity="0"', svg)
                for animate in parse(svg).iter(f"{SVG}animate"):
                    if animate.get("repeatCount") == "indefinite":
                        continue
                    self.assertEqual(animate.get("fill"), "freeze")
                    if animate.get("attributeName") == "opacity":
                        self.assertTrue(animate.get("values", "").endswith(";1"))
                self.assertNotIn("prefers-reduced-motion", svg)

    def test_every_loop_runs_on_the_page_clock(self) -> None:
        for name, svg in self.files.items():
            root = parse(svg)
            loops = [
                element.get("dur", "")
                for element in root.iter()
                if element.get("repeatCount") == "indefinite"
            ]
            loops += re.findall(r"animation:\w+ ([\d.]+s)", svg)
            for dur in loops:
                with self.subTest(file=name, dur=dur):
                    self.assertIn(float(dur.removesuffix("s")), CLOCK)

    def test_text_sizes_keep_the_floor(self) -> None:
        for name, svg in self.files.items():
            phone = name.endswith("-mobile.svg")
            for element in parse(svg).iter(f"{SVG}text"):
                size = float(element.attrib["font-size"])
                mono = "font-family" in element.attrib
                floor = kit.MICRO_PHONE if phone and mono else kit.MICRO
                with self.subTest(file=name, text=element.text):
                    self.assertGreaterEqual(size, floor)

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

    # ------------------------------------------------------------ fix: render-a-01
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

    def test_the_phone_lists_engagements_newest_first(self) -> None:
        text = reading(self.render(engagements=CUSTOMERS[:3])["experience-mobile.svg"])
        order = [text.index(row["title"].upper()) for row in CUSTOMERS[:3]]
        self.assertEqual(order, sorted(order, reverse=True))

    def test_the_phone_puts_the_sector_between_the_title_and_the_dates(self) -> None:
        texts = contents(
            self.render(engagements=CUSTOMERS[:3])["experience-mobile.svg"]
        )
        for row in CUSTOMERS[:3]:
            with self.subTest(title=row["title"]):
                at = texts.index(row["title"])
                self.assertEqual(
                    texts[at + 1 : at + 4],
                    [f"({row['sector']})", row["when"].upper(), row["role"]],
                )

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
                self.assertNotIn("(AWS)", reading(files[name]))
                self.assertNotIn("AWS CUSTOMER", reading(files[name]))

    def test_no_engagements_leaves_no_empty_heading(self) -> None:
        files = self.render(engagements=[])
        for name in ("experience.svg", "experience-mobile.svg"):
            with self.subTest(file=name):
                self.assertNotIn("ENGAGEMENTS", reading(files[name]))
                self.assert_inside(name, files[name])

    # ------------------------------------------------------------ fix: the heading
    def test_the_heading_names_customer_engagements(self) -> None:
        files = self.render(engagements=CUSTOMERS[:3])
        for name in ("experience.svg", "experience-mobile.svg"):
            with self.subTest(file=name):
                self.assertIn("CUSTOMER ENGAGEMENTS", contents(files[name]))
                self.assertNotIn("ENGAGEMENTS AT AWS", reading(files[name]))
        self.assertIn(
            ". Customer engagements at AWS: Customer 1 (Retail), Cloud Engineer",
            parse(files["experience.svg"]).get("aria-label"),
        )

    def test_every_role_says_it_was_held_at_aws(self) -> None:
        text = reading(self.render(engagements=CUSTOMERS[:3])["experience.svg"])
        for row in CUSTOMERS[:3]:
            with self.subTest(role=row["role"]):
                self.assertIn(f"{row['role']}, AWS".upper(), text)

    # ------------------------------------------------------------ fix: render-a-07
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
                if circle.get("r") == "6"
            ]
            self.assertEqual(len(stops), len(self.ctx["milestones"]) + 4)

    def test_a_full_rail_of_long_labels_never_collides_or_leaves_the_card(self) -> None:
        for count in (1, 2, 3, 4, 5):
            for extra in ([], [GENERIC]):
                rows = customers(*extra, *[LONG_SECTOR] * count)
                svg = self.render(engagements=rows)["experience.svg"]
                name = f"{count} long rows, {len(extra)} generic"
                self.assert_no_collisions(name, svg)
                self.assert_inside(name, svg)

    def test_a_sector_wraps_to_the_step_between_stops(self) -> None:
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
        # 300px between three stops holds the sector on one line; 200px between four does not
        self.assertIn(sector, three)
        self.assertNotIn(sector, four)
        self.assertIn("infrastructure)", four)

    def test_every_role_starts_at_one_y_whatever_its_sector(self) -> None:
        # oldest first: a short sector, one that wraps, a short one, and none at all
        rows = customers(ROWS[0], ROWS[3], ROWS[5], GENERIC)
        root = parse(self.render(engagements=rows)["experience.svg"])
        sub_y = max(
            float(c.get("cy")) for c in root.iter(f"{SVG}circle") if c.get("r") == "6"
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

    # ------------------------------------------------------------ fix: render-a-09
    def test_a_live_ring_enters_with_its_stop(self) -> None:
        files = self.render(engagements=[*CUSTOMERS[:2], CUSTOMERS[5]])
        root = parse(files["experience.svg"])
        parents = {child: parent for parent in root.iter() for child in parent}
        rings = [c for c in root.iter(f"{SVG}circle") if c.get("class") == "now"]
        # the current role and the one ongoing engagement, and no other stop
        self.assertEqual(len(rings), 2)
        self.assertEqual({ring.get("stroke") for ring in rings}, {kit.GREEN})
        for ring in rings:
            # the CSS pulse sets opacity on the circle, so the circle itself carries
            # no SMIL; the group around it holds opacity 0 until the stop's turn
            self.assertEqual(len(ring), 0)
            group = parents[ring]
            self.assertEqual(group.tag, f"{SVG}g")
            entrance = group[0]
            self.assertEqual(entrance.get("attributeName"), "opacity")
            self.assertTrue(entrance.get("values").startswith("0;0;"))
            self.assertGreater(float(entrance.get("keyTimes").split(";")[1]), 0)
            # the stop's dot and labels sit in the same group, so they enter together
            self.assertTrue(list(group.iter(f"{SVG}text")))
        self.assertRegex(files["experience.svg"], r"\.now\{animation:ring 2s ")

    def test_an_engagement_that_ended_is_not_drawn_live(self) -> None:
        root = parse(self.render(engagements=CUSTOMERS[:3])["experience.svg"])
        rings = [c for c in root.iter(f"{SVG}circle") if c.get("class") == "now"]
        self.assertEqual(len(rings), 1)  # the current role only
        self.assertEqual(rings[0].get("cy"), str(career.RAIL_Y))

    # ------------------------------------------------------------ fix: data from ctx
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
                self.assert_inside(name, files[name])
        self.assertIn("2033  FULL TIME", contents(files["experience.svg"]))
        self.assertNotIn("2030  FULL TIME", contents(files["experience.svg"]))

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
                self.assertEqual(
                    found, wanted
                )  # every title and row, in the context's order
                self.assertNotIn("AMBASSADOR", reading(files[name]))
        label = parse(files["publications.svg"]).get("aria-label")
        self.assertIn("Mentor of the year (2033)", label)

    def test_a_single_group_spans_the_card_and_none_leaves_only_the_eyebrow(
        self,
    ) -> None:
        one = parse(
            self.render(recognition=[("TALKS", [("One talk", "2031")])])[
                "publications.svg"
            ]
        )
        panels = [r for r in one.iter(f"{SVG}rect") if r.get("rx") == "12"]
        self.assertEqual([panel.get("width") for panel in panels], ["808"])
        for name, svg in self.render(recognition=[]).items():
            if name.startswith("publications"):
                parse(svg)

    def test_education_comes_from_the_context(self) -> None:
        rows = [
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
        files = self.render(education=rows)
        for name in ("education.svg", "education-mobile.svg"):
            text = reading(files[name])
            with self.subTest(file=name):
                for row in rows:
                    for fact in (
                        row["degree"],
                        row["school"],
                        row["city"],
                        row["when"],
                    ):
                        self.assertIn(fact.upper(), text)
                # the degree, dates, school and city only: no grade, no division
                self.assertNotIn("CGPA", text)
                self.assertNotIn("WARANGAL", text)
                self.assert_inside(name, files[name])
        self.assertEqual(
            parse(files["education.svg"]).get("aria-label"),
            "Education: Master of Example Studies, Example University, Pune, India, "
            "June 2030 to May 2032; Bachelor of Example Studies, "
            "Example College, Nagpur, India, June 2027 to May 2030",
        )

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
        lines = contents(self.render(education=rows)["education-mobile.svg"])
        for line in lines:
            with self.subTest(line=line):
                self.assertFalse(line.rstrip().endswith(career.DOT))
                self.assertFalse(line.lstrip().startswith(career.DOT))
                self.assertNotIn(career.JOIN, line)
                self.assertNotIn("CGPA", line)


if __name__ == "__main__":
    unittest.main()
