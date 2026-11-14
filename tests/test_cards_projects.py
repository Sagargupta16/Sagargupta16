"""Checks for the featured project cards: the cover scene, the text under it and the phone twin.

The baseline renders the checked-in snapshot and asserts rules, never values,
so a data refresh (a new featured project, a longer summary, more stars)
cannot fail it. The lane's own rules each have a test on a small context.
"""

from __future__ import annotations

import importlib.util
import itertools
import re
import sys
import unittest
import xml.etree.ElementTree as ET  # nosec B405 - parses SVG this repo just rendered
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kit
from cards import projects

SPEC = importlib.util.spec_from_file_location("render_svgs", SCRIPTS / "render-svgs.py")
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)
renderer.OFFLINE = True

SVG = "{http://www.w3.org/2000/svg}"
LONG_DASHES = (chr(0x2013), chr(0x2014))
CLOCK = {2, 3, 4, 6, 12, 24}  # the loop lengths the page clock allows, in seconds
ANIMATIONS = (f"{SVG}animate", f"{SVG}animateTransform")
SCENES = {
    "kalchar",
    "gitscope",
    "ledger-sync",
    "leetcode-rating-predictor",
    "blue-green-aws-terraform",
    "instagram-likes-leaderboard",
    "personal-portfolio",
    "selfhub",
}
# the covers that clear something and build it again
BUILD_SCENES = {"gitscope", "ledger-sync", "leetcode-rating-predictor"}


def project(slug: str = "kalchar", **changes: object) -> dict:
    base = {
        "slug": slug,
        "title": "Sample Project",
        "summary": "A short summary of what the project does.",
        "date": "May 2026",
        "tech": ["Python", "FastAPI", "React 19", "PostgreSQL", "Cloudflare Workers"],
        "url": "https://example.com/",
        "live": False,
        "stars": None,
    }
    return base | changes


def render(*entries: dict) -> dict[str, str]:
    return projects.render({}, {"projects": list(entries)})


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)  # nosec B314 - our own output


def size_of(svg: str) -> tuple[float, float]:
    _, _, width, height = map(float, parse(svg).attrib["viewBox"].split())
    return width, height


def labels(svg: str) -> list[str]:
    return [element.text or "" for element in parse(svg).iter(f"{SVG}text")]


def spans(svg: str) -> list[tuple[str, float, float, float, float]]:
    """Return (text, left, right, baseline, size) for every label, measured the way kit measures.

    A label under a group with a static transform would not sit where its x
    and y say, so the walk refuses one: none of this lane's text is drawn so.
    """
    out = []

    def walk(element: ET.Element, moved: bool) -> None:
        moved = moved or "transform" in element.attrib
        if element.tag == f"{SVG}text":
            if moved:
                raise AssertionError(f"text under a transform: {element.text!r}")
            text, size = element.text or "", float(element.attrib["font-size"])
            mono = element.get("class") in ("m", "k", "c")
            width = kit.text_width(text, size, mono, kit.TRACK)
            if mono and text:
                width -= kit.TRACK
            x, y = float(element.attrib["x"]), float(element.attrib["y"])
            anchor = element.get("text-anchor")
            left = (
                x - width / 2
                if anchor == "middle"
                else x - width
                if anchor == "end"
                else x
            )
            out.append((text, left, left + width, y, size))
        for child in element:
            walk(child, moved)

    walk(parse(svg), False)
    return out


def has_star(svg: str) -> bool:
    return kit.STAR in svg


def chip_row(svg: str, entry: dict, phone: bool) -> tuple[list[str], int | None, float]:
    """The tech row as drawn: the names shown, the +N count (None when there is no +N chip)
    and the room left between the last chip and the row's limit."""
    stage = projects.Stage(phone)
    row = [span for span in spans(svg) if span[3] > stage.h]
    chips = [span for span in row if span[0] in entry["tech"]]
    counts = [span for span in row if re.fullmatch(r"\+\d+", span[0])]
    # a chip's edge is 10 past its label
    end = max((right + 10 for _, _, right, _, _ in chips + counts), default=stage.x0)
    count = int(counts[0][0]) if counts else None
    return [span[0] for span in chips], count, row_limit(svg, entry, phone) - end


