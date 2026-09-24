"""Render the README's custom animated SVGs into assets/svg/."""

# Everything here is self-hosted on purpose: free widget hosts run out of quota
# (github-profile-trophy and the activity graph both answered HTTP 402 on
# 2026-09-23), while an SVG committed to this repo cannot go down.
#
# GitHub serves README images through an <img>, so each SVG must be fully
# self-contained: no scripts, no external fonts or images, CSS and SMIL
# animation only. Icons are fetched from skillicons.dev at render time and
# inlined as <symbol>s with their ids prefixed so they cannot collide.
#
# Live data (LeetCode contest stats) is fetched on every run; if a fetch fails
# the last good values in assets/svg/data.json are reused, so a flaky API never
# blanks the README. Stdlib only, like the other scripts in this folder.
#
# Run: python scripts/render-svgs.py

from __future__ import annotations

import base64
import datetime
import io
import json
import os
import re
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "svg"
DATA_FILE = OUT / "data.json"
README_PATH = ROOT / "README.md"

# Palette matches the portfolio (brand/portfolio-react): warm near-black,
# one blue family, green only for live/ok, amber only for LeetCode.
BG = "#0b1012"
CARD = "#0f171c"
BLUE = "#2563eb"
BLUE_LIGHT = "#60a5fa"
SKY = "#38bdf8"
GREEN = "#22c55e"
AMBER = "#f59e0b"
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
SANS = "'Segoe UI',Inter,-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"

LEETCODE_USER = "sagargupta1610"
DEFAULT_DATA = {
    "leetcode": {
        "badge": "Guardian",
        "rating": 2166,
        "top": 1.11,
        "contests": 107,
        "solved": 1322,
    }
}

ICON_ROWS = [
    # row 1 scrolls left: cloud, devops, languages
    [
        "aws",
        "terraform",
        "docker",
        "kubernetes",
        "githubactions",
        "git",
        "github",
        "ansible",
        "jenkins",
        "gitlab",
        "bash",
        "linux",
        "python",
        "javascript",
        "typescript",
        "cpp",
        "java",
        "cs",
        "r",
        "html",
        "css",
    ],
    # row 2 scrolls right: web, data, ML, tools
    [
        "react",
        "nextjs",
        "redux",
        "tailwind",
        "vite",
        "materialui",
        "nodejs",
        "express",
        "fastapi",
        "graphql",
        "mongodb",
        "mysql",
        "postgres",
        "redis",
        "dynamodb",
        "tensorflow",
        "pytorch",
        "opencv",
        "sklearn",
        "unity",
        "vscode",
        "figma",
        "postman",
    ],
]

HEADERS = [
    ("experience", "01", "Experience", "where I work and what shipped"),
    ("projects", "02", "Featured Projects", "what I have built and shipped"),
    (
        "community",
        "03",
        "Community and Developer Tools",
        "open tooling for Claude Code and MCP",
    ),
    ("opensource", "04", "Open Source", "merged upstream work"),
    ("connect", "05", "Connect With Me", "where to find me"),
    ("stack", "06", "Tech Stack and Tools", "what I work with daily"),
    ("stats", "07", "GitHub Stats", "activity, streaks and contests"),
    ("certs", "08", "Certifications and Badges", "verified on Credly"),
]

# Career: the top rail, oldest first, ending on the current full-time role,
# which then expands into its customer engagements on a second rail.
MILESTONES = [
    ("2021", "MCA, NIT Warangal", "NIMCET AIR 208"),
    ("2023", "Software Dev Intern", "Ikarus-3D, Mohali"),
    ("2024", "ProServe DevOps Intern", "AWS, Hyderabad"),
    ("2024", "DevOps/MLOps Cloud Consultant", "AWS, Hyderabad"),
]
ENGAGEMENTS = [
    ("Oct 2024 to Aug 2025", "State Street", "Terraform module library"),
    ("Jun 2025 to Aug 2025", "MLOps SME Program", "SageMaker pipeline"),
    ("Aug 2025 to Dec 2025", "DTCC", "Terraform modernization"),
    ("Feb 2026 to now", "RWS", "Lead DevOps, landing zone"),
]

# AI tooling strip: (label, simple-icons slug or None for a monogram)
AI_TOOLS = [
    ("Claude Code", "claude"),
    ("Kiro", None),
    ("Codex", "openai"),
    ("Amazon Q", "amazonwebservices"),
    ("Amazon Bedrock", "amazonwebservices"),
    ("MCP", "modelcontextprotocol"),
    ("GitHub Copilot", "githubcopilot"),
    ("Cursor", "cursor"),
    ("Gemini", "googlegemini"),
    ("ChatGPT", "openai"),
]

SVG_CLOSE = "</svg>"
AWS_NAME = "Amazon Web Services"
INDUSTRY_GROUP = "Industry Certifications"
PORTFOLIO_URL = "https://sagargupta.online/portfolio-react/"
ALLOWED_HOSTS = (
    "https://leetcode.com/",
    "https://skillicons.dev/",
    "https://api.github.com/",
    "https://images.credly.com/",
    "https://cdn.jsdelivr.net/",
    "https://raw.githubusercontent.com/Sagargupta16/portfolio-react/",
    "https://komarev.com/",
    "https://www.google.com/s2/favicons",
)


def fetch(
    url: str, body: dict | None = None, timeout: int = 20, token: str | None = None
) -> bytes:
    # https only, and only the hosts this script reads from
    if not url.startswith(ALLOWED_HOSTS):
        raise ValueError(f"refusing to fetch {url}")
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "User-Agent": "Sagargupta16-readme-svgs",
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
    }
    if token:
        headers["Authorization"] = f"bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    # scheme and host were checked against ALLOWED_HOSTS above
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return resp.read()


LEETCODE_QUERY = (
    "query($u:String!){userContestRanking(username:$u){rating topPercentage "
    "attendedContestsCount badge{name}} userContestRankingHistory(username:$u)"
    "{attended rating} allQuestionsCount{difficulty count} matchedUser(username:$u)"
    "{submitStats{acSubmissionNum{difficulty count}}}}"
)


def fetch_leetcode(previous: dict) -> dict:
    raw = fetch(
        "https://leetcode.com/graphql",
        {"query": LEETCODE_QUERY, "variables": {"u": LEETCODE_USER}},
    )
    d = json.loads(raw)["data"]
    rank = d["userContestRanking"]
    solved = {
        x["difficulty"]: x["count"]
        for x in d["matchedUser"]["submitStats"]["acSubmissionNum"]
    }
    totals = {x["difficulty"]: x["count"] for x in d["allQuestionsCount"]}
    history = [
        round(x["rating"]) for x in d["userContestRankingHistory"] if x["attended"]
    ]
    return {
        "badge": (rank.get("badge") or {}).get("name") or previous["badge"],
        "rating": round(rank["rating"]),
        "top": round(rank["topPercentage"], 2),
        "contests": rank["attendedContestsCount"],
        "solved": solved["All"],
        "by_difficulty": {
            k: [solved.get(k, 0), totals.get(k, 0)] for k in ("Easy", "Medium", "Hard")
        },
        "history": history,
    }


GITHUB_QUERY = (
    '{user(login:"Sagargupta16"){followers{totalCount} '
    "repositories(ownerAffiliations:OWNER,isFork:false,first:100){totalCount nodes{name stargazerCount "
    "languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}} "
    "contributionsCollection{totalCommitContributions totalPullRequestContributions "
    "totalPullRequestReviewContributions totalIssueContributions contributionCalendar"
    "{totalContributions weeks{contributionDays{contributionCount date}}}}}}"
)


def streaks(days: list[int]) -> tuple[int, int]:
    """Current and longest run of days with at least one contribution."""
    longest = run = 0
    for count in days:
        run = run + 1 if count else 0
        longest = max(longest, run)
    current = 0
    # today may still be empty; a streak is only broken by an empty yesterday
    tail = days[:-1] if days and days[-1] == 0 else days
    for count in reversed(tail):
        if not count:
            break
        current += 1
    return current, longest


def fetch_github() -> dict | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("no GITHUB_TOKEN, keeping the last github stats")
        return None
    raw = fetch("https://api.github.com/graphql", {"query": GITHUB_QUERY}, token=token)
    u = json.loads(raw)["data"]["user"]
    repos = u["repositories"]["nodes"]
    langs: dict[str, list] = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            entry = langs.setdefault(name, [0, edge["node"]["color"] or "#8b949e"])
            entry[0] += edge["size"]
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(size for size, _ in langs.values()) or 1
    cc = u["contributionsCollection"]
    days = [
        day["contributionCount"]
        for week in cc["contributionCalendar"]["weeks"]
        for day in week["contributionDays"]
    ]
    current, longest = streaks(days)
    return {
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "prs": cc["totalPullRequestContributions"],
        "reviews": cc["totalPullRequestReviewContributions"],
        "issues": cc["totalIssueContributions"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "repo_stars": {r["name"]: r["stargazerCount"] for r in repos},
        "followers": u["followers"]["totalCount"],
        "repos": u["repositories"]["totalCount"],
        "streak": current,
        "longest": longest,
        "active_days": sum(1 for c in days if c),
        "calendar": [
            [day["contributionCount"] for day in week["contributionDays"]]
            for week in cc["contributionCalendar"]["weeks"]
        ],
        "languages": [
            [name, round(size * 100 / total, 1), color] for name, (size, color) in top
        ],
    }


VIEWS_URL = "https://komarev.com/ghpvc/?username=sagargupta16"


def fetch_views() -> int:
    """Return the profile view count, read from the counter image komarev serves."""
    counts = re.findall(r">(\d[\d,]*)</text>", fetch(VIEWS_URL).decode())
    return int(counts[-1].replace(",", ""))


def load_data() -> dict:
    data = json.loads(json.dumps(DEFAULT_DATA))
    if DATA_FILE.exists():
        data.update(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    try:
        data["views"] = fetch_views()
    except Exception as exc:  # keep the last good count
        print(f"views fetch failed, reusing cached count: {exc}")
    try:
        data["leetcode"] = fetch_leetcode(data["leetcode"])
    except Exception as exc:  # keep the last good values
        print(f"leetcode fetch failed, reusing cached values: {exc}")
    try:
        github = fetch_github()
        if github:
            data["github"] = github
    except Exception as exc:  # keep the last good values
        print(f"github fetch failed, reusing cached values: {exc}")
    return data


def svg_open(w: int, h: int, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(label)}">'
    )


# ---------------------------------------------------------------- terminal hero


def typed_line(
    idx: int,
    x: int,
    y: int,
    text: str,
    begin: float,
    color: str,
    char_w: float = 8.4,
    cps: float = 38,
) -> tuple[str, float]:
    """A line that types itself out, character by character, then holds."""
    n = len(text)
    dur = max(n / cps, 0.2)
    widths = ";".join(f"{i * char_w:.1f}" for i in range(n + 1))
    clip = (
        f'<clipPath id="t{idx}"><rect x="{x}" y="{y - 14}" width="0" height="20">'
        f'<animate attributeName="width" values="{widths}" dur="{dur:.2f}s" begin="{begin:.2f}s" '
        f'calcMode="discrete" fill="freeze"/></rect></clipPath>'
    )
    line = f'<text x="{x}" y="{y}" fill="{color}" clip-path="url(#t{idx})">{escape(text)}</text>'
    return clip + line, begin + dur


def shown_line(x: int, y: int, text: str, begin: float, color: str) -> str:
    """An output line: appears whole once its command has finished typing."""
    return (
        f'<text x="{x}" y="{y}" fill="{color}" opacity="0">{escape(text)}'
        f'<set attributeName="opacity" to="1" begin="{begin:.2f}s" fill="freeze"/></text>'
    )


def render_terminal(data: dict) -> str:
    lc = data["leetcode"]
    samples = [
        s["url"].split("github.com/", 1)[1]
        for s in (data.get("portfolio") or {}).get("samples", [])
    ] or [
        "aws-samples/sample-aws-terraform-org-governance",
        "aws-samples/sample-sagemaker-image-classification-mlops",
    ]
    w, h = 840, 292 + 24 * max(len(samples) - 2, 0)
    prompt = "sagar@aws:~$ "
    script = [
        (
            "whoami",
            [
                "Sagar Gupta  |  Cloud Consultant, AWS Professional Services (DevOps / MLOps)"
            ],
        ),
        (
            "ls ~/published",
            samples,
        ),
        (
            f"leetcode --profile {LEETCODE_USER}",
            [
                f"{lc['badge']}  |  rating {lc['rating']}  |  top {lc['top']}%  |  "
                f"{lc['contests']} contests  |  {lc['solved']} solved"
            ],
        ),
    ]
    parts = [
        svg_open(w, h, "Terminal: whoami, published AWS samples, LeetCode profile"),
        f"<style>text{{font-family:{MONO};font-size:14px}}"
        ".cur{animation:blink 1.05s steps(1) infinite}"
        "@keyframes blink{50%{opacity:0}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" '
        'stroke="rgba(255,255,255,0.10)"/>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="36" rx="14" fill="{CARD}"/>',
        f'<rect x="0.5" y="24" width="{w - 1}" height="13" fill="{CARD}"/>',
        '<line x1="0" y1="37" x2="840" y2="37" stroke="rgba(255,255,255,0.08)"/>',
    ]
    for i, cx in enumerate((24, 44, 64)):
        fill = GREEN if i == 2 else "rgba(255,255,255,0.22)"
        parts.append(f'<circle cx="{cx}" cy="19" r="5.5" fill="{fill}"/>')
    parts.append(
        '<text x="420" y="24" text-anchor="middle" fill="rgba(255,255,255,0.45)" '
        'style="font-size:12px">sagar@aws: ~</text>'
    )
    y, t, idx = 70, 0.6, 0
    for cmd, outputs in script:
        parts.append(
            f'<text x="24" y="{y}" fill="{GREEN}" opacity="0">{escape(prompt)}'
            f'<set attributeName="opacity" to="1" begin="{t:.2f}s" fill="freeze"/></text>'
        )
        line, t = typed_line(
            idx, 24 + int(len(prompt) * 8.4), y, cmd, t + 0.15, "#e5e7eb"
        )
        parts.append(line)
        idx += 1
        t += 0.25
        for out in outputs:
            y += 24
            if cmd.startswith("leetcode"):
                color = AMBER
            elif "aws-samples" in out:
                color = SKY
            else:
                color = "rgba(255,255,255,0.72)"
            parts.append(shown_line(40, y, out, t, color))
            t += 0.12
        y += 34
        t += 0.45
    parts.append(
        f'<text x="24" y="{y}" fill="{GREEN}" opacity="0">{escape(prompt)}'
        f'<set attributeName="opacity" to="1" begin="{t:.2f}s" fill="freeze"/></text>'
    )
    cx = 24 + int(len(prompt) * 8.4)
    parts.append(
        f'<g opacity="0"><set attributeName="opacity" to="1" begin="{t:.2f}s" fill="freeze"/>'
        f'<rect class="cur" x="{cx}" y="{y - 13}" width="9" height="17" fill="{BLUE_LIGHT}"/></g>'
    )
    parts.append(SVG_CLOSE)
    return "".join(parts)


# ---------------------------------------------------------------- sample cards


def anim_opacity(values: str, key_times: str, dur: int = 6) -> str:
    return (
        f'<animate attributeName="opacity" values="{values}" keyTimes="{key_times}" '
        f'dur="{dur}s" repeatCount="indefinite"/>'
    )


def card_frame(w: int, h: int, title: str, sub: str, label: str) -> list[str]:
    return [
        svg_open(w, h, label),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.4px}}"
        f".t{{font-family:{SANS};font-weight:700}}</style>",
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="0.6" y2="1">'
        f'<stop offset="0" stop-color="#0e1a24"/><stop offset="0.6" stop-color="{BG}"/></linearGradient>'
        f'<radialGradient id="glow" cx="0.5" cy="0.32" r="0.55"><stop offset="0" stop-color="{BLUE}" stop-opacity="0.16"/>'
        f'<stop offset="1" stop-color="{BLUE}" stop-opacity="0"/></radialGradient></defs>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="16" fill="url(#bg)" stroke="rgba(255,255,255,0.08)"/>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="16" fill="url(#glow)"/>',
        f'<line x1="0" y1="{h - 62}" x2="{w}" y2="{h - 62}" stroke="rgba(255,255,255,0.07)"/>',
        f'<text class="t" x="20" y="{h - 34}" fill="#f3f4f6" font-size="16">{escape(title)}</text>',
        f'<text class="m" x="20" y="{h - 14}" fill="{BLUE_LIGHT}" font-size="9">{escape(sub)}</text>',
    ]


