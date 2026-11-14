"""Checks for the data side of the profile: the public snapshot, the card context and the page.

Fixtures are shaped like the portfolio repo's JSON files, not copied from the
live snapshot, so a refresh of assets/svg/data.json cannot fail these tests.
The checks that do read the checked-in snapshot assert rules, never values.
"""

import contextlib
import datetime
import importlib.util
import io
import json
import re
import sys
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET  # nosec B405
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("render_svgs", SCRIPTS / "render-svgs.py")
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)

TODAY = datetime.date(2026, 11, 13)
# every key of the ctx table in docs/readme-rendering.md, section "The context"
CTX_KEYS = {
    "today",
    "aws_title",
    "aws_title_long",
    "location",
    "disclaimer",
    "intro",
    "intro_keywords",
    "hero_lines",
    "availability",
    "years_at_aws",
    "proof",
    "milestones",
    "engagements",
    "education",
    "recognition",
    "samples",
    "projects",
    "project_count",
    "tools",
    "oss",
    "certs",
    "leetcode",
    "github",
    "contests",
    "coding_stats",
    "headers",
    "header_counts",
    "get_cards",
    "connect",
    "icon",
    "updated",
}
RAW_CLIENTS = ("Acme Bank", "Globex", "Initech")
SVG = '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}"/>'


def tool(title: str, repo: str) -> dict:
    return {
        "title": title,
        "description": f"{title} does one thing. And more.",
        "tools_tech": ["Python"],
        "github": f"https://github.com/Sagargupta16/{repo}",
    }


def portfolio_files() -> tuple[dict, dict, dict]:
    """Return (experience, projects, extra) in the shape of the portfolio repo's data files."""
    experience = {
        "professional_experience": [
            {
                "projects": [
                    {
                        "name": "Lead DevOps Consultant, Enterprise customer (Ongoing)",
                        "date": "Feb 2026 - Present",
                        "skills": ["AWS", "AWS Organizations", "SCPs"],
                    },
                    {
                        "name": "DevOps Consultant, Acme Bank",
                        "date": "Aug 2025 - Nov 2025",
                        "skills": ["AWS", "Terraform", "Cloud Migration"],
                    },
                    {
                        "name": "Medical Image Classification MLOps Pipeline (SME Program)",
                        "date": "Jun 2025 - Aug 2025",
                        "skills": ["AWS", "SageMaker"],
                        "link": "https://github.com/aws-samples/sample-sagemaker-image-classification-mlops",
                    },
                    {
                        "name": "DevOps Consultant - Globex",
                        "date": "Oct 2024 - Aug 2025",
                        "skills": ["AWS", "Terraform", "tftest"],
                    },
                ],
                "internal_contributions": [
                    {"title": "Internal tech talks", "type": "talk", "year": "2025"},
                    {"title": "Peer reviewer", "type": "program", "year": "2025-2026"},
                    {
                        "title": "AWS Sample Published: Something (aws-samples)",
                        "type": "publication",
                        "year": "2026",
                    },
                ],
                "internal_achievements": [
                    {
                        "title": "7x XYZ Ambassador across 4 communities: A, B; QRST Member",
                        "type": "program",
                        "year": "2025-2026",
                    },
                    {"title": "Senior Speaker Certification", "year": "2026"},
                ],
            },
            {"title": "Intern", "company": "Somewhere", "date": "May 2023 - July 2023"},
        ]
    }
    projects = {
        "featured_projects": [
            {
                "title": "SageMaker Image Classification MLOps",
                "description": "A sample.",
                "date": "July 2026",
                "tools_tech": ["Terraform"],
                "github": "https://github.com/aws-samples/sample-sagemaker-image-classification-mlops",
                "organization": "aws-samples",
            },
            {
                "title": "AgentCore Harness Agent with Governed MCP Tools",
                "description": "A sample.",
                "date": "October 2026",
                "tools_tech": ["Terraform"],
                "github": "https://github.com/aws-samples/sample-agentcore-harness-agent-terraform",
                "organization": "aws-samples",
            },
            {
                "title": "AWS Organizations Governance on Control Tower",
                "description": "A sample.",
                "date": "September 2026",
                "tools_tech": ["Terraform"],
                "github": "https://github.com/aws-samples/sample-aws-terraform-org-governance",
                "organization": "aws-samples",
            },
            {
                "title": "Ledger Sync",
                "description": "A dashboard.",
                "date": "July 2026",
                "tools_tech": ["TypeScript", "FastAPI"],
                "github": "https://github.com/Sagargupta16/ledger-sync",
                "live": "https://sagargupta.online/ledger-sync/",
            },
            {
                "title": "Brand New Thing",
                "description": "A project the script has no one-liner for.",
                "date": "November 2026",
                "tools_tech": ["Go"],
                "github": "https://github.com/Sagargupta16/brand-new-thing",
            },
        ],
        "collaborative_projects": [{}],
        "other_projects": [{}, {}],
        "community_projects": [
            tool("Deploy Guide", "deploy-guide"),
            tool("MCP Toolkit", "mcp-toolkit"),
            tool("Claude Skills", "claude-skills"),
            tool("ITR Agent", "itr-agent"),
            tool("readme-kit", "readme-kit"),
            tool("Bedrock Multi-Model MCP", "bedrock-multi-model-mcp"),
            tool("svg-forge", "svg-forge"),
            tool("skillcheck", "skillcheck"),
            tool("Claude Cost Optimizer", "claude-cost-optimizer"),
            tool("Awesome MCP Servers", "awesome-mcp-servers"),
            tool("orrery", "orrery"),
        ],
        "open_source_contributions": [
            {
                "repo": "axios/axios",
                "stars": 100,
                "title": "Fix a thing",
                "url": "https://github.com/axios/axios/pull/1",
                "merged_at": "2026-07-13",
                "status": "merged",
            },
            {
                "repo": "apache/airflow",
                "stars": 50,
                "title": "Add a thing",
                "url": "https://github.com/apache/airflow/pull/2",
                "merged_at": "2026-03-23",
                "status": "merged",
            },
            {
                "repo": "axios/axios",
                "stars": 100,
                "title": "Fix another thing",
                "url": "https://github.com/axios/axios/pull/3",
                "merged_at": "2026-10-01",
                "status": "merged",
            },
            {
                "repo": "aws-ia/terraform-aws-vpc",
                "stars": 10,
                "title": "Fix co-authored into a release",
                "url": "https://github.com/aws-ia/terraform-aws-vpc/commit/489899c7198b6d0099275e2ffee6852b98c6012b",
                "status": "merged",
            },
            {
                "repo": "hashicorp/terraform-provider-aws",
                "stars": 70,
                "title": "Open one",
                "url": "https://github.com/hashicorp/terraform-provider-aws/pull/4",
                "status": "open",
            },
            {
                "repo": "hashicorp/terraform-provider-aws",
                "stars": 70,
                "title": "Open two",
                "url": "https://github.com/hashicorp/terraform-provider-aws/pull/5",
                "status": "open",
            },
            {
                "repo": "forem/selfhost",
                "stars": 5,
                "title": "Fix AWS Ansible deploy",
                "url": "https://github.com/forem/selfhost/pull/91",
                "status": "closed",
                "note": "Community confirmed working. Maintainers left before review.",
            },
        ],
        "community_discussions": [
            {"repo": "community/community", "status": "accepted"},
            {"repo": "community/community", "status": "accepted"},
            {"repo": "community/community", "status": "helpful"},
            {"repo": "somebody/else", "status": "accepted"},
        ],
    }
    extra = {
        "personal": {
            "intro": "Cloud consultant at AWS Professional Services: Terraform and CI/CD. I build MCP servers.",
            "hero_taglines": ["Guardrails on from day one.", "Landing zones as code."],
            "availability": "Now: leading DevOps on a landing zone",
        },
        "education": [
            {
                "title": "Master of Computer Applications (MCA)",
                "institution": "NIT Warangal",
                "location": "Warangal, Telangana, India",
                "date": "September 2021 - July 2024",
                "cgpa": "8.38",
                "achievements": ["Passed with First Division with Distinction"],
                "skills": ["dropped from the snapshot"],
            },
            {"title": "Class XII", "institution": "A school", "cgpa": ""},
        ],
        "achievements": {
            "coding_platform_stats": {"leetcode": {"best_contest_rank": "63"}},
            "certifications": [
                {
                    "name": "AWS Certified Developer - Associate",
                    "expiryDate": "2099-01-01",
                },
                {"name": "AWS Certified AI Practitioner", "expiryDate": "2099-01-01"},
                {
                    "name": "HashiCorp Certified: Terraform Associate",
                    "expiryDate": "2020-01-01",
                },
                {"name": "A certificate with no expiry on record"},
            ],
            "achievements": [{"title": "1st Place - A contest", "date": "March 2023"}],
        },
    }
    return experience, projects, extra