def row_limit(svg: str, entry: dict, phone: bool) -> float:
    """Where the tech row has to stop: the card's padding, or short of the star chip."""
    stage = projects.Stage(phone)
    if not has_star(svg):
        return stage.x1
    star = kit.compact(entry["stars"])
    row = [span for span in spans(svg) if span[3] > stage.h]
    # the count sits 25 right of its chip's edge, and the row stops 8 short of that chip
    return min(left for text, left, _, _, _ in row if text == star) - 25 - 8


def busy(svg: str) -> tuple[float, float]:
    """When a cover first leaves its rest frame and when it is back on it, in seconds.

    Travelling lights are left out: their dash keeps moving while it is hidden,
    and each one ends on something this does count.
    """
    cover = next(
        group
        for group in parse(svg).iter(f"{SVG}g")
        if group.get("clip-path") == "url(#cover)"
    )
    start, end = kit.T, 0.0
    for animation in cover.iter():
        if animation.tag not in ANIMATIONS:
            continue
        values = animation.get("values").split(";")
        if values[0] != values[-1]:
            continue
        dur = float(animation.get("dur").rstrip("s"))
        times = [float(value) * dur for value in animation.get("keyTimes").split(";")]
        moves = [i for i in range(1, len(values)) if values[i] != values[i - 1]]
        if moves:
            start, end = min(start, times[moves[0] - 1]), max(end, times[moves[-1]])
    return start, end


def place(points: list, seconds: float) -> tuple[float, float]:
    """Where [(seconds, (x, y))] keyframes put their row at a moment, moving in straight lines."""
    for (t0, a), (t1, b) in itertools.pairwise(points):
        if t0 <= seconds <= t1 and t1 > t0:
            k = (seconds - t0) / (t1 - t0)
            return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
    return points[0][1] if seconds < points[0][0] else points[-1][1]