def box(
    x: float, y: float, w: float, h: float, stroke: str, fill: str, extra: str = ""
) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}" stroke="{stroke}" stroke-width="1.2">{extra}</rect>'


def render_org_card() -> str:
    """Policies flowing down an OU tree: the GovernanceScene cover, README-sized."""
    w, h = 410, 262
    parts = card_frame(
        w,
        h,
        "AWS Organizations Governance",
        "AWS SAMPLES  |  TERRAFORM  |  CONTROL TOWER",
        "Animated diagram: SCP and RCP policies attaching down an AWS Organizations OU tree",
    )
    node_h = 20
    nodes = {
        "mgmt": (205, 30, 76),
        "root": (205, 76, 44),
        "sec": (80, 124, 66),
        "wl": (205, 124, 66),
        "sbx": (330, 124, 66),
        "prod": (160, 170, 52),
        "dev": (250, 170, 52),
    }
    edges = [
        ("mgmt", "root"),
        ("root", "sec"),
        ("root", "wl"),
        ("root", "sbx"),
        ("wl", "prod"),
        ("wl", "dev"),
    ]
    for a, b in edges:
        ax, ay, _ = nodes[a]
        bx, by, _ = nodes[b]
        mid = (ay + node_h / 2 + by - node_h / 2) / 2
        parts.append(
            f'<path d="M{ax} {ay + node_h / 2} V{mid} H{bx} V{by - node_h / 2}" fill="none" '
            'stroke="rgba(255,255,255,0.16)" stroke-width="1.2"/>'
        )
    mx, my, mw = nodes["mgmt"]
    sx, sy, sw = nodes["sec"]
    parts.append(
        f'<path d="M{mx - mw / 2} {my} H{sx} V{sy - node_h / 2}" fill="none" stroke="{BLUE_LIGHT}" '
        f'stroke-width="1.2" stroke-dasharray="4 4" opacity="0">{anim_opacity("0;0;1;1;0", "0;0.68;0.76;0.92;1")}</path>'
    )
    parts.append(
        f'<text class="m" x="{sx - sw / 2}" y="{my + 20}" fill="{BLUE_LIGHT}" font-size="8" opacity="0">DELEGATED'
        f"{anim_opacity('0;0;1;1;0', '0;0.68;0.76;0.92;1')}</text>"
    )
    for key, (x, y, bw) in nodes.items():
        if key == "mgmt":
            parts.append(
                box(x - bw / 2, y - node_h / 2, bw, node_h, f"{BLUE}cc", f"{BLUE}22")
            )
            parts.append(
                f'<text class="m" x="{x}" y="{y + 3}" text-anchor="middle" fill="{BLUE_LIGHT}" font-size="8">MGMT</text>'
            )
        else:
            parts.append(
                box(
                    x - bw / 2,
                    y - node_h / 2,
                    bw,
                    node_h,
                    "rgba(255,255,255,0.12)",
                    "rgba(255,255,255,0.03)",
                )
            )
    lit = {
        "wl": "0;0.24;0.3;0.92;1",
        "prod": "0;0.32;0.38;0.92;1",
        "dev": "0;0.38;0.44;0.92;1",
        "sbx": "0;0.49;0.55;0.92;1",
    }
    for key, times in lit.items():
        x, y, bw = nodes[key]
        parts.append(
            box(
                x - bw / 2,
                y - node_h / 2,
                bw,
                node_h,
                BLUE_LIGHT,
                f"{BLUE}30",
                f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="{times}" dur="6s" repeatCount="indefinite"/>',
            ).replace("<rect ", '<rect opacity="0" ', 1)
        )
    for key, delay in (("prod", 0), ("dev", 0.03)):
        x, y, bw = nodes[key]
        t0 = 0.55 + delay
        parts.append(
            f'<circle cx="{x + bw / 2 - 8}" cy="{y}" r="3.2" fill="{GREEN}" opacity="0">'
            f"{anim_opacity('0;0;1;1;0', f'0;{t0:.2f};{t0 + 0.07:.2f};0.92;1')}</circle>"
        )

    def chip(text: str, pts: list[tuple[float, float]], times: str) -> str:
        values = ";".join(f"{x} {y}" for x, y in pts)
        return (
            f'<g opacity="0"><animateTransform attributeName="transform" type="translate" values="{values}" '
            f'keyTimes="{times}" dur="6s" repeatCount="indefinite"/>'
            f"{anim_opacity('0;1;1;1;1;0', times)}"
            f'<rect x="-17" y="-8" width="34" height="16" rx="4" fill="{BG}" stroke="{BLUE_LIGHT}" stroke-width="1.2"/>'
            f'<text class="m" x="0" y="3" text-anchor="middle" fill="{BLUE_LIGHT}" font-size="8">{text}</text></g>'
        )

    wl, sbx = nodes["wl"], nodes["sbx"]
    rx, ry, rw = nodes["root"]
    # chips start beside the MGMT box, pass beside the root, then park beside their OU
    start = (mx + mw / 2 + 22, my)
    at_root = (rx + rw / 2 + 22, ry)
    scp_hold = (wl[0] + wl[2] / 2 + 20, wl[1])
    rcp_hold = (sbx[0], sbx[1] + node_h / 2 + 14)
    parts.append(
        chip(
            "SCP",
            [start, start, at_root, scp_hold, scp_hold, scp_hold],
            "0;0.05;0.15;0.25;0.92;1",
        )
    )
    parts.append(
        chip(
            "RCP",
            [start, start, at_root, rcp_hold, rcp_hold, rcp_hold],
            "0;0.3;0.4;0.5;0.92;1",
        )
    )
    parts.append(SVG_CLOSE)
    return "".join(parts)


def render_mlops_card() -> str:
    """Train, gate, approve, deploy, drift back to retrain: the MLOps sample's loop."""
    w, h = 410, 262
    parts = card_frame(
        w,
        h,
        "SageMaker Image Classification MLOps",
        "AWS SAMPLES  |  TERRAFORM  |  SAGEMAKER",
        "Animated diagram: SageMaker pipeline trains, passes a quality gate, deploys, and retrains on drift",
    )
    stages = [
        ("DATA", 46),
        ("TRAIN", 128),
        ("GATE", 210),
        ("DEPLOY", 292),
        ("SERVE", 366),
    ]
    y = 92
    parts.append(
        f'<path d="M46 {y} H366" stroke="rgba(255,255,255,0.14)" stroke-width="1.2"/>'
    )
    drift = f"M366 {y + 22} C366 170, 128 170, 128 {y + 22}"
    parts.append(
        f'<path d="{drift}" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="1.2" stroke-dasharray="4 4"/>'
    )
    parts.append(
        f'<path d="{drift}" fill="none" stroke="{AMBER}" stroke-width="1.4" stroke-dasharray="4 4" opacity="0">'
        f"{anim_opacity('0;0;1;1;0', '0;0.66;0.72;0.9;1')}</path>"
    )
    parts.append(
        f'<text class="m" x="247" y="176" text-anchor="middle" fill="{AMBER}" font-size="8" opacity="0">DRIFT'
        f"{anim_opacity('0;0;1;1;0', '0;0.66;0.72;0.9;1')}</text>"
    )
    for name, x in stages:
        bw = 58 if name != "DEPLOY" else 62
        stroke = (
            f"{BLUE}cc" if name in ("TRAIN", "DEPLOY") else "rgba(255,255,255,0.14)"
        )
        fill = f"{BLUE}1f" if name in ("TRAIN", "DEPLOY") else "rgba(255,255,255,0.03)"
        parts.append(box(x - bw / 2, y - 16, bw, 32, stroke, fill))
        parts.append(
            f'<text class="m" x="{x}" y="{y + 3}" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="8">{name}</text>'
        )
    # quality gate flashes green when the model clears it
    parts.append(
        box(210 - 29, y - 16, 58, 32, GREEN, f"{GREEN}22", "")
        .replace("<rect ", '<rect opacity="0" ', 1)
        .replace(
            "</rect>", f"{anim_opacity('0;0;1;1;0', '0;0.3;0.34;0.46;0.52')}</rect>"
        )
    )
    # three architectures train in parallel under TRAIN
    for i, dx in enumerate((-16, 0, 16)):
        parts.append(
            f'<rect x="{128 + dx - 5}" y="{y + 26}" width="10" height="4" rx="2" fill="{BLUE_LIGHT}" opacity="0.25">'
            f'<animate attributeName="opacity" values="0.25;0.9;0.25" dur="1.2s" begin="{i * 0.2}s" repeatCount="indefinite"/></rect>'
        )
    # the model artefact travelling the pipeline, then the drift arc back to TRAIN
    path = f"M46 {y} H366"
    parts.append(
        f'<circle r="4" fill="#f3f4f6" opacity="0">'
        f'<animateMotion dur="6s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.08;0.62;1" '
        f'calcMode="linear" path="{path}"/>{anim_opacity("0;1;1;0;0", "0;0.08;0.62;0.64;1")}</circle>'
    )
    parts.append(
        f'<circle r="3.5" fill="{AMBER}" opacity="0">'
        f'<animateMotion dur="6s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.7;0.9;1" '
        f'calcMode="linear" path="{drift}"/>{anim_opacity("0;0;1;1;0", "0;0.69;0.71;0.9;0.92")}</circle>'
    )
    parts.append(
        f'<circle cx="366" cy="{y - 24}" r="3" fill="{GREEN}">'
        '<animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/></circle>'
    )
    parts.append(SVG_CLOSE)
    return "".join(parts)


# ---------------------------------------------------------------- section headers


def render_header(num: str, title: str, sub: str, theme: str) -> str:
    w, h = 840, 64
    ink = "#f3f4f6" if theme == "dark" else "#0b1012"
    dim = "rgba(255,255,255,0.45)" if theme == "dark" else "rgba(11,16,18,0.55)"
    rule = "rgba(255,255,255,0.10)" if theme == "dark" else "rgba(11,16,18,0.12)"
    return "".join(
        [
            svg_open(w, h, title),
            f'<defs><linearGradient id="sweep" x1="0" x2="1"><stop offset="0" stop-color="{SKY}" stop-opacity="0"/>'
            f'<stop offset="0.5" stop-color="{BLUE_LIGHT}"/><stop offset="1" stop-color="{SKY}" stop-opacity="0"/></linearGradient></defs>',
            f'<rect x="0" y="12" width="4" height="30" rx="2" fill="{BLUE}"/>',
            f'<text x="18" y="24" fill="{BLUE_LIGHT}" font-family="{MONO}" font-size="11" font-weight="700" letter-spacing="2">{num}  /  {escape(sub.upper())}</text>',
            f'<text x="18" y="46" fill="{ink}" font-family="{SANS}" font-size="24" font-weight="700">{escape(title)}</text>',
            f'<line x1="0" y1="{h - 4}" x2="{w}" y2="{h - 4}" stroke="{rule}" stroke-width="1"/>',
            f'<rect x="-160" y="{h - 5}" width="160" height="2" fill="url(#sweep)">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;1000 0" dur="4.5s" repeatCount="indefinite"/></rect>',
            f'<circle cx="{w - 8}" cy="30" r="3" fill="{dim}"/>',
            SVG_CLOSE,
        ]
    )


