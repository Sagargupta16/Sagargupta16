"""Regression coverage for phone content, expiry status, and SVG bounds."""

from __future__ import annotations

import importlib.util
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mobile_cards", ROOT / "scripts" / "mobile_cards.py"
)
assert SPEC and SPEC.loader
mobile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mobile)
SVG = "{http://www.w3.org/2000/svg}"


def visible_text(svg: str) -> str:
    return " ".join(
        element.text or "" for element in ET.fromstring(svg).iter(f"{SVG}text")
    )


class MobileCardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(
            (ROOT / "assets" / "svg" / "data.json").read_text(encoding="utf-8")
        )
        cls.context = {
            "today": "2026-10-14",
            "aws_title": "Cloud Consultant (DevOps/MLOps)",
            "career_start": (2024, 8),
            "certifications": cls.data["portfolio"]["certifications"],
            "milestones": [
                ("2018", "BCA", "DAVV", "Indore, India"),
                ("2024", "Cloud Consultant", "AWS", "Hyderabad, India"),
            ],
            "engagements": [("Feb 2026 to now", "RWS", "Lead DevOps Consultant")],
            "worked_with": [("Amazon Web Services", "Cloud Consultant (DevOps/MLOps)")],
            "publications": [
                (
                    "PUBLICATIONS & REVIEWS",
                    [("APG pattern: Deploy AWS networks", "2025")],
                )
            ],
            "headers": [
                (
                    "publications",
                    "05",
                    "Publications, Talks and Recognition",
                    "AWS samples, patterns, talks and programs",
                )
            ],
            "stack": ["aws", "githubactions", "typescript", "sklearn"],
            "ai_tools": ["Claude Code", "GitHub Copilot", "Amazon Bedrock"],
            "badges": [
                (
                    "AWS Certified Developer \u2013 Associate",
                    "https://example.invalid/badge.png",
                ),
                ("AWS Knowledge: Migration Foundations - Training Badge", ""),
            ],
        }
        cls.cards = mobile.render_mobile_cards(cls.data, cls.context)

    def assert_bounds(self, svg: str) -> None:
        root = ET.fromstring(svg)
        _, _, width, height = map(float, root.attrib["viewBox"].split())
        self.assertEqual(width, 320)
        for element in root.iter(f"{SVG}text"):
            size = float(element.attrib["font-size"])
            x, y = float(element.attrib["x"]), float(element.attrib["y"])
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y - size, 0)
            self.assertLessEqual(y + size * 0.25, height)
            self.assertLessEqual(
                x + mobile.text_width(element.text or "", size), width - 10
            )

    def test_expected_cards_are_valid_animated_svg_with_bounded_text(self) -> None:
        expected = {
            "hero",
            "profile-badges",
            "intro",
            "experience",
            "highlights",
            "worked-with",
            "publications",
            "education",
            "oss",
            "oss-merged",
            "oss-review",
            "github",
            "leetcode",
            "certs",
            "stack",
            "ai-stack",
            "competitive",
            "footer",
            "header-publications-dark",
            "header-publications-light",
            "sample-org-governance",
            "sample-sagemaker-mlops",
        }
        self.assertEqual(set(self.cards), {f"{name}-mobile.svg" for name in expected})
        for name, svg in self.cards.items():
            with self.subTest(name=name):
                self.assert_bounds(svg)
                self.assertIn("<animate", svg)
                self.assertNotIn("<script", svg)
                self.assertNotIn("<image", svg)

    def test_expired_terraform_is_separated_and_duplicate_badge_removed(self) -> None:
        text = visible_text(self.cards["certs-mobile.svg"])
        self.assertIn("Active certifications", text)
        self.assertIn("Previously earned", text)
        self.assertIn("Expired 2026-09-10", text)
        self.assertLess(text.index("Previously earned"), text.index("Terraform"))
        self.assertEqual(text.count("AWS Certified Developer"), 1)
        self.assertIn("Migration Foundations", text)

    def test_expiry_boundary_and_missing_dates(self) -> None:
        context = dict(
            self.context,
            certifications=[
                {"name": "Expires today", "expiryDate": "2026-10-14"},
                {"name": "Unknown expiry"},
            ],
        )
        text = visible_text(mobile.render_mobile_cards({}, context)["certs-mobile.svg"])
        self.assertIn("Valid through 2026-10-14", text)
        self.assertLess(text.index("Expires today"), text.index("Expiry not recorded"))
        self.assertLess(text.index("Expiry not recorded"), text.index("Unknown expiry"))

    def test_profile_badges_metadata_matches_active_count(self) -> None:
        context = dict(
            self.context,
            certifications=[
                {"name": "Active", "expiryDate": "2027-01-01"},
                {"name": "Expires today", "expiryDate": "2026-10-14"},
                {"name": "Expired", "expiryDate": "2026-10-13"},
                {"name": "Unknown expiry"},
            ],
        )
        svg = mobile.render_mobile_cards(self.data, context)[
            "profile-badges-mobile.svg"
        ]
        self.assertEqual(ET.fromstring(svg).get("data-active-certifications"), "2")
        self.assertIn("2 active certifications", visible_text(svg))

    def test_open_pr_wording_and_every_pr_title_preserved(self) -> None:
        summary = visible_text(self.cards["oss-mobile.svg"])
        self.assertIn("Open PRs", summary)
        self.assertIn("Repos with merges", summary)
        for entry in self.data["portfolio"]["oss"]:
            if entry["status"] not in {"merged", "open"}:
                continue
            name = "oss-merged" if entry["status"] == "merged" else "oss-review"
            text = visible_text(self.cards[f"{name}-mobile.svg"])
            self.assertIn("".join(entry["title"].split()), "".join(text.split()))
            self.assertIn("".join(entry["repo"].split()), "".join(text.split()))

    def test_long_content_grows_instead_of_truncating(self) -> None:
        long_title = "WWW " * 30 + "unbroken-" * 24 + " & <complete>"
        context = dict(
            self.context, publications=[("PUBLICATIONS", [(long_title, "2026")])]
        )
        svg = mobile.render_mobile_cards(self.data, context)["publications-mobile.svg"]
        self.assert_bounds(svg)
        self.assertIn("".join(long_title.split()), "".join(visible_text(svg).split()))
        self.assertGreater(float(ET.fromstring(svg).attrib["height"]), 500)

    def test_source_dates_are_only_shown_when_provided(self) -> None:
        missing = dict(self.data, source_updated_at={})
        without_date = mobile.render_mobile_cards(missing, self.context)[
            "github-mobile.svg"
        ]
        self.assertNotIn("Updated", visible_text(without_date))
        data = dict(self.data, source_updated_at={"github": "2026-10-12T09:15:00Z"})
        text = visible_text(
            mobile.render_mobile_cards(data, self.context)["github-mobile.svg"]
        )
        self.assertIn("Updated 2026-10-12", text)
        self.assertNotIn("Updated 2026-10-14", text)

    def test_github_uses_supported_participation_fields(self) -> None:
        data = {"github": {"active_days": 311}}
        text = visible_text(
            mobile.render_mobile_cards(data, self.context)["github-mobile.svg"]
        )
        self.assertIn("311 active days", text)
        self.assertNotIn("reviews", text)
        self.assertNotIn("issues", text)

    def test_unrated_leetcode_has_no_fabricated_percentile(self) -> None:
        data = {
            "leetcode": {
                "badge": "",
                "rating": None,
                "top": None,
                "contests": 0,
                "solved": 12,
                "history": [],
            }
        }
        text = visible_text(
            mobile.render_mobile_cards(data, self.context)["leetcode-mobile.svg"]
        )
        self.assertNotIn("None", text)
        self.assertNotIn("%", text)
        self.assertIn("- Top worldwide", text)

    def test_render_has_no_io_or_input_mutation(self) -> None:
        before = json.dumps((self.data, self.context), sort_keys=True)
        with patch(
            "builtins.open", side_effect=AssertionError("Rendering must not read files")
        ):
            mobile.render_mobile_cards(self.data, self.context)
        self.assertEqual(json.dumps((self.data, self.context), sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()
