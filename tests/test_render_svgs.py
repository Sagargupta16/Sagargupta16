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
    def test_picture_wraps_image_with_numeric_width(self):
        picture = ET.fromstring(renderer._img("card.svg", "A & B", "400"))  # nosec B314
        self.assertEqual(picture.findall("source"), [])
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
        root = ET.fromstring(renderer.render_project_card(project, 0))  # nosec B314
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


if __name__ == "__main__":
    unittest.main()
