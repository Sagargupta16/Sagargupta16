#!/usr/bin/env python3
"""Validate the generated SVG profile without network access or dependencies."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys

# parses only this repository's own generated SVGs, never third-party input
import xml.etree.ElementTree as ET  # nosec B405
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
UNESCAPED_AMPERSAND = re.compile(r"&(?!#\d+;|#x[0-9a-fA-F]+;|[a-zA-Z][a-zA-Z0-9]+;)")
REQUIRED_CONFIG = (
    "github.username",
    "linkedin.username",
    "leetcode.username",
    "credly.username",
    "portfolio.url",
    "career.current_role",
    "resume.path",
)


def read_profile_config(path: Path) -> dict[str, str]:
    """Read the two-level scalar YAML used by profiles.yml; reject other shapes."""
    values: dict[str, str] = {}
    section = ""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        heading = re.fullmatch(r"([a-z_]+):\s*(?:#.*)?", line)
        if heading:
            section = heading[1]
            continue
        scalar = re.fullmatch(r"  ([a-z_]+):\s*(.*?)\s*", line)
        if not section or not scalar:
            raise ValueError(
                f"{path.name}:{number}: expected a two-level scalar setting"
            )
        key, raw = scalar.groups()
        if raw.startswith('"'):
            value, end = json.JSONDecoder().raw_decode(raw)
            tail = raw[end:].strip()
            if not isinstance(value, str) or (tail and not tail.startswith("#")):
                raise ValueError(f"{path.name}:{number}: invalid quoted setting")
        elif raw.startswith("'"):
            quoted = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", raw)
            if not quoted:
                raise ValueError(f"{path.name}:{number}: invalid quoted setting")
            value = quoted[1].replace("''", "'")
        else:
            value = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
            if not value or value.startswith(("[", "{", "&", "*", "|", ">")):
                raise ValueError(f"{path.name}:{number}: expected a scalar value")
        full_key = f"{section}.{key}"
        if full_key in values:
            raise ValueError(f"{path.name}:{number}: duplicate setting {full_key}")
        values[full_key] = value
    return values


def url_issue(value: str, *, image: bool = False) -> str | None:
    if re.search(r"[\x00-\x20\x7f<>\"\\]", value):
        return "URL contains whitespace, control characters or unsafe delimiters"
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "URL is malformed"
    allowed = {"https"} if image else {"https", "mailto"}
    if parsed.scheme and parsed.scheme.lower() not in allowed:
        return f"unsupported URL scheme: {parsed.scheme}"
    if value.startswith("//") or parsed.username or parsed.password:
        return "protocol-relative URLs and embedded credentials are not allowed"
    if parsed.scheme == "https" and not parsed.hostname:
        return "HTTPS URL has no hostname"
    if parsed.hostname == "github.com" and parsed.path.rstrip("/") == "/pulls":
        return "github.com/pulls requires login; use public github.com/search"
    if not value:
        return "empty URL"
    return None


def srcset_urls(value: str) -> list[str]:
    candidates = []
    for candidate in value.split(","):
        parts = candidate.split()
        if not parts or len(parts) > 2:
            raise ValueError("invalid srcset candidate")
        if len(parts) == 2 and not re.fullmatch(
            r"(?:\d+w|(?:\d+(?:\.\d+)?)x)", parts[1]
        ):
            raise ValueError("invalid srcset descriptor")
        candidates.append(parts[0])
    return candidates


class ProfileHTML(HTMLParser):
    def __init__(self, document: str) -> None:
        """Collect the links, image sources and issues of one document."""
        super().__init__(convert_charrefs=True)
        self.document = document
        self.issues: list[str] = []
        self.links: list[str] = []
        self.images: set[str] = set()

    def report(self, message: str) -> None:
        self.issues.append(f"{self.document}:{self.getpos()[0]}: {message}")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self._check_markup(tag, attrs, attributes)
        if tag == "a":
            self._check_link(attributes.get("href", "") or "")
        if tag in {"img", "source"}:
            self._check_image(tag, attributes)

    def _check_markup(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        attributes: dict[str, str | None],
    ) -> None:
        """Report markup that GitHub strips or that breaks once sanitized."""
        if len(attributes) != len(attrs):
            self.report(f"duplicate attribute on <{tag}>")
        if tag in {"script", "iframe", "style"}:
            self.report(f"<{tag}> is unsupported in a GitHub README")
        for key, _ in attrs:
            if key.startswith("on") or key == "style":
                self.report(f"unsupported attribute {key} on <{tag}>")
        for raw in re.findall(r"""=\s*("[^"]*"|'[^']*')""", self.get_starttag_text()):
            if UNESCAPED_AMPERSAND.search(raw):
                self.report("escape attribute ampersands as &amp;")

    def _check_link(self, link: str) -> None:
        issue = url_issue(link)
        if issue:
            self.report(issue)
        self.links.append(link)

    def _check_image(self, tag: str, attributes: dict[str, str | None]) -> None:
        candidates: list[str] = []
        if attributes.get("src"):
            candidates.append(attributes["src"])
        if "srcset" in attributes:
            try:
                candidates.extend(srcset_urls(attributes["srcset"] or ""))
            except ValueError as error:
                self.report(str(error))
        if not candidates:
            self.report(f"<{tag}> has no image source")
        for source in candidates:
            issue = url_issue(source, image=True)
            if issue:
                self.report(issue)
            self.images.add(source)
        if tag == "img" and "alt" not in attributes:
            self.report("<img> is missing alt text")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def local_image(root: Path, source: str) -> Path | None:
    parsed = urlsplit(source)
    if parsed.scheme or parsed.netloc:
        return None
    path = (root / unquote(parsed.path)).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"image escapes repository: {source}")
    return path


