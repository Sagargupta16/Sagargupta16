"""The three aws-samples cards: each sample's architecture as a looping diagram over its title and tags.

A current-look port of render_agentcore_card, render_org_card and render_mlops_card.
Desktop cards are 410 wide (shown at 400) and share one height, so a row of them
stays level when a title wraps. The phone twins are 320 wide on the mobile_cards
engine: the same diagram, then the title and tags as flowing blocks.
"""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
from __future__ import annotations

from collections.abc import Callable

import kit
import mobile_cards
from mobile_cards import Card

DESKTOP = 410
FOOT = 200  # desktop: the diagram sits above this rule, the title and tags below it
TITLE_SIZE, TITLE_STEP = 16, 22
TAG_SIZE, TAG_TRACK, TAG_STEP = 10.5, 1.4, 16
SOURCE = "AWS SAMPLES"  # the first tag on every card
SEPARATOR = "  |  "
WIRE = "rgba(255,255,255,0.16)"
RECT_OPEN = "<rect "
RECT_HIDDEN = '<rect opacity="0" '
RECT_CLOSE = "</rect>"
# The phone engine's root has no class for the diagram's node labels, so the
# phone card carries this rule in its <defs>; phone boxes are narrower and the
# labels drop the desktop's 0.5px tracking.
PHONE_DEFS = (
    f"<style>.l{{font-family:{kit.MONO};font-weight:700;letter-spacing:0px}}</style>"
)


def anim_opacity(values: str, key_times: str) -> str:
    """One opacity loop on the diagrams' 6 s clock."""
    return kit.loop("opacity", values, key_times, 6)


def box(
    x: float, y: float, w: float, h: float, stroke: str, fill: str, extra: str = ""
) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}" stroke="{stroke}" stroke-width="1.2">{extra}</rect>'


# ---------------------------------------------------------------- title and tags


def tag_lines(tags: list[str], width: float, size: float, tracking: float) -> list[str]:
    """The tag line, broken only at a separator so no line starts or ends with one."""
    lines, line = [], ""
    for tag in [SOURCE, *(str(tag).upper() for tag in tags)]:
        joined = f"{line}{SEPARATOR}{tag}" if line else tag
        if line and kit.text_width(joined, size, True, tracking) > width:
            lines.append(line)
            joined = tag
        line = joined
    return [*lines, line]


def title_lines(title: str) -> list[str]:
    """A desktop title wrapped to the card's 20px margins."""
    return mobile_cards.wrap_text(title, DESKTOP - 40, TITLE_SIZE)


def card_frame(
    titles: list[str], tags: list[str], rows: int, tag_rows: int, label: str
) -> list[str]:
    """The desktop card around a diagram drawn above FOOT.

    rows and tag_rows are the most title and tag lines any card in the set
    has: every card takes that height, and a shorter title sits centred in
    its foot.
    """
    w = DESKTOP
    h = FOOT + 62 + TITLE_STEP * (rows - 1) + TAG_STEP * (tag_rows - 1)
    drop = (TITLE_STEP * (rows - len(titles)) + TAG_STEP * (tag_rows - len(tags))) / 2
    tag_y = FOOT + 48 + TITLE_STEP * (len(titles) - 1) + drop
    return [
        kit.svg_open(w, h, label),
        f"<style>.m{{font-family:{kit.MONO};font-weight:700;letter-spacing:{TAG_TRACK}px}}"
        f".l{{font-family:{kit.MONO};font-weight:700;letter-spacing:0.5px}}"
        f".t{{font-family:{kit.SANS};font-weight:700}}</style>",
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="0.6" y2="1">'
        f'<stop offset="0" stop-color="#0e1a24"/><stop offset="0.6" stop-color="{kit.BG}"/></linearGradient>'
        f'<radialGradient id="glow" cx="0.5" cy="0.32" r="0.55"><stop offset="0" stop-color="{kit.BLUE}" stop-opacity="0.16"/>'
        f'<stop offset="1" stop-color="{kit.BLUE}" stop-opacity="0"/></radialGradient></defs>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1:g}" rx="16" fill="url(#bg)" stroke="rgba(255,255,255,0.08)"/>',
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1:g}" rx="16" fill="url(#glow)"/>',
        f'<line x1="0" y1="{FOOT}" x2="{w}" y2="{FOOT}" stroke="rgba(255,255,255,0.07)"/>',
        *(
            f'<text class="t" x="20" y="{FOOT + 28 + TITLE_STEP * i + drop:g}" fill="{kit.INK}" font-size="{TITLE_SIZE}">{kit.esc(line)}</text>'
            for i, line in enumerate(titles)
        ),
        *(
            f'<text class="m" x="20" y="{tag_y + TAG_STEP * i:g}" fill="{kit.BLUE_LIGHT}" font-size="{TAG_SIZE}">{kit.esc(line)}</text>'
            for i, line in enumerate(tags)
        ),
    ]


