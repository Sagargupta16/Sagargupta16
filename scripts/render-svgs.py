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

import json
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

# Career milestones for the timeline, oldest first. Two short lines each so
# every label fits its 168 px column; the last one is the current role.
MILESTONES = [
    ("2021", "MCA, NIT Warangal", "NIMCET AIR 208"),
    ("2023", "Software Dev Intern", "Ikarus-3D, Mohali"),
    ("2024", "ProServe DevOps Intern", "AWS, Hyderabad"),
    ("2024", "Cloud Consultant", "AWS ProServe"),
    ("2026", "Lead DevOps Consultant", "RWS engagement"),
]


SVG_CLOSE = "</svg>"
ALLOWED_HOSTS = ("https://leetcode.com/", "https://skillicons.dev/")


def fetch(url: str, body: dict | None = None, timeout: int = 20) -> bytes:
    # https only, and only the two hosts this script reads from
    if not url.startswith(ALLOWED_HOSTS):
        raise ValueError(f"refusing to fetch {url}")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "Sagargupta16-readme-svgs",
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
        },
    )
    # scheme and host were checked against ALLOWED_HOSTS above
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return resp.read()


def load_data() -> dict:
    data = json.loads(json.dumps(DEFAULT_DATA))
    if DATA_FILE.exists():
        data.update(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    query = (
        "query($u:String!){userContestRanking(username:$u){rating topPercentage "
        "attendedContestsCount badge{name}} matchedUser(username:$u){submitStats"
        "{acSubmissionNum{difficulty count}}}}"
    )
    try:
        raw = fetch(
            "https://leetcode.com/graphql",
            {"query": query, "variables": {"u": LEETCODE_USER}},
        )
        d = json.loads(raw)["data"]
        rank = d["userContestRanking"]
        solved = next(
            x["count"]
            for x in d["matchedUser"]["submitStats"]["acSubmissionNum"]
            if x["difficulty"] == "All"
        )
        data["leetcode"] = {
            "badge": (rank.get("badge") or {}).get("name") or data["leetcode"]["badge"],
            "rating": round(rank["rating"]),
            "top": round(rank["topPercentage"], 2),
            "contests": rank["attendedContestsCount"],
            "solved": solved,
        }
    except Exception as exc:  # keep the last good values
        print(f"leetcode fetch failed, reusing cached values: {exc}")
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


def render_experience() -> str:
    """A rail that draws itself left to right, lighting each milestone as it passes."""
    w, h = 840, 196
    left, right, rail_y = 84, 756, 92
    step = (right - left) / (len(MILESTONES) - 1)
    draw = 3.0  # seconds for the rail to reach the last milestone
    parts = [
        svg_open(
            w, h, "Career timeline: " + ", ".join(f"{y} {a}" for y, a, _ in MILESTONES)
        ),
        f"<style>.m{{font-family:{MONO};font-weight:700;letter-spacing:1.4px}}"
        f".t{{font-family:{SANS};font-weight:700}}"
        ".now{animation:ring 2.2s ease-out infinite;transform-origin:center;transform-box:fill-box}"
        "@keyframes ring{0%{opacity:0.9;transform:scale(1)}100%{opacity:0;transform:scale(2.6)}}</style>",
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="rgba(255,255,255,0.08)"/>',
        f'<text class="m" x="24" y="30" fill="{BLUE_LIGHT}" font-size="10">CAREER</text>',
        f'<line x1="{left}" y1="{rail_y}" x2="{right}" y2="{rail_y}" stroke="rgba(255,255,255,0.10)" stroke-width="2"/>',
        f'<line x1="{left}" y1="{rail_y}" x2="{right}" y2="{rail_y}" stroke="{BLUE}" stroke-width="2" '
        f'stroke-dasharray="{right - left}" stroke-dashoffset="{right - left}">'
        f'<animate attributeName="stroke-dashoffset" from="{right - left}" to="0" dur="{draw}s" begin="0.3s" fill="freeze"/></line>',
    ]
    last = len(MILESTONES) - 1
    for i, (year, role, where) in enumerate(MILESTONES):
        x = left + i * step
        at = 0.3 + draw * i / last
        current = i == last
        dot = GREEN if current else BLUE_LIGHT
        if current:
            parts.append(
                f'<circle class="now" cx="{x}" cy="{rail_y}" r="7" fill="none" stroke="{GREEN}" stroke-width="1.5" opacity="0">'
                f'<set attributeName="opacity" to="1" begin="{at:.2f}s" fill="freeze"/></circle>'
            )
        parts.append(
            f'<circle cx="{x}" cy="{rail_y}" r="6" fill="{BG}" stroke="{dot}" stroke-width="2" opacity="0.25">'
            f'<animate attributeName="opacity" to="1" begin="{at:.2f}s" dur="0.3s" fill="freeze"/></circle>'
        )
        parts.append(
            f'<circle cx="{x}" cy="{rail_y}" r="2.6" fill="{dot}" opacity="0">'
            f'<animate attributeName="opacity" to="1" begin="{at:.2f}s" dur="0.3s" fill="freeze"/></circle>'
        )
        year_fill = GREEN if current else BLUE_LIGHT
        label = f"{year}  NOW" if current else year
        parts.append(
            f'<text class="m" x="{x}" y="{rail_y - 22}" text-anchor="middle" fill="{year_fill}" font-size="10" opacity="0.35">{label}'
            f'<animate attributeName="opacity" to="1" begin="{at:.2f}s" dur="0.3s" fill="freeze"/></text>'
        )
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{at + 0.1:.2f}s" dur="0.4s" fill="freeze"/>'
            f'<text class="t" x="{x}" y="{rail_y + 32}" text-anchor="middle" fill="#f3f4f6" font-size="13">{escape(role)}</text>'
            f'<text class="m" x="{x}" y="{rail_y + 52}" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-size="9">'
            f"{escape(where.upper())}</text></g>"
        )
    parts.append(SVG_CLOSE)
    return "".join(parts)


# ---------------------------------------------------------------- highlights


def readme_counts() -> dict:
    """Counts that already live in the README, so the highlights card never drifts from it."""
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
        ("135+", "AWS accounts onboarded", BLUE_LIGHT),
        ("~90%", "faster account setup", BLUE_LIGHT),
        ("1000+", "preventive controls, CCMv4", BLUE_LIGHT),
        ("10/10", "client CSAT", BLUE_LIGHT),
        ("2", "published AWS samples", SKY),
        (str(counts["merged"]), "merged upstream contributions", SKY),
        (lc["badge"], f"LeetCode, top {lc['top']}%", AMBER),
        (str(counts["certs"]), "industry certifications", SKY),
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
        live = accent == AMBER
        dot = (
            f'<circle cx="{x + tw - 14}" cy="{y + 16}" r="3" fill="{GREEN}">'
            '<animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/></circle>'
            if live
            else ""
        )
        parts.append(
            f'<g opacity="0"><animate attributeName="opacity" to="1" begin="{begin:.2f}s" dur="0.45s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 10" to="0 0" begin="{begin:.2f}s" dur="0.45s" fill="freeze"/>'
            f'<rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="12" fill="{CARD}" stroke="rgba(255,255,255,0.08)"/>'
            f'<rect x="{x}" y="{y + 18}" width="3" height="26" rx="1.5" fill="{accent}"/>'
            f'<text class="v" x="{x + 18}" y="{y + 42}" fill="#f3f4f6" font-size="26">{escape(value)}</text>'
            f'<text class="m" x="{x + 18}" y="{y + 64}" fill="rgba(255,255,255,0.5)" font-size="8.5">{escape(label.upper())}</text>'
            f"{dot}</g>"
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
