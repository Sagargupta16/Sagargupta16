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
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

# the renderer and this validator share one expiry rule, one issuer rule and the
# public labels, so what is written and what is accepted cannot drift apart
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mobile_cards import (
    CUSTOMER_LABELS,
    GENERIC_CUSTOMER,
    PROGRAMS,
    PUBLIC_AMBASSADOR,
    cert_issuer,
    cert_status,
)

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = "assets/svg/data.json"
CREDLY_FILE = "assets/credly-badges.md"
DOCUMENTS = ("README.md", "COMMUNITY.md")
SVG_ROOT = "{http://www.w3.org/2000/svg}svg"
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
# House style: a hyphen, never an en dash (U+2013) or em dash (U+2014), in
# anything published. Built from code points so this file holds neither.
DASHES = re.compile(f"[{chr(0x2013)}{chr(0x2014)}]")
# Code points that render as emoji by default, plus the selector (U+FE0F) that
# turns a plain symbol into one. Arrows, check marks, stars and the middle dot
# are text and stay allowed.
EMOJI_RANGES = (
    "1F000-1FAFF 231A-231B 23E9-23EC 23F0 23F3 25FD-25FE 2614-2615 2648-2653 267F 2693 "
    "26A1 26AA-26AB 26BD-26BE 26C4-26C5 26CE 26D4 26EA 26F2-26F3 26F5 26FA 26FD 2705 "
    "270A-270B 2728 274C 274E 2753-2755 2757 2795-2797 27B0 27BF 2B1B-2B1C 2B50 2B55 FE0F"
)
EMOJI = re.compile(
    "["
    + "".join(
        "-".join(chr(int(point, 16)) for point in span.split("-"))
        for span in EMOJI_RANGES.split()
    )
    + "]"
)
# The internal community acronym is never published, and it is not stored here
# either: instead every "ambassador" must sit inside the one public wording, or
# inside a public badge name from the Credly block his Credly action writes.
# Between two words of either there may be any space, or the tags where a card
# wraps the phrase onto its next line, as long as no tag holds the word itself.
AMBASSADOR = re.compile("ambassador", re.IGNORECASE)
GAP = r"(?:\s|<(?:(?!ambassador)[^<>])*>)+"
# The only labels the renderer's public snapshot gives an engagement, by kind.
CUSTOMER_CLIENTS = frozenset({*CUSTOMER_LABELS.values(), GENERIC_CUSTOMER})
PROGRAM_CLIENTS = frozenset(PROGRAMS.values())
# what the cards print in brackets under "Customer N": a table label without " customer"
CUSTOMER_SECTORS = frozenset(
    label.removesuffix(" customer") for label in CUSTOMER_LABELS.values()
)
SHOWN_CUSTOMER = re.compile(r"\bCustomer \d+\s*\(([^)]*)\)")
# The counts a visitor reads, in card text and in README alt text.
ACTIVE_SHOWN = re.compile(
    r"(\d+)\s+active\s+(?:AWS\s+)?certifications?\b", re.IGNORECASE
)
AWS_CERTIFIED_SHOWN = re.compile(r"(\d+)x\s+AWS\s+certified\b", re.IGNORECASE)
YEARS_SHOWN = re.compile(r"(\d+)\+\s*years\s+at\s+AWS\b", re.IGNORECASE)
# The generated pages are HTML only: inline Markdown links and images, and
# reference definitions, would skip the reference checks below.
MARKDOWN_LINK = re.compile(
    r"!?\[[^\]\n]*\]\([^)\n]*\)|^ {0,3}\[[^\]\n]+\]:[ \t]*\S", re.MULTILINE
)
EXTERNAL_CSS = re.compile(r"@import|@font-face", re.IGNORECASE)
EXTERNAL_URL = re.compile(r"""url\(\s*['"]?(?!#|data:)""", re.IGNORECASE)
STALE_AFTER = dt.timedelta(days=3)


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
        """Collect the links, image sources, alt texts and issues of one document."""
        super().__init__(convert_charrefs=True)
        self.document = document
        self.issues: list[str] = []
        self.links: list[str] = []
        self.images: set[str] = set()
        self.alts: list[str] = []

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
        if tag == "img":
            self.alts.append(attributes.get("alt") or "")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def local_path(root: Path, source: str, kind: str = "image") -> Path | None:
    """Resolve a relative image or link inside the repository; None for a remote or in-page one."""
    parsed = urlsplit(source)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    path = (root / unquote(parsed.path)).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"{kind} escapes repository: {source}")
    return path