class OfflineCards(unittest.TestCase):
    """Every file the lane draws from the checked-in snapshot."""

    @classmethod
    def setUpClass(cls) -> None:
        data = renderer.load_data()
        cls.ctx = renderer.build_context(data)
        cls.files = projects.render(data, cls.ctx)
        cls.again = projects.render(data, cls.ctx)

    def test_file_names(self) -> None:
        expected = set()
        for entry in self.ctx["projects"]:
            expected |= {
                f"project-{entry['slug']}.svg",
                f"project-{entry['slug']}-mobile.svg",
            }
        self.assertEqual(set(self.files), expected)
        self.assertTrue(expected)
        for name in self.files:
            self.assertRegex(name, renderer.CARD_FILE)

    def test_every_file_parses_and_is_labelled(self) -> None:
        for name, svg in self.files.items():
            root = parse(svg)
            self.assertEqual(root.tag, f"{SVG}svg", name)
            self.assertEqual(root.get("role"), "img", name)
            self.assertGreater(len(root.get("aria-label", "")), 20, name)

    def test_the_label_is_the_title_and_the_summary(self) -> None:
        for entry in self.ctx["projects"]:
            for suffix in ("", "-mobile"):
                label = parse(self.files[f"project-{entry['slug']}{suffix}.svg"]).get(
                    "aria-label"
                )
                self.assertTrue(label.startswith(entry["title"]), label)
                self.assertIn(entry["summary"], label)

    def test_render_is_deterministic(self) -> None:
        self.assertEqual(self.files, self.again)

    def test_widths(self) -> None:
        for name, svg in self.files.items():
            self.assertEqual(
                size_of(svg)[0], 320 if name.endswith("-mobile.svg") else 400, name
            )

    def test_desktop_cards_share_one_height(self) -> None:
        heights = {
            size_of(svg)[1] for name, svg in self.files.items() if "-mobile" not in name
        }
        self.assertEqual(len(heights), 1, heights)

    def test_no_text_leaves_the_canvas(self) -> None:
        for name, svg in self.files.items():
            width, height = size_of(svg)
            for text, left, right, baseline, size in spans(svg):
                self.assertGreaterEqual(left, 0, f"{name}: {text!r}")
                self.assertLessEqual(right, width, f"{name}: {text!r}")
                self.assertGreaterEqual(baseline - size, 0, f"{name}: {text!r}")
                self.assertLessEqual(baseline, height, f"{name}: {text!r}")

    def test_text_under_the_cover_keeps_the_card_padding(self) -> None:
        for name, svg in self.files.items():
            stage = projects.Stage(name.endswith("-mobile.svg"))
            for text, left, right, baseline, _ in spans(svg):
                if baseline > stage.h:
                    self.assertGreaterEqual(left, stage.x0 - 0.01, f"{name}: {text!r}")
                    self.assertLessEqual(right, stage.x1 + 0.01, f"{name}: {text!r}")

    def test_text_floor(self) -> None:
        for name, svg in self.files.items():
            floor = kit.MICRO_PHONE if name.endswith("-mobile.svg") else kit.MICRO
            for text, _, _, _, size in spans(svg):
                self.assertGreaterEqual(size, floor, f"{name}: {text!r}")

    def test_no_long_dash_and_no_amber(self) -> None:
        for name, svg in self.files.items():
            for dash in LONG_DASHES:
                self.assertNotIn(dash, svg, name)
            self.assertNotIn(kit.AMBER, svg, name)

    def test_self_contained(self) -> None:
        for name, svg in self.files.items():
            for banned in (
                "<script",
                "<foreignObject",
                "<image",
                "href=",
                "@import",
                "prefers-reduced-motion",
            ):
                self.assertNotIn(banned, svg, f"{name}: {banned}")

    def test_ids_are_unique(self) -> None:
        for name, svg in self.files.items():
            ids = re.findall(r' id="([^"]+)"', svg)
            self.assertEqual(len(ids), len(set(ids)), name)
            for reference in re.findall(r"url\(#([^)]+)\)", svg):
                self.assertIn(reference, ids, name)

    def test_hidden_at_rest_means_in_transit(self) -> None:
        """Anything that rests at opacity 0 is a packet, cursor or flash: it carries its own repeating fade."""
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
                    fades,
                    f"{name}: <{element.tag.split('}')[1]}> rests hidden with no loop",
                )
                peak = max(float(value) for value in fades[0].get("values").split(";"))
                self.assertGreater(peak, 0.5, name)

    def test_the_text_under_the_cover_rests_visible(self) -> None:
        """The title, summary and chips enter with kit's poster-safe entrance: no opacity attribute, ends at 1."""
        for name, svg in self.files.items():
            stage = projects.Stage(name.endswith("-mobile.svg"))
            root = parse(svg)
            parents = {child: parent for parent in root.iter() for child in parent}
            for element in root.iter(f"{SVG}text"):
                if float(element.attrib["y"]) <= stage.h:
                    continue
                node = element
                while node is not None:
                    self.assertIsNone(node.get("opacity"), f"{name}: {element.text!r}")
                    node = parents.get(node)
            for animation in root.iter(f"{SVG}animate"):
                if (
                    animation.get("repeatCount")
                    or animation.get("attributeName") != "opacity"
                ):
                    continue
                self.assertEqual(animation.get("fill"), "freeze", name)
                self.assertEqual(animation.get("values").split(";")[-1], "1", name)

    def test_loops_run_on_the_page_clock(self) -> None:
        for name, svg in self.files.items():
            for animation in parse(svg).iter():
                if (
                    animation.tag not in ANIMATIONS
                    or animation.get("repeatCount") != "indefinite"
                ):
                    continue
                self.assertIn(float(animation.get("dur").rstrip("s")), CLOCK, name)

    def test_key_times_match_their_values(self) -> None:
        for name, svg in self.files.items():
            for animation in parse(svg).iter():
                if animation.tag not in ANIMATIONS or not animation.get("keyTimes"):
                    continue
                times = [float(value) for value in animation.get("keyTimes").split(";")]
                values = animation.get("values").split(";")
                self.assertEqual(len(times), len(values), name)
                self.assertEqual((times[0], times[-1]), (0.0, 1.0), name)
                self.assertEqual(times, sorted(times), name)

    def test_loops_close_where_they_open(self) -> None:
        """A fade or a move ends each loop on its first value; a travelling dash is periodic instead."""
        for name, svg in self.files.items():
            for animation in parse(svg).iter():
                if (
                    animation.tag not in ANIMATIONS
                    or animation.get("repeatCount") != "indefinite"
                ):
                    continue
                if animation.get("attributeName") in ("stroke-dashoffset", "r"):
                    continue
                values = animation.get("values").split(";")
                if (
                    animation.get("attributeName") == "opacity"
                    and animation.get("dur") == "2s"
                ):
                    continue  # kit.live_dot's ring fades out and restarts
                self.assertEqual(values[0], values[-1], f"{name}: {animation.attrib}")

    def test_motion_budget_and_weight(self) -> None:
        for name, svg in self.files.items():
            animated = {
                id(parent)
                for parent in parse(svg).iter()
                for child in parent
                if child.tag in ANIMATIONS
            }
            self.assertLessEqual(len(animated), 40, name)
            self.assertLessEqual(len(svg.encode("utf-8")), 30_000, name)

    def test_summary_keeps_every_word_or_says_it_was_cut(self) -> None:
        for entry in self.ctx["projects"]:
            for phone in (False, True):
                lines = projects._summary(entry, phone)
                joined = " ".join(lines)
                cap = projects.PHONE_LINES if phone else projects.DESKTOP_LINES
                self.assertLessEqual(len(lines), cap)
                if joined.endswith("..."):
                    self.assertTrue(
                        entry["summary"].startswith(joined[:-3].rstrip()), joined
                    )
                else:
                    self.assertEqual(joined, " ".join(entry["summary"].split()))
                svg = self.files[
                    f"project-{entry['slug']}{'-mobile' if phone else ''}.svg"
                ]
                shown = labels(svg)
                for line in lines:
                    self.assertIn(line, shown)

    def test_card_text_comes_from_the_context(self) -> None:
        for entry in self.ctx["projects"]:
            for suffix in ("", "-mobile"):
                shown = labels(self.files[f"project-{entry['slug']}{suffix}.svg"])
                self.assertIn(entry["date"].upper(), shown)
                self.assertIn(entry["title"], shown)
                self.assertEqual("LIVE" in shown, bool(entry["live"]), entry["slug"])

    def test_chips_are_tech_names_in_order_and_a_count_of_the_rest(self) -> None:
        for entry in self.ctx["projects"]:
            for suffix in ("", "-mobile"):
                name = f"project-{entry['slug']}{suffix}.svg"
                chips, count, free = chip_row(self.files[name], entry, bool(suffix))
                self.assertTrue(chips, name)
                self.assertEqual(
                    chips, [tech for tech in entry["tech"] if tech in chips], name
                )
                hidden = [tech for tech in entry["tech"] if tech not in chips]
                if count is None:
                    # the count is only dropped to keep a second name on the row
                    self.assertTrue(not hidden or len(chips) >= 2, name)
                else:
                    self.assertEqual(count, len(hidden), name)
                    self.assertGreater(count, 0, name)
                # a name is left out only when the room left on the row cannot hold it
                stage = projects.Stage(bool(suffix))
                for tech in hidden:
                    self.assertGreater(
                        kit.chip_width(tech, stage.micro) + projects.CHIP_GAP,
                        free,
                        f"{name}: {tech}",
                    )

    def test_a_phone_row_keeps_two_names(self) -> None:
        """Two names wherever two fit side by side, taking them in the row's own order:
        the first name that fits, then any later one that fits after it. Two long names
        cannot share a phone row, and then one is shown."""
        stage = projects.Stage(True)
        for entry in self.ctx["projects"]:
            name = f"project-{entry['slug']}-mobile.svg"
            svg = self.files[name]
            chips, _, _ = chip_row(svg, entry, True)
            room = row_limit(svg, entry, True) - stage.x0
            widths = [kit.chip_width(tech, stage.micro) for tech in entry["tech"]]
            first = next((i for i, w in enumerate(widths) if w <= room), None)
            wanted = 0 if first is None else 1
            after = room - (widths[first] + projects.CHIP_GAP) if wanted else 0
            if wanted and any(w <= after for w in widths[first + 1 :]):
                wanted = 2
            self.assertGreaterEqual(len(chips), wanted, name)

    def test_non_live_cards_say_where_the_link_goes(self) -> None:
        for entry in self.ctx["projects"]:
            wanted = not entry["live"] and "//github.com/" in (entry["url"] or "")
            for suffix in ("", "-mobile"):
                shown = labels(self.files[f"project-{entry['slug']}{suffix}.svg"])
                self.assertEqual("SOURCE" in shown, wanted, entry["slug"])

    def test_build_covers_hold_the_finished_frame_and_never_reset_together(
        self,
    ) -> None:
        """A cover that clears and rebuilds opens finished, is busy for under half the loop, and
        starts apart from the cards beside, above and below it."""
        starts = {}
        for index, entry in enumerate(self.ctx["projects"]):
            for suffix in ("", "-mobile"):
                name = f"project-{entry['slug']}{suffix}.svg"
                start, end = busy(self.files[name])
                if entry["slug"] not in BUILD_SCENES:
                    continue
                self.assertGreaterEqual(start, projects.CLEAR_AT, name)
                self.assertLessEqual(end - start, kit.T / 2, name)
                self.assertLessEqual(end, kit.T, name)
                starts[(index, suffix)] = start
        self.assertTrue(starts)
        for (index, suffix), start in starts.items():
            for other in (index + 1, index + 2):
                if (other, suffix) in starts:
                    self.assertGreaterEqual(
                        abs(starts[(other, suffix)] - start), 0.5, (index, other)
                    )

    def test_star_chip_follows_the_floor(self) -> None:
        for entry in self.ctx["projects"]:
            wanted = (entry["stars"] or 0) >= projects.STAR_FLOOR
            for suffix in ("", "-mobile"):
                self.assertEqual(
                    has_star(self.files[f"project-{entry['slug']}{suffix}.svg"]),
                    wanted,
                    entry["slug"],
                )