def snapshot() -> dict:
    with contextlib.redirect_stdout(io.StringIO()):
        return renderer.portfolio_snapshot(*portfolio_files())


def data_fixture() -> dict:
    return {
        "leetcode": {"badge": "Guardian", "rating": 2100.4, "history": [1500, 2166]},
        "github": {
            "stars": 12,
            "repo_stars": {
                "orrery": 7,
                "awesome-mcp-servers": 88,
                "itr-agent": 10,
                "deploy-guide": 3,
                "mcp-toolkit": 5,
                "ledger-sync": 10,
            },
        },
        "portfolio": snapshot(),
        "oss_stars": {"axios/axios": 109000, "apache/airflow": 47000},
        "npm": {
            "@sagargupta1610/orrery": 1793,
            "@sagargupta1610/skillcheck": 2070,
            "itr-agent": 32,
        },
        "source_updated_at": {"leetcode": "2026-11-13T00:00:00+00:00"},
    }


@contextlib.contextmanager
def scratch_repo(data: dict | None = None):
    """Point the renderer at an empty folder so no test reads or writes the real assets."""
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory)
        if data is not None:
            (out / "data.json").write_text(json.dumps(data), encoding="utf-8")
        with (
            patch.object(renderer, "OUT", out),
            patch.object(renderer, "DATA_FILE", out / "data.json"),
            patch.object(renderer, "ICONS_FILE", out / "icons.json"),
            patch.object(renderer, "CREDLY_PATH", out / "credly-badges.md"),
            patch.object(renderer, "README_PATH", out / "README.md"),
            patch.object(renderer, "COMMUNITY_PAGE", out / "COMMUNITY.md"),
            patch.object(renderer, "LABELS", {}),
            patch.object(renderer, "utc_today", return_value=TODAY),
        ):
            yield out


def context(data: dict | None = None) -> dict:
    with scratch_repo(), contextlib.redirect_stdout(io.StringIO()):
        return renderer.build_context(data or data_fixture())