def svg_text(tree: ET.Element) -> str:
    return " ".join(
        "".join(element.itertext())
        for element in tree.iter()
        if element.tag.rsplit("}", 1)[-1] in {"text", "title", "desc"}
    )


def character_issues(name: str, text: str) -> list[str]:
    """No en dash, em dash or emoji in anything published under his name, typed or as an entity."""
    issues = []
    for label, pattern in (("an en or em dash", DASHES), ("an emoji", EMOJI)):
        # &mdash;, &#8212; and &#128640; render as the character itself
        for form in (text, unescape(text)):
            match = pattern.search(form)
            if match:
                line = form.count("\n", 0, match.start()) + 1
                issues.append(
                    f"{name}:{line}: contains {label} (U+{ord(match[0]):04X})"
                )
                break
    return issues


def markdown_issues(name: str, text: str) -> list[str]:
    """README.md and COMMUNITY.md are generated as HTML, so Markdown link syntax is a hand edit."""
    return [
        f"{name}:{text.count(chr(10), 0, match.start()) + 1}: Markdown link or image "
        "syntax; the generated pages use HTML <a> and <img> only"
        for match in MARKDOWN_LINK.finditer(text)
    ]


def svg_safety_issues(name: str, raw: str, tree: ET.Element) -> list[str]:
    """GitHub shows each card through <img>, so it must be one self-contained file with no script."""
    issues = []
    if tree.tag != SVG_ROOT:
        issues.append(f"{name}: expected an SVG root element and namespace")
    for element in tree.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"script", "foreignObject"}:
            issues.append(f"{name}: SVG must not contain <{tag}>")
        for key, value in element.attrib.items():
            attribute = key.rsplit("}", 1)[-1]
            inside = value.strip().startswith(("#", "data:"))
            if attribute in {"href", "src"} and not inside:
                issues.append(
                    f"{name}: <{tag}> {attribute} points outside the file; "
                    "only a fragment or a data: URI loads in a README image"
                )
            if attribute.lower().startswith("on"):
                issues.append(f"{name}: event attribute {attribute} on <{tag}>")
    if EXTERNAL_CSS.search(raw):
        issues.append(f"{name}: @import and @font-face cannot load in a README image")
    if EXTERNAL_URL.search(raw):
        issues.append(f"{name}: url() points outside the file")
    return issues


def _smil_list(value: str) -> list[str]:
    return [item.strip() for item in value.strip().strip(";").split(";")]


def timing_issues(name: str, tree: ET.Element) -> list[str]:
    """A SMIL list that does not line up is dropped, and the element silently never animates."""
    issues = []
    for element in tree.iter():
        key_times = element.get("keyTimes")
        if key_times is None:
            continue
        tag = element.tag.rsplit("}", 1)[-1]
        times = _smil_list(key_times)
        try:
            numbers = [float(time) for time in times]
        except ValueError:
            issues.append(f"{name}: <{tag}> keyTimes is not a list of numbers")
            continue
        values = element.get("values") or element.get("keyPoints")
        if values is not None and len(_smil_list(values)) != len(times):
            issues.append(
                f"{name}: <{tag}> has {len(times)} keyTimes for "
                f"{len(_smil_list(values))} values"
            )
        # a discrete animation may hold its last value from before 1
        ends = element.get("calcMode") == "discrete" or numbers[-1] == 1
        if numbers[0] != 0 or not ends or numbers != sorted(numbers):
            issues.append(
                f"{name}: <{tag}> keyTimes must rise from 0 to 1, got {key_times}"
            )
        splines = element.get("keySplines")
        if splines is not None and len(_smil_list(splines)) != len(times) - 1:
            issues.append(
                f"{name}: <{tag}> needs {len(times) - 1} keySplines for {len(times)} keyTimes"
            )
    return issues