# ---------------------------------------------------------------- tech strip


def fetch_icon(name: str) -> str | None:
    try:
        raw = fetch(f"https://skillicons.dev/icons?i={name}").decode()
    except Exception as exc:
        print(f"icon {name} failed: {exc}")
        return None
    inner = raw.find("<svg", raw.find("<svg") + 1)
    end = raw.rfind(SVG_CLOSE, 0, raw.rfind(SVG_CLOSE))
    if inner == -1 or end == -1:
        return None
    body = raw[inner : end + len(SVG_CLOSE)]
    body = re.sub(r'\sid="([^"]+)"', lambda m: f' id="{name}-{m.group(1)}"', body)
    body = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{name}-{m.group(1)})", body)
    body = re.sub(r'href="#([^"]+)"', lambda m: f'href="#{name}-{m.group(1)}"', body)
    inner_body = body[body.find(">") + 1 : body.rfind(SVG_CLOSE)]
    return f'<symbol id="i-{name}" viewBox="0 0 256 256">{inner_body}</symbol>'


def render_stack() -> str | None:
    size, gap = 44, 14
    step = size + gap
    w, h = 840, 150
    symbols = []
    for row in ICON_ROWS:
        for name in row:
            sym = fetch_icon(name)
            if sym is None:
                return None
            symbols.append(sym)
    parts = [
        svg_open(w, h, "Tech stack: " + ", ".join(n for row in ICON_ROWS for n in row)),
        f"<defs>{''.join(symbols)}"
        + f'<linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="{BG}"/>'
        f'<stop offset="0.08" stop-color="{BG}" stop-opacity="0"/><stop offset="0.92" stop-color="{BG}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{BG}"/></linearGradient>'
        f'<clipPath id="win"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14"/></clipPath></defs>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        '<g clip-path="url(#win)">',
    ]
    for r, row in enumerate(ICON_ROWS):
        span = len(row) * step
        y = 22 + r * (size + 18)
        uses = "".join(
            f'<use href="#i-{n}" x="{i * step}" y="{y}" width="{size}" height="{size}"/>'
            for i, n in enumerate(row + row)
        )
        values = f"0 0;{-span} 0" if r == 0 else f"{-span} 0;0 0"
        parts.append(
            f'<g><animateTransform attributeName="transform" type="translate" values="{values}" '
            f'dur="{len(row) * 1.6:.1f}s" repeatCount="indefinite"/>{uses}</g>'
        )
    parts.append(
        f'</g><rect x="0" y="0" width="{w}" height="{h}" rx="14" fill="url(#fade)"/></svg>'
    )
    return "".join(parts)


# ---------------------------------------------------------------- divider


def render_divider() -> str:
    w, h = 840, 14
    return "".join(
        [
            svg_open(w, h, "divider"),
            f'<defs><linearGradient id="pulse" x1="0" x2="1"><stop offset="0" stop-color="{BLUE}" stop-opacity="0"/>'
            f'<stop offset="0.5" stop-color="{BLUE_LIGHT}"/><stop offset="1" stop-color="{BLUE}" stop-opacity="0"/></linearGradient></defs>',
            f'<line x1="0" y1="7" x2="{w}" y2="7" stroke="rgba(127,127,127,0.28)" stroke-width="1"/>',
            f'<circle cx="{w / 2}" cy="7" r="2.5" fill="{BLUE_LIGHT}"/>',
            '<rect x="-220" y="6" width="220" height="2" fill="url(#pulse)">'
            '<animateTransform attributeName="transform" type="translate" values="0 0;1060 0" dur="3.6s" repeatCount="indefinite"/></rect>',
            SVG_CLOSE,
        ]
    )


# ---------------------------------------------------------------- career timeline


def _rail(x1: float, x2: float, y: float, begin: float, dur: float) -> str:
    length = x2 - x1
    return (
        f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="rgba(255,255,255,0.10)" stroke-width="2"/>'
        f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{BLUE}" stroke-width="2" '
        f'stroke-dasharray="{length}" stroke-dashoffset="{length}">'
        f'<animate attributeName="stroke-dashoffset" from="{length}" to="0" dur="{dur}s" begin="{begin:.2f}s" fill="freeze"/></line>'
    )


def _node(x: float, y: float, at: float, color: str, ring: bool = False) -> str:
    out = ""
    if ring:
        out += (
            f'<circle class="now" cx="{x}" cy="{y}" r="7" fill="none" stroke="{color}" stroke-width="1.5" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{at:.2f}s" fill="freeze"/></circle>'
        )
    return out + (
        f'<circle cx="{x}" cy="{y}" r="6" fill="{BG}" stroke="{color}" stroke-width="2" opacity="0.25">'
        f'<animate attributeName="opacity" to="1" begin="{at:.2f}s" dur="0.3s" fill="freeze"/></circle>'
        f'<circle cx="{x}" cy="{y}" r="2.6" fill="{color}" opacity="0">'
        f'<animate attributeName="opacity" to="1" begin="{at:.2f}s" dur="0.3s" fill="freeze"/></circle>'
    )


def _fade_group(at: float, body: str) -> str:
    return (
        f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{at:.2f}s" dur="0.4s" fill="freeze"/>'
        f"{body}</g>"
    )


def render_experience(data: dict) -> str:
    """Top rail to the current role, which then expands into its customer engagements."""
    pf = data.get("portfolio") or {}
    engagements = [
        (e["when"], e["client"], e["tagline"]) for e in _customers(pf)
    ] or ENGAGEMENTS
    w, h = 840, 330
    left, right, top_y = 96, 690, 84
    step = (right - left) / (len(MILESTONES) - 1)
    draw = 2.4
    parts = [
        svg_open(
            w,
            h,
            "Career: "
            + ", ".join(f"{y} {a}" for y, a, _ in MILESTONES)
            + "; engagements: "
            + ", ".join(e[1] for e in engagements),
        ),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.4px}}"
        f".t{{font-family:{SANS};font-weight:700}}"
        ".now{animation:ring 2.2s ease-out infinite;transform-origin:center;transform-box:fill-box}"
        "@keyframes ring{0%{opacity:0.9;transform:scale(1)}100%{opacity:0;transform:scale(2.6)}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="30" fill="{BLUE_LIGHT}" font-size="10">CAREER</text>',
        _rail(left, right, top_y, 0.3, draw),
    ]
    last = len(MILESTONES) - 1
    for i, (year, role, where) in enumerate(MILESTONES):
        x = left + i * step
        at = 0.3 + draw * i / last
        current = i == last
        color = GREEN if current else BLUE_LIGHT
        label = f"{year}  FULL TIME" if current else year
        parts.append(_node(x, top_y, at, color, ring=current))
        parts.append(
            _fade_group(
                at,
                (
                    f'<text class="m" x="{x}" y="{top_y - 22}" text-anchor="middle" fill="{color}" font-size="10">{label}</text>'
                    f'<text class="t" x="{x}" y="{top_y + 30}" text-anchor="middle" fill="#f3f4f6" font-size="13">{escape(role)}</text>'
                    f'<text class="m" x="{x}" y="{top_y + 49}" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-size="9">{escape(where.upper())}</text>'
                ),
            )
        )
    # the current role opens into its engagements: a drop, then a bracket over the second rail
    open_at = 0.3 + draw + 0.2
    sub_y, sub_left, sub_right = 250, 120, 720
    bracket_y = 176
    drop = f"M{right} {top_y + 58} V{bracket_y} H{sub_left} M{right} {bracket_y} H{sub_right}"
    parts.append(
        f'<path d="{drop}" fill="none" stroke="{GREEN}88" stroke-width="1.4" stroke-dasharray="3 4" opacity="0">'
        f'<animate attributeName="opacity" to="1" begin="{open_at:.2f}s" dur="0.4s" fill="freeze"/></path>'
    )
    parts.append(
        _fade_group(
            open_at,
            (
                f'<text class="m" x="{sub_left}" y="{bracket_y - 8}" fill="{GREEN}" font-size="9">CUSTOMER ENGAGEMENTS</text>'
            ),
        )
    )
    sub_draw = 1.8
    parts.append(_rail(sub_left, sub_right, sub_y, open_at + 0.3, sub_draw))
    sub_step = (sub_right - sub_left) / max(len(engagements) - 1, 1)
    sub_last = max(len(engagements) - 1, 1)
    for i, (when, client, what) in enumerate(engagements):
        x = sub_left + i * sub_step
        at = open_at + 0.3 + sub_draw * i / sub_last
        current = i == sub_last
        color = GREEN if current else SKY
        parts.append(
            f'<line x1="{x}" y1="{bracket_y}" x2="{x}" y2="{sub_y - 8}" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>'
        )
        parts.append(_node(x, sub_y, at, color, ring=current))
        when_label = when.upper()
        parts.append(
            _fade_group(
                at,
                (
                    f'<text class="m" x="{x}" y="{sub_y - 16}" text-anchor="middle" fill="{color}" font-size="8.5">{escape(when_label)}</text>'
                    f'<text class="t" x="{x}" y="{sub_y + 28}" text-anchor="middle" fill="#f3f4f6" font-size="13">{escape(client)}</text>'
                    f'<text class="m" x="{x}" y="{sub_y + 46}" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-size="8.5">{escape(what.upper())}</text>'
                ),
            )
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


# ---------------------------------------------------------------- highlights


def render_highlights(data: dict) -> str:
    lc = data["leetcode"]
    pf = data.get("portfolio") or {}
    samples = len(pf.get("samples", [])) or 2
    tfc = next(
        (
            m.group(1)
            for a in pf.get("achievements", [])
            if (m := re.match(r"(\d+)x TFC", a["title"]))
        ),
        "5",
    )
    merged = sum(1 for e in pf.get("oss", []) if e.get("status") == "merged")
    tiles = [
        ("10/10", "average client CSAT", GREEN),
        ("5/5", "average Pulse feedback", GREEN),
        (str(samples), "published AWS samples", SKY),
        (f"{tfc}x", "TFC ambassador", SKY),
        (str(merged), "merged upstream contributions", BLUE_LIGHT),
        (
            str(len(credly_badges(INDUSTRY_GROUP))),
            "industry certifications",
            BLUE_LIGHT,
        ),
        (lc["badge"], f"LeetCode, top {lc['top']}%", AMBER),
        (f"{lc['solved']:,}", "LeetCode problems solved", AMBER),
    ]
    w, h = 840, 212
    cols, gap, pad = 4, 12, 16
    tw = (w - 2 * pad - (cols - 1) * gap) / cols
    th = 80
    parts = [
        svg_open(w, h, "Highlights: " + "; ".join(f"{v} {k}" for v, k, _ in tiles)),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}"
        f".v{{font-family:{SANS};font-weight:800}}</style>",
    ]
    for i, (value, label, accent) in enumerate(tiles):
        col, row = i % cols, i // cols
        x = pad + col * (tw + gap)
        y = pad + row * (th + gap)
        begin = 0.2 + i * 0.12
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{begin:.2f}s" dur="0.45s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 10" to="0 0" begin="{begin:.2f}s" dur="0.45s" fill="freeze"/>'
            f'<rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="12" fill="{CARD}" stroke="rgba(255,255,255,0.08)"/>'
            f'<rect x="{x}" y="{y + 18}" width="3" height="26" rx="1.5" fill="{accent}"/>'
            f'<text class="v" x="{x + 18}" y="{y + 42}" fill="#f3f4f6" font-size="26">{escape(value)}</text>'
            f'<text class="m" x="{x + 18}" y="{y + 64}" fill="rgba(255,255,255,0.5)" font-size="8.5">{escape(label.upper())}</text></g>'
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


# ---------------------------------------------------------------- hero and footer

HERO_LINES = [
    "Cloud Consultant, AWS Professional Services",
    "DevOps and MLOps on AWS, in Terraform",
    "Building AI agents and MCP tooling",
    "Full stack developer, NIT Warangal alumnus",
]


def _rotating(
    lines: list[str],
    x: float,
    y: float,
    cls: str,
    size: int,
    color: str,
    slot: float = 3.0,
) -> str:
    """Lines that take turns: each slides in, holds, and fades before the next."""
    n = len(lines)
    dur = slot * n
    out = []
    for i, text in enumerate(lines):
        a = i / n
        b = a + 0.04
        c = a + 1 / n - 0.04
        d = a + 1 / n
        times = sorted({0.0, round(a, 3), round(b, 3), round(c, 3), round(d, 3), 1.0})
        values = ["1" if round(b, 3) <= t <= round(c, 3) else "0" for t in times]
        out.append(
            f'<text class="{cls}" x="{x}" y="{y}" fill="{color}" font-size="{size}" opacity="0">{escape(text)}'
            f'<animate attributeName="opacity" values="{";".join(values)}" keyTimes="{";".join(f"{t:g}" for t in times)}" '
            f'dur="{dur}s" repeatCount="indefinite"/></text>'
        )
    return "".join(out)


