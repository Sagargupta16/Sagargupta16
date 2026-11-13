"""Regression checks for broken generated profile assets, unsafe links and confidentiality leaks."""

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
NOW = dt.datetime(2026, 10, 14, 12, tzinfo=dt.timezone.utc)
ROLE = "ProServe (Cloud Consultant) - DevOps/MLOps"
CARD = "assets/svg/certs-status.svg"
# built from code points so this file holds no dash or emoji itself
EN_DASH, EM_DASH, ROCKET, STAR = chr(0x2013), chr(0x2014), chr(0x1F680), chr(0x2B50)
# the renderer's fixed public labels, read from the module both scripts share
CUSTOMER_LABELS = sorted(validator.CUSTOMER_LABELS.values())
PROGRAM_LABEL = next(iter(validator.PROGRAMS.values()))
# a made-up public badge name of the shape Credly uses, with an en dash as Credly writes it
BADGE = f"Example Cloud (EX-CL) Ambassador {EN_DASH} Foundational (L100)"
# the shape assets/svg/data.json has today, built from the renderer's own labels
DATA = {
    "portfolio": {
        "engagements": [
            {
                "when": "Oct 2024 to Aug 2025",
                "client": CUSTOMER_LABELS[0],
                "role": "DevOps Consultant",
                "stack": ["Terraform", "tftest"],
                "kind": "customer",
                "ongoing": False,
                "start": [2024, 10],
                "end": [2025, 8],
            },
            {
                "when": "Jun 2025 to Aug 2025",
                "client": PROGRAM_LABEL,
                "role": "Medical Image Classification MLOps Pipeline",
                "stack": ["SageMaker", "CloudWatch"],
                "kind": "program",
                "ongoing": False,
                "start": [2025, 6],
                "end": [2025, 8],
            },
            {
                "when": "Feb 2026 to now",
                "client": validator.GENERIC_CUSTOMER,
                "role": "Lead DevOps Consultant",
                "stack": ["AWS Organizations", "SCPs"],
                "kind": "customer",
                "ongoing": True,
                "start": [2026, 2],
                "end": None,
            },
        ],
        "achievements": [
            {
                "title": "7x AWS community ambassador",
                "type": "program",
                "year": "2025-2026",
            }
        ],
        "certifications": [
            {"name": "AWS Certified Developer - Associate", "expiryDate": "2027-01-01"},
            {
                "name": "HashiCorp Certified: Terraform Associate (003)",
                "expiryDate": "2026-09-10",
            },
        ],
    },
    "source_updated_at": {
        "github": "2026-10-13T15:28:43+00:00",
        "portfolio": "2026-10-13T15:28:44+00:00",
    },
}


class ValidateReadmeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / ".github/config").mkdir(parents=True)
        (self.root / "assets/svg").mkdir(parents=True)
        self.config = self.root / ".github/config/profiles.yml"
        self.config.write_text(
            'github:\n  username: "test-user"\n'
            'linkedin:\n  username: "test-user"\n'
            'leetcode:\n  username: "coder123" # Not the GitHub username\n'
            'credly:\n  username: "test-user"\n'
            'portfolio:\n  url: "https://example.com/"\n'
            f'career:\n  current_role: "{ROLE}"\n'
            '  start_date: "2024-08"  # full-time start\n'
            'resume:\n  path: "https://example.com/resume.pdf"\n',
            encoding="utf-8",
        )
        self.data = json.loads(json.dumps(DATA))
        self.save_data()
        self.write_svg("certs-status.svg")
        self.write_svg("certs-status-mobile.svg")
        self.readme = (
            '<a href="https://example.com/">'
            '<picture><source media="(min-width: 1012px)" '
            'srcset="assets/svg/certs-status.svg">'
            '<img src="assets/svg/certs-status-mobile.svg" alt="1 active certification"></picture></a>\n'
            '<a href="https://example.com/resume.pdf"><img src="assets/svg/certs-status-mobile.svg" alt="Resume"></a>\n'
            '<a href="https://leetcode.com/coder123/"><img src="assets/svg/certs-status-mobile.svg" alt="LeetCode"></a>\n'
            '<a href="https://github.com/search?q=is%3Apr&amp;type=pullrequests">'
            '<img src="assets/svg/certs-status-mobile.svg" alt="Pull requests"></a>\n'
        )
        self.save_readme()
        self.save_community(
            '<img src="assets/svg/certs-status-mobile.svg" alt="Community">'
        )

    def write_svg(
        self,
        name,
        attrs='data-active-certifications="1"',
        body="<text>2+ years at AWS</text>",
    ):
        (self.root / "assets/svg" / name).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Card" {attrs}>'
            f"<text>{ROLE} at AWS</text>{body}</svg>",
            encoding="utf-8",
        )

    def save_readme(self):
        (self.root / "README.md").write_text(self.readme, encoding="utf-8")

    def save_community(self, text):
        (self.root / "COMMUNITY.md").write_text(text, encoding="utf-8")

    def save_data(self):
        (self.root / "assets/svg/data.json").write_text(
            json.dumps(self.data), encoding="utf-8"
        )

    def issues(self, today=TODAY):
        return validator.validate(self.root, today)

    def assert_issue(self, fragment, today=TODAY):
        issues = self.issues(today)
        self.assertTrue(any(fragment in issue for issue in issues), issues)

    def cli(self, *arguments):
        return subprocess.run(  # nosec B603
            [sys.executable, str(SCRIPT), "--root", str(self.root), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )

    # ------------------------------------------------------------ documents
    def test_valid_profile_with_escaped_search_query(self):
        self.assertEqual([], self.issues())

    def test_missing_mobile_srcset_asset_fails(self):
        self.readme = self.readme.replace(
            'src="assets/svg/certs-status-mobile.svg" alt="1 active',
            'src="assets/svg/missing.svg" alt="1 active',
        )
        self.save_readme()
        self.assert_issue("missing image assets/svg/missing.svg")

    def test_every_srcset_candidate_is_checked(self):
        self.readme = self.readme.replace(
            'srcset="assets/svg/certs-status.svg"',
            'srcset="assets/svg/certs-status.svg 1x, assets/svg/missing.svg 2x"',
        )
        self.save_readme()
        self.assert_issue("missing.svg")

    def test_github_pulls_link_fails(self):
        self.readme += '<a href="https://github.com/pulls?q=is%3Apr">PRs</a>'
        self.save_readme()
        self.assert_issue("requires login")

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
        self.assert_issue("escape attribute ampersands")

    def test_encoded_path_traversal_fails(self):
        self.readme += '<img src="%2E%2E/outside.svg" alt="Bad path">'
        self.save_readme()
        self.assert_issue("image escapes repository")

    def test_wrong_leetcode_username_fails(self):
        self.readme = self.readme.replace(
            "leetcode.com/coder123/", "leetcode.com/test-user/"
        )
        self.save_readme()
        self.assert_issue("leetcode.username")

    def test_remote_image_is_allowed(self):
        self.readme += (
            '<img src="https://raw.githubusercontent.com/test-user/test-user/output/github-snake.svg" '
            'alt="Contribution snake">'
        )
        self.save_readme()
        self.assertEqual([], self.issues())

    def test_relative_link_must_lead_to_a_file(self):
        self.readme += '<a href="COMMUNITY.md#tools">Community tools</a>'
        self.save_readme()
        self.assertEqual([], self.issues())
        self.readme += '<a href="docs/missing.md">Missing</a>'
        self.save_readme()
        self.assert_issue("link target does not exist: docs/missing.md")

    # ------------------------------------------------------------ role and years
    def test_wrong_role_in_svg_fails(self):
        for path in (self.root / "assets/svg").rglob("*.svg"):
            path.write_text(
                path.read_text().replace("Cloud Consultant", "Software Engineer"),
                encoding="utf-8",
            )
        self.assert_issue("career.current_role")

    def test_years_at_aws_must_follow_the_start_date(self):
        self.write_svg("hero.svg", "", "<text>3+ YEARS AT AWS</text>")
        issues = self.issues()
        self.assertEqual(
            [
                "career.start_date: a card shows 3+ years at AWS, expected 2+ from 2024-08"
            ],
            issues,
        )

    def test_years_in_alt_text_must_follow_the_start_date(self):
        self.readme = self.readme.replace("Resume", "Sagar Gupta, 3+ years&#160;at AWS")
        self.save_readme()
        self.assertEqual(
            [
                "career.start_date: a card shows 3+ years at AWS, expected 2+ from 2024-08"
            ],
            self.issues(),
        )
        self.save_community(
            '<img src="assets/svg/certs-status-mobile.svg" alt="2+ years at AWS">'
        )
        self.readme = self.readme.replace("3+", "2+")
        self.save_readme()
        self.assertEqual([], self.issues())

    def test_years_at_aws_turn_over_in_the_start_month(self):
        config = validator.read_profile_config(self.config)

        def check(day):
            return validator.experience_issues(config, "2+ YEARS AT AWS", day)

        self.assertIn("expected 1+ from 2024-08", check(dt.date(2026, 7, 31))[0])
        self.assertEqual([], check(dt.date(2026, 8, 1)))
        self.assertEqual([], check(dt.date(2027, 7, 31)))
        self.assertIn("expected 3+ from 2024-08", check(dt.date(2027, 8, 1))[0])

    def test_malformed_start_date_is_reported(self):
        self.config.write_text(
            self.config.read_text(encoding="utf-8").replace("2024-08", "Aug 2024"),
            encoding="utf-8",
        )
        self.assert_issue("career.start_date: expected YYYY-MM")

    # ------------------------------------------------------------ certifications
    def test_expired_certification_cannot_count_as_active(self):
        self.write_svg("certs-status.svg", 'data-active-certifications="2"')
        self.assert_issue("expected 1")

    def test_status_card_must_carry_the_active_count(self):
        self.write_svg("certs-status-mobile.svg", "")
        self.assert_issue(
            "assets/svg/certs-status-mobile.svg: missing active certification metadata"
        )

    def test_invalid_certification_data_reports_error(self):
        (self.root / "assets/svg/data.json").write_text(
            '{"portfolio": []}', encoding="utf-8"
        )
        self.assert_issue("missing certification expiry data")

    def test_unreadable_expiry_warns_and_is_not_counted_as_active(self):
        self.data["portfolio"]["certifications"] += [
            {"name": "Unverified certificate"},
            {"name": "Timestamped certificate", "expiryDate": "2029-01-31T00:00:00Z"},
        ]
        self.save_data()
        self.assertEqual([], self.issues())
        notes = validator.warnings(self.root, NOW)
        self.assertEqual(2, len(notes), notes)
        self.assertTrue(all("not counted as active" in note for note in notes))

    def test_expiry_day_is_still_active(self):
        self.assertEqual([], self.issues(dt.date(2027, 1, 1)))
        self.assert_issue("expected 0", dt.date(2027, 1, 2))

    def test_active_count_uses_the_cards_own_expiry_rule(self):
        self.assertIs(validator.cert_status, sys.modules["mobile_cards"].cert_status)

    def test_shown_certification_counts_must_match_the_active_count(self):
        # the root attribute still says 1; the text a visitor reads must agree with it
        plants = {
            "card text": lambda text: self.write_svg(
                "certs-status.svg", body=f"<text>{text}</text>"
            ),
            "alt text": lambda text: (
                setattr(self, "readme", self.readme.replace("Resume", text)),
                self.save_readme(),
            ),
        }
        cases = {
            "6 active AWS certifications": "shows 6 active certifications, expected 1",
            "6 ACTIVE CERTIFICATIONS": "shows 6 active certifications, expected 1",
            "6x AWS certified": "shows 6x AWS certified, expected 1x",
            "0 active certifications": "shows 0 active certifications, expected 1",
        }
        for where, plant in plants.items():
            for text, message in cases.items():
                with self.subTest(where=where, text=text):
                    self.setUp()
                    plant(text)
                    self.assertEqual(
                        [f"a card or alt text {message} on {TODAY}"], self.issues()
                    )
        for text in ("1 active AWS certification", "1x AWS certified"):
            with self.subTest(text=text):
                self.setUp()
                plants["alt text"](text)
                self.assertEqual([], self.issues())

    def test_aws_certified_counts_only_active_aws_certifications(self):
        # an active certification from another issuer counts as active, not as AWS
        self.data["portfolio"]["certifications"].append(
            {
                "name": "HashiCorp Certified: Terraform Associate (004)",
                "expiryDate": "2099-01-01",
            }
        )
        self.save_data()
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            self.write_svg(name, 'data-active-certifications="2"')
        self.readme = self.readme.replace(
            "Resume", "2 active certifications, 1x AWS certified"
        )
        self.readme = self.readme.replace("1 active certification", "2 active")
        self.save_readme()
        self.assertEqual([], self.issues())
        self.readme = self.readme.replace("1x AWS certified", "2x AWS certified")
        self.save_readme()
        self.assertEqual(
            [f"a card or alt text shows 2x AWS certified, expected 1x on {TODAY}"],
            self.issues(),
        )

    # ------------------------------------------------------------ confidentiality
    def set_engagement(self, **fields):
        self.data["portfolio"]["engagements"] = [{"when": "Jan 2027 to now", **fields}]
        self.save_data()

    def test_the_renderer_and_the_validator_share_one_set_of_rules(self):
        shared = sys.modules["mobile_cards"]
        for name in (
            "CUSTOMER_LABELS",
            "PROGRAMS",
            "GENERIC_CUSTOMER",
            "PUBLIC_AMBASSADOR",
            "cert_issuer",
        ):
            with self.subTest(name=name):
                self.assertIs(getattr(validator, name), getattr(shared, name))

    def test_only_the_fixed_public_labels_pass(self):
        for client in (*CUSTOMER_LABELS, validator.GENERIC_CUSTOMER):
            with self.subTest(client=client):
                self.set_engagement(client=client, kind="customer")
                self.assertEqual([], self.issues())

    def test_named_customer_fails_whatever_the_separator(self):
        middle_dot = chr(0xB7)
        for client in (
            "DevOps Consultant, Acme Bank",
            "DevOps Consultant - Acme Bank",
            "DevOps Consultant at Acme Bank",
            "Acme Bank",
            "",
            # ending in "customer" is not enough: only the fixed labels pass
            "Acme Bank customer",
            "Acme Bank - customer",
            "Acme Bank, financial services customer",
            "Acme Bank | customer",
            "Acme Bank / customer",
            "Acme Bank: customer",
            f"Acme Bank {middle_dot} customer",
            "ACME BANK CUSTOMER",
            "Fintech customer (Acme Bank)",
            "DevOps Consultant, Enterprise customer",
            f"{CUSTOMER_LABELS[0]} (Acme Bank)",
            CUSTOMER_LABELS[0].upper(),
            PROGRAM_LABEL,  # a program's name is not a customer label
        ):
            with self.subTest(client=client):
                self.set_engagement(client=client, kind="customer")
                issues = self.issues()
                self.assertEqual(1, len(issues), issues)
                self.assertIn(
                    "engagement Jan 2027 to now is not in its public", issues[0]
                )
                # the log of a public workflow must not repeat the name
                self.assertNotIn("acme", issues[0].lower())

    def test_a_label_that_is_not_text_fails(self):
        for client in (None, ["Acme Bank"], {"name": "Acme Bank"}):
            with self.subTest(client=client):
                self.set_engagement(client=client, kind="customer")
                self.assert_issue("is not in its public shape")

    def test_customer_named_only_in_the_name_field_fails(self):
        self.set_engagement(
            client=CUSTOMER_LABELS[0],
            kind="customer",
            name="DevOps Consultant, Acme Bank (Ongoing)",
        )
        self.assert_issue("is not in its public shape")

    def test_only_allowlisted_programs_keep_their_name(self):
        self.set_engagement(client=PROGRAM_LABEL, kind="program")
        self.assertEqual([], self.issues())
        for client in (
            "Acme Partner Program",
            CUSTOMER_LABELS[0],
            PROGRAM_LABEL.upper(),
        ):
            with self.subTest(client=client):
                self.set_engagement(client=client, kind="program")
                self.assert_issue("is not in its public shape")

    def test_ambassador_outside_the_public_wording_fails_everywhere(self):
        # QZX stands in for the internal acronym, which is stored nowhere
        leaks = (
            "5x QZX Ambassador: AI/ML",
            "5x QZX Community Ambassador",
            "5x Qzx Ambassador",
            "5x qzx ambassador",
            "QZX-Ambassador",
            "QZX&#160;Ambassador",
            "5x Q.Z.X. Ambassador",
            "5x AWS QZX Ambassador",
        )
        cases = {
            CARD: lambda leak: self.write_svg(
                "certs-status.svg", body=f"<text>{leak}</text>"
            ),
            "assets/svg/certs-status-mobile.svg": lambda leak: self.write_svg(
                "certs-status-mobile.svg",
                f'data-active-certifications="1" data-note="{leak.upper()}"',
            ),
            "assets/svg/hero.svg": lambda leak: self.write_svg(
                "hero.svg", "", f'<g aria-label="Sagar Gupta, {leak}"/>'
            ),
            "README.md": lambda leak: (
                setattr(self, "readme", self.readme.replace("Resume", leak)),
                self.save_readme(),
            ),
            "COMMUNITY.md": lambda leak: self.save_community(
                f'<img src="assets/svg/certs-status-mobile.svg" alt="{leak}">'
            ),
            "assets/svg/data.json": lambda leak: (
                self.data["portfolio"]["achievements"].append({"title": leak}),
                self.save_data(),
            ),
        }
        for name, plant in cases.items():
            for leak in leaks:
                with self.subTest(file=name, leak=leak):
                    self.setUp()
                    plant(leak)
                    issues = self.issues()
                    self.assertEqual(1, len(issues), issues)
                    self.assertTrue(
                        issues[0].startswith(f'{name}: "ambassador" appears outside'),
                        issues,
                    )
                    self.assertNotIn("qzx", issues[0].lower())

    def test_ambassador_split_across_card_text_still_fails(self):
        for body in (
            "<text>5x QZX</text><text>Ambassador</text>",
            "<text>5x QZX</text><text>Community</text><text>Ambassador</text>",
            "<text>5x QZX Ambas<tspan>sador</tspan></text>",
            "<text>5x QZX&#160;Ambassador</text>",
            # a tag inside the public wording may not carry the word itself
            '<text>AWS community <tspan data-note="QZX ambassador"/>ambassador</text>',
        ):
            with self.subTest(body=body):
                self.write_svg("certs-status.svg", body=body)
                self.assertEqual(
                    [
                        f'{CARD}: "ambassador" appears outside the public wording '
                        '"AWS community ambassador"; the internal community acronym '
                        "is never published"
                    ],
                    self.issues(),
                )
        # a no-break space in the snapshot, stored as a JSON escape, still fails
        self.write_svg("certs-status.svg")
        self.data["portfolio"]["achievements"].append(
            {"title": f"5x QZX{chr(0xA0)}Ambassador"}
        )
        self.save_data()
        self.assert_issue('assets/svg/data.json: "ambassador" appears outside')

    def test_public_ambassador_wording_passes(self):
        self.write_svg(
            "publications.svg",
            "",
            "<text>7x AWS community ambassador</text><text>7X AWS COMMUNITY AMBASSADOR</text>"
            # a card that wraps the wording onto its next line
            '<text>7x AWS community</text><text x="0" y="9">ambassador (2025-2026)</text>'
            "<text>AWS&#160;community ambassador</text>",
        )
        self.readme = self.readme.replace(
            "Resume", "7x AWS community ambassador (2025-2026)"
        )
        self.save_readme()
        self.assertEqual([], self.issues())

    def test_a_badge_name_passes_only_when_the_credly_block_lists_it(self):
        # the published copies fold the en dash Credly writes into a hyphen
        shown = BADGE.replace(EN_DASH, "-")
        self.readme = self.readme.replace("Resume", shown)
        self.save_readme()
        self.write_svg("certs.svg", "", f"<title>{shown}</title>")
        self.assert_issue('README.md: "ambassador" appears outside')
        self.assert_issue('assets/svg/certs.svg: "ambassador" appears outside')
        (self.root / "assets/credly-badges.md").write_text(
            f'<a href="https://www.credly.com/badges/1" title="{BADGE}">'
            f'<picture><img src="https://images.credly.com/1.png" alt="{BADGE}"></picture></a>',
            encoding="utf-8",
        )
        self.assertEqual([], self.issues())
        # a listed name covers that exact name only, not another phrase with the word
        self.write_svg(
            "certs.svg", "", "<title>QZX Ambassador Foundational (L100)</title>"
        )
        self.assert_issue('assets/svg/certs.svg: "ambassador" appears outside')

    # ------------------------------------------------------------ dashes and emoji
    def test_dash_or_emoji_fails_in_every_published_file(self):
        plants = {
            "README.md": lambda mark: (
                setattr(self, "readme", self.readme + f"\n<!-- {mark} -->"),
                self.save_readme(),
            ),
            "COMMUNITY.md": lambda mark: self.save_community(
                f'<img src="assets/svg/certs-status-mobile.svg" alt="Tools {mark} more">'
            ),
            CARD: lambda mark: self.write_svg(
                "certs-status.svg", body=f"<text>Developer {mark} Associate</text>"
            ),
        }
        marks = {
            EN_DASH: "en or em dash (U+2013)",
            EM_DASH: "en or em dash (U+2014)",
            ROCKET: "an emoji (U+1F680)",
            STAR: "an emoji (U+2B50)",
            # an entity renders as the character itself
            "&#8212;": "en or em dash (U+2014)",
            "&#x2013;": "en or em dash (U+2013)",
            "&#128640;": "an emoji (U+1F680)",
        }
        # named entities are HTML only; an SVG with one does not parse at all
        named = {
            "&mdash;": "en or em dash (U+2014)",
            "&ndash;": "en or em dash (U+2013)",
        }
        for name, plant in plants.items():
            for mark, message in {**marks, **({} if name == CARD else named)}.items():
                with self.subTest(file=name, mark=mark):
                    self.setUp()
                    plant(mark)
                    issues = self.issues()
                    self.assertEqual(1, len(issues), issues)
                    self.assertTrue(issues[0].startswith(f"{name}:"), issues)
                    self.assertIn(message, issues[0])

    def test_markdown_links_and_images_fail_in_the_generated_pages(self):
        for snippet in (
            "See [the docs](docs/nope.md).",
            "![card](assets/svg/nope.svg)",
            "![card](http://example.com/x.png)",
            "[docs]: https://example.com/",
        ):
            for name in ("README.md", "COMMUNITY.md"):
                with self.subTest(file=name, snippet=snippet):
                    self.setUp()
                    if name == "README.md":
                        self.readme += f"\n{snippet}\n"
                        self.save_readme()
                    else:
                        self.save_community(
                            '<img src="assets/svg/certs-status-mobile.svg" alt="Community">'
                            f"\n\n{snippet}\n"
                        )
                    issues = self.issues()
                    self.assertEqual(1, len(issues), issues)
                    self.assertRegex(
                        issues[0], rf"^{name}:\d+: Markdown link or image syntax"
                    )

    def test_plain_symbols_are_not_emoji(self):
        symbols = "".join(chr(point) for point in (0x2192, 0x2713, 0x2605, 0xB7))
        self.write_svg("certs-status.svg", body=f"<text>Next {symbols}</text>")
        self.assertEqual([], self.issues())

    # ------------------------------------------------------------ svg safety
    def test_malformed_svg_fails(self):
        (self.root / "assets/svg/certs-status.svg").write_text(
            "<svg><text></svg>", encoding="utf-8"
        )
        self.assert_issue("mismatched tag")

    def test_card_that_no_document_shows_is_still_checked(self):
        (self.root / "assets/svg/orphan.svg").write_text(
            "<svg><text></svg>", encoding="utf-8"
        )
        self.assert_issue("assets/svg/orphan.svg: mismatched tag")

    def test_card_must_be_self_contained_and_script_free(self):
        cases = {
            '<image href="https://example.com/logo.png"/>': "<image> href points outside the file",
            '<image xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="logo.png"/>': "<image> href points outside the file",
            '<a href="https://example.com/"><text>Link</text></a>': "<a> href points outside the file",
            "<script>alert(1)</script>": "SVG must not contain <script>",
            '<foreignObject width="10" height="10"/>': "SVG must not contain <foreignObject>",
            '<rect width="1" height="1" onload="alert(1)"/>': "event attribute onload on <rect>",
            "<style>@import url(https://example.com/font.css);</style>": "@import and @font-face",
            "<style>@font-face{font-family:x;src:url(data:font/woff2;base64,AA==)}</style>": "@import and @font-face",
            '<rect width="1" height="1" fill="url(https://example.com/paint.svg#p)"/>': "url() points outside the file",
        }
        for body, message in cases.items():
            with self.subTest(body=body):
                self.write_svg("certs-status.svg", body=body)
                self.assert_issue(f"{CARD}: {message}")

    def test_fragments_and_data_uris_are_allowed(self):
        self.write_svg(
            "certs-status.svg",
            body='<defs><clipPath id="card"><rect width="9" height="9"/></clipPath></defs>'
            '<g clip-path="url(#card)"><use href="#card"/>'
            '<image href="data:image/png;base64,iVBORw0KGgo=" width="1" height="1"/></g>',
        )
        self.assertEqual([], self.issues())

    def test_smil_lists_must_line_up(self):
        animate = '<rect width="1" height="1"><animate attributeName="opacity" dur="2s" {}/></rect>'
        cases = {
            'values="0;1;0" keyTimes="0;1"': "has 2 keyTimes for 3 values",
            'values="0;1" keyTimes="0;0.8"': "keyTimes must rise from 0 to 1",
            'values="0;1" keyTimes="0.2;1"': "keyTimes must rise from 0 to 1",
            'values="0;1;0" keyTimes="0;0.9;0.5"': "keyTimes must rise from 0 to 1",
            'values="0;1" keyTimes="0;soon"': "keyTimes is not a list of numbers",
            'values="0;0;1" keyTimes="0;0.5;1" calcMode="spline" keySplines="0 0 1 1"': "needs 2 keySplines for 3 keyTimes",
        }
        for attributes, message in cases.items():
            with self.subTest(attributes=attributes):
                self.write_svg("certs-status.svg", body=animate.format(attributes))
                self.assert_issue(f"{CARD}: <animate> {message}")
        motion = (
            '<circle r="2"><animateMotion dur="2s" path="M0 0H9" '
            'keyPoints="0;1;1" keyTimes="0;1"/></circle>'
        )
        self.write_svg("certs-status.svg", body=motion)
        self.assert_issue(f"{CARD}: <animateMotion> has 2 keyTimes for 3 values")

    def test_well_formed_smil_passes(self):
        self.write_svg(
            "certs-status.svg",
            body='<rect width="1" height="1">'
            '<animate attributeName="opacity" values="0;0;1" keyTimes="0;0.2;1" dur="0.5s" '
            'fill="freeze" calcMode="spline" keySplines="0 0 1 1;0.16 1 0.3 1"/>'
            '<animate attributeName="x" values="0;4;8" keyTimes="0;0.33;0.66" dur="6s" '
            'calcMode="discrete" repeatCount="indefinite"/>'
            '<animate attributeName="y" from="0" to="4" dur="2s"/></rect>',
        )
        self.assertEqual([], self.issues())

    # ------------------------------------------------------------ staleness
    def test_stale_source_warns_without_failing(self):
        self.assertEqual([], validator.warnings(self.root, NOW))
        self.data["source_updated_at"]["github"] = "2026-10-10T09:00:00+00:00"
        self.data["source_updated_at"]["views"] = "yesterday"
        self.save_data()
        self.assertEqual(
            [
                "assets/svg/data.json: github data is 4 days old, last refreshed 2026-10-10",
                "assets/svg/data.json: views has no readable refresh time",
            ],
            validator.warnings(self.root, NOW),
        )
        self.assertEqual([], self.issues())

    def test_three_days_old_is_not_stale_yet(self):
        self.data["source_updated_at"] = {"github": "2026-10-11T12:00:00+00:00"}
        self.save_data()
        self.assertEqual([], validator.warnings(self.root, NOW))

    def test_cli_prints_warning_annotations_and_still_passes(self):
        # the command line reads the real clock, so nothing here may depend on the date
        self.data["source_updated_at"]["github"] = "2020-01-01T00:00:00+00:00"
        self.data["portfolio"]["certifications"] = [
            {"name": "Never expires in a test run", "expiryDate": "9999-12-31"}
        ]
        self.save_data()
        for name in ("certs-status.svg", "certs-status-mobile.svg"):
            self.write_svg(name, body="")
        result = self.cli()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("::warning::assets/svg/data.json: github data is", result.stdout)

    # ------------------------------------------------------------ command line
    def test_config_value_reader_handles_inline_comment(self):
        config = validator.read_profile_config(self.config)
        self.assertEqual("coder123", config["leetcode.username"])
        self.assertEqual("2024-08", config["career.start_date"])

    def test_cli_config_value_prints_one_setting(self):
        result = self.cli("--config-value", "credly.username")
        self.assertEqual((0, "test-user\n"), (result.returncode, result.stdout))
        result = self.cli("--config-value", "career.start_date")
        self.assertEqual((0, "2024-08\n"), (result.returncode, result.stdout))

    def test_cli_config_value_fails_on_an_unknown_key(self):
        result = self.cli("--config-value", "credly.missing")
        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("Profile configuration error", result.stderr)

    def test_cli_exits_nonzero_on_validation_error(self):
        self.readme += '<img src="assets/svg/missing.svg" alt="Missing">'
        self.save_readme()
        result = self.cli()
        self.assertEqual(1, result.returncode)
        self.assertIn("missing image", result.stderr)


if __name__ == "__main__":
    unittest.main()
