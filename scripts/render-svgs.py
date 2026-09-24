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
import json
import os
import re
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "svg"
DATA_FILE = OUT / "data.json"

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
ALLOWED_HOSTS = (
    "https://leetcode.com/",
    "https://skillicons.dev/",
    "https://api.github.com/",
    "https://images.credly.com/",
    "https://cdn.jsdelivr.net/",
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
    "repositories(ownerAffiliations:OWNER,isFork:false,first:100){totalCount nodes{stargazerCount "
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


def load_data() -> dict:
    data = json.loads(json.dumps(DEFAULT_DATA))
    if DATA_FILE.exists():
        data.update(json.loads(DATA_FILE.read_text(encoding="utf-8")))
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
    w, h = 840, 292
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
            [
                "aws-samples/sample-aws-terraform-org-governance",
                "aws-samples/sample-sagemaker-image-classification-mlops",
            ],
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


def render_experience() -> str:
    """Top rail to the current role, which then expands into its customer engagements."""
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
            + ", ".join(e[1] for e in ENGAGEMENTS),
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
    sub_step = (sub_right - sub_left) / (len(ENGAGEMENTS) - 1)
    sub_last = len(ENGAGEMENTS) - 1
    for i, (when, client, what) in enumerate(ENGAGEMENTS):
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


def readme_counts() -> dict:
    """Counts that already live in the README, so the cards never drift from it."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    merged = 0
    if "Merged contributions" in text:
        block = text.split("Merged contributions", 1)[1].split("<details>", 1)[0]
        merged = sum(1 for line in block.splitlines() if line.startswith("| ["))
    certs = 0
    if "Industry Certifications" in text:
        para = text.split("Industry Certifications", 1)[1].split("</p>", 1)[0]
        certs = para.count("<a href")
    return {"merged": merged, "certs": certs}


def render_highlights(data: dict) -> str:
    lc = data["leetcode"]
    counts = readme_counts()
    tiles = [
        ("10/10", "average client CSAT", GREEN),
        ("5/5", "average Pulse feedback", GREEN),
        ("2", "published AWS samples", SKY),
        ("5x", "TFC ambassador", SKY),
        (str(counts["merged"]), "merged upstream contributions", BLUE_LIGHT),
        (str(counts["certs"]), "industry certifications", BLUE_LIGHT),
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


def credly_badges() -> list[tuple[str, str]]:
    """(title, image url) for each industry certification in the README's Credly block."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    if "Industry Certifications" not in text:
        return []
    para = text.split("Industry Certifications", 1)[1].split("</p>", 1)[0]
    return re.findall(r'title="([^"]+)"><picture><img src="([^"]+)"', para)


PNG_MAGIC = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
JPEG_MAGIC = bytes([0xFF, 0xD8, 0xFF])


def _data_uri(url: str) -> str | None:
    try:
        raw = fetch(url)
    except Exception as exc:
        print(f"badge image failed: {exc}")
        return None
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


def render_certs() -> str | None:
    badges = credly_badges()
    images = [_data_uri(url) for _, url in badges]
    if not badges or any(img is None for img in images):
        return None
    w, h = 840, 250
    n = len(badges)
    col = (w - 32) / n
    parts = [
        svg_open(w, h, "Industry certifications: " + ", ".join(t for t, _ in badges)),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1px}}"
        ".float{animation:float 4s ease-in-out infinite}"
        "@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}</style>",
        '<defs><linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset="0.5" stop-color="#fff" stop-opacity="0.16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="card"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14"/></clipPath></defs>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="30" fill="{BLUE_LIGHT}" font-size="10">{n} INDUSTRY CERTIFICATIONS  |  VERIFIED ON CREDLY</text>',
    ]
    for i, ((title, _), img) in enumerate(zip(badges, images)):
        cx = 16 + col * i + col / 2
        begin = 0.2 + i * 0.15
        short = title.replace("AWS Certified ", "").replace("HashiCorp Certified: ", "").replace(" - ", " ")
        lines = _wrap(short, 18)[:3]
        text = "".join(
            f'<text class="m" x="{cx}" y="{176 + j * 13}" text-anchor="middle" fill="rgba(255,255,255,0.72)" font-size="8.5">{escape(line.upper())}</text>'
            for j, line in enumerate(lines)
        )
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{begin:.2f}s" dur="0.5s" fill="freeze"/>'
            f'<g class="float" style="animation-delay:{i * 0.35:.2f}s">'
            f'<image href="{img}" x="{cx - 48}" y="52" width="96" height="96"/></g>{text}</g>'
        )
    parts.append(
        '<g clip-path="url(#card)"><rect x="-160" y="40" width="120" height="120" fill="url(#shine)" transform="skewX(-20)">'
        '<animateTransform attributeName="transform" type="translate" values="0 0;1100 0" dur="5s" repeatCount="indefinite" additive="sum"/></rect></g>'
    )
    parts.append(SVG_CLOSE)
    return "".join(parts)


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


def write(name: str, content: str) -> None:
    path = OUT / name
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {name} ({len(content):,} bytes)")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_data()
    write("data.json", json.dumps(data, indent=2) + "\n")
    write("terminal.svg", render_terminal(data))
    write("experience.svg", render_experience())
    write("highlights.svg", render_highlights(data))
    write("hero.svg", render_hero(data))
    write("footer.svg", render_footer())
    for name, content in (
        ("certs.svg", render_certs()),
        ("leetcode.svg", render_leetcode(data)),
        ("github.svg", render_github(data)),
        ("ai-stack.svg", render_ai_stack()),
    ):
        if content is None:
            print(f"{name} kept as is: its data fetch failed")
        else:
            write(name, content)
    write("sample-org-governance.svg", render_org_card())
    write("sample-sagemaker-mlops.svg", render_mlops_card())
    for key, num, title, sub in HEADERS:
        for theme in ("dark", "light"):
            write(f"header-{key}-{theme}.svg", render_header(num, title, sub, theme))
    stack = render_stack()
    if stack is not None:
        write("stack.svg", stack)
    else:
        print("stack.svg kept as is: an icon fetch failed")
    write("divider.svg", render_divider())


if __name__ == "__main__":
    main()