class EngagementTests(unittest.TestCase):
    def test_comma_and_dash_customer_names_are_both_scrubbed(self):
        public = snapshot()
        text = json.dumps(public)
        for raw in RAW_CLIENTS:
            self.assertNotIn(raw, text)
        rows = {e["when"]: e for e in public["engagements"]}
        dash = rows["Oct 2024 to Aug 2025"]  # 'Role - Client', the older format
        self.assertEqual(dash["client"], "Global financial services customer")
        self.assertEqual(dash["role"], "DevOps Consultant")
        comma = rows["Aug 2025 to Nov 2025"]  # 'Role, Client', today's format
        self.assertEqual(comma["client"], "Financial market infrastructure customer")
        self.assertEqual(comma["role"], "DevOps Consultant")
        self.assertEqual(
            [comma["kind"], comma["start"], comma["end"]],
            ["customer", [2025, 8], [2025, 11]],
        )
        self.assertEqual(comma["stack"], ["Terraform"])
        for row in public["engagements"]:
            self.assertNotIn("name", row)
            self.assertNotIn("link", row)

    def test_the_role_is_kept_and_the_label_comes_from_the_month_table(self):
        current = snapshot()["engagements"][-1]
        self.assertEqual(current["client"], renderer.CUSTOMER_LABELS["Feb 2026"])
        self.assertEqual(current["role"], "Lead DevOps Consultant")
        self.assertTrue(current["ongoing"])
        self.assertEqual([current["when"], current["end"]], ["Feb 2026 to now", None])

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
                self.assertIs(getattr(renderer, name), getattr(shared, name))

    def test_a_raw_client_can_never_pass(self):
        middle_dot = chr(0xB7)
        names = [
            "DevOps Consultant, Acme Bank",
            "DevOps Consultant - Acme Bank",
            "Lead DevOps Consultant - Acme Bank, Inc (Ongoing)",
            "Consultant, Initech, Acme Bank",
            "Acme Bank platform rebuild",
            "Acme Bank",
            "",
            # a label the portfolio wrote that ends in "customer" is never kept
            "DevOps Consultant, Acme Bank customer",
            "DevOps Lead, Acme Bank customer (Ongoing)",
            "DevOps Consultant - Acme Bank - customer",
            "DevOps Consultant, Acme Bank, financial services customer",
            "DevOps Consultant, Acme Bank | customer",
            "DevOps Consultant, Acme Bank / customer",
            "DevOps Consultant, Acme Bank: customer",
            f"DevOps Consultant, Acme Bank {middle_dot} customer",
            "DEVOPS CONSULTANT, ACME BANK CUSTOMER",
            "DevOps Consultant, Fintech customer (Acme Bank)",
        ]
        shapes = [{"name": n, "date": "Jan 2027 - Present"} for n in names]
        # an older cache, and caches someone edited by hand
        shapes.append(
            {
                "name": "Role - Acme Bank",
                "client": "Acme Bank",
                "when": "Jan 2027 to now",
            }
        )
        shapes.append(
            {"client": "Acme Bank", "role": "DevOps Consultant", "kind": "program"}
        )
        for client in (
            "Acme Bank customer",
            "Fintech customer (Acme Bank)",
            "ACME BANK CUSTOMER",
        ):
            shapes.append(
                {
                    "client": client,
                    "role": "DevOps Consultant",
                    "when": "Jan 2027 to now",
                }
            )
        with contextlib.redirect_stdout(io.StringIO()):
            public = renderer.public_portfolio({"engagements": shapes})["engagements"]
            twice = renderer.public_portfolio({"engagements": public})["engagements"]
        self.assertEqual(public, twice)  # scrubbing a scrubbed snapshot changes nothing
        for row in public:
            self.assertNotIn("acme", json.dumps(row).lower())
            self.assertEqual(row["kind"], "customer")
            self.assertEqual(row["client"], renderer.GENERIC_CUSTOMER)

    def test_a_customer_label_always_comes_from_the_month_table(self):
        for month, label in renderer.CUSTOMER_LABELS.items():
            for name in (
                "DevOps Consultant, Acme Bank customer",
                "DevOps Consultant, Fintech customer (Acme Bank)",
                f"DevOps Consultant, {renderer.GENERIC_CUSTOMER}",
            ):
                with self.subTest(month=month, name=name):
                    row = renderer._public_engagement(
                        {"name": name, "date": f"{month} - Present"}
                    )
                    self.assertEqual(row["client"], label)
                    self.assertEqual(row["role"], "DevOps Consultant")

    def test_a_month_missing_from_the_table_warns_and_shows_the_generic_label(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            row = renderer._public_engagement(
                {
                    "name": "DevOps Consultant, Acme Bank customer",
                    "date": "Jan 2027 - Present",
                }
            )
            known = renderer._public_engagement(
                {"name": "DevOps Consultant, Acme Bank", "date": "Oct 2024 - Aug 2025"}
            )
        self.assertEqual(row["client"], renderer.GENERIC_CUSTOMER)
        self.assertEqual(known["client"], renderer.CUSTOMER_LABELS["Oct 2024"])
        warnings = out.getvalue().splitlines()
        self.assertEqual(1, len(warnings), warnings)  # the known month is silent
        self.assertTrue(warnings[0].startswith("::warning::"), warnings)
        self.assertIn("Jan 2027", warnings[0])
        self.assertIn("CUSTOMER_LABELS", warnings[0])
        self.assertNotIn("acme", warnings[0].lower())

    def test_the_scrub_is_idempotent(self):
        shapes = [
            # a program role with its own bracket before the program's
            {
                "name": "Medical Image Classification MLOps Pipeline (Phase 2) (SME Program)",
                "date": "Jun 2025 - Aug 2025",
            },
            {
                "name": "Pipeline (Phase 2) (SME Program) (Ongoing)",
                "date": "Jun 2025 - Present",
            },
            {"name": "Pipeline (SME Program)", "date": "Jun 2025 - Aug 2025"},
        ]
        # and every engagement the checked-in snapshot holds, whatever a refresh put there
        cached = json.loads(renderer.DATA_FILE.read_text(encoding="utf-8"))
        shapes += cached["portfolio"]["engagements"]
        with contextlib.redirect_stdout(io.StringIO()):
            for shape in shapes:
                with self.subTest(shape=shape):
                    once = renderer._public_engagement(shape)
                    self.assertEqual(renderer._public_engagement(once), once)
            first = renderer._public_engagement(shapes[0])
            # an offline re-render must leave data.json as it is
            for row in cached["portfolio"]["engagements"]:
                with self.subTest(row=row["when"]):
                    self.assertEqual(renderer._public_engagement(row), row)
        self.assertEqual(
            first["role"], "Medical Image Classification MLOps Pipeline (Phase 2)"
        )
        self.assertEqual(first["kind"], "program")

    def test_a_program_stays_a_program(self):
        program = snapshot()["engagements"][1]
        self.assertEqual(program["kind"], "program")
        self.assertEqual(program["client"], "MLOps SME Program")
        self.assertEqual(program["role"], "Medical Image Classification MLOps Pipeline")
        again = renderer.public_portfolio({"engagements": [program]})["engagements"]
        self.assertEqual(again, [program])

    def test_zero_parsed_customers_raises(self):
        experience, projects, extra = portfolio_files()
        aws = experience["professional_experience"][0]
        aws["projects"] = [
            {
                "name": "DevOps Consultant @ Enterprise customer",
                "date": "Feb 2026 - Present",
            },
            {"name": "Pipeline (SME Program)", "date": "Jun 2025 - Aug 2025"},
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(renderer.PortfolioShapeError):
                renderer.portfolio_snapshot(experience, projects, extra)
            with self.assertRaises(renderer.PortfolioShapeError):
                renderer.build_context({"portfolio": {"engagements": aws["projects"]}})
        # the refresh must not swallow it and carry on with the cached snapshot
        with (
            patch.object(renderer, "OFFLINE", False),
            patch.object(
                renderer,
                "fetch_portfolio",
                side_effect=renderer.PortfolioShapeError("x"),
            ),
            self.assertRaises(renderer.PortfolioShapeError),
        ):
            renderer.refresh_portfolio({"portfolio": snapshot()})
        aws["projects"] = []  # no engagements at all is not a parse failure
        self.assertEqual(
            renderer.portfolio_snapshot(experience, projects, extra)["engagements"], []
        )

    def test_internal_ambassador_line_becomes_the_public_wording(self):
        titles = [a["title"] for a in snapshot()["achievements"]]
        self.assertEqual(
            titles, ["7x AWS community ambassador", "Senior Speaker Certification"]
        )
        # QZX stands in for the internal acronym: any title with the word is rewritten
        # whole, whatever its case or separator, and keeps only its count
        cases = {
            "ABCDE Ambassador": "AWS community ambassador",
            "Graduate, 3x AB Ambassador in two groups": "3x AWS community ambassador",
            "7x QZX Community Ambassador": "7x AWS community ambassador",
            "5x Qzx Ambassador": "5x AWS community ambassador",
            "5x qzx ambassador": "5x AWS community ambassador",
            "QZX-Ambassador": "AWS community ambassador",
            "QZX Ambassador (7x)": "7x AWS community ambassador",
            "QZX AMBASSADOR (12X)": "12x AWS community ambassador",
            "AWS community ambassador, QZX member": "AWS community ambassador",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                public = renderer._public_achievement({"title": title, "year": "2026"})
                self.assertEqual(public, {"title": expected, "year": "2026"})
                # and the public wording is left as it is
                self.assertEqual(renderer._public_achievement(public), public)
        kept = {"title": "Senior Speaker Certification", "year": "2026"}
        self.assertEqual(renderer._public_achievement(kept), kept)

    def test_checked_in_snapshot_names_no_customer(self):
        data = json.loads(renderer.DATA_FILE.read_text(encoding="utf-8"))
        engagements = data["portfolio"]["engagements"]
        self.assertTrue(engagements)
        customer_labels = {
            *renderer.CUSTOMER_LABELS.values(),
            renderer.GENERIC_CUSTOMER,
        }
        for row in engagements:
            self.assertNotIn("name", row)
            if row["kind"] == "program":
                self.assertIn(row["client"], renderer.PROGRAMS.values())
            else:
                self.assertEqual(row["kind"], "customer")
                self.assertIn(row["client"], customer_labels)
        for row in data["portfolio"]["achievements"]:
            if "ambassador" in row["title"].lower():
                self.assertRegex(row["title"], r"^(\d+x )?AWS community ambassador$")
        self.assertNotIn("views", data)


class SnapshotTests(unittest.TestCase):
    def test_snapshot_keeps_what_the_cards_read_and_drops_the_rest(self):
        public = snapshot()
        self.assertEqual(public["community_answers"], 2)
        self.assertEqual(public["hero_taglines"][0], "Guardrails on from day one.")
        self.assertEqual(
            public["availability"], "Now: leading DevOps on a landing zone"
        )
        self.assertEqual(public["project_count"], 5 + 1 + 2 + 11)
        self.assertNotIn("skills", public["education"][0])
        for dead in ("earlier", "samples"):
            self.assertNotIn(dead, public)
        for row in public["engagements"]:
            self.assertEqual(
                set(row),
                {
                    "when",
                    "client",
                    "role",
                    "stack",
                    "kind",
                    "ongoing",
                    "start",
                    "end",
                },
            )

    def test_long_dashes_are_folded_out_of_the_snapshot(self):
        experience, projects, extra = portfolio_files()
        dash = chr(0x2013)
        projects["open_source_contributions"][0]["title"] = f"Fix a {dash} b"
        with contextlib.redirect_stdout(io.StringIO()):
            public = renderer.portfolio_snapshot(experience, projects, extra)
        self.assertEqual(public["oss"][0]["title"], "Fix a - b")
        self.assertNotIn(dash, json.dumps(public, ensure_ascii=False))


class OpenSourceTests(unittest.TestCase):
    def test_community_line_never_prints_zero(self):
        fix = "a community-confirmed fix for the AWS Ansible deploy and Elastic IP allocation in forem/selfhost"
        pf = snapshot()
        self.assertEqual(
            renderer.community_line(pf),
            f"Community impact: {fix}, plus 2 accepted answers on GitHub Community Q&A",
        )
        for missing in (0, None):
            line = renderer.community_line({**pf, "community_answers": missing})
            self.assertEqual(line, f"Community impact: {fix}")
        del pf["community_answers"]  # an older cache has no count at all
        self.assertNotIn("0", renderer.community_line(pf))
        self.assertNotIn("plus", renderer.community_line(pf))

    def test_community_line_claims_the_fix_only_while_the_portfolio_backs_it(self):
        pf = snapshot()
        forem = next(e for e in pf["oss"] if e["repo"] == "forem/selfhost")
        forem["note"] = "Closed without review."
        self.assertEqual(
            renderer.community_line(pf),
            "Community impact: 2 accepted answers on GitHub Community Q&A",
        )
        self.assertEqual(renderer.community_line({**pf, "community_answers": 0}), "")

    def test_search_links_carry_one_repo_qualifier_per_repository(self):
        oss = context()["oss"]
        merged = renderer.search_url(renderer._repos(oss["merged"]), "merged")
        self.assertTrue(
            merged.startswith(
                "https://github.com/search?q=is%3Apr+author%3ASagargupta16+is%3Amerged+repo%3A"
            )
        )
        self.assertTrue(merged.endswith("&type=pullrequests"))
        for repo in ("axios%2Faxios", "apache%2Fairflow", "aws-ia%2Fterraform-aws-vpc"):
            self.assertEqual(merged.count(f"repo%3A{repo}"), 1)
        self.assertEqual(merged.count("repo%3A"), oss["repos"])
        self.assertNotIn("-user", merged)
        opened = renderer.search_url(renderer._repos(oss["open"]), "open")
        self.assertIn("is%3Aopen", opened)
        self.assertEqual(opened.count("repo%3A"), 1)  # two open PRs, one repository

    def test_links_escape_queries_without_changing_destination(self):
        url = renderer.search_url(["axios/axios", "apache/airflow"], "merged")
        markup = renderer._link(url, "Merged pull requests")
        self.assertIn("&amp;type=pullrequests", markup)
        self.assertEqual(ET.fromstring(markup).get("href"), url)  # nosec B314

    def test_oss_facts_and_alt_text(self):
        oss = context()["oss"]
        self.assertEqual(
            [oss["merged_count"], oss["open_count"], oss["repos"]], [4, 2, 3]
        )
        self.assertEqual(
            [r["date"] for r in oss["merged"]],
            ["2026-10-01", "2026-07-13", "2026-03-23", ""],
        )
        # live stars win over the portfolio's copy; a repo counts once
        self.assertEqual(oss["combined_stars"], 109000 + 47000 + 10)
        alt = renderer._oss_alt(oss, merged=True)
        self.assertEqual(
            alt,
            "4 contributions merged upstream, in axios/axios, apache/airflow, aws-ia/terraform-aws-vpc",
        )
        self.assertNotIn("pull requests merged", alt)
        self.assertTrue(
            renderer._oss_alt(oss, merged=False).startswith(
                "2 pull requests open upstream"
            )
        )


class ContextTests(unittest.TestCase):
    def test_build_context_has_every_key_in_the_plan_table(self):
        ctx = context()
        self.assertEqual(CTX_KEYS - set(ctx), set())
        # the two keys the hero pilot added, listed in the same docs section
        self.assertEqual(set(ctx) - CTX_KEYS, {"greeting", "badges"})
        # the contract is documented in the repo, never in a gitignored scratch file
        self.assertIn("docs/readme-rendering.md", renderer.build_context.__doc__)
        self.assertNotIn(".scratch", renderer.build_context.__doc__)
        self.assertTrue(callable(ctx["icon"]))
        json.dumps({k: v for k, v in ctx.items() if not callable(v)})  # plain data
        real = json.loads(renderer.DATA_FILE.read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(CTX_KEYS - set(renderer.build_context(real)), set())

    def test_context_values(self):
        ctx = context()
        self.assertEqual(ctx["today"], "2026-11-13")
        self.assertEqual(ctx["aws_title"], "ProServe (Cloud Consultant) - DevOps/MLOps")
        self.assertEqual(ctx["aws_title_long"], ctx["aws_title"] + " at AWS")
        self.assertEqual(ctx["location"], "Hyderabad, India")
        self.assertEqual(ctx["greeting"], "Hi, I am")
        self.assertEqual(ctx["years_at_aws"], 2)
        self.assertEqual(
            ctx["hero_lines"], ["Guardrails on from day one.", "Landing zones as code."]
        )
        self.assertEqual(
            ctx["intro_keywords"],
            ["AWS Professional Services", "Terraform", "CI/CD", "MCP servers"],
        )
        # open source is not a proof cell: it keeps a compact section of its own
        self.assertEqual(
            ctx["proof"],
            [
                {"value": "3", "label": "aws-samples"},
                {"value": "2x", "label": "AWS certified"},
                {"value": "2166", "label": "LeetCode Guardian peak"},
                {"value": "2+", "label": "years at AWS"},
            ],
        )
        self.assertEqual(
            [m["kind"] for m in ctx["milestones"]],
            ["study", "study", "work", "work", "work"],
        )
        self.assertEqual(
            [m["current"] for m in ctx["milestones"]], [False] * 4 + [True]
        )
        # the fixture's program is left out: three customers, numbered oldest first
        self.assertEqual(
            [(e["kind"], e["title"], e["sector"]) for e in ctx["engagements"]],
            [
                ("customer", "Customer 1", "Global financial services"),
                ("customer", "Customer 2", "Financial market infrastructure"),
                ("customer", "Customer 3", "Enterprise"),
            ],
        )
        self.assertEqual(
            ctx["education"],
            [
                {
                    "degree": "Master of Computer Applications (MCA)",
                    "school": "NIT Warangal",
                    "city": "Warangal, India",
                    "when": "September 2021 to July 2024",
                }
            ],
        )
        self.assertEqual(
            ctx["recognition"],
            [
                ("REVIEWS", [("Peer reviewer", "2025-2026")]),
                ("TALKS", [("Internal tech talks", "2025")]),
                (
                    "PROGRAMS AND RECOGNITION",
                    [
                        ("7x AWS community ambassador", "2025-2026"),
                        ("Senior Speaker Certification", "2026"),
                    ],
                ),
            ],
        )
        self.assertEqual(
            [s["key"] for s in ctx["samples"]],
            ["agentcore-harness", "org-governance", "sagemaker-mlops"],
        )
        self.assertEqual(ctx["samples"][0]["tags"], ["TERRAFORM", "AGENTCORE", "MCP"])
        self.assertEqual(ctx["project_count"], 19)
        self.assertEqual(ctx["updated"], {"leetcode": "2026-11-13T00:00:00+00:00"})

    def test_recognition_leaves_out_the_sme_program_line(self):
        data = data_fixture()
        data["portfolio"]["achievements"] = [
            {"title": "Example MLOps SME program graduate", "year": "2025"},
            {"title": "Example SME Program - mentor", "year": "2026"},
            {"title": "graduate of the example sme programme", "year": "2024"},
            # an SME role is recognition, not the program, and stays
            {"title": "AWS Training and Certification SME", "year": "2025"},
            {"title": "Senior Speaker Certification", "year": "2026"},
        ]
        groups = dict(context(data)["recognition"])
        self.assertEqual(
            groups["PROGRAMS AND RECOGNITION"],
            [
                ("Senior Speaker Certification", "2026"),
                ("AWS Training and Certification SME", "2025"),
            ],
        )
        # the group goes when the program line was all it held
        data["portfolio"]["achievements"] = data["portfolio"]["achievements"][:1]
        groups = dict(context(data)["recognition"])
        self.assertNotIn("PROGRAMS AND RECOGNITION", groups)
        self.assertEqual(list(groups), ["REVIEWS", "TALKS"])
        # and the checked-in snapshot, whatever a refresh put there
        real = json.loads(renderer.DATA_FILE.read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            shown = renderer.build_context(real)["recognition"]
        for _, items in shown:
            for text, _ in items:
                self.assertNotRegex(text, r"(?i)\bSME program")

    def test_engagements_are_customers_only_numbered_oldest_first(self):
        data = data_fixture()
        rows = data["portfolio"]["engagements"]
        self.assertIn("program", {e["kind"] for e in rows})
        data["portfolio"]["engagements"] = rows[::-1]  # handed newest first
        ctx = context(data)
        customers = sorted(
            (e for e in rows if e["kind"] == "customer"), key=lambda e: e["start"]
        )
        self.assertEqual(
            [e["when"] for e in ctx["engagements"]], [e["when"] for e in customers]
        )
        for number, e in enumerate(ctx["engagements"], start=1):
            with self.subTest(when=e["when"]):
                self.assertEqual(e["kind"], "customer")
                self.assertEqual(e["number"], number)
                self.assertEqual(e["title"], f"Customer {number}")
                # the sector is the table label without " customer"
                self.assertEqual(f"{e['sector']} customer", e["client"])
                self.assertLessEqual(
                    {"when", "client", "role", "stack", "kind", "ongoing", "start"},
                    set(e),
                )
        text = json.dumps(ctx["engagements"])
        for program in (*renderer.PROGRAMS.values(), "SME", "Medical Image"):
            self.assertNotIn(program, text)

    def test_a_number_counts_every_customer_however_many_the_cards_show(self):
        data = data_fixture()
        years = range(2020, 2025)  # five: one more than the cards show
        data["portfolio"]["engagements"] = [
            {"name": "DevOps Consultant, Acme Bank", "date": f"Mar {year} - Jun {year}"}
            for year in years
        ]
        ctx = context(data)
        self.assertEqual(
            [e["title"] for e in ctx["engagements"]],
            [f"Customer {n}" for n in range(1, len(years) + 1)],
        )
        self.assertNotIn("Acme", json.dumps(ctx["engagements"]))

    def test_the_generic_label_has_no_sector(self):
        data = data_fixture()
        data["portfolio"]["engagements"] = [
            {"name": "DevOps Consultant, Acme Bank", "date": "Mar 2027 - Present"},
            {"name": "DevOps Consultant, Initech", "date": "Oct 2024 - Aug 2025"},
        ]
        ctx = context(data)
        known = renderer.CUSTOMER_LABELS["Oct 2024"]
        self.assertEqual(
            [(e["title"], e["client"], e["sector"]) for e in ctx["engagements"]],
            [
                ("Customer 1", known, known.removesuffix(" customer")),
                ("Customer 2", renderer.GENERIC_CUSTOMER, ""),
            ],
        )

    def test_the_public_snapshot_keeps_its_shape_and_its_program(self):
        data = data_fixture()
        before = json.loads(json.dumps(data["portfolio"]["engagements"]))
        context(data)
        self.assertEqual(data["portfolio"]["engagements"], before)
        self.assertIn("program", {e["kind"] for e in before})
        for row in before:
            self.assertFalse({"number", "title", "sector"} & set(row))

    def test_fallbacks_when_the_cache_is_older_than_the_hero_fields(self):
        data = data_fixture()
        for key in ("hero_taglines", "availability"):
            del data["portfolio"][key]
        ctx = context(data)
        self.assertEqual(ctx["hero_lines"], renderer.HERO_LINES)
        self.assertEqual(len(ctx["hero_lines"]), 3)
        self.assertEqual(ctx["availability"], "")

    def test_a_tagline_longer_than_the_phone_reel_warns_and_is_passed_on_whole(self):
        fits = "x" * renderer.HERO_LINE_MAX
        long = "Terraform, CI/CD and MLOps pipelines, end to end, in every account."
        data = data_fixture()
        data["portfolio"]["hero_taglines"] = [fits, long]
        out = io.StringIO()
        with scratch_repo(), contextlib.redirect_stdout(out):
            ctx = renderer.build_context(data)
        self.assertEqual(ctx["hero_lines"], [fits, long])  # the line is never cut here
        warnings = [w for w in out.getvalue().splitlines() if "hero tagline" in w]
        self.assertEqual(1, len(warnings), warnings)
        self.assertTrue(warnings[0].startswith("::warning::"), warnings)
        self.assertIn(long, warnings[0])
        self.assertIn(f"about {renderer.HERO_LINE_MAX}", warnings[0])
        self.assertIn("shortens it", warnings[0])

    def test_certifications_come_from_the_recorded_expiry(self):
        certs = context()["certs"]
        self.assertEqual(certs["active_count"], 2)
        self.assertEqual(certs["issuer"], "AWS")
        self.assertEqual(
            certs["lapsed"],
            [
                {
                    "name": "HashiCorp Certified: Terraform Associate",
                    "expired": "2020-01-01",
                }
            ],
        )
        self.assertEqual(
            certs["active"][0],
            {"name": "AWS Certified Developer - Associate", "expires": "2099-01-01"},
        )

    def test_headers_are_numbered_by_their_order(self):
        ctx = context()
        self.assertEqual(
            [h[1] for h in ctx["headers"]], [f"{n:02d}" for n in range(1, 10)]
        )
        self.assertEqual(ctx["headers"][4][0], "publications")
        self.assertEqual(ctx["headers"][4][3], "reviews, talks and programs")
        self.assertEqual(set(ctx["header_counts"]), {h[0] for h in ctx["headers"]})
        # every card in the section; COMMUNITY.md shows its header above every tool
        self.assertEqual(ctx["header_counts"]["projects"], "5 featured")
        self.assertEqual(ctx["header_counts"]["community"], "11 tools")
        # a fact another card already shows is left out (hard rule 17): years at
        # AWS, samples and active certifications are hero proof cells, and the
        # merged count is the first open-source tile
        for key in ("experience", "opensource", "certs", "stack"):
            self.assertEqual(ctx["header_counts"][key], "", key)

    def test_tools_carry_kind_stars_and_npm_downloads(self):
        tools = context()["tools"]
        self.assertEqual(
            [t["slug"] for t in tools],
            [*renderer.COMMUNITY_TOP, "mcp-toolkit", "deploy-guide"],  # then by stars
        )
        self.assertEqual([t["top"] for t in tools], [True] * 9 + [False] * 2)
        by_slug = {t["slug"]: t for t in tools}
        self.assertEqual(by_slug["orrery"]["kind"], "CLI")
        self.assertEqual(by_slug["orrery"]["stars"], 7)
        self.assertEqual(by_slug["orrery"]["npm_monthly"], 1793)
        self.assertEqual(by_slug["orrery"]["repo"], "orrery")
        self.assertEqual(by_slug["skillcheck"]["stars"], 0)  # unknown to the star map
        self.assertEqual(by_slug["skillcheck"]["npm_monthly"], 2070)
        self.assertIsNone(by_slug["itr-agent"]["npm_monthly"])  # under 100 a month
        self.assertIsNone(
            by_slug["bedrock-multi-model-mcp"]["npm_monthly"]
        )  # no count cached
        self.assertIsNone(by_slug["awesome-mcp-servers"]["npm_monthly"])  # not on npm
        kinds = {
            "MCP SERVER",
            "CLAUDE CODE PLUGIN",
            "GITHUB ACTION",
            "CLI",
            "AGENT SKILLS",
            "GUIDE",
            "CURATED LIST",
            "WORKFLOWS",
        }
        self.assertTrue(set(renderer.TOOL_KINDS.values()) <= kinds)
        self.assertEqual(len(renderer.COMMUNITY_TOP), 9)  # three rows of three
        self.assertEqual(renderer.COMMUNITY_TOP[0], "orrery")

    def test_card_summaries_hold_no_counts_and_a_cut_one_warns(self):
        for slug in (
            "svg-forge",
            "agent-brain",
            "shared-workflows",
            "claude-cost-optimizer",
        ):
            summary = renderer.CARD_SUMMARIES[slug]
            self.assertLessEqual(len(summary), 110, slug)
            self.assertFalse(any(ch.isdigit() for ch in summary), slug)
        for slug in ("claude-skills", "claude-code-recipes", "ledger-sync"):
            self.assertFalse(
                any(ch.isdigit() for ch in renderer.CARD_SUMMARIES[slug]), slug
            )
        self.assertNotIn("%", renderer.CARD_SUMMARIES["claude-cost-optimizer"])
        long = {"title": "Wordy", "description": "word " * 60}
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            cut = renderer._card_text(long, 96)
        self.assertTrue(cut.endswith("..."))
        self.assertIn("::warning::card summary for Wordy", log.getvalue())
        projects = {p["slug"]: p for p in context()["projects"]}
        self.assertEqual(
            projects["ledger-sync"]["summary"], renderer.CARD_SUMMARIES["ledger-sync"]
        )
        self.assertTrue(projects["ledger-sync"]["live"])
        self.assertEqual(projects["ledger-sync"]["stars"], 10)
        self.assertEqual(
            projects["brand-new-thing"]["summary"],
            "A project the script has no one-liner for",
        )
        self.assertFalse(projects["brand-new-thing"]["live"])
        self.assertIsNone(projects["brand-new-thing"]["stars"])

    def test_icons_and_connect_buttons_read_the_checked_in_cache(self):
        with scratch_repo() as out, contextlib.redirect_stdout(io.StringIO()):
            (out / "icons.json").write_text(
                json.dumps({"linkedin": "M1 1h2", "terraform": "M0 0h24"}),
                encoding="utf-8",
            )
            ctx = renderer.build_context(data_fixture())
        self.assertEqual(ctx["icon"]("terraform"), "M0 0h24")
        self.assertIsNone(ctx["icon"]("no-such-brand"))
        connect = ctx["connect"]
        self.assertEqual(
            [c["key"] for c in connect], ["linkedin", "resume", "email", "portfolio"]
        )
        self.assertEqual([c["primary"] for c in connect], [False, True, False, False])
        self.assertEqual(connect[0]["icon"], "M1 1h2")
        self.assertIsNone(connect[1]["icon"])
        cached = (
            renderer.load_icons()
        )  # the real cache covers what the page draws today
        for _, _, slug, _ in renderer.CONNECT:
            self.assertIn(slug, cached)
        self.assertEqual(set(renderer.ICON_SLUGS) - set(cached), set())
        self.assertNotIn("latest", renderer.SIMPLE_ICONS_VERSION)


class RefreshTests(unittest.TestCase):
    def test_failed_fetch_keeps_the_last_good_values(self):
        cached = data_fixture()
        log = io.StringIO()
        with (
            scratch_repo(cached),
            patch.object(renderer, "OFFLINE", False),
            patch.object(renderer, "fetch", side_effect=OSError("down")),
            patch.dict(renderer.os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}),
            contextlib.redirect_stdout(log),
        ):
            actual = renderer.load_data()
            renderer.refresh_portfolio(actual)
            renderer.refresh_npm(actual)
            icons = renderer.refresh_icons()
        self.assertEqual(actual, cached)  # values and the success timestamps alike
        self.assertEqual(icons, {})
        warnings = [
            line
            for line in log.getvalue().splitlines()
            if line.startswith("::warning::")
        ]
        for source in (
            "leetcode fetch failed",
            "GITHUB_TOKEN",
            "portfolio fetch failed",
            "npm downloads",
            "simple icon",
        ):
            self.assertTrue(any(source in line for line in warnings), source)

    def test_npm_refresh_updates_what_answers_and_keeps_the_rest(self):
        def answer(url: str, *args, **kwargs) -> bytes:
            if url.endswith("/itr-agent"):
                raise OSError("timeout")
            return json.dumps({"downloads": 4321}).encode()

        data = {"npm": {"itr-agent": 32, "@sagargupta1610/orrery": 5}}
        with (
            patch.object(renderer, "OFFLINE", False),
            patch.object(renderer, "fetch", side_effect=answer) as fetch,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            renderer.refresh_npm(data)
        self.assertEqual(data["npm"]["itr-agent"], 32)
        self.assertEqual(data["npm"]["@sagargupta1610/orrery"], 4321)
        self.assertEqual(data["npm"]["bedrock-multi-model-mcp"], 4321)
        self.assertIn("npm", data["source_updated_at"])
        self.assertEqual(
            fetch.call_args_list[0].args[0],
            "https://api.npmjs.org/downloads/point/last-month/@sagargupta1610/orrery",
        )

    def test_icon_refresh_fetches_only_missing_slugs_from_a_pinned_release(self):
        with scratch_repo() as out, patch.object(renderer, "OFFLINE", False):
            have = {
                s: "M0 0"
                for s in renderer.ICON_SLUGS
                if s not in ("terraform", "linkedin")
            }
            (out / "icons.json").write_text(json.dumps(have), encoding="utf-8")
            with patch.object(
                renderer,
                "fetch",
                return_value=b'<svg><title>x</title><path d="M1 2z"/></svg>',
            ) as fetch:
                icons = renderer.refresh_icons()
        urls = sorted(call.args[0] for call in fetch.call_args_list)
        self.assertEqual(
            urls,
            [
                "https://cdn.jsdelivr.net/npm/simple-icons@13.21.0/icons/linkedin.svg",
                f"https://cdn.jsdelivr.net/npm/simple-icons@{renderer.SIMPLE_ICONS_VERSION}/icons/terraform.svg",
            ],
        )
        self.assertEqual(icons["terraform"], "M1 2z")
        self.assertEqual(len(icons), len(renderer.ICON_SLUGS))

    def test_offline_does_not_fetch_or_mark_data_current(self):
        with (
            scratch_repo(data_fixture()),
            patch.object(renderer, "OFFLINE", True),
            patch.object(
                renderer, "fetch", side_effect=AssertionError("network request")
            ),
            patch.object(
                renderer.urllib.request,
                "urlopen",
                side_effect=AssertionError("network request"),
            ),
            patch.object(
                renderer, "record_refresh", side_effect=AssertionError("false refresh")
            ),
        ):
            data = renderer.load_data()
            renderer.refresh_portfolio(data)
            renderer.refresh_npm(data)
            self.assertEqual(renderer.refresh_icons(), {})
            with contextlib.redirect_stdout(io.StringIO()):
                renderer.build_context(data)
        self.assertTrue(data["portfolio"]["featured"])
        with patch.object(renderer, "OFFLINE", True), self.assertRaises(RuntimeError):
            renderer.fetch("https://api.github.com/user")

    def test_old_cache_is_scrubbed_and_loses_the_view_counter_on_load(self):
        old = {
            "views": 25563,
            "source_updated_at": {"views": "2026-11-12T00:00:00+00:00"},
            "portfolio": {
                "engagements": [
                    {
                        "when": "Oct 2024 to Aug 2025",
                        "client": "DevOps Consultant, Acme Bank",
                        "tagline": "Terraform",
                        "stack": ["Terraform"],
                        "link": None,
                        "name": "DevOps Consultant, Acme Bank",
                    }
                ]
            },
        }
        with scratch_repo(old), patch.object(renderer, "OFFLINE", True):
            data = renderer.load_data()
        self.assertNotIn("views", data)
        self.assertEqual(data["source_updated_at"], {})
        self.assertNotIn("Acme", json.dumps(data))
        self.assertEqual(
            data["portfolio"]["engagements"][0]["client"],
            "Global financial services customer",
        )

    def test_fetch_sends_only_the_headers_each_host_needs(self):
        seen = []

        class Reply:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"{}"

        def urlopen(request, timeout=0):
            seen.append(request)
            return Reply()

        with (
            patch.object(renderer, "OFFLINE", False),
            patch.object(renderer.urllib.request, "urlopen", side_effect=urlopen),
        ):
            renderer.fetch("https://api.github.com/repos/a/b", token="t")
            renderer.fetch("https://leetcode.com/graphql", {"query": "q"})
            with self.assertRaises(ValueError):
                renderer.fetch("https://komarev.com/ghpvc/?username=sagargupta16")
            with self.assertRaises(ValueError):
                renderer.fetch("https://skillicons.dev/icons?i=aws")
            with self.assertRaises(ValueError):
                renderer.fetch(
                    "https://cdn.jsdelivr.net/npm/simple-icons/icons/aws.svg"
                )
        github, leetcode = seen
        self.assertIsNone(github.get_header("Referer"))
        self.assertIsNone(github.get_header("Content-type"))
        self.assertIsNone(github.data)
        self.assertEqual(github.get_header("Authorization"), "bearer t")
        self.assertEqual(leetcode.get_header("Referer"), "https://leetcode.com")
        self.assertEqual(leetcode.get_header("Content-type"), "application/json")
        self.assertIsNone(leetcode.get_header("Authorization"))

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


class ReadmeTests(unittest.TestCase):
    def test_picture_falls_back_to_the_phone_layout_below_desktop_width(self):
        with scratch_repo() as out:
            (out / "card-mobile.svg").touch()
            picture = ET.fromstring(renderer._img("card.svg", "A & B", "400"))  # nosec B314
            alone = ET.fromstring(renderer._img("button.svg", "Only one width"))  # nosec B314
        sources = picture.findall("source")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].get("media"), "(min-width: 1012px)")
        self.assertEqual(sources[0].get("srcset"), "assets/svg/card.svg")
        self.assertEqual(picture.find("img").get("src"), "assets/svg/card-mobile.svg")
        self.assertEqual(picture.find("img").get("width"), "400")
        self.assertEqual(picture.find("img").get("alt"), "A & B")
        self.assertNotIn("style=", ET.tostring(picture, encoding="unicode"))
        self.assertEqual(alone.findall("source"), [])
        self.assertEqual(alone.find("img").get("src"), "assets/svg/button.svg")

    def test_header_picture_prefers_the_wide_pair_and_falls_back_to_the_phone_file(
        self,
    ):
        with scratch_repo() as out:
            for name in (
                "header-stack-dark.svg",
                "header-stack-light.svg",
                "header-stack-dark-mobile.svg",
            ):
                (out / name).touch()
            picture = ET.fromstring(renderer._header("stack"))  # nosec B314
            # the header's own label, datum included, wins over the bare title
            renderer.LABELS["header-stack-dark.svg"] = "Tech Stack and Tools: 4 lanes"
            labelled = ET.fromstring(renderer._header("stack"))  # nosec B314
        self.assertEqual(
            labelled.find("img").get("alt"), "Tech Stack and Tools: 4 lanes"
        )
        self.assertEqual(
            [s.get("srcset") for s in picture.findall("source")],
            [
                "assets/svg/header-stack-light.svg",
                "assets/svg/header-stack-dark.svg",
                "assets/svg/header-stack-dark-mobile.svg",
            ],
        )
        self.assertEqual(
            picture.find("img").get("src"), "assets/svg/header-stack-dark-mobile.svg"
        )
        self.assertEqual(picture.find("img").get("alt"), "Tech Stack and Tools")

    def readme(self) -> tuple[str, str]:
        data = data_fixture()
        with scratch_repo(), contextlib.redirect_stdout(io.StringIO()):
            ctx = renderer.build_context(data)
            renderer.LABELS["hero.svg"] = "The hero card's own label"
            renderer.LABELS["sample-org-governance.svg"] = "The org card's own label"
            renderer.LABELS["oss-review.svg"] = "The review card's own label"
            return renderer.render_readme(data, ctx), renderer.render_community_page(
                ctx
            )

    def test_readme_follows_the_page_plan(self):
        readme, _ = self.readme()
        order = [
            "hero.svg",
            "connect-linkedin.svg",
            "connect-resume.svg",
            "connect-email.svg",
            "connect-portfolio.svg",
            "header-experience-dark.svg",
            "experience.svg",
            "header-projects-dark.svg",
            "sample-agentcore-harness.svg",
            "sample-org-governance.svg",
            "sample-sagemaker-mlops.svg",
            "project-ledger-sync.svg",
            "project-brand-new-thing.svg",
            "cta-portfolio.svg",
            "header-opensource-dark.svg",
            "oss.svg",
            "oss-review.svg",
            "get-oss.svg",
            "header-certs-dark.svg",
            "certs-status.svg",
            "certs.svg",
            "get-certs.svg",
            "header-publications-dark.svg",
            "publications.svg",
            "header-stack-dark.svg",
            "stack.svg",
            "header-community-dark.svg",
            *(f"tool-{slug}.svg" for slug in renderer.COMMUNITY_TOP),
            "cta-community.svg",
            "header-stats-dark.svg",
            "github.svg",
            "get-github.svg",
            "leetcode.svg",
            "get-leetcode.svg",
            "competitive.svg",
            "header-education-dark.svg",
            "education.svg",
            "footer.svg",
        ]
        places = [readme.index(f"assets/svg/{name}") for name in order]
        self.assertEqual(places, sorted(places))
        self.assertTrue(readme.startswith(renderer.GENERATED_NOTE))
        for gone in (
            "profile-badges",
            "intro.svg",
            "snake",
            "connect-github",
            "connect-leetcode",
            "tool-deploy-guide",  # not one of the top nine: only on COMMUNITY.md
            "divider",  # each section header owns the break
            "oss-merged",  # its ledger is on oss.svg
            "ai-stack",  # a lane of stack.svg
            "http://",
        ):
            self.assertNotIn(gone, readme)
        blocks = readme.split("\n\n")
        # each header is a block of its own, once, in HEADERS order; the first
        # one follows the connect row with nothing in between
        heads = []
        for key, _, _ in renderer.HEADERS:
            with self.subTest(header=key):
                found = [i for i, b in enumerate(blocks) if f"header-{key}-" in b]
                self.assertEqual(len(found), 1)
                names = re.findall(r"assets/svg/([a-z0-9-]+)\.svg", blocks[found[0]])
                self.assertTrue(names)
                for name in names:
                    self.assertTrue(name.startswith(f"header-{key}-"), name)
                heads += found
        self.assertEqual(heads, sorted(heads))
        self.assertIn("connect-linkedin.svg", blocks[heads[0] - 1])
        # the footer, then the closing row of three of the four buttons, last
        self.assertIn("assets/svg/footer.svg", blocks[-2])
        self.assertEqual(
            re.findall(r"assets/svg/([a-z0-9-]+)\.svg", blocks[-1]),
            ["connect-resume", "connect-email", "connect-portfolio"],
        )
        # a 1px copy of the visit counter follows the footer, and sits nowhere else
        self.assertTrue(
            blocks[-2].endswith(
                f' <picture><img src="{renderer.VIEWS_PIXEL}" width="1" height="1" alt="" /></picture>'
            )
        )
        self.assertEqual(readme.count("komarev"), 1)
        # the lead sample is full width on a row of its own, the other two share one
        lead = next(b for b in blocks if "sample-agentcore-harness.svg" in b)
        self.assertTrue(
            lead.startswith(
                '<a href="https://github.com/aws-samples/sample-agentcore-harness-agent-terraform">'
            )
        )
        self.assertEqual(lead.count("assets/svg/sample-"), 1)
        self.assertEqual(lead.count('width="100%"'), 1)
        pair = blocks[blocks.index(lead) + 1]
        self.assertTrue(pair.startswith('<p align="center">'))
        self.assertEqual(
            re.findall(r"assets/svg/(sample-[a-z0-9-]+)\.svg", pair),
            ["sample-org-governance", "sample-sagemaker-mlops"],
        )
        self.assertEqual(pair.count('width="400"'), 2)
        # the open-source summary carries the merged ledger and its search link
        oss = next(b for b in blocks if "assets/svg/oss.svg" in b)
        self.assertIn("is%3Amerged", oss)
        self.assertEqual(readme.count("is%3Amerged"), 1)
        self.assertEqual(sum("assets/svg/stack.svg" in b for b in blocks), 1)
        projects = next(b for b in blocks if "project-ledger-sync.svg" in b)
        self.assertEqual(projects.count('width="400"'), 2)
        tools = next(b for b in blocks if "tool-orrery.svg" in b)
        self.assertEqual(tools.count('width="270"'), 9)
        # cards only: no Markdown headings, lists or paragraphs outside the images
        for block in blocks[1:]:
            self.assertTrue(block.lstrip().startswith("<"), block[:60])

    def test_alt_text(self):
        readme, _ = self.readme()
        # a sample card's own label wins; the others fall back to the sample line
        self.assertEqual(readme.count("published as a solution under aws-samples"), 2)
        self.assertIn(
            'alt="AgentCore Harness Agent with Governed MCP Tools, published as a solution under aws-samples"',
            readme,
        )
        self.assertIn('alt="The org card&#x27;s own label"', readme)
        self.assertNotIn("published AWS sample", readme)
        self.assertIn(
            'alt="The hero card&#x27;s own label"', readme
        )  # the rendered aria-label
        self.assertIn('alt="4 contributions merged upstream, in axios/axios,', readme)
        # the review card's label wins over the renderer's open-PR sentence
        self.assertIn('alt="The review card&#x27;s own label"', readme)
        self.assertNotIn("pull requests open upstream", readme)
        self.assertIn('alt="View all 19 projects"', readme)
        self.assertIn('alt="See all 11 community tools"', readme)
        self.assertIn("is%3Amerged+repo%3Aaxios%2Faxios", readme)

    def test_a_card_this_run_did_not_write_takes_its_alt_text_from_the_file(self):
        data = data_fixture()
        with scratch_repo() as out, contextlib.redirect_stdout(io.StringIO()):
            # no module drew stack.svg in this run, so its label comes from the file
            (out / "stack.svg").write_text(
                SVG.format(label="Stack: AWS &amp; Terraform"), encoding="utf-8"
            )
            # an unlabelled file falls back to the renderer's own alt text
            (out / "competitive.svg").write_text("<svg/>", encoding="utf-8")
            # a label from this run wins over the file it is about to replace
            (out / "education.svg").write_text(
                SVG.format(label="Last run"), encoding="utf-8"
            )
            renderer.LABELS["education.svg"] = "Drawn in this run"
            readme = renderer.render_readme(data, renderer.build_context(data))
            kept = renderer._file_label("stack.svg")
            absent = renderer._file_label("no-such-card.svg")
        self.assertEqual([kept, absent], ["Stack: AWS & Terraform", ""])
        self.assertIn('alt="Stack: AWS &amp; Terraform"', readme)
        self.assertIn('alt="Competitive programming"', readme)  # the fallback
        self.assertIn('alt="Drawn in this run"', readme)
        self.assertNotIn("Last run", readme)

    def test_cta_is_left_out_when_the_project_count_is_unknown(self):
        data = data_fixture()
        del data["portfolio"]["project_count"]
        with scratch_repo(), contextlib.redirect_stdout(io.StringIO()):
            readme = renderer.render_readme(data, renderer.build_context(data))
        self.assertNotIn("cta-portfolio", readme)
        self.assertNotIn("View all", readme)

    def test_community_page_lists_every_tool_top_nine_first(self):
        _, page = self.readme()
        order = [*renderer.COMMUNITY_TOP, "mcp-toolkit", "deploy-guide"]
        places = [page.index(f"assets/svg/tool-{slug}.svg") for slug in order]
        self.assertEqual(places, sorted(places))
        self.assertEqual(page.count("assets/svg/tool-"), 11)
        self.assertLess(page.index("header-community"), places[0])
        self.assertGreater(page.index("cta-profile.svg"), places[-1])


class WritingTests(unittest.TestCase):
    def fake(self, files: dict) -> types.SimpleNamespace:
        return types.SimpleNamespace(render=lambda data, ctx: files)

    def test_a_missing_module_is_named_and_skipped(self):
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            self.assertIsNone(renderer.render_module("not-written-yet", {}, {}))
        self.assertEqual(log.getvalue().strip(), "missing module not-written-yet")
        # every card on the page comes from a module, the stack card included
        self.assertEqual(
            renderer.cards.MODULES,
            (
                "hero",
                "chrome",
                "career",
                "samples",
                "projects",
                "oss",
                "stack",
                "tools",
                "stats",
            ),
        )

    def test_only_plain_svg_names_are_accepted_from_a_module(self):
        good = {"hero.svg": "<svg/>", "tool-svg-forge-mobile.svg": "<svg/>"}
        with patch.object(renderer, "load_card_module", return_value=self.fake(good)):
            self.assertEqual(renderer.render_module("hero", {}, {}), good)
        for bad in (
            "../README.md",
            "sub/hero.svg",
            "hero.png",
            "Hero.svg",
            "hero.svg ",
            ".svg",
            "github.svg",
            "certs.svg",
        ):
            with patch.object(
                renderer, "load_card_module", return_value=self.fake({bad: "<svg/>"})
            ):
                with self.assertRaises(ValueError, msg=bad):
                    renderer.render_module("hero", {}, {})

    def run_main(
        self, *flags: str, modules: dict | None = None, absent: tuple = ()
    ) -> tuple[set[str], Path]:
        modules = modules or {}
        with (
            scratch_repo(data_fixture()) as out,
            patch.object(renderer, "OFFLINE", False),
            patch.object(sys, "argv", ["render-svgs.py", "--offline", *flags]),
            patch.object(renderer.cards, "MODULES", tuple(modules) + tuple(absent)),
            patch.object(
                renderer, "load_card_module", side_effect=lambda name: modules.get(name)
            ),
            patch.object(
                renderer.leetcode_card,
                "render_card",
                return_value=SVG.format(label="LeetCode"),
            ),
            patch.object(
                renderer.github_stats_card,
                "render_card",
                return_value=SVG.format(label="GitHub"),
            ),
            contextlib.redirect_stdout(io.StringIO()) as log,
        ):
            renderer.main()
            self.log = log.getvalue()
            self.readme_text = (
                (out / "README.md").read_text(encoding="utf-8")
                if (out / "README.md").exists()
                else ""
            )
            return {path.name for path in out.iterdir()}, out

    def test_data_only_writes_the_snapshot_and_the_icon_cache_and_nothing_else(self):
        hero = self.fake({"hero.svg": SVG.format(label="Hero")})
        written, _ = self.run_main("--data-only", modules={"hero": hero})
        self.assertEqual(written, {"data.json", "icons.json"})

    def test_main_writes_what_the_modules_return_then_the_pages(self):
        hero = self.fake(
            {
                "hero.svg": SVG.format(label="Hero says hello"),
                "hero-mobile.svg": SVG.format(label="Hero"),
            }
        )
        written, _ = self.run_main(modules={"hero": hero})
        self.assertEqual(
            written,
            {
                "data.json",
                "icons.json",
                "hero.svg",
                "hero-mobile.svg",
                "github.svg",
                "leetcode.svg",
                "README.md",
                "COMMUNITY.md",
            },
        )
        self.assertIn('srcset="assets/svg/hero.svg"', self.readme_text)
        self.assertIn('src="assets/svg/hero-mobile.svg"', self.readme_text)
        self.assertIn('alt="Hero says hello"', self.readme_text)

    def test_the_stack_card_comes_from_its_module(self):
        stack = self.fake(
            {
                "stack.svg": SVG.format(label="Stack: AWS, Terraform and Claude Code"),
                "stack-mobile.svg": SVG.format(label="Stack"),
            }
        )
        written, _ = self.run_main(modules={"stack": stack})
        self.assertLessEqual({"stack.svg", "stack-mobile.svg"}, written)
        self.assertIn('srcset="assets/svg/stack.svg"', self.readme_text)
        self.assertIn('src="assets/svg/stack-mobile.svg"', self.readme_text)
        self.assertIn('alt="Stack: AWS, Terraform and Claude Code"', self.readme_text)
        self.assertEqual(self.readme_text.count("assets/svg/stack"), 2)  # one picture

    def test_a_listed_module_that_is_missing_stops_the_run(self):
        hero = self.fake({"hero.svg": SVG.format(label="Hero")})
        with self.assertRaises(SystemExit) as stop:
            self.run_main(modules={"hero": hero}, absent=("gone",))
        self.assertIn("cards/gone.py", str(stop.exception))

    def test_two_modules_may_not_draw_the_same_file(self):
        one = self.fake({"footer.svg": SVG.format(label="a")})
        two = self.fake({"footer.svg": SVG.format(label="b")})
        with self.assertRaises(ValueError):
            self.run_main(modules={"chrome": one, "career": two})


if __name__ == "__main__":
    unittest.main()