def svg_text(tree: ET.Element) -> str:
    return " ".join(
        "".join(element.itertext())
        for element in tree.iter()
        if element.tag.rsplit("}", 1)[-1] in {"text", "title", "desc"}
    )


def experience_issues(config: dict[str, str], text: str, today: dt.date) -> list[str]:
    """Every "N+ years at AWS" the cards show must follow career.start_date."""
    start = config.get("career.start_date")
    if not start:
        return []
    match = re.fullmatch(r"(\d{4})-(\d{2})", start)
    if not match:
        return [f"career.start_date: expected YYYY-MM, got {start!r}"]
    year, month = int(match[1]), int(match[2])
    expected = today.year - year - (today.month < month)
    shown = {int(n) for n in re.findall(r"(\d+)\+ years at AWS", text, re.IGNORECASE)}
    return [
        f"career.start_date: a card shows {n}+ years at AWS, expected {expected}+ from {start}"
        for n in sorted(shown - {expected})
    ]


def profile_link_issues(links: list[str], config: dict[str, str]) -> list[str]:
    issues = []
    profile_routes = (
        ("linkedin.com", r"/in/([^/]+)", "linkedin.username"),
        ("leetcode.com", r"/(?:u/)?([^/]+)/?", "leetcode.username"),
        ("credly.com", r"/users/([^/]+)", "credly.username"),
        ("monkeytype.com", r"/profile/([^/]+)", "monkeytype.username"),
        ("holopin.me", r"/([^/]+)", "holopin.username"),
        ("holopin.io", r"/@([^/]+)", "holopin.username"),
    )
    github_reserved = {
        "search",
        "explore",
        "topics",
        "settings",
        "notifications",
        "pulls",
    }
    for link in links:
        try:
            parsed = urlsplit(link)
        except ValueError:
            continue
        host = (parsed.hostname or "").removeprefix("www.")
        for expected_host, route, setting in profile_routes:
            match = re.fullmatch(route + "/?", parsed.path)
            if host == expected_host and match and setting in config:
                if unquote(match[1]).casefold() != config[setting].casefold():
                    issues.append(
                        f"{setting}: link uses {match[1]!r}, expected {config[setting]!r}"
                    )
        if host == "github.com" and parsed.path.strip("/").count("/") == 0:
            username = parsed.path.strip("/")
            if username and username not in github_reserved:
                if username.casefold() != config["github.username"].casefold():
                    issues.append(f"github.username: unexpected profile link {link}")
    for setting in ("portfolio.url", "resume.path"):
        if config[setting] not in links:
            issues.append(
                f"{setting}: configured URL is missing from README: {config[setting]}"
            )
    return issues