def check_svg(
    root: Path, path: Path, trees: dict[Path, ET.Element], texts: dict[str, str]
) -> list[str]:
    """Parse one SVG and run the per-file checks; a file that parses is kept in trees and texts."""
    name = path.relative_to(root).as_posix()
    try:
        # only this repository's own generated SVGs reach this parse
        data = path.read_bytes()
        tree = ET.fromstring(data)  # nosec B314
        raw = data.decode("utf-8")
    except (OSError, ValueError, ET.ParseError) as error:
        return [f"{name}: {error}"]
    trees[path], texts[name] = tree, raw
    return svg_safety_issues(name, raw, tree) + timing_issues(name, tree)


def experience_issues(config: dict[str, str], text: str, today: dt.date) -> list[str]:
    """Every "N+ years at AWS" the cards and their alt text show must follow career.start_date."""
    start = config.get("career.start_date")
    if not start:
        return []
    match = re.fullmatch(r"(\d{4})-(\d{2})", start)
    if not match:
        return [f"career.start_date: expected YYYY-MM, got {start!r}"]
    year, month = int(match[1]), int(match[2])
    expected = today.year - year - (today.month < month)
    shown = {int(n) for n in YEARS_SHOWN.findall(text)}
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


def read_data(root: Path) -> tuple[dict, str, list[str]]:
    """Load the public snapshot once: the data, its raw text, and why it could not be read."""
    try:
        raw = (root / DATA_FILE).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError) as error:
        return {}, "", [f"{DATA_FILE}: {error}"]
    return (data if isinstance(data, dict) else {}), raw, []


def _portfolio(data: dict) -> dict:
    portfolio = data.get("portfolio")
    return portfolio if isinstance(portfolio, dict) else {}