# ---------------------------------------------------------------- organizations


def org_diagram(mobile: bool = False) -> list[str]:
    """Policies flowing down an OU tree: the GovernanceScene cover, README-sized."""
    parts = []
    node_h = 20
    # (centre x, centre y, width); the phone tree is the same tree on 88px OU boxes
    nodes = {
        "mgmt": (160, 30, 64) if mobile else (205, 30, 76),
        "root": (160, 76, 52) if mobile else (205, 76, 44),
        "sec": (60, 124, 88) if mobile else (80, 124, 66),
        "wl": (160, 124, 88) if mobile else (205, 124, 66),
        "sbx": (260, 124, 88) if mobile else (330, 124, 66),
        "prod": (110, 170, 84) if mobile else (152, 170, 88),
        "dev": (214, 170, 108) if mobile else (262, 170, 112),
    }
    # OU names as the sample writes them: Control Tower's Security and Sandbox (README),
    # Workloads with Production and Non-Production (examples/standard/terraform.tfvars)
    names = {
        "root": "Root",
        "sec": "Security",
        "wl": "Workloads",
        "sbx": "Sandbox",
        "prod": "Production",
        "dev": "Non-Production",
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
            f'stroke="{WIRE}" stroke-width="1.2"/>'
        )
    mx, my, mw = nodes["mgmt"]
    sx, sy, _ = nodes["sec"]
    parts.append(
        f'<path d="M{mx - mw / 2} {my} H{sx} V{sy - node_h / 2}" fill="none" stroke="{kit.BLUE_LIGHT}" '
        f'stroke-width="1.2" stroke-dasharray="4 4" opacity="0">{anim_opacity("0;0;1;1;0", "0;0.68;0.76;0.92;1")}</path>'
    )
    parts.append(
        f'<text class="l" x="{sx + 6}" y="{my + 20}" fill="{kit.BLUE_LIGHT}" font-size="10" opacity="0">DELEGATED'
        f"{anim_opacity('0;0;1;1;0', '0;0.68;0.76;0.92;1')}</text>"
    )
    for key, (x, y, bw) in nodes.items():
        if key == "mgmt":
            parts.append(
                box(
                    x - bw / 2,
                    y - node_h / 2,
                    bw,
                    node_h,
                    kit.BLUE_EDGE,
                    f"{kit.BLUE}22",
                )
            )
            parts.append(
                f'<text class="l" x="{x}" y="{y + 3}" text-anchor="middle" fill="{kit.BLUE_LIGHT}" font-size="10">MGMT</text>'
            )
        else:
            parts.append(
                box(
                    x - bw / 2,
                    y - node_h / 2,
                    bw,
                    node_h,
                    "rgba(255,255,255,0.12)",
                    kit.HAIR_FILL,
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
                kit.BLUE_LIGHT,
                f"{kit.BLUE}30",
                f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="{times}" dur="6s" repeatCount="indefinite"/>',
            ).replace(RECT_OPEN, RECT_HIDDEN, 1)
        )
    # labels above the lit boxes; the two account OUs leave room on the right for their dot
    for key, name in names.items():
        x, y, _ = nodes[key]
        cx = x - 6 if key in ("prod", "dev") else x
        parts.append(
            f'<text class="l" x="{cx}" y="{y + 3.5}" text-anchor="middle" fill="rgba(255,255,255,0.72)" '
            f'font-size="10">{name.upper()}</text>'
        )
    for key, delay in (("prod", 0), ("dev", 0.03)):
        x, y, bw = nodes[key]
        t0 = 0.55 + delay
        parts.append(
            f'<circle cx="{x + bw / 2 - 8}" cy="{y}" r="3.2" fill="{kit.GREEN}" opacity="0">'
            f"{anim_opacity('0;0;1;1;0', f'0;{t0:.2f};{t0 + 0.07:.2f};0.92;1')}</circle>"
        )

    def chip(text: str, pts: list[tuple[float, float]], times: str) -> str:
        values = ";".join(f"{x} {y}" for x, y in pts)
        return (
            f'<g opacity="0"><animateTransform attributeName="transform" type="translate" values="{values}" '
            f'keyTimes="{times}" dur="6s" repeatCount="indefinite"/>'
            f"{anim_opacity('0;1;1;1;1;0', times)}"
            f'<rect x="-17" y="-8" width="34" height="16" rx="4" fill="{kit.BG}" stroke="{kit.BLUE_LIGHT}" stroke-width="1.2"/>'
            f'<text class="l" x="0" y="3" text-anchor="middle" fill="{kit.BLUE_LIGHT}" font-size="10">{text}</text></g>'
        )

    wl, sbx = nodes["wl"], nodes["sbx"]
    rx, ry, rw = nodes["root"]
    # chips start beside the MGMT box, pass beside the root, then park beside their OU
    start = (mx + mw / 2 + 22, my)
    at_root = (rx + rw / 2 + 22, ry)
    # beside Workloads on desktop; on the phone Sandbox sits there, so the chip pins to the box's corner
    scp_hold = (
        (wl[0] + wl[2] / 2 - 10, wl[1] - 14)
        if mobile
        else (wl[0] + wl[2] / 2 + 20, wl[1])
    )
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
    return parts