class LaneRules(unittest.TestCase):
    def test_every_portfolio_scene_is_registered(self) -> None:
        self.assertEqual(set(projects.COVERS), SCENES)

    def test_star_chip_only_from_ten_stars(self) -> None:
        for stars, wanted in (
            (None, False),
            (0, False),
            (9, False),
            (10, True),
            (1234, True),
        ):
            files = render(project(stars=stars))
            for name, svg in files.items():
                self.assertEqual(has_star(svg), wanted, f"{name} with {stars}")
        self.assertIn(
            "1.2K", labels(render(project(stars=1234))["project-kalchar.svg"])
        )

    def test_star_chip_reserves_its_room_only_when_drawn(self) -> None:
        tech = ["TypeScript", "React 19", "FastAPI", "Tailwind CSS"]
        plain = labels(render(project(tech=tech, stars=9))["project-kalchar.svg"])
        starred = labels(render(project(tech=tech, stars=10))["project-kalchar.svg"])
        self.assertGreaterEqual(
            len([name for name in tech if name in plain]),
            len([name for name in tech if name in starred]),
        )
        for name, svg in render(project(tech=tech, stars=123456)).items():
            row = [
                span
                for span in spans(svg)
                if span[0] in tech or span[0].startswith("+")
            ]
            star_left = min(
                left for text, left, _, _, _ in spans(svg) if text == "123K"
            )
            for text, _, right, _, _ in row:
                self.assertLess(right, star_left - 8, f"{name}: {text}")

    def test_chip_row_passes_over_a_name_that_does_not_fit(self) -> None:
        tech = [
            "JavaScript",
            "TypeScript",
            "Chrome Extension",
            "Manifest V3",
            "GitHub GraphQL API",
            "Cloudflare Workers",
            "esbuild",
        ]
        entry = project(tech=tech)
        chips, count, _ = chip_row(render(entry)["project-kalchar.svg"], entry, False)
        self.assertEqual(chips, ["JavaScript", "TypeScript", "Manifest V3"])
        self.assertEqual(count, 4)

    def test_the_count_gives_way_to_the_second_name(self) -> None:
        tech = ["Fourteen Chars", "Another Longer", "Third One Long"]
        entry = project(tech=tech)
        svg = render(entry)["project-kalchar-mobile.svg"]
        chips, count, _ = chip_row(svg, entry, True)
        self.assertEqual(chips, tech[:2])
        self.assertIsNone(count)
        # with room to spare the count comes back
        entry = project(tech=["Go", "Rust", "A Name Far Too Long For Any Phone Row"])
        chips, count, _ = chip_row(
            render(entry)["project-kalchar-mobile.svg"], entry, True
        )
        self.assertEqual((chips, count), (["Go", "Rust"], 1))

    def test_source_mark_only_on_a_repository_link_that_is_not_live(self) -> None:
        for url, live, wanted in (
            ("https://github.com/Sagargupta16/SelfHub", False, True),
            ("https://github.com/Sagargupta16/SelfHub", True, False),
            ("https://example.com/", False, False),
            ("https://notgithub.com/x/y", False, False),
            ("", False, False),
        ):
            for name, svg in render(project(url=url, live=live)).items():
                self.assertEqual("SOURCE" in labels(svg), wanted, f"{name}: {url}")
                self.assertEqual("LIVE" in labels(svg), live, name)

    def test_clear_times_step_along_the_grid(self) -> None:
        clears = [projects.Stage(False, index).clear for index in range(12)]
        self.assertEqual(clears[0], projects.CLEAR_AT)
        for index, clear in enumerate(clears):
            self.assertGreaterEqual(clear, projects.CLEAR_AT)
            # a build takes under 5 s and has to end inside the loop
            self.assertLessEqual(clear + 5, kit.T)
            self.assertEqual(clear, projects.Stage(True, index).clear)
            for other in clears[index + 1 : index + 3]:
                self.assertGreaterEqual(abs(other - clear), 0.5)

    def test_gallery_has_no_sheen(self) -> None:
        for name, svg in render(project("kalchar")).items():
            self.assertNotIn("sheen", svg, name)
            for element in parse(svg).iter(f"{SVG}path"):
                self.assertNotEqual(element.get("fill"), "rgba(255,255,255,0.10)", name)

    def test_leaderboard_names_both_tabs(self) -> None:
        files = render(project("instagram-likes-leaderboard"))
        desktop = labels(files["project-instagram-likes-leaderboard.svg"])
        phone = labels(files["project-instagram-likes-leaderboard-mobile.svg"])
        for shown, tabs in (
            (desktop, ("YOU FOLLOW", "NON-MUTUALS")),
            (phone, ("FANS", "NON-MUTUALS")),
        ):
            for tab in tabs:
                # once at rest and once lit
                self.assertEqual(shown.count(tab), 2, tab)
            self.assertIn("POSTS", shown)

    def test_swapping_rows_never_cross(self) -> None:
        step, width, start, home = 18.0, 200.0, 6.8, 10.0
        leader, runner = projects._swap(start, step, width, home)
        for points in (leader, runner):
            self.assertEqual(points[0][1], (0, 0))
            self.assertEqual(points[-1][1], (0, 0))
            self.assertEqual([t for t, _ in points], sorted(t for t, _ in points))
        self.assertEqual(place(leader, home), (0, step))
        self.assertEqual(place(runner, home), (0, -step))
        moment = start
        while moment <= home:
            (ax, ay), (bx, by) = place(leader, moment), place(runner, moment)
            apart = abs((step + by) - ay)  # the runner-up starts one row down
            self.assertTrue(
                apart >= step / 2 or abs(ax - bx) >= width * 0.8, f"at {moment:.2f}s"
            )
            moment += 0.01

    def test_blue_green_shows_the_pipeline(self) -> None:
        for name, svg in render(project("blue-green-aws-terraform")).items():
            stage = projects.Stage(name.endswith("-mobile.svg"))
            cover = [span for span in spans(svg) if span[3] <= stage.h]
            names = [span[0] for span in cover]
            for label in ("CODEPIPELINE", "ALB", "CANARY", "TG 1", "TG 2"):
                self.assertIn(label, names, name)
            for text, left, right, _, _ in cover:
                self.assertGreaterEqual(left, stage.x0 - 0.01, f"{name}: {text}")
                self.assertLessEqual(right, stage.x1 + 0.01, f"{name}: {text}")

    def test_generic_cover_always_reads_as_a_pipeline(self) -> None:
        for tech, wanted in (
            (["Rust", "WebAssembly", "Cloudflare Workers", "D1"], None),
            (
                ["Go", "gRPC", "Redis", "Docker", "Helm", "Kafka"],
                ["GO", "GRPC", "REDIS", "DOCKER"],
            ),
            (["Python"], ["PYTHON", "BUILD", "SHIP"]),
            ([], ["CODE", "BUILD", "SHIP"]),
        ):
            for name, svg in render(project("nothing-known", tech=tech)).items():
                stage = projects.Stage(name.endswith("-mobile.svg"))
                cover = [span for span in spans(svg) if span[3] <= stage.h]
                # each node is drawn at rest and again lit
                nodes = [span[0] for span in cover][::2]
                self.assertEqual(nodes, [span[0] for span in cover][1::2], name)
                self.assertGreaterEqual(len(nodes), 3, name)
                self.assertLessEqual(len(nodes), 4, name)
                if wanted:
                    self.assertEqual(nodes, wanted, name)
                else:
                    # a name too long for the band is passed over, the rest keep their order
                    stack = [item.upper() for item in tech]
                    self.assertEqual(nodes, [item for item in stack if item in nodes])
                    self.assertEqual(nodes[:2], ["RUST", "WEBASSEMBLY"], name)
                # the labels run left to right with a node's padding and a gap between them
                edges = [(left, right) for _, left, right, _, _ in cover][::2]
                for (_, right), (left, _) in itertools.pairwise(edges):
                    self.assertGreater(left - right, 2 * 9 + 10, name)

    def test_live_mark_only_when_live(self) -> None:
        for live in (True, False):
            for name, svg in render(project(live=live)).items():
                self.assertEqual("LIVE" in labels(svg), live, name)
                body = svg[svg.index("</g></g>") :] if not live else svg
                self.assertEqual(kit.GREEN in body, live, name)

    def test_unknown_slug_gets_the_generic_cover(self) -> None:
        entry = project(
            "not-in-the-portfolio-yet", tech=["Rust", "WebAssembly", "PostgreSQL"]
        )
        files = render(entry)
        self.assertEqual(
            set(files),
            {
                "project-not-in-the-portfolio-yet.svg",
                "project-not-in-the-portfolio-yet-mobile.svg",
            },
        )
        for name, svg in files.items():
            stage = projects.Stage(name.endswith("-mobile.svg"))
            self.assertIn(projects._cover_generic(stage, entry), svg, name)
            cover = [
                text for text, _, _, baseline, _ in spans(svg) if baseline <= stage.h
            ]
            self.assertTrue(cover, name)
            self.assertEqual(cover[0], "RUST")
            for text in cover:
                self.assertIn(text, [name.upper() for name in entry["tech"]])

    def test_generic_cover_survives_an_empty_or_long_stack(self) -> None:
        for tech in (
            [],
            ["An Extremely Long Technology Name That Cannot Fit In Any Cover At All"],
        ):
            for name, svg in render(project("nothing-known", tech=tech)).items():
                width, _ = size_of(svg)
                for text, left, right, _, _ in spans(svg):
                    self.assertGreaterEqual(left, 0, f"{name}: {text!r}")
                    self.assertLessEqual(right, width, f"{name}: {text!r}")

    def test_desktop_heights_match_across_short_and_long_summaries(self) -> None:
        long = " ".join(
            ["A sentence that keeps going well past what three lines can hold."] * 6
        )
        files = render(
            project("kalchar", summary="Short."),
            project("gitscope", summary=long),
            project("unknown-one", tech=[]),
        )
        heights = {
            size_of(svg)[1] for name, svg in files.items() if "-mobile" not in name
        }
        self.assertEqual(len(heights), 1, heights)
        cut = [
            text
            for text in labels(files["project-gitscope.svg"])
            if text.endswith("...")
        ]
        self.assertEqual(len(cut), 1)
        self.assertLessEqual(
            len(projects._summary(project(summary=long), False)), projects.DESKTOP_LINES
        )
        self.assertLessEqual(
            len(projects._summary(project(summary=long), True)), projects.PHONE_LINES
        )

    def test_long_title_stays_inside_the_card(self) -> None:
        title = "A Title That Is Much Longer Than Any Card Could Ever Show On One Line Of Text"
        for name, svg in render(project(title=title)).items():
            stage = projects.Stage(name.endswith("-mobile.svg"))
            shown = [span for span in spans(svg) if span[0].startswith("A Title")]
            self.assertEqual(len(shown), 1, name)
            text, _, right, _, size = shown[0]
            self.assertLessEqual(right, stage.x1, name)
            self.assertGreaterEqual(size, 15, name)
            self.assertTrue(text.endswith("..."), name)

    def test_text_is_escaped(self) -> None:
        files = render(
            project(
                "odd",
                title="Tom & Jerry <fast>",
                summary='Says "hi" & leaves.',
                tech=["C & C++", "<T>"],
            )
        )
        for name, svg in files.items():
            shown = labels(svg)
            self.assertIn("Tom & Jerry <fast>", shown, name)
            self.assertIn("C & C++", shown, name)

    def test_no_projects_is_no_files(self) -> None:
        self.assertEqual(projects.render({}, {"projects": []}), {})

    def test_beam_never_runs_backwards_and_ends_where_it_rests(self) -> None:
        route = projects.Route(projects._line((0, 0), (100, 0)))
        beam = projects._beam(
            route, [projects._trip(1, 2), projects._trip(5, 6), projects._trip(9, 10)]
        )
        values = [
            float(v) for v in re.search(r'values="([^"]+)"', beam).group(1).split(";")
        ]
        self.assertEqual(values, sorted(values, reverse=True))
        dash, gap = map(
            float, re.search(r'stroke-dasharray="([^"]+)"', beam).group(1).split()
        )
        rest = float(re.search(r'stroke-dashoffset="([^"]+)"', beam).group(1))
        self.assertEqual(values[0], rest)
        self.assertAlmostEqual((values[0] - values[-1]) / (dash + gap), 3, places=2)
        self.assertGreater(
            rest, dash
        )  # at rest the dash sits before the start of the path


if __name__ == "__main__":
    unittest.main()