def render_hero(data: dict) -> str:
    lc = data["leetcode"]
    w, h = 840, 250
    nodes = [
        (620, 70, "AWS"),
        (730, 60, "TF"),
        (790, 140, "K8S"),
        (690, 180, "ML"),
        (590, 160, "CI"),
        (700, 118, "MCP"),
    ]
    links = [(0, 5), (1, 5), (2, 5), (3, 5), (4, 5), (0, 1), (2, 3), (3, 4)]
    parts = [
        svg_open(
            w,
            h,
            f"Sagar Gupta. Cloud Consultant at AWS Professional Services. LeetCode {lc['badge']}.",
        ),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:2px}}"
        f".n{{font-family:{SANS};font-weight:800;letter-spacing:-1px}}.s{{font-family:{SANS};font-weight:600}}</style>",
        '<defs><pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">'
        '<path d="M24 0H0V24" fill="none" stroke="rgba(255,255,255,0.035)" stroke-width="1"/></pattern>'
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0e1a24"/><stop offset="0.7" stop-color="{BG}"/></linearGradient>'
        f'<linearGradient id="scan" x1="0" x2="1"><stop offset="0" stop-color="{SKY}" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="{SKY}" stop-opacity="0.10"/><stop offset="1" stop-color="{SKY}" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="card"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="18"/></clipPath></defs>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="18" fill="url(#bg)" stroke="rgba(255,255,255,0.09)"/>',
        f'<g clip-path="url(#card)"><rect width="{w}" height="{h}" fill="url(#grid)"/>'
        f'<rect x="-200" y="0" width="200" height="{h}" fill="url(#scan)">'
        '<animateTransform attributeName="transform" type="translate" values="0 0;1240 0" dur="7s" repeatCount="indefinite"/></rect></g>',
        f'<text class="m" x="44" y="62" fill="{BLUE_LIGHT}" font-size="11">HI, I AM</text>',
        '<text class="n" x="40" y="118" fill="#f8fafc" font-size="58">Sagar Gupta</text>',
        _rotating(HERO_LINES, 44, 152, "s", 18, "rgba(255,255,255,0.78)"),
        f'<rect x="44" y="176" width="236" height="28" rx="14" fill="{GREEN}14" stroke="{GREEN}55"/>',
        f'<circle cx="62" cy="190" r="4" fill="{GREEN}"><animate attributeName="opacity" values="1;0.35;1" dur="1.8s" repeatCount="indefinite"/></circle>',
        f'<text class="m" x="74" y="194" fill="{GREEN}" font-size="10" style="letter-spacing:1px">BUILDING CLOUD AT AWS</text>',
        '<text class="m" x="296" y="194" fill="rgba(255,255,255,0.45)" font-size="10" style="letter-spacing:1px">HYDERABAD, INDIA</text>',
    ]
    for a, b in links:
        x1, y1, _ = nodes[a]
        x2, y2, _ = nodes[b]
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>'
        )
    for i, (a, b) in enumerate(links[:5]):
        x1, y1, _ = nodes[a]
        x2, y2, _ = nodes[b]
        parts.append(
            f'<circle r="2.6" fill="{SKY}"><animateMotion dur="2.4s" begin="{i * 0.45:.2f}s" repeatCount="indefinite" path="M{x1} {y1} L{x2} {y2}"/></circle>'
        )
    for i, (x, y, label) in enumerate(nodes):
        hub = label == "MCP"
        r = 22 if hub else 17
        stroke = f"{BLUE}dd" if hub else "rgba(255,255,255,0.16)"
        fill = f"{BLUE}26" if hub else CARD
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.3">'
            f'<animate attributeName="r" values="{r};{r + 1.5};{r}" dur="3s" begin="{i * 0.4:.1f}s" repeatCount="indefinite"/></circle>'
            f'<text class="m" x="{x}" y="{y + 3.5}" text-anchor="middle" fill="{BLUE_LIGHT if hub else "rgba(255,255,255,0.7)"}" '
            f'font-size="9" style="letter-spacing:1px">{label}</text>'
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


FOOTER_LINES = [
    "Thanks for visiting",
    "Open to collaboration",
    "Let's build something great",
]


def render_footer() -> str:
    w, h = 840, 150
    wave = "M0 110 C 140 80, 280 140, 420 110 S 700 80, 840 110"
    return "".join(
        [
            svg_open(w, h, "Thanks for visiting. Open to collaboration."),
            f"<style>.s{{font-family:{SANS};font-weight:800}}.m{{font-family:{MONO};font-weight:700;letter-spacing:2px}}</style>",
            f'<text class="m" x="{w / 2}" y="34" text-anchor="middle" fill="{BLUE_LIGHT}" font-size="10">SAGAR GUPTA  |  AWS PROFESSIONAL SERVICES</text>',
            _rotating(FOOTER_LINES, w / 2, 78, "s", 30, "#f3f4f6").replace(
                "<text ", '<text text-anchor="middle" '
            ),
            f'<path d="{wave}" fill="none" stroke="rgba(127,127,127,0.25)" stroke-width="1.2"/>',
            f'<path d="{wave}" fill="none" stroke="{BLUE_LIGHT}" stroke-width="2" stroke-dasharray="120 900" stroke-linecap="round">'
            '<animate attributeName="stroke-dashoffset" values="1020;0" dur="4s" repeatCount="indefinite"/></path>',
            f'<circle r="3.5" fill="{SKY}"><animateMotion dur="4s" repeatCount="indefinite" path="{wave}"/></circle>',
            SVG_CLOSE,
        ]
    )


# ---------------------------------------------------------------- certifications


def _plain_dashes(text: str) -> str:
    """Return text with en and em dashes replaced by a plain hyphen."""
    return text.replace("\u2013", "-").replace("\u2014", "-")


def credly_badges(group: str) -> list[tuple[str, str]]:
    """Return (title, image url) pairs for one group of the Credly block."""
    source = CREDLY_PATH if CREDLY_PATH.exists() else README_PATH
    wanted = ("Industry",) if group == INDUSTRY_GROUP else ("Professional", "Knowledge")
    current = None
    found: list[tuple[str, str]] = []
    # Headings come as '#### Industry Certifications' or as an icon plus '**Industry Certifications**'
    # depending on the updater version, so a heading is any non-badge line naming a group.
    for line in source.read_text(encoding="utf-8").splitlines():
        if "<a " not in line:
            named = next(
                (k for k in ("Industry", "Professional", "Knowledge") if k in line),
                None,
            )
            if named:
                current = named
            continue
        if current in wanted:
            found += re.findall(
                r'title="([^"]+)">(?:<picture>)?<img src="([^"]+)"', line
            )
    return [(_plain_dashes(title), url) for title, url in found]


PNG_MAGIC = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
JPEG_MAGIC = bytes([0xFF, 0xD8, 0xFF])


def _downscale(raw: bytes, px: int) -> bytes:
    """Return the image shrunk to px square as an optimized PNG, or unchanged without Pillow."""
    try:
        from PIL import (
            Image,
        )  # optional: the workflow installs it, local runs work without it
    except ImportError:
        return raw
    with Image.open(io.BytesIO(raw)) as img:
        img.thumbnail((px, px), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
    return out.getvalue() if out.tell() < len(raw) else raw


def _data_uri(url: str, px: int = 0) -> str | None:
    try:
        raw = fetch(url)
    except Exception as exc:
        print(f"badge image failed: {exc}")
        return None
    if px:
        raw = _downscale(raw, px)
    if raw.startswith(PNG_MAGIC):
        mime = "image/png"
    elif raw.startswith(JPEG_MAGIC):
        mime = "image/jpeg"
    else:
        return None
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def _wrap(text: str, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


LEARNING_GROUP = "Learning and Partner Badges"
# (group, label, drawn size, label lines, badges per row)
CREDLY_GROUPS = [
    (INDUSTRY_GROUP, "INDUSTRY CERTIFICATIONS", 84, 3, 6),
    (LEARNING_GROUP, "LEARNING AND PARTNER BADGES", 58, 2, 8),
]


def _short_badge(title: str) -> str:
    for prefix in (
        "AWS Certified ",
        "HashiCorp Certified: ",
        "AWS Knowledge: ",
        "AWS Partner: ",
        "AWS Educate ",
    ):
        title = title.replace(prefix, "")
    return title.replace(" - Training Badge", "").replace(" - ", " ")


def _badge_row(
    chunk: list[tuple[str, str]],
    top: float,
    size: int,
    max_lines: int,
    delay: float,
    images: dict,
    per_row: int,
) -> list[str]:
    """Return one centered row of floating badges with their wrapped labels."""
    w = 840
    col = (w - 32) / per_row
    x0 = 16 + (w - 32 - col * len(chunk)) / 2
    out = []
    for i, (title, url) in enumerate(chunk):
        cx = x0 + col * i + col / 2
        words = _wrap(_short_badge(title), 16 if size < 80 else 18)[:max_lines]
        text = "".join(
            f'<text class="m" x="{cx:.1f}" y="{top + size + 16 + j * 12}" text-anchor="middle" '
            f'fill="rgba(255,255,255,0.7)" font-size="{8.5 if size >= 80 else 7.5}">{escape(line.upper())}</text>'
            for j, line in enumerate(words)
        )
        out.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{delay + i * 0.06:.2f}s" dur="0.5s" fill="freeze"/>'
            f'<g class="float" style="animation-delay:{i * 0.35:.2f}s">'
            f'<image href="{images[url]}" x="{cx - size / 2:.1f}" y="{top}" width="{size}" height="{size}"/></g>{text}</g>'
        )
    return out


def render_certs() -> str | None:
    groups = [
        (label, size, lines, per_row, credly_badges(key))
        for key, label, size, lines, per_row in CREDLY_GROUPS
    ]
    # each badge is fetched once and shrunk to twice its drawn size, sharp on high-density screens
    images = {
        url: _data_uri(url, size * 2)
        for _, size, _, _, badges in groups
        for _, url in badges
    }
    if not groups[0][4] or any(img is None for img in images.values()):
        return None
    w = 840
    parts, y, delay = [], 34, 0.2
    for label, size, max_lines, per_row, badges in groups:
        if not badges:
            continue
        parts.append(
            f'<text class="m" x="24" y="{y}" fill="{BLUE_LIGHT}" font-size="10">{len(badges)} {label}</text>'
        )
        top = y + 14
        row_h = size + 16 + max_lines * 12 + 14
        # at most per_row per row, so labels never collide
        for start in range(0, len(badges), per_row):
            chunk = badges[start : start + per_row]
            parts += _badge_row(chunk, top, size, max_lines, delay, images, per_row)
            delay += 0.06 * len(chunk)
            top += row_h
        y = top + 12
    h = y - 10
    head = [
        svg_open(
            w,
            h,
            "Credly badges: "
            + ", ".join(t for *_, badges in groups for t, _ in badges),
        ),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1px}}"
        ".float{animation:float 4s ease-in-out infinite}"
        "@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}</style>",
        '<defs><linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset="0.5" stop-color="#fff" stop-opacity="0.14"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="card"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14"/></clipPath></defs>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
    ]
    shine = (
        f'<g clip-path="url(#card)"><rect x="-160" y="0" width="120" height="{h}" fill="url(#shine)" transform="skewX(-20)">'
        '<animateTransform attributeName="transform" type="translate" values="0 0;1100 0" dur="6s" repeatCount="indefinite" additive="sum"/></rect></g>'
    )
    return "".join(head + parts + [shine, SVG_CLOSE])


# ---------------------------------------------------------------- leetcode


LC_COLORS = {"Easy": "#00b8a3", "Medium": "#ffc01e", "Hard": "#ef4743"}