# ---------------------------------------------------------------- mlops


_ML_WIRES = "ml-wires"  # the clip that keeps the model packet on the wires between the boxes


def mlops_diagram(mobile: bool = False) -> list[str]:
    """Train, gate, deploy, serve, drift back to retrain: the MLOps sample's loop."""
    parts = []
    xs = (40, 100, 160, 220, 280) if mobile else (46, 128, 210, 292, 366)
    stages = list(zip(("DATA", "TRAIN", "GATE", "DEPLOY", "SERVE"), xs))
    train, gate, serve = xs[1], xs[2], xs[4]
    narrow = 44 if mobile else 58  # DEPLOY gets 4px more
    y = 92
    parts.append(
        f'<path d="M{xs[0]} {y} H{serve}" stroke="{kit.HAIR_STRONG}" stroke-width="1.2"/>'
    )
    drift = f"M{serve} {y + 22} C{serve} 170, {train} 170, {train} {y + 22}"
    parts.append(
        f'<path d="{drift}" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="1.2" stroke-dasharray="4 4"/>'
    )
    parts.append(
        f'<path d="{drift}" fill="none" stroke="{kit.AMBER}" stroke-width="1.4" stroke-dasharray="4 4" opacity="0">'
        f"{anim_opacity('0;0;1;1;0', '0;0.66;0.72;0.9;1')}</path>"
    )
    parts.append(
        f'<text class="l" x="{(train + serve) // 2}" y="176" text-anchor="middle" fill="{kit.AMBER}" font-size="10" opacity="0">DRIFT'
        f"{anim_opacity('0;0;1;1;0', '0;0.66;0.72;0.9;1')}</text>"
    )
    for name, x in stages:
        bw = narrow if name != "DEPLOY" else narrow + 4
        stroke = kit.BLUE_EDGE if name in ("TRAIN", "DEPLOY") else kit.HAIR_STRONG
        fill = f"{kit.BLUE}1f" if name in ("TRAIN", "DEPLOY") else kit.HAIR_FILL
        parts.append(box(x - bw / 2, y - 16, bw, 32, stroke, fill))
        parts.append(
            f'<text class="l" x="{x}" y="{y + 3}" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="10">{name}</text>'
        )
    # quality gate flashes green when the model clears it
    parts.append(
        box(gate - narrow // 2, y - 16, narrow, 32, kit.GREEN, f"{kit.GREEN}22", "")
        .replace(RECT_OPEN, RECT_HIDDEN, 1)
        .replace(
            RECT_CLOSE,
            f"{anim_opacity('0;0;1;1;0;0', '0;0.3;0.34;0.46;0.52;1')}</rect>",
        )
    )
    # three architectures train in parallel under TRAIN
    dot, step = (8, 12) if mobile else (10, 16)
    for i, dx in enumerate((-step, 0, step)):
        parts.append(
            f'<rect x="{train + dx - dot // 2}" y="{y + 26}" width="{dot}" height="4" rx="2" fill="{kit.BLUE_LIGHT}" opacity="0.25">'
            f'<animate attributeName="opacity" values="0.25;0.9;0.25" dur="1.2s" begin="{i * 0.2}s" repeatCount="indefinite"/></rect>'
        )
    # the model artefact travelling the pipeline, then the drift arc back to TRAIN
    path = f"M{xs[0]} {y} H{serve}"
    widths = [narrow + 4 if name == "DEPLOY" else narrow for name, _ in stages]
    windows = "".join(
        f'<rect x="{x + bw / 2:g}" y="{y - 5}" width="{nx - nbw / 2 - x - bw / 2:g}" height="10"/>'
        for (x, bw), (nx, nbw) in zip(zip(xs, widths), zip(xs[1:], widths[1:]))
    )
    parts.append(
        f'<clipPath id="{_ML_WIRES}">{windows}</clipPath>'
        f'<g clip-path="url(#{_ML_WIRES})"><circle r="4" fill="{kit.INK}" opacity="0">'
        f'<animateMotion dur="6s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.08;0.62;1" '
        f'calcMode="linear" path="{path}"/>{anim_opacity("0;1;1;0;0", "0;0.08;0.62;0.64;1")}</circle></g>'
    )
    parts.append(
        f'<circle r="3.5" fill="{kit.AMBER}" opacity="0">'
        f'<animateMotion dur="6s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.7;0.9;1" '
        f'calcMode="linear" path="{drift}"/>{anim_opacity("0;0;1;1;0;0", "0;0.69;0.71;0.9;0.92;1")}</circle>'
    )
    parts.append(
        f'<circle cx="{serve}" cy="{y - 24}" r="3" fill="{kit.GREEN}">'
        '<animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/></circle>'
    )
    return parts


# ---------------------------------------------------------------- agentcore

_AC_Y = 66  # request lane
_AC_LY = 146  # release lane
_AC_DIM = kit.META  # 4.5:1 on the card's navy panels
_AC_LABEL = "rgba(255,255,255,0.7)"
_AC_WIRES = "ac-wires"  # the clip that keeps the phone packets on the wires
# (label, centre x, box width) for the request lane; the release lane shares the centres
_AC_LANE = [
    ("MCP CLIENT", 52, 70),
    ("CEDAR GATE", 150, 76),
    ("9 TOOLS", 255, 74),
    ("HARNESS", 358, 72),
]
# the phone lane: 68px boxes on a 74px pitch, room for a 10-letter label in each
_AC_LANE_PHONE = [(name, 49 + 74 * i, 68) for i, (name, _, _) in enumerate(_AC_LANE)]


def _ac_flash(t_on: float, t_off: float, end: float = 1) -> str:
    """Fade in at t_on, hold, fade out by t_off (fractions of the 6s loop)."""
    return anim_opacity(
        "0;0;1;1;0;0",
        f"0;{t_on:.2f};{t_on + 0.02:.2f};{t_off:.2f};{t_off + 0.03:.2f};{end}",
    )


def _ac_lit(
    x: float, y: float, bw: float, bh: float, color: str, t_on: float, t_off: float
) -> str:
    return (
        box(x - bw / 2, y - bh / 2, bw, bh, color, f"{color}26")
        .replace(RECT_OPEN, RECT_HIDDEN, 1)
        .replace(RECT_CLOSE, f"{_ac_flash(t_on, t_off)}</rect>")
    )


def _ac_packets(edges: list[float], starts: list[float]) -> list[str]:
    """Desktop: the denied call stops at the gate; the allowed one runs on to the harness."""
    y = _AC_Y
    span = starts[3] - edges[0]
    at_gate = (starts[1] - edges[0]) / span
    at_tools = (starts[2] - edges[0]) / span
    return [
        (
            f'<circle r="4" fill="{kit.INK}" opacity="0">'
            f'<animateMotion dur="6s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.04;0.12;1" '
            f'calcMode="linear" path="M{edges[0]:g} {y} H{starts[1]:g}"/>{anim_opacity("0;0;1;1;0;0", "0;0.03;0.05;0.15;0.18;1")}</circle>'
        ),
        (
            f'<circle r="4" fill="{kit.INK}" opacity="0">'
            f'<animateMotion dur="6s" repeatCount="indefinite" '
            f'keyPoints="0;0;{at_gate:.4f};{at_gate:.4f};{at_tools:.4f};{at_tools:.4f};1;1" '
            f'keyTimes="0;0.26;0.32;0.4;0.48;0.54;0.6;1" calcMode="linear" path="M{edges[0]:g} {y} H{starts[3]:g}"/>'
            f"{anim_opacity('0;0;1;1;0;0', '0;0.25;0.27;0.6;0.62;1')}</circle>"
        ),
    ]


def _ac_packets_on_wires(edges: list[float], starts: list[float]) -> list[str]:
    """Phone: the same two calls, clipped to the wires so a packet never covers a box label.

    The phone boxes leave 6px of wire between them, and a packet that crossed a
    box painted over its label (9 TOOLS, CEDAR GATE). Here each packet rests in
    the middle of a wire, and the clip hides it while it slides behind a box, so
    it is seen leaving one box and arriving at the next.
    """
    y = _AC_Y
    wires = list(zip(edges, starts[1:]))
    radius = min(4, min(b - a for a, b in wires) / 2)
    stops = [(a + b) / 2 for a, b in wires]
    # both ends sit a radius inside a box, where the clip hides the whole packet
    first, last = edges[0] - radius, starts[3] + radius
    at = [(x - first) / (last - first) for x in stops]
    windows = "".join(
        f'<rect x="{a:g}" y="{y - radius - 1:g}" width="{b - a:g}" height="{2 * radius + 2:g}"/>'
        for a, b in wires
    )
    denied = (
        f'<circle r="{radius:g}" fill="{kit.INK}" opacity="0">'
        f'<animateMotion dur="6s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.04;0.12;1" '
        f'calcMode="linear" path="M{first:g} {y} H{stops[0]:g}"/>{anim_opacity("0;0;1;1;0;0", "0;0.03;0.05;0.15;0.18;1")}</circle>'
    )
    allowed = (
        f'<circle r="{radius:g}" fill="{kit.INK}" opacity="0">'
        f'<animateMotion dur="6s" repeatCount="indefinite" '
        f'keyPoints="0;0;{at[0]:.4f};{at[0]:.4f};{at[1]:.4f};{at[1]:.4f};{at[2]:.4f};{at[2]:.4f};1;1" '
        f'keyTimes="0;0.26;0.32;0.4;0.48;0.54;0.6;0.66;0.7;1" calcMode="linear" path="M{first:g} {y} H{last:g}"/>'
        f"{anim_opacity('0;0;1;1;0;0', '0;0.25;0.27;0.68;0.7;1')}</circle>"
    )
    return [
        f'<clipPath id="{_AC_WIRES}">{windows}</clipPath>',
        f'<g clip-path="url(#{_AC_WIRES})">{denied}{allowed}</g>',
    ]


def _ac_request_lane(lane: list[tuple[str, int, int]], on_wires: bool) -> list[str]:
    """Client, Cedar gate on the gateway, tools runtime, harness; deny then allow."""
    y = _AC_Y
    client_x, (_, gate_x, gate_w) = lane[0][1], lane[1]
    edges = [x + bw / 2 for _, x, bw in lane]
    starts = [x - bw / 2 for _, x, bw in lane]
    parts = [
        f'<path d="M{a:g} {y} H{b:g}" stroke="{WIRE}" stroke-width="1.2"/>'
        for a, b in zip(edges, starts[1:])
    ]
    for name, x, bw in lane:
        accent = name in ("CEDAR GATE", "HARNESS")
        parts.extend(
            [
                box(
                    x - bw / 2,
                    y - 16,
                    bw,
                    32,
                    kit.BLUE_EDGE if accent else kit.HAIR_STRONG,
                    f"{kit.BLUE}1f" if accent else kit.HAIR_FILL,
                ),
                f'<text class="l" x="{x}" y="{y + 3}" text-anchor="middle" fill="{_AC_LABEL}" font-size="10">{name}</text>',
            ]
        )
    parts.append(
        f'<text class="l" x="{gate_x}" y="{y - 26}" text-anchor="middle" fill="{kit.BLUE_LIGHT}" font-size="10">DEFAULT DENY</text>'
    )
    parts.extend(
        f'<text class="l" x="{client_x}" y="{y + 30 + i * 12}" text-anchor="middle" fill="{_AC_DIM}" font-size="10">{client}</text>'
        for i, client in enumerate(("CLAUDE CODE", "CODEX", "KIRO"))
    )
    # first call is not on the allow list and stops at the gate; the second passes
    parts.extend(
        [
            _ac_lit(gate_x, y, gate_w, 32, kit.AMBER, 0.12, 0.2),
            f'<text class="l" x="{gate_x}" y="{y + 30}" text-anchor="middle" fill="{kit.AMBER}" font-size="10" opacity="0">DENY{_ac_flash(0.12, 0.2)}</text>',
            _ac_lit(gate_x, y, gate_w, 32, kit.GREEN, 0.32, 0.42),
            f'<text class="l" x="{gate_x}" y="{y + 30}" text-anchor="middle" fill="{kit.GREEN}" font-size="10" opacity="0">ALLOW{_ac_flash(0.32, 0.42)}</text>',
        ]
    )
    parts.extend(
        _ac_packets_on_wires(edges, starts) if on_wires else _ac_packets(edges, starts)
    )
    return parts


def _ac_tools_and_harness(lane: list[tuple[str, int, int]]) -> list[str]:
    """8 tools plus ask_architect, which hands the request to the hosted agent."""
    y = _AC_Y
    tools_x, (_, harness_x, harness_w) = lane[2][1], lane[3]
    ask_pulse = anim_opacity("0.85;0.85;1;1;0.85;0.85", "0;0.48;0.5;0.62;0.66;1")
    parts = []
    for i in range(9):
        col, row = i % 3, i // 3
        cx, cy = tools_x - 14 + col * 14, y + 24 + row * 8
        ask = i == 8
        fill = kit.BLUE_LIGHT if ask else "rgba(255,255,255,0.18)"
        parts.append(
            f'<rect x="{cx - 5}" y="{cy}" width="10" height="5" rx="1.5" fill="{fill}"'
            f' opacity="{0.85 if ask else 1}">'
            + (ask_pulse if ask else "")
            + RECT_CLOSE
        )
    parts.extend(
        [
            f'<text class="l" x="{tools_x}" y="{y + 56}" text-anchor="middle" fill="{kit.BLUE_LIGHT}" font-size="10" opacity="0.85">ask_architect'
            f"{ask_pulse}</text>",
            _ac_lit(harness_x, y, harness_w, 32, kit.BLUE_LIGHT, 0.6, 0.7),
        ]
    )
    parts.extend(
        f'<text class="l" x="{harness_x}" y="{y + 30 + i * 12}" text-anchor="middle" fill="{kit.BLUE_LIGHT}" font-size="10" opacity="0.85">{label}'
        f"{anim_opacity('0.85;0.85;1;1;0.85;0.85', '0;0.6;0.62;0.7;0.73;1')}</text>"
        for i, label in enumerate(("3 SKILLS", "MEMORY"))
    )
    return parts


def _ac_release_lane(lane: list[tuple[str, int, int]]) -> list[str]:
    """A version reaches PROD only after AgentCore Evaluations passes it."""
    ly = _AC_LY
    xs = [x for _, x, _ in lane]
    stages = list(
        zip(("BUILD", "DEFAULT", "EVAL", "PROD"), xs, (0.66, 0.72, 0.78, 0.88))
    )
    parts = []
    for (_, a, _), (_, b, t) in zip(stages, stages[1:]):
        parts.extend(
            [
                f'<path d="M{a + 32} {ly} H{b - 32}" stroke="{WIRE}" stroke-width="1.2"/>',
                f'<path d="M{a + 32} {ly} H{b - 32}" stroke="{kit.BLUE_LIGHT}" stroke-width="1.4" opacity="0">'
                f"{_ac_flash(t - 0.03, 0.95)}</path>",
            ]
        )
    for name, x, t in stages:
        parts.extend(
            [
                box(x - 32, ly - 12, 64, 24, kit.HAIR_STRONG, kit.HAIR_FILL),
                _ac_lit(
                    x,
                    ly,
                    64,
                    24,
                    kit.GREEN if name == "PROD" else kit.BLUE_LIGHT,
                    t,
                    0.95,
                ),
            ]
        )
        if name == "EVAL":
            parts.append(_ac_lit(x, ly, 64, 24, kit.GREEN, 0.83, 0.95))
        parts.append(
            f'<text class="l" x="{x}" y="{ly + 3}" text-anchor="middle" fill="{_AC_LABEL}" font-size="10">{name}</text>'
        )
    parts.extend(
        [
            f'<text class="l" x="{xs[2]}" y="{ly + 26}" text-anchor="middle" fill="{kit.GREEN}" font-size="10" opacity="0">PASS{_ac_flash(0.83, 0.95)}</text>',
            f'<circle cx="{xs[3] + 32 - 8}" cy="{ly}" r="3" fill="{kit.GREEN}">'
            '<animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/></circle>',
        ]
    )
    return parts


def agentcore_diagram(mobile: bool = False) -> list[str]:
    """A call denied then allowed by the Cedar gate, ask_architect into the harness, eval-gated PROD."""
    lane = _AC_LANE_PHONE if mobile else _AC_LANE
    return [
        *_ac_request_lane(lane, on_wires=mobile),
        *_ac_tools_and_harness(lane),
        *_ac_release_lane(lane),
    ]


# ---------------------------------------------------------------- the cards

# key -> (diagram, aria-label, the first and last y the diagram draws at)
DIAGRAMS: dict[str, tuple[Callable[[bool], list[str]], str, tuple[int, int]]] = {
    "agentcore-harness": (
        agentcore_diagram,
        "Animated diagram: a default-deny Cedar gate on AgentCore Gateway blocks one MCP call "
        "and allows the next to 9 tools, ask_architect runs the harness with 3 skills and memory, "
        "and a version reaches PROD only after an evaluation passes",
        (32, 174),
    ),
    "org-governance": (
        org_diagram,
        "Animated diagram: SCP and RCP policies attaching down an AWS Organizations OU tree: "
        "Root, Security, Workloads with Production and Non-Production, Sandbox",
        (20, 180),
    ),
    "sagemaker-mlops": (
        mlops_diagram,
        "Animated diagram: SageMaker pipeline trains, passes a quality gate, deploys, and retrains on drift",
        (64, 178),
    ),
}


def desktop_card(sample: dict, rows: int, tag_rows: int) -> str:
    """One 410px card; rows and tag_rows are the set's tallest title and tag blocks."""
    diagram, label, _ = DIAGRAMS[sample["key"]]
    titles = title_lines(sample["title"])
    tags = tag_lines(sample["tags"], DESKTOP - 40, TAG_SIZE, TAG_TRACK)
    return "".join(
        [
            *card_frame(titles, tags, rows, tag_rows, label),
            *diagram(False),
            kit.SVG_CLOSE,
        ]
    )


def phone_card(sample: dict) -> str:
    """One 320px card: the phone diagram as a raw block, then a rule, the title and the tags."""
    diagram, label, (top, bottom) = DIAGRAMS[sample["key"]]
    card = Card(label)
    card.raw(
        f'<g transform="translate(0 {-top})">{"".join(diagram(True))}</g>',
        bottom - top + 6,
    )
    card.divider()
    card.lines(sample["title"], size=TITLE_SIZE, weight=700)
    card.y += 4
    with card.block():
        for line in tag_lines(
            sample["tags"], mobile_cards.CONTENT_WIDTH, mobile_cards.MICRO, kit.TRACK
        ):
            card.lines(
                line,
                size=mobile_cards.MICRO,
                color=kit.BLUE_LIGHT,
                weight=700,
                mono=True,
            )
    return card.finish(defs=PHONE_DEFS)


def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for every sample in ctx that has a diagram, desktop and -mobile."""
    samples = [sample for sample in ctx["samples"] if sample["key"] in DIAGRAMS]
    # one height for the desktop set: the tallest title block and the tallest tag block
    rows = max((len(title_lines(s["title"])) for s in samples), default=1)
    tag_rows = max(
        (len(tag_lines(s["tags"], DESKTOP - 40, TAG_SIZE, TAG_TRACK)) for s in samples),
        default=1,
    )
    files = {}
    for sample in samples:
        files[f"sample-{sample['key']}.svg"] = desktop_card(sample, rows, tag_rows)
        files[f"sample-{sample['key']}-mobile.svg"] = phone_card(sample)
    return files