def certification_issues(
    root: Path, trees: dict[Path, ET.Element], today: dt.date
) -> list[str]:
    try:
        data = json.loads((root / "assets/svg/data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"assets/svg/data.json: {error}"]
    portfolio = data.get("portfolio", {}) if isinstance(data, dict) else {}
    certs = portfolio.get("certifications", []) if isinstance(portfolio, dict) else []
    if not isinstance(certs, list) or not certs:
        return ["assets/svg/data.json: missing certification expiry data"]
    active = 0
    try:
        for cert in certs:
            expiry = cert.get("expiryDate")
            if expiry and dt.date.fromisoformat(expiry) >= today:
                active += 1
    except (TypeError, ValueError, AttributeError):
        return ["assets/svg/data.json: invalid certification expiry date"]
    issues = []
    for path, tree in trees.items():
        count = tree.get("data-active-certifications")
        card_name = path.stem.removesuffix("-mobile")
        if card_name in {"profile-badges", "certs-status"} and count is None:
            issues.append(
                f"{path.relative_to(root)}: missing active certification metadata"
            )
        if count is not None and count != str(active):
            issues.append(
                f"{path.relative_to(root)}: active certifications is {count}, expected {active} on {today}"
            )
    return issues


def read_documents(root: Path) -> tuple[list[ProfileHTML], list[str]]:
    """Parse README.md and COMMUNITY.md, keeping each one's markup issues."""
    documents: list[ProfileHTML] = []
    issues: list[str] = []
    for filename in ("README.md", "COMMUNITY.md"):
        try:
            html = (root / filename).read_text(encoding="utf-8")
        except OSError as error:
            issues.append(str(error))
            continue
        parsed = ProfileHTML(filename)
        parsed.feed(html)
        documents.append(parsed)
        issues.extend(parsed.issues)
    return documents, issues


def svg_issues(
    root: Path, document: str, source: str, trees: dict[Path, ET.Element]
) -> list[str]:
    """Check one image reference; a parsed local SVG is kept in trees."""
    path = local_image(root, source)
    if path is None:
        return []
    if not path.is_file():
        return [f"{document}: missing image {source}"]
    if path.suffix.lower() != ".svg":
        return [f"{document}: local profile image must be SVG: {source}"]
    if path not in trees:
        # only this repository's own generated SVGs reach this parse
        trees[path] = ET.parse(path).getroot()  # nosec B314
    tree = trees[path]
    issues = []
    if tree.tag != "{http://www.w3.org/2000/svg}svg":
        issues.append(f"{source}: expected an SVG root element and namespace")
    if any(element.tag.rsplit("}", 1)[-1] == "script" for element in tree.iter()):
        issues.append(f"{source}: SVG must not contain scripts")
    return issues


def validate(root: Path, today: dt.date | None = None) -> list[str]:
    root = root.resolve()
    today = today or dt.datetime.now(dt.timezone.utc).date()
    try:
        config = read_profile_config(root / ".github/config/profiles.yml")
    except (OSError, ValueError) as error:
        return [str(error)]
    missing = [key for key in REQUIRED_CONFIG if not config.get(key)]
    if missing:
        return ["Missing profile settings: " + ", ".join(missing)]
    documents, issues = read_documents(root)
    trees: dict[Path, ET.Element] = {}
    for document in documents:
        for source in sorted(document.images):
            try:
                issues.extend(svg_issues(root, document.document, source, trees))
            except (OSError, ValueError, ET.ParseError) as error:
                issues.append(f"{source}: {error}")
    if documents:
        issues.extend(profile_link_issues(documents[0].links, config))
    text = re.sub(r"\s+", " ", " ".join(svg_text(tree) for tree in trees.values()))
    if config["career.current_role"] not in text:
        issues.append(
            "career.current_role: configured role is missing from the SVG content"
        )
    issues.extend(experience_issues(config, text, today))
    issues.extend(certification_issues(root, trees, today))
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT, help="repository or fixture root"
    )
    parser.add_argument(
        "--config-value", help="print one scalar profile setting, for workflows"
    )
    arguments = parser.parse_args()
    if arguments.config_value:
        try:
            config = read_profile_config(arguments.root / ".github/config/profiles.yml")
            print(config[arguments.config_value])
        except (OSError, ValueError, KeyError) as error:
            print(f"Profile configuration error: {error}", file=sys.stderr)
            return 1
        return 0
    issues = validate(arguments.root)
    if issues:
        print("Profile validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print(
        "README and community SVG references, links, profile settings and certification counts are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