def render_leetcode(data: dict) -> str | None:
    lc = data["leetcode"]
    history = lc.get("history") or []
    if len(history) < 2:
        return None
    w, h = 840, 270
    cx0, cx1, cy0, cy1 = 40, 540, 70, 220
    lo, hi = min(history), max(history)
    span = max(hi - lo, 1)
    pts = [
        (
            cx0 + (cx1 - cx0) * i / (len(history) - 1),
            cy1 - (cy1 - cy0) * (r - lo) / span,
        )
        for i, r in enumerate(history)
    ]
    line = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    length = sum(
        ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:])
    )
    area = f"{line} L{cx1} {cy1} L{cx0} {cy1} Z"
    peak_i = history.index(hi)
    px, py = pts[peak_i]
    lx, ly = pts[-1]
    parts = [
        svg_open(
            w,
            h,
            f"LeetCode {lc['badge']}: rating {lc['rating']}, top {lc['top']}%, {lc['contests']} contests, {lc['solved']} solved",
        ),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.v{{font-family:{SANS};font-weight:800}}"
        ".ring{animation:ring 2.2s ease-out infinite;transform-origin:center;transform-box:fill-box}"
        "@keyframes ring{0%{opacity:0.9;transform:scale(1)}100%{opacity:0;transform:scale(2.8)}}</style>",
        f'<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{AMBER}" stop-opacity="0.28"/>'
        f'<stop offset="1" stop-color="{AMBER}" stop-opacity="0"/></linearGradient></defs>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="32" fill="{AMBER}" font-size="10">LEETCODE CONTEST RATING  |  {lc["contests"]} CONTESTS</text>',
    ]
    for frac in (0, 0.5, 1):
        y = cy1 - (cy1 - cy0) * frac
        value = round(lo + span * frac)
        parts.append(
            f'<line x1="{cx0}" y1="{y:.1f}" x2="{cx1}" y2="{y:.1f}" stroke="rgba(255,255,255,0.06)"/>'
            f'<text class="m" x="{cx1 + 8}" y="{y + 3:.1f}" fill="rgba(255,255,255,0.35)" font-size="8">{value}</text>'
        )
    parts += [
        f'<path d="{area}" fill="url(#area)" opacity="0"><animate attributeName="opacity" to="1" begin="2.2s" dur="0.8s" fill="freeze"/></path>',
        f'<path d="{line}" fill="none" stroke="{AMBER}" stroke-width="2" stroke-linejoin="round" stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}">'
        f'<animate attributeName="stroke-dashoffset" from="{length:.0f}" to="0" dur="2.4s" begin="0.2s" fill="freeze"/></path>',
        f'<circle class="ring" cx="{px:.1f}" cy="{py:.1f}" r="5" fill="none" stroke="{AMBER}" stroke-width="1.5" opacity="0">'
        '<set attributeName="opacity" to="1" begin="2.6s" fill="freeze"/></circle>',
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="{AMBER}" opacity="0"><set attributeName="opacity" to="1" begin="2.6s" fill="freeze"/></circle>',
        f'<text class="m" x="{px - 6:.1f}" y="{py - 12:.1f}" text-anchor="end" fill="{AMBER}" font-size="9" opacity="0">PEAK {hi}'
        '<set attributeName="opacity" to="1" begin="2.6s" fill="freeze"/></text>',
    ]
    rx = 600
    parts += [
        f'<text class="v" x="{rx}" y="84" fill="{AMBER}" font-size="30">{escape(lc["badge"])}</text>',
        f'<text class="m" x="{rx}" y="104" fill="rgba(255,255,255,0.55)" font-size="9">RATING {lc["rating"]}  |  TOP {lc["top"]}%</text>',
        f'<text class="v" x="{rx}" y="146" fill="#f3f4f6" font-size="22">{lc["solved"]:,}<tspan class="m" font-size="9" fill="rgba(255,255,255,0.5)">  SOLVED</tspan></text>',
    ]
    for j, (level, (done, total)) in enumerate((lc.get("by_difficulty") or {}).items()):
        y = 168 + j * 22
        frac = done / total if total else 0
        bar = 200 * frac
        parts.append(
            f'<text class="m" x="{rx}" y="{y}" fill="{LC_COLORS[level]}" font-size="8.5">{level.upper()}</text>'
            f'<text class="m" x="{rx + 200}" y="{y}" text-anchor="end" fill="rgba(255,255,255,0.5)" font-size="8.5">{done}/{total}</text>'
            f'<rect x="{rx}" y="{y + 5}" width="200" height="5" rx="2.5" fill="rgba(255,255,255,0.07)"/>'
            f'<rect x="{rx}" y="{y + 5}" width="{bar:.1f}" height="5" rx="2.5" fill="{LC_COLORS[level]}" transform="scale(0 1)" style="transform-origin:{rx}px 0">'
            f'<animateTransform attributeName="transform" type="scale" from="0 1" to="1 1" begin="{0.6 + j * 0.2:.1f}s" dur="0.9s" fill="freeze"/></rect>'
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


# ---------------------------------------------------------------- github


def _level(count: int, cuts: list[int]) -> int:
    return 0 if count == 0 else 1 + sum(1 for c in cuts if count > c)


def render_github(data: dict) -> str | None:
    gh = data.get("github")
    if not gh:
        return None
    w, h = 840, 340
    tiles = [
        (f"{gh['contributions']:,}", "contributions, last year"),
        (f"{gh['commits']:,}", "commits"),
        (f"{gh['prs']:,}", "pull requests"),
        (f"{gh['stars']:,}", "stars earned"),
        (f"{gh['followers']:,}", "followers"),
    ]
    parts = [
        svg_open(
            w,
            h,
            f"GitHub: {gh['contributions']} contributions last year, {gh['streak']} day streak, {gh['stars']} stars",
        ),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.v{{font-family:{SANS};font-weight:800}}"
        ".c{opacity:0;animation:in .5s ease forwards}@keyframes in{to{opacity:1}}"
        + "".join(f".w{i}{{animation-delay:{0.4 + i * 0.03:.2f}s}}" for i in range(54))
        + ".grow{transform:scaleX(0);transform-origin:left;transform-box:fill-box;animation:grow 1.2s .5s ease forwards}"
        "@keyframes grow{to{transform:scaleX(1)}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="30" fill="{BLUE_LIGHT}" font-size="10">GITHUB  |  @SAGARGUPTA16</text>',
    ]
    tw = (w - 32 - 4 * 10) / 5
    for i, (value, label) in enumerate(tiles):
        x = 16 + i * (tw + 10)
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{0.1 + i * 0.1:.1f}s" dur="0.4s" fill="freeze"/>'
            f'<rect x="{x}" y="44" width="{tw}" height="64" rx="10" fill="{CARD}" stroke="rgba(255,255,255,0.07)"/>'
            f'<text class="v" x="{x + 14}" y="76" fill="#f3f4f6" font-size="22">{value}</text>'
            f'<text class="m" x="{x + 14}" y="95" fill="rgba(255,255,255,0.5)" font-size="8">{label.upper()}</text></g>'
        )
    # contribution calendar, one column per week
    cal = gh["calendar"]
    nonzero = sorted(c for week in cal for c in week if c)
    cuts = [nonzero[len(nonzero) * q // 4] for q in (1, 2, 3)] if nonzero else [0, 0, 0]
    shades = [
        "rgba(255,255,255,0.05)",
        f"{BLUE}55",
        f"{BLUE}99",
        f"{BLUE}dd",
        BLUE_LIGHT,
    ]
    cell, gap, gx, gy = 9, 2.6, 24, 128
    for wi, week in enumerate(cal):
        for di, count in enumerate(week):
            x = gx + wi * (cell + gap)
            y = gy + di * (cell + gap)
            parts.append(
                f'<rect class="c w{wi}" x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="2" fill="{shades[_level(count, cuts)]}"/>'
            )
    sx = gx + len(cal) * (cell + gap) + 18
    parts += [
        f'<rect x="{sx}" y="{gy}" width="{w - 16 - sx}" height="{7 * (cell + gap) - gap:.0f}" rx="10" fill="{CARD}" stroke="rgba(255,255,255,0.07)"/>',
        f'<text class="m" x="{sx + 14}" y="{gy + 20}" fill="{GREEN}" font-size="8.5">CURRENT STREAK</text>',
        f'<text class="v" x="{sx + 14}" y="{gy + 46}" fill="#f3f4f6" font-size="22">{gh["streak"]}<tspan class="m" font-size="9" fill="rgba(255,255,255,0.5)"> DAYS</tspan></text>',
        f'<text class="m" x="{sx + 14}" y="{gy + 66}" fill="rgba(255,255,255,0.5)" font-size="8">LONGEST {gh["longest"]}  |  ACTIVE {gh["active_days"]}</text>',
    ]
    # languages, stacked bar plus legend
    ly = 232
    parts.append(
        f'<text class="m" x="24" y="{ly}" fill="rgba(255,255,255,0.5)" font-size="8.5">TOP LANGUAGES BY CODE SIZE</text>'
    )
    total = sum(p for _, p, _ in gh["languages"]) or 1
    x = 24.0
    bar_w = w - 48
    segs = []
    for name, pct, color in gh["languages"]:
        seg = bar_w * pct / total
        segs.append(
            f'<rect x="{x:.1f}" y="{ly + 10}" width="{seg:.1f}" height="10" fill="{color}"/>'
        )
        x += seg
    parts.append(
        f'<g class="grow"><clipPath id="bar"><rect x="24" y="{ly + 10}" width="{bar_w}" height="10" rx="5"/></clipPath>'
        f'<g clip-path="url(#bar)">{"".join(segs)}</g></g>'
    )
    for i, (name, pct, color) in enumerate(gh["languages"]):
        lx = 24 + (i % 3) * 270
        lyy = ly + 44 + (i // 3) * 20
        parts.append(
            f'<circle cx="{lx + 5}" cy="{lyy - 3}" r="4.5" fill="{color}"/>'
            f'<text class="m" x="{lx + 16}" y="{lyy}" fill="rgba(255,255,255,0.75)" font-size="9">{escape(name.upper())}  {pct}%</text>'
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


# ---------------------------------------------------------------- ai stack


def fetch_simple_icon(slug: str) -> str | None:
    try:
        raw = fetch(
            f"https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{slug}.svg"
        ).decode()
    except Exception as exc:
        print(f"simple icon {slug} failed: {exc}")
        return None
    m = re.search(r'<path d="([^"]+)"', raw)
    return m.group(1) if m else None


def render_ai_stack() -> str | None:
    paths: dict[str, str] = {}
    for _, slug in AI_TOOLS:
        if slug and slug not in paths:
            d = fetch_simple_icon(slug)
            if d is None:
                return None
            paths[slug] = d
    w, h = 840, 150
    cols, gap, pad = 5, 10, 16
    cw = (w - 2 * pad - (cols - 1) * gap) / cols
    ch = 44
    cycle = len(AI_TOOLS) * 0.6
    parts = [
        svg_open(w, h, "AI-assisted engineering: " + ", ".join(t for t, _ in AI_TOOLS)),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1px}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="28" fill="{BLUE_LIGHT}" font-size="10" style="letter-spacing:1.6px">AI-ASSISTED ENGINEERING</text>',
    ]
    for i, (label, slug) in enumerate(AI_TOOLS):
        col, row = i % cols, i // cols
        x = pad + col * (cw + gap)
        y = 42 + row * (ch + 10)
        if slug:
            icon = (
                f'<svg x="{x + 12}" y="{y + 12}" width="20" height="20" viewBox="0 0 24 24">'
                f'<path d="{paths[slug]}" fill="rgba(255,255,255,0.85)"/></svg>'
            )
        else:
            icon = (
                f'<circle cx="{x + 22}" cy="{y + 22}" r="10" fill="none" stroke="rgba(255,255,255,0.85)" stroke-width="1.6"/>'
                f'<text class="m" x="{x + 22}" y="{y + 26}" text-anchor="middle" fill="rgba(255,255,255,0.9)" font-size="10">{label[0]}</text>'
            )
        a = i / len(AI_TOOLS)
        b = a + 0.5 / len(AI_TOOLS)
        c = min(a + 1 / len(AI_TOOLS), 1)
        glow_times = f"0;{a:.3f};{b:.3f};{c:.3f};1"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="10" fill="{CARD}" stroke="rgba(255,255,255,0.08)"/>'
            f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="10" fill="{BLUE}1c" stroke="{BLUE_LIGHT}" stroke-width="1.2" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{glow_times}" dur="{cycle:.1f}s" repeatCount="indefinite"/></rect>'
            f"{icon}"
            f'<text class="m" x="{x + 42}" y="{y + 26}" fill="rgba(255,255,255,0.85)" font-size="10">{escape(label.upper())}</text>'
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


# ---------------------------------------------------------------- portfolio as the source of truth

# The portfolio repo is where Sagar updates everything; this README follows it.
# Fetched from the published main branch so a portfolio merge flows here on the
# next daily run. Only fields the portfolio already has are read.
PORTFOLIO_RAW = (
    "https://raw.githubusercontent.com/Sagargupta16/portfolio-react/main/data/"
)
MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ],
        start=1,
    )
}
GENERIC_SKILLS = {"AWS", "Cloud Migration", "Solution Architecture"}


def _start_key(date: str) -> tuple[int, int]:
    """Return a sort key for a range like 'Oct 2024 - Aug 2025' or 'March 2024 - July 2024'."""
    m = re.match(r"\s*([A-Za-z]+)\s+(\d{4})", date)
    if not m:
        return (0, 0)
    return (int(m.group(2)), MONTHS.get(m.group(1)[:3].lower(), 0))


def _range_label(date: str) -> str:
    parts = [p.strip() for p in date.split(" - ")]
    parts = ["now" if p.lower() == "present" else p for p in parts]
    return " to ".join(parts)


def _client_label(name: str) -> str:
    """Return the client, e.g. 'State Street' from 'DevOps Consultant - State Street'."""
    name = name.strip().removesuffix("(Ongoing)").strip()
    if " - " in name:
        return name.rsplit(" - ", 1)[1].strip()
    paren = re.search(r"\(([^)]+)\)", name)
    if paren:
        domain = next((k for k in ("MLOps", "DevOps", "AI") if k in name), "")
        return f"{domain} {paren.group(1)}".strip()
    return name


def _tagline(name: str, skills: list[str], count: int = 2) -> str:
    picked = [s for s in skills if s not in GENERIC_SKILLS][:count]
    lead = "Lead DevOps, " if name.startswith("Lead") else ""
    return lead + ", ".join(picked if not lead else picked[:1])


def portfolio_snapshot(experience: dict, projects: dict, extra: dict) -> dict:
    """Return the small slice of portfolio data the README uses, cached in data.json."""
    aws = experience["professional_experience"][0]
    engagements = sorted(
        aws.get("projects", []), key=lambda p: _start_key(p.get("date", ""))
    )
    samples = [
        {"title": p["title"], "url": p["github"]}
        for p in projects.get("featured_projects", [])
        if p.get("organization") == "aws-samples" and p.get("github")
    ]
    return {
        "engagements": [
            {
                "when": _range_label(p.get("date", "")),
                "client": _client_label(p["name"]),
                "tagline": _tagline(p["name"], p.get("skills", [])),
                "stack": [s for s in p.get("skills", []) if s not in GENERIC_SKILLS][
                    :6
                ],
                "link": p.get("link"),
                "name": p["name"],
            }
            for p in engagements
        ],
        "earlier": [
            {
                "title": e["title"],
                "company": e["company"],
                "date": e["date"],
                "position": e.get("position", ""),
            }
            for e in experience["professional_experience"][1:]
        ],
        "contributions": aws.get("internal_contributions", []),
        "achievements": aws.get("internal_achievements", []),
        "samples": samples,
        "oss": projects.get("open_source_contributions", []),
        "featured": [
            {
                k: p.get(k)
                for k in (
                    "title",
                    "description",
                    "date",
                    "tools_tech",
                    "github",
                    "live",
                    "organization",
                )
            }
            for p in projects.get("featured_projects", [])
        ],
        "community": [
            {k: p.get(k) for k in ("title", "description", "tools_tech", "github")}
            for p in projects.get("community_projects", [])
        ],
        "intro": extra.get("personal", {}).get("intro", ""),
        "education": extra.get("education", []),
        "coding_stats": extra.get("achievements", {}).get("coding_platform_stats", {}),
        "contests": extra.get("achievements", {}).get("achievements", []),
        "project_count": sum(
            len(projects.get(k, []))
            for k in (
                "featured_projects",
                "collaborative_projects",
                "other_projects",
                "community_projects",
            )
        ),
    }