def _phrase(text: str) -> re.Pattern[str]:
    """Match a phrase in any case, its words split by any space or by the tags between card lines."""
    words = DASHES.sub("-", text).split()
    return re.compile(
        r"(?<![A-Za-z0-9])" + GAP.join(map(re.escape, words)) + r"(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def public_badge_names(root: Path) -> list[str]:
    """The Credly badge names that hold "ambassador": public names his Credly action publishes."""
    try:
        text = (root / CREDLY_FILE).read_text(encoding="utf-8")
    except OSError:
        return []
    names = {unescape(title) for title in re.findall(r'title="([^"]+)"', text)}
    return sorted(name for name in names if AMBASSADOR.search(name))


def stray_ambassador(text: str, badges: list[str]) -> bool:
    """True when an "ambassador" in text is outside the public wording and every public badge name."""
    text = DASHES.sub("-", unescape(text))
    if not AMBASSADOR.search(text):
        return False
    for phrase in (PUBLIC_AMBASSADOR, *badges):
        text = _phrase(phrase).sub(" ", text)
    return bool(AMBASSADOR.search(text))


def confidentiality_issues(
    data: dict, texts: dict[str, list[str]], badges: list[str]
) -> list[str]:
    """Customers show only the fixed public labels, and "ambassador" only in the public wording."""
    issues = []
    engagements = _portfolio(data).get("engagements")
    for engagement in engagements if isinstance(engagements, list) else []:
        if not isinstance(engagement, dict):
            continue
        # The client is one of the renderer's fixed labels for its kind, whatever
        # the portfolio wrote, and the portfolio's name never rides along. The
        # value itself is never echoed.
        client = engagement.get("client")
        program = engagement.get("kind") == "program"
        allowed = PROGRAM_CLIENTS if program else CUSTOMER_CLIENTS
        if (
            not isinstance(client, str)
            or client not in allowed
            or engagement.get("name")
        ):
            issues.append(
                f"{DATA_FILE}: engagement {engagement.get('when', '?')} is not in its public "
                "shape: a customer shows its CUSTOMER_LABELS month label or "
                f'"{GENERIC_CUSTOMER}", a program its PROGRAMS name, and no name is kept; '
                "the renderer's public snapshot must relabel it"
            )
    for name, forms in texts.items():
        shown = {
            m.group(1).strip() for form in forms for m in SHOWN_CUSTOMER.finditer(form)
        }
        if shown - CUSTOMER_SECTORS:
            issues.append(
                f'{name}: a "Customer N (...)" line names something other than a sector '
                "from CUSTOMER_LABELS; the cards print only the table's generic sectors"
            )
        if any(stray_ambassador(form, badges) for form in forms):
            issues.append(
                f'{name}: "ambassador" appears outside the public wording '
                f'"{PUBLIC_AMBASSADOR}"; the internal community acronym is never published'
            )
    return issues


def certification_issues(
    root: Path,
    data: dict,
    trees: dict[Path, ET.Element],
    today: dt.date,
    shown: str,
) -> list[str]:
    """The status card's metadata and every count a visitor reads follow the recorded expiries."""
    certs = _portfolio(data).get("certifications")
    if not isinstance(certs, list) or not certs:
        return [f"{DATA_FILE}: missing certification expiry data"]
    current = [
        cert
        for cert in certs
        if isinstance(cert, dict) and cert_status(cert, today)[0] == "active"
    ]
    active = len(current)
    # the hero's "Nx AWS certified" counts only the AWS ones, by the renderer's own rule
    aws = sum(cert_issuer(str(cert.get("name") or "")) == "AWS" for cert in current)
    issues = []
    for path, tree in trees.items():
        count = tree.get("data-active-certifications")
        name = path.relative_to(root).as_posix()
        if path.stem.removesuffix("-mobile") == "certs-status" and count is None:
            issues.append(f"{name}: missing active certification metadata")
        if count is not None and count != str(active):
            issues.append(
                f"{name}: active certifications is {count}, expected {active} on {today}"
            )
    for n in sorted({int(n) for n in ACTIVE_SHOWN.findall(shown)} - {active}):
        issues.append(
            f"a card or alt text shows {n} active certifications, expected {active} on {today}"
        )
    for n in sorted({int(n) for n in AWS_CERTIFIED_SHOWN.findall(shown)} - {aws}):
        issues.append(
            f"a card or alt text shows {n}x AWS certified, expected {aws}x on {today}"
        )
    return issues


def read_documents(root: Path) -> tuple[list[ProfileHTML], dict[str, str], list[str]]:
    """Parse README.md and COMMUNITY.md, keeping each one's raw text and markup issues."""
    documents: list[ProfileHTML] = []
    texts: dict[str, str] = {}
    issues: list[str] = []
    for filename in DOCUMENTS:
        try:
            html = (root / filename).read_text(encoding="utf-8")
        except OSError as error:
            issues.append(str(error))
            continue
        parsed = ProfileHTML(filename)
        parsed.feed(html)
        documents.append(parsed)
        texts[filename] = html
        issues.extend(parsed.issues)
    return documents, texts, issues


def reference_issues(
    root: Path,
    document: ProfileHTML,
    trees: dict[Path, ET.Element],
    texts: dict[str, str],
) -> list[str]:
    """A local image must be an SVG that exists, and a relative link must lead to a file."""
    issues = []
    for source in sorted(document.images):
        try:
            path = local_path(root, source)
        except ValueError as error:
            issues.append(f"{source}: {error}")
            continue
        if path is None:
            continue
        if not path.is_file():
            issues.append(f"{document.document}: missing image {source}")
        elif path.suffix.lower() != ".svg":
            issues.append(
                f"{document.document}: local profile image must be SVG: {source}"
            )
        elif path.parent != root / "assets/svg":
            # the cards in assets/svg were all checked already
            issues.extend(check_svg(root, path, trees, texts))
    for link in document.links:
        try:
            path = local_path(root, link, "link")
        except ValueError as error:
            issues.append(f"{document.document}: {error}")
            continue
        if path is not None and not path.exists():
            issues.append(f"{document.document}: link target does not exist: {link}")
    return issues


def warnings(root: Path, now: dt.datetime | None = None) -> list[str]:
    """Worth a look, but never a reason to block the daily commit: stale sources, unreadable expiry dates."""
    now = now or dt.datetime.now(dt.timezone.utc)
    data, _, _ = read_data(root)
    notes = []
    updated = data.get("source_updated_at")
    for source, stamp in sorted(updated.items()) if isinstance(updated, dict) else []:
        try:
            when = dt.datetime.fromisoformat(str(stamp))
        except ValueError:
            notes.append(f"{DATA_FILE}: {source} has no readable refresh time")
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        if now - when > STALE_AFTER:
            notes.append(
                f"{DATA_FILE}: {source} data is {(now - when).days} days old, "
                f"last refreshed {when.date()}"
            )
    certs = _portfolio(data).get("certifications")
    for cert in certs if isinstance(certs, list) else []:
        if isinstance(cert, dict) and cert_status(cert, now.date())[0] == "unknown":
            notes.append(
                f"{DATA_FILE}: {cert.get('name', 'a certification')} has no readable "
                "expiry date and is not counted as active"
            )
    return notes


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
    documents, texts, issues = read_documents(root)
    trees: dict[Path, ET.Element] = {}
    # every card is checked, whether or not a document shows it yet
    for path in sorted((root / "assets/svg").glob("*.svg")):
        issues.extend(check_svg(root, path, trees, texts))
    for document in documents:
        issues.extend(reference_issues(root, document, trees, texts))
        issues.extend(markdown_issues(document.document, texts[document.document]))
    if documents:
        issues.extend(profile_link_issues(documents[0].links, config))
    for name, text in texts.items():
        issues.extend(character_issues(name, text))
    text = re.sub(r"\s+", " ", " ".join(svg_text(tree) for tree in trees.values()))
    if config["career.current_role"] not in text:
        issues.append(
            "career.current_role: configured role is missing from the SVG content"
        )
    # what a visitor reads: the cards' text and the alt text the pages give them
    alts = " ".join(alt for document in documents for alt in document.alts)
    shown = re.sub(r"\s+", " ", f"{text} {alts}")
    issues.extend(experience_issues(config, shown, today))
    data, raw, data_issues = read_data(root)
    issues.extend(data_issues)
    if not data_issues:
        # each file's raw text, plus each card's text content (a word split across
        # tspans reads whole there) and the snapshot with its JSON escapes decoded
        forms = {name: [raw_text] for name, raw_text in texts.items()}
        for path, tree in trees.items():
            forms[path.relative_to(root).as_posix()].append(svg_text(tree))
        forms[DATA_FILE] = [raw, json.dumps(data, ensure_ascii=False)]
        badges = public_badge_names(root)
        issues.extend(confidentiality_issues(data, forms, badges))
        issues.extend(certification_issues(root, data, trees, today, shown))
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
    # GitHub Actions turns these lines into annotations; they never fail the run
    for note in warnings(arguments.root):
        print(f"::warning::{note}")
    issues = validate(arguments.root)
    if issues:
        print("Profile validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print(
        "README and community SVG references, links, profile settings, confidentiality "
        "rules and certification counts are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
