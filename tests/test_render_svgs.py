"""Regression checks for GitHub-compatible embedding and snapshot freshness."""

import importlib.util
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET  # nosec B405
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("render_svgs", SCRIPTS / "render-svgs.py")
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


class RendererTests(unittest.TestCase):
    def test_divider_sources_are_resolved_when_readme_is_rendered(self):
        data = json.loads(renderer.DATA_FILE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with patch.object(renderer, "OUT", out):
                self.assertNotIn("divider-mobile.svg", renderer.render_readme(data))
                (out / "divider-mobile.svg").touch()
                self.assertIn("divider-mobile.svg", renderer.render_readme(data))

    def test_picture_selects_the_phone_layout_on_small_screens(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "card-mobile.svg").touch()
            with patch.object(renderer, "OUT", out):
                picture = ET.fromstring(renderer._img("card.svg", "A & B", "400"))  # nosec B314
        sources = picture.findall("source")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].get("media"), "(max-width: 600px)")
        self.assertIn("card-mobile.svg", sources[0].get("srcset"))
        self.assertEqual(picture.find("img").get("width"), "400")
        self.assertEqual(picture.find("img").get("alt"), "A & B")
        self.assertNotIn("style=", ET.tostring(picture, encoding="unicode"))

    def test_failed_fetch_preserves_success_timestamp_and_values(self):
        snapshot = {
            "views": 12,
            "leetcode": {"rating": 2166, "solved": 1325},
            "github": {"stars": 302},
            "source_updated_at": {
                "views": "2026-10-01T00:00:00+00:00",
                "leetcode": "2026-10-02T00:00:00+00:00",
                "github": "2026-10-03T00:00:00+00:00",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            with (
                patch.object(renderer, "DATA_FILE", path),
                patch.object(renderer, "OFFLINE", False),
                patch.object(renderer, "fetch_views", side_effect=OSError("offline")),
                patch.object(
                    renderer, "fetch_leetcode", side_effect=OSError("offline")
                ),
                patch.object(renderer, "fetch_github", return_value=None),
            ):
                actual = renderer.load_data()
        self.assertEqual(actual, snapshot)

    def test_offline_snapshot_does_not_fetch_or_mark_data_current(self):
        with (
            patch.object(renderer, "OFFLINE", True),
            patch.object(
                renderer, "fetch", side_effect=AssertionError("network request")
            ),
            patch.object(
                renderer, "record_refresh", side_effect=AssertionError("false refresh")
            ),
        ):
            data = renderer.load_data()
            renderer.refresh_portfolio(data)
        self.assertTrue(data["portfolio"]["featured"])

    def test_long_project_copy_is_not_truncated_or_outside_canvas(self):
        project = {
            "title": "A project with a deliberately long descriptive title",
            "description": "A useful description.",
            "card_summary": " ".join(["Useful information"] * 20),
            "tools_tech": ["Python", "TypeScript"],
        }
        for mobile in (False, True):
            root = ET.fromstring(renderer.render_project_card(project, 0, mobile))  # nosec B314
            height = float(root.get("height"))
            texts = root.findall(".//{http://www.w3.org/2000/svg}text")
            for text in texts:
                self.assertLess(float(text.get("y")), height)
            body = " ".join("".join(text.itertext()) for text in texts)
            self.assertIn(project["card_summary"], body)

    def test_links_escape_queries_without_changing_destination(self):
        url = renderer.MERGED_URL
        markup = renderer._link(url, "Open pull requests")
        self.assertIn("&amp;type=pullrequests", markup)
        self.assertEqual(ET.fromstring(markup).get("href"), url)  # nosec B314
        self.assertNotIn("github.com/pulls", url)

    def test_active_count_excludes_expired_certificates(self):
        data = {
            "portfolio": {
                "certifications": [
                    {"name": "AWS Certified Developer", "expiryDate": "2099-01-01"},
                    {"name": "Terraform Associate", "expiryDate": "2020-01-01"},
                    {"name": "Certificate with unknown expiry"},
                ]
            }
        }
        root = ET.fromstring(renderer.render_certification_status(data))  # nosec B314
        self.assertEqual(root.get("data-active-certifications"), "1")
        self.assertIn("Previously earned", root.get("aria-label"))
        self.assertIn("Expiry not recorded", root.get("aria-label"))

    def test_leetcode_response_without_badge_keeps_the_last_one(self):
        payload = {
            "data": {
                "matchedUser": {
                    "submitStats": {
                        "acSubmissionNum": [{"difficulty": "All", "count": 3}]
                    }
                },
                "userContestRanking": {
                    "rating": 1400,
                    "topPercentage": 60,
                    "attendedContestsCount": 1,
                    "badge": None,
                },
                "userContestRankingHistory": [],
                "allQuestionsCount": [],
            }
        }
        with patch.object(renderer, "fetch", return_value=json.dumps(payload).encode()):
            result = renderer.fetch_leetcode({"badge": "Guardian"})
        self.assertEqual(result["badge"], "Guardian")
        payload["errors"] = [{"message": "Partial response"}]
        with patch.object(renderer, "fetch", return_value=json.dumps(payload).encode()):
            with self.assertRaises(LookupError):
                renderer.fetch_leetcode({"badge": "Guardian"})

    def test_customer_names_never_reach_the_snapshot(self):
        pf = {
            "engagements": [
                {
                    "when": "Oct 2024 to Aug 2025",
                    "client": "Acme Bank",
                    "name": "DevOps Consultant - Acme Bank",
                },
                {
                    "when": "Jan 2027 to now",
                    "client": "Globex",
                    "name": "Lead DevOps Consultant - Globex (Ongoing)",
                },
                {
                    "when": "Jun 2025 to Aug 2025",
                    "client": "MLOps SME Program",
                    "name": "Pipeline (SME Program)",
                },
            ],
            "achievements": [{"title": "5x TFC Ambassador: AI/ML, Serverless"}],
        }
        public = renderer.public_portfolio(pf)
        text = json.dumps(public)
        self.assertNotIn("Acme", text)
        self.assertNotIn("Globex", text)
        self.assertNotIn("TFC", text)
        clients = [e["client"] for e in public["engagements"]]
        self.assertEqual(
            clients,
            ["Global financial services customer", "AWS customer", "MLOps SME Program"],
        )
        self.assertEqual(
            public["engagements"][1]["name"],
            "Lead DevOps Consultant - AWS customer (Ongoing)",
        )
        self.assertEqual(
            public["achievements"][0]["title"], "5x AWS community ambassador"
        )

    def test_highlights_leave_out_figures_without_data(self):
        self.assertEqual(renderer.highlight_tiles({}), [])
        pf = {
            "samples": [{"title": "Sample"}],
            "achievements": [{"title": "Associate Speaker Certification"}],
            "certifications": [{"name": "Expired", "expiryDate": "2020-01-01"}],
        }
        self.assertEqual(renderer.highlight_tiles(pf), [("1", "published AWS samples")])


if __name__ == "__main__":
    unittest.main()
