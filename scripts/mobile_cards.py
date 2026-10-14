"""Static, self-contained 320px SVG layouts selected by README picture sources."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
from __future__ import annotations

import datetime
import re
import unicodedata
from html import escape

WIDTH, PAD, BODY_SIZE = 320, 20, 17
CONTENT_WIDTH = WIDTH - PAD * 2
BG, CARD, WHITE = "#0b1012", "#0f171c", "#f3f4f6"
MUTED, BLUE, SKY = "#b1bfcc", "#60a5fa", "#38bdf8"
GREEN, AMBER, BORDER = "#4ade80", "#fbbf24", "#26343d"
SANS = "'Segoe UI',-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"


def _advance(character: str) -> float:
    if unicodedata.combining(character):
        return 0
    if unicodedata.east_asian_width(character) in {"W", "F"}:
        return 1.05
    if character in "W@%M":
        return 1
    if character in "ilI.,:;'!|`":
        return 0.34
    if character in " fjrt()[]":
        return 0.44
    return 0.76 if character.isupper() else 0.64


def text_width(text: str, size: float = BODY_SIZE) -> float:
    """Conservative sans-serif glyph advances for portable line wrapping."""
    return sum(_advance(character) for character in text) * size


def wrap_text(text: str, width: float, size: float = BODY_SIZE) -> list[str]:
    """Wrap words, splitting long tokens without dropping any content."""
    lines, current = [], ""
    for word in str(text).split():
        candidate = f"{current} {word}" if current else word
        if text_width(candidate, size) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        for character in word:
            if current and text_width(current + character, size) > width:
                lines.append(current)
                current = ""
            current += character
    if current:
        lines.append(current)
    return lines


class Card:
    def __init__(self, label: str, accent: str = BLUE):
        self.label, self.accent = label, accent
        self.parts: list[str] = []
        self.y: float = PAD

    def lines(
        self,
        text: str,
        *,
        x: float = PAD,
        y: float | None = None,
        width: float = CONTENT_WIDTH,
        size: float = BODY_SIZE,
        color: str = WHITE,
        weight: int = 500,
    ) -> float:
        cursor = self.y if y is None else y
        for line in wrap_text(text, width, size):
            cursor += size
            self.parts.append(
                f'<text x="{x:g}" y="{cursor:g}" font-size="{size:g}" '
                f'font-weight="{weight}" fill="{color}">{escape(line)}</text>'
            )
            cursor += size * 0.42
        if y is None:
            self.y = cursor
        return cursor

    def title(self, text: str) -> None:
        self.lines(text, size=20, color=self.accent, weight=700)
        self.y += 12

    def divider(self) -> None:
        self.y += 8
        self.parts.append(
            f'<path d="M{PAD} {self.y:g}H{WIDTH - PAD}" stroke="{BORDER}"/>'
        )
        self.y += 16

    def row(self, title: str, detail: str = "", metadata: str = "") -> None:
        self.lines(title, weight=650)
        if metadata:
            self.y += 4
            self.lines(metadata, size=15, color=self.accent)
        if detail:
            self.y += 5
            self.lines(detail, color=MUTED)
        self.y += 16

    def metrics(self, items: list[tuple[str, str]]) -> None:
        gap, tile_width = 12, (CONTENT_WIDTH - 12) / 2
        inner = tile_width - 20
        for index in range(0, len(items), 2):
            pair = items[index : index + 2]
            height = max(
                24
                + len(wrap_text(value, inner, 26)) * 26 * 1.42
                + len(wrap_text(label, inner, 15)) * 15 * 1.42
                for value, label in pair
            )
            for column, (value, label) in enumerate(pair):
                x = PAD + column * (tile_width + gap)
                self.parts.append(
                    f'<rect x="{x:g}" y="{self.y:g}" width="{tile_width:g}" '
                    f'height="{height:g}" rx="10" fill="{CARD}" stroke="{BORDER}"/>'
                )
                bottom = self.lines(
                    value,
                    x=x + 10,
                    y=self.y + 10,
                    width=inner,
                    size=26,
                    color=self.accent,
                    weight=750,
                )
                self.lines(
                    label, x=x + 10, y=bottom + 4, width=inner, size=15, color=MUTED
                )
            self.y += height + gap

    def chips(self, labels: list[str]) -> None:
        x, line_bottom = float(PAD), self.y
        for label in labels:
            chip_width = min(CONTENT_WIDTH, text_width(label, 16) + 20)
            chip_height = len(wrap_text(label, chip_width - 20, 16)) * 23 + 16
            if x + chip_width > WIDTH - PAD:
                x, self.y = float(PAD), line_bottom + 8
            self.parts.append(
                f'<rect x="{x:g}" y="{self.y:g}" width="{chip_width:g}" '
                f'height="{chip_height:g}" rx="8" fill="{CARD}" stroke="{BORDER}"/>'
            )
            self.lines(label, x=x + 10, y=self.y + 7, width=chip_width - 20, size=16)
            line_bottom = max(line_bottom, self.y + chip_height)
            x += chip_width + 8
        self.y = line_bottom + 12

    def finish(self) -> str:
        height = int(self.y + PAD + 0.999)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(self.label, quote=True)}">'
            f"<title>{escape(self.label)}</title>"
            f"<style>text{{font-family:{SANS};font-variant-numeric:tabular-nums}}</style>"
            f'<rect x=".5" y=".5" width="{WIDTH - 1}" height="{height - 1}" rx="14" '
            f'fill="{BG}" stroke="{BORDER}"/>' + "".join(self.parts) + "</svg>"
        )


def _number(value: object) -> str:
    if value is None or value == "":
        return "—"
    return f"{value:,}" if isinstance(value, int) else str(value)


def _updated(card: Card, data: dict, source: str) -> None:
    updates = data.get("source_updated_at") or {}
    value = updates.get(source) if isinstance(updates, dict) else None
    if value:
        card.y += 6
        card.lines(f"Updated {str(value)[:10]}", size=14, color=MUTED)


def _cert_status(certificate: dict, today: str) -> tuple[str, str]:
    expiry = certificate.get("expiryDate")
    if not expiry:
        return "unknown", "Expiry not recorded"
    try:
        expires = datetime.date.fromisoformat(str(expiry)[:10])
        current = datetime.date.fromisoformat(today)
    except ValueError:
        return "unknown", "Expiry not recorded"
    if expires < current:
        return "expired", f"Expired {expires.isoformat()}"
    return "active", f"Valid through {expires.isoformat()}"


def _hero(data: dict, context: dict) -> str:
    card = Card("Sagar Gupta, cloud consultant at AWS", SKY)
    card.lines("HI, I AM", size=15, color=BLUE, weight=700)
    card.y += 8
    card.lines("Sagar Gupta", size=34, weight=750)
    card.y += 12
    card.lines(context.get("aws_title", "Cloud Consultant") + " at AWS", weight=650)
    card.y += 12
    card.lines("DevOps · MLOps · AI agent tooling", color=MUTED)
    card.y += 16
    card.lines("Hyderabad, India", size=16, color=GREEN)
    return card.finish()


def _profile_badges(data: dict, context: dict) -> str:
    github, leetcode = data.get("github") or {}, data.get("leetcode") or {}
    card = Card("Profile at a glance")
    card.metrics(
        [
            (_number(data.get("views")), "Profile views"),
            (_number(github.get("followers")), "Followers"),
            (_number(github.get("stars")), "Total stars"),
            (
                _number(max(leetcode.get("history") or [leetcode.get("rating", 0)])),
                "Peak rating",
            ),
        ]
    )
    certificates = context.get("certifications", [])
    active = [
        c for c in certificates if _cert_status(c, context["today"])[0] == "active"
    ]
    if certificates:
        card.lines(
            f"{len(active)} active certifications", size=16, color=SKY, weight=650
        )
    start_year, start_month = context.get("career_start", (2024, 8))
    today = datetime.date.fromisoformat(context["today"])
    years = today.year - start_year - (today.month < start_month)
    card.lines(f"{max(years, 0)}+ years at AWS", size=16, color=GREEN)
    if leetcode.get("badge"):
        card.lines(f"LeetCode {leetcode['badge']}", size=16, color=AMBER)
    card.lines("sagargupta.online", size=16, color=BLUE)
    return card.finish().replace(
        'role="img"', f'role="img" data-active-certifications="{len(active)}"', 1
    )


def _intro(data: dict, context: dict) -> str:
    card = Card("About Sagar Gupta")
    card.title("About")
    card.lines(
        (data.get("portfolio") or {}).get("intro") or context.get("aws_title", "")
    )
    card.divider()
    card.chips(["DevOps", "MLOps", "AWS cloud", "Full stack"])
    return card.finish()


def _experience(data: dict, context: dict) -> str:
    card = Card("Career and AWS customer engagements", GREEN)
    card.title("Career")
    milestones = context.get("milestones", [])
    for index, (year, role, organization, city) in enumerate(milestones):
        top = card.y
        card.parts.append(f'<circle cx="24" cy="{top + 10:g}" r="4" fill="{GREEN}"/>')
        bottom = card.lines(
            f"{year} · {role}", x=38, y=top, width=WIDTH - PAD - 38, weight=650
        )
        bottom = card.lines(
            f"{organization} · {city}",
            x=38,
            y=bottom + 3,
            width=WIDTH - PAD - 38,
            size=16,
            color=MUTED,
        )
        card.y = bottom + 20
        if index < len(milestones) - 1:
            card.parts.append(
                f'<path d="M24 {top + 18:g}V{card.y:g}" stroke="{BORDER}"/>'
            )
    card.divider()
    card.title("Customer engagements")
    for when, client, role in reversed(context.get("engagements", [])):
        card.row(client, role, when)
    return card.finish()


def _highlights(data: dict, context: dict) -> str:
    portfolio = data.get("portfolio") or {}
    ambassador = next(
        (
            match.group(1)
            for achievement in portfolio.get("achievements", [])
            if (match := re.match(r"(\d+)x TFC", achievement.get("title", "")))
        ),
        None,
    )
    items = [
        ("10/10", "State Street client satisfaction"),
        ("~90%", "Faster account setup"),
        (str(len(portfolio.get("samples", []))), "Published AWS samples"),
    ]
    if ambassador:
        items.append((f"{ambassador}x", "TFC ambassador"))
    card = Card("Highlights from AWS work", GREEN)
    card.metrics(items)
    return card.finish()


def _worked_with(data: dict, context: dict) -> str:
    card = Card("Organizations and roles", GREEN)
    card.title("Worked with")
    for company, role in context.get("worked_with", []):
        card.row(company, role)
    return card.finish()


def _publications(data: dict, context: dict) -> str:
    card = Card("Publications, talks and recognition", SKY)
    for index, (label, entries) in enumerate(context.get("publications", [])):
        if index:
            card.divider()
        card.title(label.capitalize() if label.isupper() else label)
        for text, year in entries:
            text = text.replace("APG pattern:", "AWS Prescriptive Guidance pattern:")
            card.row(text, metadata=str(year))
    return card.finish()


def _education(data: dict, context: dict) -> str:
    card = Card("Education")
    card.title("Education")
    for entry in (data.get("portfolio") or {}).get("education", [])[:2]:
        card.row(
            entry.get("title", ""), entry.get("institution", ""), entry.get("date", "")
        )
        if entry.get("location"):
            card.lines(entry["location"], size=16, color=MUTED)
        if entry.get("cgpa"):
            card.lines(f"CGPA {entry['cgpa']}", size=16, color=SKY, weight=650)
        achievements = entry.get("achievements") or []
        if achievements:
            card.lines(
                achievements[0].removeprefix("Passed with "), size=16, color=MUTED
            )
        card.y += 20
    return card.finish()


def _oss(data: dict, context: dict) -> str:
    entries = (data.get("portfolio") or {}).get("oss", [])
    merged = [entry for entry in entries if entry.get("status") == "merged"]
    opened = [entry for entry in entries if entry.get("status") == "open"]
    repositories = sorted({entry["repo"] for entry in merged})
    reach = sum(
        data.get("oss_stars", {}).get(repository, 0) for repository in repositories
    )
    card = Card("Open source contributions", GREEN)
    card.title("Open source")
    card.metrics(
        [
            (str(len(merged)), "Merged upstream"),
            (str(len(opened)), "Open PRs"),
            (str(len(repositories)), "Repos with merges"),
            (
                f"{reach // 1000}K+" if reach >= 1000 else str(reach),
                "Combined repo stars",
            ),
        ]
    )
    card.lines("Merged into", size=16, color=GREEN, weight=650)
    card.y += 8
    for repository in repositories:
        card.lines(repository, size=16, color=MUTED)
    _updated(card, data, "portfolio")
    return card.finish()


def _oss_list(data: dict, status: str) -> str:
    entries = [
        entry
        for entry in (data.get("portfolio") or {}).get("oss", [])
        if entry.get("status") == status
    ]
    label = "Merged upstream" if status == "merged" else "Open PRs"
    if status == "merged":
        entries.sort(key=lambda entry: entry.get("merged_at") or "", reverse=True)
    card = Card(f"{len(entries)} {label}", GREEN if status == "merged" else AMBER)
    card.title(f"{len(entries)} {label}")
    for index, entry in enumerate(entries):
        if index:
            card.divider()
        number = entry.get("url", "").rstrip("/").rsplit("/", 1)[-1]
        metadata = f"PR #{number}" if number.isdigit() else ""
        if status == "merged" and entry.get("merged_at"):
            metadata += f" · {entry['merged_at'][:10]}"
        card.row(entry.get("repo", ""), entry.get("title", ""), metadata)
    if status == "open":
        card.divider()
        card.lines("Community impact", color=AMBER, weight=650)
        card.y += 8
        card.lines(
            "Fixed the AWS Ansible deploy and Elastic IP allocation in forem/selfhost, "
            "plus 3 accepted answers on GitHub Community Q&A.",
            color=MUTED,
        )
    _updated(card, data, "portfolio")
    return card.finish()


def _github(data: dict, context: dict) -> str:
    github = data.get("github") or {}
    card = Card("GitHub activity")
    card.title("GitHub activity")
    card.metrics(
        [
            (_number(github.get(key)), label)
            for key, label in [
                ("contributions", "Contributions"),
                ("commits", "Commits"),
                ("prs", "Pull requests"),
                ("stars", "Stars"),
                ("streak", "Current streak days"),
                ("longest", "Longest streak days"),
            ]
        ]
    )
    if github.get("active_days") is not None:
        card.row("Participation", f"{_number(github['active_days'])} active days")
    languages = github.get("languages") or []
    if languages:
        card.divider()
        card.title("Top languages")
        for language, percent, _color in languages:
            card.lines(f"{language} · {percent:g}%", size=16, color=MUTED)
            card.y += 4
    _updated(card, data, "github")
    return card.finish()


def _rating_chart(card: Card, history: list[float]) -> None:
    if len(history) < 2:
        return
    card.divider()
    card.lines("Contest rating history", size=16, color=AMBER, weight=650)
    card.y += 10
    low, high = min(history), max(history)
    left, right = PAD + 42, WIDTH - PAD
    top, bottom = card.y + 8, card.y + 130
    for value, y in [(high, top), (low, bottom)]:
        card.lines(str(round(value)), x=PAD, y=y - 9, width=40, size=13, color=MUTED)
        card.parts.append(f'<path d="M{left} {y:g}H{right}" stroke="{BORDER}"/>')
    points = [
        (
            left + index * (right - left) / (len(history) - 1),
            bottom - (value - low) / max(high - low, 1) * (bottom - top),
        )
        for index, value in enumerate(history)
    ]
    path = " ".join(
        f"{'M' if index == 0 else 'L'}{x:.2f} {y:.2f}"
        for index, (x, y) in enumerate(points)
    )
    card.parts.append(
        f'<path d="{path}" stroke="{AMBER}" stroke-width="2" '
        'fill="none" stroke-linejoin="round"/>'
    )
    card.y = bottom + 18
    card.lines(
        f"Peak {round(high):,} · {len(history)} rated contests", size=15, color=MUTED
    )


def _leetcode(data: dict, context: dict) -> str:
    leetcode = data.get("leetcode") or {}
    card = Card("LeetCode coding and contest statistics", AMBER)
    card.title(f"LeetCode · {leetcode.get('badge', '')}".rstrip(" ·"))
    card.metrics(
        [
            (_number(leetcode.get("rating")), "Contest rating"),
            (
                f"{leetcode['top']}%" if leetcode.get("top") is not None else "—",
                "Top worldwide",
            ),
            (_number(leetcode.get("solved")), "Problems solved"),
            (_number(leetcode.get("contests")), "Contests"),
        ]
    )
    for label, counts in (leetcode.get("by_difficulty") or {}).items():
        card.lines(f"{label} · {counts[0]:,} / {counts[1]:,}", size=16, color=MUTED)
    _rating_chart(card, leetcode.get("history") or [])
    _updated(card, data, "leetcode")
    return card.finish()


def _normal_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("–", "-").replace("—", "-")).casefold()


def _certifications(data: dict, context: dict) -> str:
    certificates = context.get("certifications", [])
    card = Card("Certifications and professional badges", SKY)
    groups = [
        ("active", "Active certifications"),
        ("expired", "Previously earned"),
        ("unknown", "Expiry not recorded"),
    ]
    for status, label in groups:
        entries = [
            certificate
            for certificate in certificates
            if _cert_status(certificate, context["today"])[0] == status
        ]
        if not entries:
            continue
        if card.y > PAD:
            card.divider()
        card.title(label)
        for certificate in entries:
            card.row(
                certificate["name"],
                metadata=_cert_status(certificate, context["today"])[1],
            )
    known = {_normal_name(certificate["name"]) for certificate in certificates}
    badge_names = list(
        dict.fromkeys(
            name
            for name, _url in context.get("badges", [])
            if _normal_name(name) not in known
        )
    )
    if badge_names:
        card.divider()
        card.title("Professional & training badges")
        for name in badge_names:
            card.row(name)
    return card.finish()


STACK_NAMES = {
    "aws": "AWS",
    "githubactions": "GitHub Actions",
    "gitlab": "GitLab",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "cpp": "C++",
    "cs": "C#",
    "r": "R",
    "html": "HTML",
    "css": "CSS",
    "nextjs": "Next.js",
    "tailwind": "Tailwind CSS",
    "materialui": "Material UI",
    "nodejs": "Node.js",
    "fastapi": "FastAPI",
    "graphql": "GraphQL",
    "mongodb": "MongoDB",
    "mysql": "MySQL",
    "postgres": "PostgreSQL",
    "dynamodb": "DynamoDB",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "opencv": "OpenCV",
    "sklearn": "scikit-learn",
    "vscode": "VS Code",
    "github": "GitHub",
}


def _stack(data: dict, context: dict) -> str:
    card = Card("Tech stack and tools")
    card.title("Tech stack")
    card.chips(
        [STACK_NAMES.get(slug, slug.capitalize()) for slug in context.get("stack", [])]
    )
    return card.finish()


def _ai_stack(data: dict, context: dict) -> str:
    card = Card("AI development tools", SKY)
    card.title("AI tools")
    card.chips(context.get("ai_tools", []))
    return card.finish()


def _competitive(data: dict, context: dict) -> str:
    portfolio = data.get("portfolio") or {}
    stats = portfolio.get("coding_stats") or {}
    card = Card("Competitive programming results", AMBER)
    card.title("Competitive programming")
    best_rank = stats.get("leetcode", {}).get("best_contest_rank")
    metrics = [
        (f"#{best_rank}" if best_rank else "—", "LeetCode best rank"),
        (
            _number(stats.get("geeksforgeeks", {}).get("problems_solved")),
            "GeeksforGeeks solved",
        ),
        (
            _number(stats.get("hackerrank", {}).get("problem_solving")),
            "HackerRank problem solving",
        ),
    ]
    kickstart = next(
        (
            entry
            for entry in portfolio.get("contests", [])
            if "Round E" in entry.get("title", "")
        ),
        None,
    )
    if kickstart and (rank := re.search(r"Rank (\d+)", kickstart["title"])):
        metrics.append((f"#{rank.group(1)}", "Kick Start 2022 Round E"))
    card.metrics(metrics)
    for entry in portfolio.get("contests", []):
        if re.match(r"(1st|2nd|3rd|4th) Place", entry.get("title", "")):
            card.divider()
            card.row(entry["title"], entry.get("organizer", ""), entry.get("date", ""))
    return card.finish()


def _sample(title: str, purpose: str, steps: list[tuple[str, str]]) -> str:
    card = Card(title, SKY)
    card.lines("AWS SAMPLE", size=15, color=SKY, weight=700)
    card.y += 8
    card.title(title)
    card.lines(purpose, color=MUTED)
    card.divider()
    for index, (step, detail) in enumerate(steps, start=1):
        card.row(f"{index:02d} · {step}", detail)
    card.lines("View source on GitHub →", size=16, color=BLUE, weight=650)
    return card.finish()


def _footer(data: dict, context: dict) -> str:
    card = Card("Thanks for visiting. Explore Sagar Gupta's portfolio.")
    card.title("Thanks for visiting")
    card.lines("Explore the projects and the work behind them.", color=MUTED)
    card.y += 16
    card.lines("Visit my portfolio →", weight=700)
    card.lines("sagargupta.online", size=16, color=BLUE)
    return card.finish()


def _header(number: str, title: str, subtitle: str, theme: str) -> str:
    card = Card(title)
    color = "#1d4ed8" if theme == "light" else BLUE
    foreground = "#17212b" if theme == "light" else WHITE
    secondary = "#475569" if theme == "light" else MUTED
    card.lines(number, size=15, color=color, weight=700)
    card.y += 6
    card.lines(title, size=20, weight=700, color=foreground)
    card.y += 5
    card.lines(subtitle, size=15, color=secondary)
    height = int(card.y + 12)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(title, quote=True)}">'
        f"<style>text{{font-family:{SANS}}}</style>" + "".join(card.parts) + "</svg>"
    )


def render_mobile_cards(data: dict, context: dict) -> dict[str, str]:
    """Render phone variants from supplied data without file or network access."""
    renderers = {
        "hero": _hero,
        "profile-badges": _profile_badges,
        "intro": _intro,
        "experience": _experience,
        "highlights": _highlights,
        "worked-with": _worked_with,
        "publications": _publications,
        "education": _education,
        "oss": _oss,
        "github": _github,
        "leetcode": _leetcode,
        "certs": _certifications,
        "stack": _stack,
        "ai-stack": _ai_stack,
        "competitive": _competitive,
        "footer": _footer,
    }
    cards = {
        f"{name}-mobile.svg": renderer(data, context)
        for name, renderer in renderers.items()
    }
    cards["oss-merged-mobile.svg"] = _oss_list(data, "merged")
    cards["oss-review-mobile.svg"] = _oss_list(data, "open")
    cards["sample-org-governance-mobile.svg"] = _sample(
        "AWS Organizations governance",
        "A Terraform governance layer on an existing AWS Control Tower landing zone.",
        [
            ("Organize", "Declare the organizational unit hierarchy."),
            ("Govern", "Apply Organizations policies and Control Tower controls."),
            ("Delegate", "Configure delegated administrators for AWS services."),
        ],
    )
    cards["sample-sagemaker-mlops-mobile.svg"] = _sample(
        "SageMaker image classification MLOps",
        "An end-to-end MLOps pipeline, declared in Terraform.",
        [
            (
                "Ingest and train",
                "Event-driven ingestion and SageMaker training pipelines.",
            ),
            (
                "Evaluate and deploy",
                "Quality gates and human-approved model deployment.",
            ),
            ("Monitor and retrain", "Detect drift and trigger the retraining loop."),
        ],
    )
    for key, number, title, subtitle in context.get("headers", []):
        for theme in ("dark", "light"):
            cards[f"header-{key}-{theme}-mobile.svg"] = _header(
                number, title, subtitle, theme
            )
    return cards
