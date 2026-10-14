"""Regression checks for broken generated profile assets and unsafe links."""

import datetime as dt
import importlib.util
import json
import subprocess  # nosec B404
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate-readme.py"
SPEC = importlib.util.spec_from_file_location("validate_readme", SCRIPT)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)
TODAY = dt.date(2026, 10, 14)


class ValidateReadmeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / ".github/config").mkdir(parents=True)
        (self.root / "assets/svg").mkdir(parents=True)
        (self.root / ".github/config/profiles.yml").write_text(
            'github:\n  username: "test-user"\n'
            'linkedin:\n  username: "test-user"\n'
            'leetcode:\n  username: "coder123" # Not the GitHub username\n'
            'credly:\n  username: "test-user"\n'
            'portfolio:\n  url: "https://example.com/"\n'
            'career:\n  current_role: "Cloud Consultant (DevOps/MLOps)"\n'
            'resume:\n  path: "https://example.com/resume.pdf"\n',
            encoding="utf-8",
        )
        (self.root / "assets/svg/data.json").write_text(
            json.dumps(
                {
                    "portfolio": {
                        "certifications": [
                            {"name": "AWS certificate", "expiryDate": "2027-01-01"},
                            {
                                "name": "Terraform certificate",
                                "expiryDate": "2026-09-10",
                            },
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        self.write_svg("profile-badges.svg", 'data-active-certifications="1"')
        self.write_svg("profile-badges-light.svg", 'data-active-certifications="1"')
        self.readme = (
            '<a href="https://example.com/">'
            '<picture><source media="(prefers-color-scheme: light)" '
            'srcset="assets/svg/profile-badges-light.svg">'
            '<img src="assets/svg/profile-badges.svg" alt="Cloud profile"></picture></a>\n'
            '<a href="https://example.com/resume.pdf">Resume</a>\n'
            '<a href="https://leetcode.com/coder123/">LeetCode</a>\n'
            '<a href="https://github.com/search?q=is%3Apr&amp;type=pullrequests">PRs</a>\n'
        )
        (self.root / "COMMUNITY.md").write_text(
            '<img src="assets/svg/profile-badges-light.svg" alt="Community">',
            encoding="utf-8",
        )
        self.save_readme()

    def write_svg(self, name, attrs="", body=""):
        (self.root / "assets/svg" / name).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" {attrs}>'
            f"<text>Cloud Consultant (DevOps/MLOps)</text>{body}</svg>",
            encoding="utf-8",
        )

    def save_readme(self):
        (self.root / "README.md").write_text(self.readme, encoding="utf-8")

    def issues(self):
        return validator.validate(self.root, TODAY)

    def test_valid_profile_with_escaped_search_query(self):
        self.assertEqual([], self.issues())

    def test_missing_srcset_asset_fails(self):
        self.readme = self.readme.replace(
            "assets/svg/profile-badges-light.svg", "assets/svg/missing.svg"
        )
        self.save_readme()
        self.assertTrue(
            any(
                "missing image assets/svg/missing.svg" in issue
                for issue in self.issues()
            )
        )

    def test_every_srcset_candidate_is_checked(self):
        self.readme = self.readme.replace(
            'srcset="assets/svg/profile-badges-light.svg"',
            'srcset="assets/svg/profile-badges-light.svg 1x, assets/svg/missing.svg 2x"',
        )
        self.save_readme()
        self.assertTrue(any("missing.svg" in issue for issue in self.issues()))

    def test_malformed_svg_fails(self):
        (self.root / "assets/svg/profile-badges.svg").write_text(
            "<svg><text></svg>", encoding="utf-8"
        )
        self.assertTrue(any("mismatched tag" in issue for issue in self.issues()))

    def test_github_pulls_link_fails(self):
        self.readme += '<a href="https://github.com/pulls?q=is%3Apr">PRs</a>'
        self.save_readme()
        self.assertTrue(any("requires login" in issue for issue in self.issues()))

    def test_unsafe_link_fails(self):
        for link in (
            "javascript:alert(1)",
            "//example.com/",
            "https://user:pass@example.com/",
        ):
            with self.subTest(link=link):
                parsed = validator.ProfileHTML("README.md")
                parsed.feed(f'<a href="{link}">Link</a>')
                self.assertTrue(parsed.issues)

    def test_unescaped_attribute_ampersand_fails(self):
        self.readme = self.readme.replace("&amp;type=", "&type=")
        self.save_readme()
        self.assertTrue(
            any("escape attribute ampersands" in issue for issue in self.issues())
        )

    def test_encoded_path_traversal_fails(self):
        self.readme += '<img src="%2E%2E/outside.svg" alt="Bad path">'
        self.save_readme()
        self.assertTrue(
            any("image escapes repository" in issue for issue in self.issues())
        )

    def test_wrong_leetcode_username_fails(self):
        self.readme = self.readme.replace(
            "leetcode.com/coder123/", "leetcode.com/test-user/"
        )
        self.save_readme()
        self.assertTrue(any("leetcode.username" in issue for issue in self.issues()))

    def test_wrong_role_in_svg_fails(self):
        for path in (self.root / "assets/svg").rglob("*.svg"):
            path.write_text(
                path.read_text().replace("Cloud Consultant", "Software Engineer"),
                encoding="utf-8",
            )
        self.assertTrue(any("career.current_role" in issue for issue in self.issues()))

    def test_expired_certification_cannot_count_as_active(self):
        self.write_svg("profile-badges.svg", 'data-active-certifications="2"')
        self.assertTrue(any("expected 1" in issue for issue in self.issues()))

    def test_invalid_certification_data_reports_error(self):
        (self.root / "assets/svg/data.json").write_text(
            '{"portfolio": []}', encoding="utf-8"
        )
        self.assertTrue(
            any("missing certification expiry data" in issue for issue in self.issues())
        )

    def test_unknown_expiry_is_not_counted_as_active(self):
        path = self.root / "assets/svg/data.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["portfolio"]["certifications"].append({"name": "Unverified certificate"})
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual([], self.issues())

    def test_expiry_day_is_still_active(self):
        self.assertEqual([], validator.validate(self.root, dt.date(2027, 1, 1)))
        self.assertTrue(
            any(
                "expected 0" in issue
                for issue in validator.validate(self.root, dt.date(2027, 1, 2))
            )
        )

    def test_remote_snake_image_is_allowed(self):
        self.readme += (
            '<img src="https://raw.githubusercontent.com/test-user/test-user/output/github-snake.svg" '
            'alt="Contribution snake">'
        )
        self.save_readme()
        self.assertEqual([], self.issues())

    def test_config_value_reader_handles_inline_comment(self):
        config = validator.read_profile_config(
            self.root / ".github/config/profiles.yml"
        )
        self.assertEqual("coder123", config["leetcode.username"])

    def test_cli_exits_nonzero_on_validation_error(self):
        self.readme += '<img src="assets/svg/missing.svg" alt="Missing">'
        self.save_readme()
        result = subprocess.run(  # nosec B603
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("missing image", result.stderr)


if __name__ == "__main__":
    unittest.main()