def fetch_portfolio() -> dict:
    experience = json.loads(fetch(f"{PORTFOLIO_RAW}experience.json"))
    projects = json.loads(fetch(f"{PORTFOLIO_RAW}projects.json"))
    extra = {
        name: json.loads(fetch(f"{PORTFOLIO_RAW}{name}.json"))
        for name in ("personal", "education", "achievements")
    }
    return portfolio_snapshot(experience, projects, extra)


PR_URL = re.compile(r"^https://github\.com/([^/]+/[^/]+)/pull/(\d+)$")


def live_pr_state(url: str, token: str | None) -> tuple[str, str | None] | None:
    """Return (state, merged_at) straight from GitHub, or None for non-PR links."""
    m = PR_URL.match(url)
    if not m:
        return None
    d = json.loads(
        fetch(
            f"https://api.github.com/repos/{m.group(1)}/pulls/{m.group(2)}", token=token
        )
    )
    if d.get("merged_at"):
        return "merged", d["merged_at"]
    return d.get("state", "open"), None


def oss_with_live_state(oss: list[dict]) -> list[dict]:
    """Re-check every entry the portfolio still lists as open; merged ones move over on their own."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    out = []
    for entry in oss:
        entry = dict(entry)
        if entry.get("status") == "open":
            try:
                live = live_pr_state(entry["url"], token)
            except Exception as exc:
                print(f"pr state check failed for {entry['url']}: {exc}")
                live = None
            if live:
                entry["status"], merged_at = live
                if merged_at:
                    entry["merged_at"] = merged_at
                    print(f"now merged, portfolio still says open: {entry['url']}")
        out.append(entry)
    return out


# ---------------------------------------------------------------- README blocks


def _pr_label(url: str) -> str:
    m = PR_URL.match(url)
    if m:
        return f"#{m.group(2)}"
    sha = re.search(r"/commit/([0-9a-f]{7})", url)
    return f"commit {sha.group(1)}" if sha else "link"


# ---------------------------------------------------------------- cards and badges

CREDLY_PATH = ROOT / "assets" / "credly-badges.md"
CAREER_START = (2024, 8)  # full time at AWS since August 2024


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _summary(text: str, limit: int = 118) -> str:
    """Return the first sentence of a description, cut at a word boundary."""
    first = text.split(". ", 1)[0].rstrip(".")
    if len(first) <= limit:
        return first
    cut = first[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "..."


def _chips(items: list[str], x: float, y: float, max_w: float, color: str) -> str:
    out, cx = [], x
    for item in items:
        w = 12 + len(item) * 6.2
        if cx + w > x + max_w:
            break
        out.append(
            f'<rect x="{cx:.1f}" y="{y}" width="{w:.1f}" height="20" rx="10" fill="{color}14" stroke="{color}55"/>'
            f'<text class="m" x="{cx + w / 2:.1f}" y="{y + 13.5}" text-anchor="middle" fill="{color}" font-size="9">{escape(item)}</text>'
        )
        cx += w + 6
    return "".join(out)


def render_project_card(p: dict, index: int) -> str:
    w, h = 410, 196
    live = bool(p.get("live"))
    lines = _wrap(_summary(p["description"]), 56)[:3]
    body = "".join(
        f'<text class="s" x="22" y="{86 + j * 18}" fill="rgba(255,255,255,0.68)" font-size="12.5">{escape(line)}</text>'
        for j, line in enumerate(lines)
    )
    status = (
        f'<circle cx="{w - 72}" cy="30" r="3.5" fill="{GREEN}"><animate attributeName="opacity" values="1;0.35;1" dur="1.8s" repeatCount="indefinite"/></circle>'
        f'<text class="m" x="{w - 62}" y="34" fill="{GREEN}" font-size="9">LIVE</text>'
        if live
        else f'<text class="m" x="{w - 22}" y="34" text-anchor="end" fill="rgba(255,255,255,0.4)" font-size="9">SOURCE</text>'
    )
    return "".join(
        [
            svg_open(w, h, f"{p['title']}: {_summary(p['description'])}"),
            f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1px}}.t{{font-family:{SANS};font-weight:800}}"
            f".s{{font-family:{SANS};font-weight:500}}</style>",
            '<defs><linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset="0.5" stop-color="#fff" stop-opacity="0.06"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<clipPath id="c"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="16"/></clipPath></defs>',
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="16" fill="{CARD}" stroke="rgba(255,255,255,0.09)"/>',
            f'<rect x="0" y="22" width="3" height="28" rx="1.5" fill="{BLUE_LIGHT}"/>',
            f'<text class="m" x="22" y="34" fill="{BLUE_LIGHT}" font-size="9">{escape(p.get("date", "").upper())}</text>',
            status,
            f'<text class="t" x="22" y="62" fill="#f3f4f6" font-size="19">{escape(p["title"])}</text>',
            body,
            _chips(p.get("tools_tech", [])[:5], 22, h - 38, w - 44, SKY),
            f'<g clip-path="url(#c)"><rect x="-140" y="0" width="120" height="{h}" fill="url(#shine)" transform="skewX(-18)">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;700 0" dur="6s" begin="{index * 0.7:.1f}s" repeatCount="indefinite" additive="sum"/></rect></g>',
            SVG_CLOSE,
        ]
    )


def render_tool_card(p: dict, stars: int | None, index: int) -> str:
    w, h = 270, 150
    lines = _wrap(_summary(p["description"], 96), 38)[:3]
    body = "".join(
        f'<text class="s" x="18" y="{68 + j * 16}" fill="rgba(255,255,255,0.66)" font-size="11">{escape(line)}</text>'
        for j, line in enumerate(lines)
    )
    star = (
        f'<path d="M{w - 50} {h - 30} l3.1 6.3 6.9 1 -5 4.9 1.2 6.9 -6.2 -3.3 -6.2 3.3 1.2 -6.9 -5 -4.9 6.9 -1z" fill="{AMBER}"/>'
        f'<text class="m" x="{w - 36}" y="{h - 17}" fill="{AMBER}" font-size="11">{stars}</text>'
        if stars is not None
        else ""
    )
    return "".join(
        [
            svg_open(w, h, f"{p['title']}: {_summary(p['description'], 96)}"),
            f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1px}}.t{{font-family:{SANS};font-weight:800}}"
            f".s{{font-family:{SANS};font-weight:500}}</style>",
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{CARD}" stroke="rgba(255,255,255,0.09)"/>',
            f'<rect x="0" y="20" width="3" height="24" rx="1.5" fill="{SKY}">'
            f'<animate attributeName="opacity" values="1;0.4;1" dur="3s" begin="{index * 0.25:.2f}s" repeatCount="indefinite"/></rect>',
            f'<text class="t" x="18" y="40" fill="#f3f4f6" font-size="15">{escape(p["title"])}</text>',
            star,
            body,
            _chips(p.get("tools_tech", [])[:3], 18, h - 32, w - 92, BLUE_LIGHT),
            SVG_CLOSE,
        ]
    )


def render_profile_badges(data: dict) -> str:
    gh = data.get("github") or {}
    lc = data["leetcode"]
    today = datetime.date.today()
    years = today.year - CAREER_START[0] - (1 if today.month < CAREER_START[1] else 0)
    certs = len(credly_badges(INDUSTRY_GROUP))
    pills = [
        ("PROFILE VIEWS", f"{data.get('views', 0):,}", BLUE_LIGHT),
        ("FOLLOWERS", f"{gh.get('followers', 0):,}", BLUE_LIGHT),
        ("TOTAL STARS", f"{gh.get('stars', 0):,}", AMBER),
        (
            "LEETCODE",
            f"{lc['badge'].upper()}  |  PEAK {max(lc.get('history') or [lc['rating']])}",
            AMBER,
        ),
        ("CERTIFIED", f"{certs}x AWS / TERRAFORM", SKY),
        ("EXPERIENCE", f"{years}+ YEARS AT AWS", GREEN),
        ("PORTFOLIO", "SAGARGUPTA.ONLINE", BLUE_LIGHT),
    ]
    w, h = 840, 104
    parts = [
        svg_open(w, h, "; ".join(f"{k.title()} {v}" for k, v, _ in pills)),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}</style>",
    ]
    # two centered rows: four, then three
    for row, (lo, hi) in enumerate(((0, 4), (4, 7))):
        items = pills[lo:hi]
        widths = [24 + (len(k) + len(v)) * 7.1 + 18 for k, v, _ in items]
        total = sum(widths) + 12 * (len(items) - 1)
        x = (w - total) / 2
        y = 8 + row * 50
        for i, ((key, value, color), bw) in enumerate(zip(items, widths)):
            kw = 16 + len(key) * 7.1
            begin = 0.1 + (lo + i) * 0.1
            parts.append(
                f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{begin:.1f}s" dur="0.4s" fill="freeze"/>'
                f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="36" rx="18" fill="{CARD}" stroke="{color}55"/>'
                f'<rect x="{x:.1f}" y="{y}" width="{kw:.1f}" height="36" rx="18" fill="{color}1f"/>'
                f'<text class="m" x="{x + kw / 2:.1f}" y="{y + 22}" text-anchor="middle" fill="rgba(255,255,255,0.6)" font-size="9.5">{key}</text>'
                f'<text class="m" x="{x + kw + (bw - kw) / 2:.1f}" y="{y + 22}" text-anchor="middle" fill="{color}" font-size="10.5">{escape(value)}</text></g>'
            )
            x += bw + 12
    parts.append(SVG_CLOSE)
    return "".join(parts)


CONNECT = [
    (
        "linkedin",
        "LinkedIn",
        "linkedin",
        "https://www.linkedin.com/in/sagar-gupta-16-10",
    ),
    ("leetcode", "LeetCode", "leetcode", "https://leetcode.com/sagargupta1610/"),
    (
        "portfolio",
        "Portfolio",
        "googlechrome",
        PORTFOLIO_URL,
    ),
    ("email", "Email", "gmail", "mailto:sg85207@gmail.com"),
    ("github", "GitHub", "github", "https://github.com/Sagargupta16"),
]


def _button_label(label: str, has_icon: bool, w: int) -> str:
    if has_icon:
        return f'<text class="m" x="48" y="27" fill="#f3f4f6" font-size="11">{label.upper()}</text>'
    return f'<text class="m" x="{w / 2}" y="27" text-anchor="middle" fill="#f3f4f6" font-size="11">{label.upper()}</text>'


def render_connect_button(label: str, icon_path: str | None, index: int) -> str:
    w, h = 156, 44
    icon = (
        f'<svg x="16" y="12" width="20" height="20" viewBox="0 0 24 24"><path d="{icon_path}" fill="rgba(255,255,255,0.9)"/></svg>'
        if icon_path
        else ""
    )
    return "".join(
        [
            svg_open(w, h, label),
            f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.4px}}</style>",
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="22" fill="{CARD}" stroke="{BLUE_LIGHT}66"/>',
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="22" fill="{BLUE}22" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;0.1;0.2;1" dur="5s" begin="{index * 0.5:.1f}s" repeatCount="indefinite"/></rect>',
            icon,
            _button_label(label, icon_path is not None, w),
            SVG_CLOSE,
        ]
    )


def _oss_chip_label(repo: str, count: int, stars: int) -> str:
    """Return a chip label: repo, a count when merged more than once, and its stars."""
    label = repo
    if count > 1:
        label += f"  x{count}"
    if stars >= 1000:
        label += f"  {stars / 1000:.1f}K"
    elif stars:
        label += f"  {stars}"
    return label


def render_oss(data: dict) -> str | None:
    pf = data.get("portfolio") or {}
    oss = pf.get("oss") or []
    merged = [e for e in oss if e.get("status") == "merged"]
    review = [e for e in oss if e.get("status") == "open"]
    if not merged:
        return None
    stars = data.get("oss_stars", {})
    repos: dict[str, int] = {}
    for e in merged:
        repos[e["repo"]] = repos.get(e["repo"], 0) + 1
    ranked = sorted(repos, key=lambda r: -stars.get(r, 0))
    reach = sum(stars.get(r, 0) for r in repos)
    w, h = 840, 250
    tiles = [
        (str(len(merged)), "merged upstream"),
        (str(len(review)), "in review"),
        (str(len(repos)), "projects contributed to"),
        (
            f"{reach // 1000}K+" if reach >= 1000 else str(reach),
            "combined stars",
        ),
    ]
    parts = [
        svg_open(
            w,
            h,
            f"Open source: {len(merged)} merged upstream, {len(review)} in review, across {len(repos)} projects",
        ),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.v{{font-family:{SANS};font-weight:800}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="30" fill="{BLUE_LIGHT}" font-size="10">OPEN SOURCE  |  MERGED UPSTREAM</text>',
    ]
    tw = (w - 32 - 3 * 10) / 4
    for i, (value, label) in enumerate(tiles):
        x = 16 + i * (tw + 10)
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{0.1 + i * 0.1:.1f}s" dur="0.4s" fill="freeze"/>'
            f'<rect x="{x:.1f}" y="44" width="{tw:.1f}" height="62" rx="10" fill="{CARD}" stroke="rgba(255,255,255,0.07)"/>'
            f'<text class="v" x="{x + 14:.1f}" y="76" fill="#f3f4f6" font-size="22">{value}</text>'
            f'<text class="m" x="{x + 14:.1f}" y="95" fill="rgba(255,255,255,0.5)" font-size="8">{label.upper()}</text></g>'
        )
    # merged-into chips, biggest projects first
    x, y = 24.0, 128
    for i, repo in enumerate(ranked):
        label = _oss_chip_label(repo, repos[repo], stars.get(repo, 0))
        cw = 16 + len(label) * 6.3
        if x + cw > w - 24:
            x, y = 24.0, y + 30
        if y > h - 30:
            break
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{0.5 + i * 0.06:.2f}s" dur="0.4s" fill="freeze"/>'
            f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="22" rx="11" fill="{SKY}12" stroke="{SKY}44"/>'
            f'<text class="m" x="{x + cw / 2:.1f}" y="{y + 15}" text-anchor="middle" fill="rgba(255,255,255,0.8)" font-size="9">{escape(label)}</text></g>'
        )
        x += cw + 8
    parts.append(SVG_CLOSE)
    return "".join(parts)


def fetch_oss_stars(oss: list[dict]) -> dict[str, int]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    stars = {}
    for repo in sorted({e["repo"] for e in oss}):
        try:
            stars[repo] = json.loads(
                fetch(f"https://api.github.com/repos/{repo}", token=token)
            ).get("stargazers_count", 0)
        except Exception as exc:
            print(f"stars for {repo} failed: {exc}")
    return stars


def render_cards(data: dict) -> None:
    pf = data.get("portfolio") or {}
    for i, p in enumerate(
        q for q in pf.get("featured", []) if q.get("organization") != "aws-samples"
    ):
        write(f"project-{_slug(p['title'])}.svg", render_project_card(p, i))
    repo_stars = (data.get("github") or {}).get("repo_stars", {})
    for i, p in enumerate(pf.get("community", [])):
        name = p["github"].rstrip("/").rsplit("/", 1)[-1]
        write(
            f"tool-{_slug(p['title'])}.svg",
            render_tool_card(p, repo_stars.get(name), i),
        )
    paths = {}
    for _, _, slug, _ in CONNECT:
        paths[slug] = fetch_simple_icon(slug)
    for i, (key, label, slug, _) in enumerate(CONNECT):
        write(f"connect-{key}.svg", render_connect_button(label, paths[slug], i))


# ---------------------------------------------------------------- list cards (engagements, publications, OSS)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3].rsplit(" ", 1)[0] + "..."


def render_list_card(
    kicker: str, rows: list[tuple[str, str, str]], accent: str, footer: str = ""
) -> str:
    """Return a card of rows: bold primary, dimmed secondary line, mono meta on the right."""
    w = 840
    row_h = 46
    top = 50
    h = top + len(rows) * row_h + (34 if footer else 12)
    parts = [
        svg_open(
            w, h, kicker.title() + ": " + "; ".join(f"{a} {b} {c}" for a, b, c in rows)
        ),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.t{{font-family:{SANS};font-weight:700}}"
        f".s{{font-family:{SANS};font-weight:500}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="31" fill="{accent}" font-size="10">{escape(kicker)}</text>',
    ]
    for i, (primary, secondary, meta) in enumerate(rows):
        y = top + i * row_h
        begin = 0.15 + i * 0.07
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{begin:.2f}s" dur="0.4s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="-8 0" to="0 0" begin="{begin:.2f}s" dur="0.4s" fill="freeze"/>'
            f'<line x1="24" y1="{y}" x2="{w - 24}" y2="{y}" stroke="rgba(255,255,255,0.06)"/>'
            f'<circle cx="30" cy="{y + 23}" r="3" fill="{accent}"/>'
            f'<text class="t" x="44" y="{y + 20}" fill="#f3f4f6" font-size="13.5">{escape(_clip(primary, 60))}</text>'
            f'<text class="s" x="44" y="{y + 37}" fill="rgba(255,255,255,0.6)" font-size="11.5">{escape(_clip(secondary, 104))}</text>'
            f'<text class="m" x="{w - 24}" y="{y + 20}" text-anchor="end" fill="rgba(255,255,255,0.45)" font-size="9">{escape(meta.upper())}</text></g>'
        )
    if footer:
        parts.append(
            f'<text class="s" x="24" y="{h - 14}" fill="rgba(255,255,255,0.55)" font-size="11">{escape(_clip(footer, 150))}</text>'
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


COMPANY_ICONS = {AWS_NAME: "aws.amazon.com", "RWS": "rws.com", "DTCC": "dtcc.com"}


def _customers(pf: dict) -> list[dict]:
    """Return the engagements that were customer work ('Role - Client'), newest last."""
    return [e for e in pf.get("engagements", []) if " - " in e["name"]]


def _company_icon(name: str) -> str | None:
    domain = COMPANY_ICONS.get(name)
    if not domain:
        return None
    return _data_uri(f"https://www.google.com/s2/favicons?domain={domain}&sz=64", 64)


def _logo_tile(name: str, x: float, y: float, size: int) -> str:
    icon = _company_icon(name)
    frame = f'<rect x="{x:.1f}" y="{y}" width="{size}" height="{size}" rx="12" fill="#ffffff0f" stroke="rgba(255,255,255,0.12)"/>'
    if icon:
        pad = 9
        return frame + f'<image href="{icon}" x="{x + pad:.1f}" y="{y + pad}" width="{size - 2 * pad}" height="{size - 2 * pad}"/>'
    initials = "".join(word[0] for word in name.replace("-", " ").split()[:2]).upper()
    return frame + (
        f'<text class="t" x="{x + size / 2:.1f}" y="{y + size / 2 + 6}" text-anchor="middle" fill="{BLUE_LIGHT}" font-size="17">{escape(initials)}</text>'
    )


def render_worked_with(pf: dict) -> str:
    """Return a row of company tiles: logo, company, and the title held there."""
    tiles = [(AWS_NAME, "DevOps/MLOps Cloud Consultant")]
    for e in reversed(_customers(pf)):
        role = e["name"].replace(" (Ongoing)", "").rsplit(" - ", 1)[0]
        tiles.append((e["client"], role))
    for e in pf.get("earlier", []):
        if e["company"] != AWS_NAME:
            tiles.append((e["company"], f"{e['title']} (intern)" if e.get("position") == "Internship" else e["title"]))
    w, h = 840, 232
    gap, pad = 10, 16
    tw = (w - 2 * pad - (len(tiles) - 1) * gap) / len(tiles)
    parts = [
        svg_open(w, h, "Worked with: " + "; ".join(f"{c}, {r}" for c, r in tiles)),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.t{{font-family:{SANS};font-weight:800}}"
        f".s{{font-family:{SANS};font-weight:500}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="31" fill="{GREEN}" font-size="10">WORKED WITH  |  AVERAGE CSAT 10/10  |  AVERAGE PULSE 5/5</text>',
    ]
    for i, (company, role) in enumerate(tiles):
        x = pad + i * (tw + gap)
        cx = x + tw / 2
        begin = 0.15 + i * 0.12
        lines = _wrap(role, 22)[:2]
        role_text = "".join(
            f'<text class="s" x="{cx:.1f}" y="{168 + j * 16}" text-anchor="middle" fill="rgba(255,255,255,0.62)" font-size="11.5">{escape(line)}</text>'
            for j, line in enumerate(lines)
        )
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{begin:.2f}s" dur="0.45s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 10" to="0 0" begin="{begin:.2f}s" dur="0.45s" fill="freeze"/>'
            f'<rect x="{x:.1f}" y="46" width="{tw:.1f}" height="{h - 62}" rx="12" fill="{CARD}" stroke="rgba(255,255,255,0.07)"/>'
            + _logo_tile(company, cx - 26, 62, 52)
            + f'<text class="t" x="{cx:.1f}" y="146" text-anchor="middle" fill="#f3f4f6" font-size="14.5">{escape(company)}</text>'
            + role_text
            + "</g>"
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


def _publication_groups(pf: dict) -> list[tuple[str, list[tuple[str, str]]]]:
    samples, papers, talks = [], [], []
    for c in sorted(pf.get("contributions", []), key=lambda c: str(c.get("year", "")), reverse=True):
        title, year = c["title"], str(c.get("year", ""))
        if title.startswith("AWS Sample Published: "):
            samples.append((title.split(": ", 1)[1].removesuffix("(aws-samples, MIT-0)").strip(), year))
        elif title.startswith("APG Pattern: "):
            papers.append(("APG pattern: " + title.split(": ", 1)[1].removesuffix("(Published)").strip(), year))
        elif "Peer Reviewed" in title:
            papers.append((title.replace(" Peer Reviewed", " peer reviewed"), year))
        elif title.startswith("Tech Talk: "):
            talks.append((title.split(": ", 1)[1], year))
        else:
            papers.append((title, year))
    recognition = [(a["title"].replace(" - ", ", "), str(a.get("year", ""))) for a in pf.get("achievements", [])]
    return [("AWS SAMPLES", samples), ("PUBLICATIONS", papers), ("TECH TALKS", talks), ("RECOGNITION", recognition)]


def _panel(label: str, items: list[tuple[str, str]], x: float, y: float, pw: float, ph: float, accent: str, delay: float) -> str:
    out = [
        f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{delay:.2f}s" dur="0.45s" fill="freeze"/>'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{pw:.1f}" height="{ph:.1f}" rx="12" fill="{CARD}" stroke="rgba(255,255,255,0.07)"/>'
        f'<rect x="{x:.1f}" y="{y + 16:.1f}" width="3" height="22" rx="1.5" fill="{accent}"/>'
        f'<text class="m" x="{x + 18:.1f}" y="{y + 31:.1f}" fill="{accent}" font-size="9.5">{label}</text>'
    ]
    cy = y + 56
    for text, year in items:
        lines = _wrap(text, 50)[:3]
        out.append(
            f'<circle cx="{x + 21:.1f}" cy="{cy - 4:.1f}" r="2.5" fill="{accent}"/>'
            f'<text class="m" x="{x + pw - 16:.1f}" y="{cy:.1f}" text-anchor="end" fill="rgba(255,255,255,0.4)" font-size="8.5">{escape(year)}</text>'
            + "".join(
                f'<text class="s" x="{x + 32:.1f}" y="{cy + j * 16:.1f}" fill="rgba(255,255,255,0.78)" font-size="12">{escape(line)}</text>'
                for j, line in enumerate(lines)
            )
        )
        cy += 16 * len(lines) + 12
    out.append("</g>")
    return "".join(out)


def _panel_height(items: list[tuple[str, str]]) -> float:
    return 56 + sum(16 * len(_wrap(text, 50)[:3]) + 12 for text, _ in items) + 4


def render_publications(pf: dict) -> str:
    """Return AWS samples, publications, talks and recognition as a 2x2 grid of panels."""
    groups = _publication_groups(pf)
    accents = [SKY, BLUE_LIGHT, GREEN, AMBER]
    w, pad, gap = 840, 16, 12
    pw = (w - 2 * pad - gap) / 2
    rows = [groups[0:2], groups[2:4]]
    heights = [max(_panel_height(items) for _, items in row) for row in rows]
    h = 44 + sum(heights) + gap + pad
    parts = [
        svg_open(w, h, "Publications, talks and recognition: " + "; ".join(t for _, items in groups for t, _ in items)),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.s{{font-family:{SANS};font-weight:500}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="30" fill="{SKY}" font-size="10">PUBLICATIONS, TALKS AND RECOGNITION</text>',
    ]
    y = 44.0
    for r, row in enumerate(rows):
        for c, (label, items) in enumerate(row):
            i = r * 2 + c
            parts.append(_panel(label, items, pad + c * (pw + gap), y, pw, heights[r], accents[i], 0.15 + i * 0.12))
        y += heights[r] + gap
    parts.append(SVG_CLOSE)
    return "".join(parts)


def render_education(pf: dict) -> str:
    rows = []
    for e in pf.get("education", [])[:2]:
        facts = [f"CGPA {e['cgpa']}"] if e.get("cgpa") else []
        facts += list((e.get("achievements") or [])[:2])
        rows.append(
            (
                f"{e['title']}",
                f"{e['institution']}  |  {', '.join(facts)}",
                _range_label(e["date"]),
            )
        )
    return render_list_card("EDUCATION", rows, BLUE_LIGHT)


def render_oss_merged(pf: dict) -> str:
    merged = sorted(
        (e for e in pf.get("oss", []) if e.get("status") == "merged"),
        key=lambda e: e.get("merged_at") or "",
        reverse=True,
    )
    rows = [(e["repo"], e["title"], _pr_label(e["url"])) for e in merged]
    return render_list_card(
        f"{len(rows)} MERGED UPSTREAM  |  NEWEST FIRST", rows, GREEN
    )


def render_oss_review(pf: dict) -> str:
    grouped: dict[str, list[dict]] = {}
    for e in pf.get("oss", []):
        if e.get("status") == "open":
            grouped.setdefault(e["repo"], []).append(e)
    ordered = sorted(grouped.items(), key=lambda kv: -len(kv[1]))
    rows = [
        (
            repo,
            "; ".join(e["title"] for e in entries),
            ", ".join(
                _pr_label(e["url"])
                for e in sorted(entries, key=lambda e: _pr_label(e["url"]))
            ),
        )
        for repo, entries in ordered
    ]
    count = sum(len(v) for v in grouped.values())
    footer = "Community impact: fixed the AWS Ansible deploy and Elastic IP allocation in forem/selfhost, plus 3 accepted answers on GitHub Community Q&A"
    return render_list_card(f"{count} PRS IN REVIEW", rows, AMBER, footer)


def render_competitive(pf: dict, data: dict) -> str:
    stats = pf.get("coding_stats", {})
    lc = data["leetcode"]
    tiles = [
        (
            "LEETCODE",
            lc["badge"],
            f"best contest rank {stats.get('leetcode', {}).get('best_contest_rank', '')}",
        ),
        (
            "GEEKSFORGEEKS",
            stats.get("geeksforgeeks", {}).get("problems_solved", ""),
            "problems solved",
        ),
        (
            "HACKERRANK",
            stats.get("hackerrank", {}).get("problem_solving", ""),
            "problem solving",
        ),
        ("KICK START '22", "1289", "round E rank"),
    ]
    podiums = [
        a["title"]
        for a in pf.get("contests", [])
        if re.match(r"(1st|2nd|3rd|4th) Place", a["title"])
    ]
    w, h = 840, 196
    tw = (w - 32 - 3 * 10) / 4
    parts = [
        svg_open(
            w,
            h,
            "Competitive programming: "
            + "; ".join(f"{a} {b} {c}" for a, b, c in tiles)
            + "; "
            + "; ".join(podiums),
        ),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}.v{{font-family:{SANS};font-weight:800}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="30" fill="{AMBER}" font-size="10">COMPETITIVE PROGRAMMING</text>',
    ]
    for i, (key, value, label) in enumerate(tiles):
        x = 16 + i * (tw + 10)
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{0.1 + i * 0.1:.1f}s" dur="0.4s" fill="freeze"/>'
            f'<rect x="{x:.1f}" y="44" width="{tw:.1f}" height="72" rx="10" fill="{CARD}" stroke="rgba(255,255,255,0.07)"/>'
            f'<text class="m" x="{x + 14:.1f}" y="64" fill="{AMBER}" font-size="8.5">{escape(key)}</text>'
            f'<text class="v" x="{x + 14:.1f}" y="90" fill="#f3f4f6" font-size="20">{escape(str(value))}</text>'
            f'<text class="m" x="{x + 14:.1f}" y="107" fill="rgba(255,255,255,0.5)" font-size="8">{escape(label.upper())}</text></g>'
        )
    x, y = 24.0, 134
    for i, title in enumerate(podiums):
        label = title.replace(" Place - ", "  ").replace(", ", " ")
        cw = 16 + len(label) * 6.2
        if x + cw > w - 24:
            x, y = 24.0, y + 28
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{0.5 + i * 0.06:.2f}s" dur="0.4s" fill="freeze"/>'
            f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="22" rx="11" fill="{AMBER}12" stroke="{AMBER}44"/>'
            f'<text class="m" x="{x + cw / 2:.1f}" y="{y + 15}" text-anchor="middle" fill="rgba(255,255,255,0.82)" font-size="9">{escape(label.upper())}</text></g>'
        )
        x += cw + 8
    parts.append(SVG_CLOSE)
    return "".join(parts)


INTRO_KEYWORDS = [
    "AWS Professional Services",
    "Terraform",
    "CI/CD",
    "MLOps pipelines",
    "agent tooling",
]
SPECIALTIES = [
    "DevOps Engineering",
    "MLOps",
    "AWS Cloud Infrastructure",
    "Full Stack Development",
]


def _highlight(line: str) -> str:
    """Escape a line and color the intro keywords it contains."""
    out = escape(line)
    for word in INTRO_KEYWORDS:
        out = out.replace(
            escape(word),
            f'<tspan fill="{BLUE_LIGHT}" font-weight="700">{escape(word)}</tspan>',
        )
    return out


def render_intro(pf: dict) -> str:
    intro = pf.get("intro") or (
        "Cloud consultant at AWS Professional Services. I build the AWS platforms that regulated companies migrate onto: "
        "Terraform, CI/CD, MLOps pipelines, and lately the agent tooling that makes that work faster."
    )
    lines = _wrap(intro, 92)
    w = 840
    h = 60 + len(lines) * 24 + 56
    parts = [
        svg_open(w, h, intro),
        f"<style>.s{{font-family:{SANS};font-weight:500}}.m{{font-family:{MONO};font-weight:700;letter-spacing:1.2px}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{CARD}" stroke="rgba(255,255,255,0.08)"/>',
        f'<rect x="0" y="24" width="3" height="{len(lines) * 24 + 12}" rx="1.5" fill="{BLUE}"/>',
        f'<text class="m" x="28" y="36" fill="{BLUE_LIGHT}" font-size="10">ABOUT</text>',
    ]
    for i, line in enumerate(lines):
        parts.append(
            f'<text class="s" x="28" y="{64 + i * 24}" fill="rgba(255,255,255,0.8)" font-size="15.5">{_highlight(line)}</text>'
        )
    parts.append(_chips(SPECIALTIES, 28, h - 40, w - 56, SKY))
    parts.append(SVG_CLOSE)
    return "".join(parts)


CTAS = [
    (
        "cta-portfolio",
        "View all {n} projects",
        PORTFOLIO_URL,
    ),
    (
        "cta-resume",
        "Download resume",
        "https://github.com/Sagargupta16/latex-resume/releases/latest/download/resume.pdf",
    ),
]


def render_cta(label: str, primary: bool) -> str:
    w, h = 250, 48
    fill = BLUE if primary else CARD
    return "".join(
        [
            svg_open(w, h, label),
            f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.4px}}</style>",
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="24" fill="{fill}" stroke="{BLUE_LIGHT}88"/>',
            f'<text class="m" x="{w / 2}" y="29" text-anchor="middle" fill="#ffffff" font-size="11.5">{escape(label.upper())}</text>',
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="24" fill="#ffffff" opacity="0">'
            '<animate attributeName="opacity" values="0;0.12;0" dur="3s" repeatCount="indefinite"/></rect>',
            SVG_CLOSE,
        ]
    )


# ---------------------------------------------------------------- the README itself


def _img(src: str, alt: str, width: str = "100%") -> str:
    return f'<img src="assets/svg/{src}" width="{width}" alt="{escape(alt, quote=True)}" />'


def _link(href: str, inner: str) -> str:
    return f'<a href="{href}">{inner}</a>'


def _header(key: str, title: str) -> str:
    return (
        "<picture>\n"
        f'  <source media="(prefers-color-scheme: dark)" srcset="assets/svg/header-{key}-dark.svg">\n'
        f'  <source media="(prefers-color-scheme: light)" srcset="assets/svg/header-{key}-light.svg">\n'
        f"  {_img(f'header-{key}-dark.svg', title)}\n"
        "</picture>"
    )


def _row(cells: list[str], width: str) -> str:
    """Return linked images side by side; no table, so GitHub draws no grid lines."""
    inner = "\n".join(c.replace('width="100%"', f'width="{width}"') for c in cells)
    return f'<p align="center">\n{inner}\n</p>'


DIVIDER = _img("divider.svg", "")
CREDLY_URL = "https://www.credly.com/users/sagar-gupta.f8eb96cc"
MERGED_URL = "https://github.com/pulls?q=is%3Apr+author%3ASagargupta16+is%3Amerged+-user%3ASagargupta16"
REVIEW_URL = "https://github.com/pulls?q=is%3Apr+author%3ASagargupta16+is%3Aopen+-user%3ASagargupta16"
SNAKE = (
    "<picture>\n"
    '  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Sagargupta16/Sagargupta16/output/github-snake-dark.svg" />\n'
    '  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Sagargupta16/Sagargupta16/output/github-snake.svg" />\n'
    '  <img alt="Contribution snake" src="https://raw.githubusercontent.com/Sagargupta16/Sagargupta16/output/github-snake.svg" width="100%" />\n'
    "</picture>"
)


def render_readme(data: dict) -> str:
    pf = data.get("portfolio") or {}
    projects = [
        p for p in pf.get("featured", []) if p.get("organization") != "aws-samples"
    ]
    project_cells = [
        _link(
            p.get("live") or p.get("github"),
            _img(
                f"project-{_slug(p['title'])}.svg",
                f"{p['title']}: {_summary(p['description'])}",
            ),
        )
        for p in projects
    ]
    tool_cells = [
        _link(
            p["github"],
            _img(
                f"tool-{_slug(p['title'])}.svg",
                f"{p['title']}: {_summary(p['description'], 96)}",
            ),
        )
        for p in pf.get("community", [])
    ]
    samples = [
        _link(
            "https://github.com/aws-samples/sample-aws-terraform-org-governance",
            _img(
                "sample-org-governance.svg",
                "AWS Organizations Governance, published AWS sample",
            ),
        ),
        _link(
            "https://github.com/aws-samples/sample-sagemaker-image-classification-mlops",
            _img(
                "sample-sagemaker-mlops.svg",
                "SageMaker Image Classification MLOps, published AWS sample",
            ),
        ),
    ]
    count = pf.get("project_count", 45)
    ctas = [
        _link(url, _img(f"{key}.svg", label.format(n=count)))
        for key, label, url in CTAS
    ]
    connect = [
        _link(url, _img(f"connect-{key}.svg", label)) for key, label, _, url in CONNECT
    ]
    blocks = [
        "<!-- Generated by scripts/render-svgs.py from the portfolio data. Edit the portfolio or the script, not this file. -->",
        _link(
            PORTFOLIO_URL,
            _img(
                "hero.svg",
                "Sagar Gupta, ProServe (Cloud Consultant) - DevOps/MLOps at AWS Professional Services",
            ),
        ),
        _link(
            PORTFOLIO_URL,
            _img(
                "profile-badges.svg",
                "Followers, total stars, LeetCode, certifications, years at AWS, portfolio",
            ),
        ),
        _img("intro.svg", pf.get("intro") or "About"),
        _img(
            "terminal.svg", "Terminal: whoami, published AWS samples, LeetCode profile"
        ),
        DIVIDER,
        _header("experience", "Experience"),
        _img("experience.svg", "Career timeline and customer engagements"),
        _img("highlights.svg", "Highlights"),
        _img("worked-with.svg", "Worked with: companies and customers"),
        _img("publications.svg", "Publications, talks and recognition"),
        _img("education.svg", "Education"),
        DIVIDER,
        _header("projects", "Featured Projects"),
        _row(samples, "49%"),
        _row(project_cells, "49%"),
        _row(ctas, "30%"),
        DIVIDER,
        _header("community", "Community and Developer Tools"),
        _row(tool_cells, "32%"),
        DIVIDER,
        _header("opensource", "Open Source"),
        _link(MERGED_URL, _img("oss.svg", "Open source summary")),
        _link(MERGED_URL, _img("oss-merged.svg", "Merged upstream pull requests")),
        _link(REVIEW_URL, _img("oss-review.svg", "Pull requests in review")),
        DIVIDER,
        _header("connect", "Connect With Me"),
        _row(connect, "18%"),
        DIVIDER,
        _header("stack", "Tech Stack and Tools"),
        _img("stack.svg", "Tech stack"),
        _img("ai-stack.svg", "AI-assisted engineering"),
        DIVIDER,
        _header("stats", "GitHub Stats"),
        _img("github.svg", "GitHub stats"),
        _link(
            "https://leetcode.com/sagargupta1610/",
            _img("leetcode.svg", "LeetCode contest rating"),
        ),
        _img("competitive.svg", "Competitive programming"),
        SNAKE,
        DIVIDER,
        _header("certs", "Certifications and Badges"),
        _link(CREDLY_URL, _img("certs.svg", "Credly badges")),
        DIVIDER,
        # a 1px copy of the komarev counter keeps visits counted; the number itself shows in profile-badges.svg
        _img("footer.svg", "Thanks for visiting")
        + f' <img src="{VIEWS_URL}" width="1" height="1" alt="" />',
    ]
    return "\n\n".join(blocks) + "\n"


def write_readme(data: dict) -> None:
    content = render_readme(data)
    old = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else None
    if old != content:
        # README_PATH is a constant; only the generated layout above is written
        with open(README_PATH, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        print("wrote README.md")


def write(name: str, content: str) -> None:
    path = OUT / name
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {name} ({len(content):,} bytes)")


def refresh_portfolio(data: dict) -> None:
    try:
        data["portfolio"] = fetch_portfolio()
    except Exception as exc:  # keep the last good snapshot
        print(f"portfolio fetch failed, reusing cached snapshot: {exc}")
    if data.get("portfolio"):
        data["portfolio"]["oss"] = oss_with_live_state(data["portfolio"]["oss"])
        stars = fetch_oss_stars(data["portfolio"]["oss"])
        if stars:
            data["oss_stars"] = {**data.get("oss_stars", {}), **stars}


def write_optional(name: str, content: str | None) -> None:
    if content is None:
        print(f"{name} kept as is: its data fetch failed")
    else:
        write(name, content)


def write_portfolio_cards(data: dict) -> None:
    pf = data.get("portfolio") or {}
    if pf:
        write("intro.svg", render_intro(pf))
        write("worked-with.svg", render_worked_with(pf))
        write("publications.svg", render_publications(pf))
        write("education.svg", render_education(pf))
        write("oss-merged.svg", render_oss_merged(pf))
        write("oss-review.svg", render_oss_review(pf))
        write("competitive.svg", render_competitive(pf, data))
    for i, (key, label, _) in enumerate(CTAS):
        write(
            f"{key}.svg",
            render_cta(label.format(n=pf.get("project_count", 45)), i == 0),
        )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_data()
    refresh_portfolio(data)
    write("data.json", json.dumps(data, indent=2) + "\n")
    write("terminal.svg", render_terminal(data))
    write("experience.svg", render_experience(data))
    write("highlights.svg", render_highlights(data))
    write("hero.svg", render_hero(data))
    write("footer.svg", render_footer())
    write("profile-badges.svg", render_profile_badges(data))
    render_cards(data)
    write_portfolio_cards(data)
    for name, content in (
        ("certs.svg", render_certs()),
        ("leetcode.svg", render_leetcode(data)),
        ("github.svg", render_github(data)),
        ("ai-stack.svg", render_ai_stack()),
        ("oss.svg", render_oss(data)),
        ("stack.svg", render_stack()),
    ):
        write_optional(name, content)
    write("sample-org-governance.svg", render_org_card())
    write("sample-sagemaker-mlops.svg", render_mlops_card())
    for key, num, title, sub in HEADERS:
        for theme in ("dark", "light"):
            write(f"header-{key}-{theme}.svg", render_header(num, title, sub, theme))
    write("divider.svg", render_divider())
    write_readme(data)


if __name__ == "__main__":
    main()
