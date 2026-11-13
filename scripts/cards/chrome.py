"""The page chrome in its current look: section headers, buttons, get-this-card strips, the footer and the divider."""

# Copyright (c) Sagar Gupta. Distributed under the repository's MIT license.
#
# A port of the drawing code these files had in render-svgs.py and
# mobile_cards.py, on kit's palette and the phone engine. The look is kept:
# each desktop file carries its own small <style> with the tracking it always
# had. What changed is noted where it happens: the footer comet, escaped
# button labels, counts and header copy read from ctx, balanced phone kickers.
from __future__ import annotations

import kit
import mobile_cards as mobile

WIDE = 840
ARROW = chr(0x2192)  # the phone cards' link arrow

# Headers sit on the page with no background, so each has a dark and a light
# file. The light blue that reads on the dark page is 2.5:1 on white; light
# pages get the deeper pair.
THEMES = ("dark", "light")
LIGHT_INK, LIGHT_KICKER, LIGHT_EDGE = kit.BG, "#1d4ed8", "#0284c7"
LIGHT_INK_PHONE = "#17212b"
RULES = {"dark": "rgba(255,255,255,0.10)", "light": "rgba(11,16,18,0.12)"}
HEADER_DOTS = {"dark": "rgba(255,255,255,0.45)", "light": "rgba(11,16,18,0.55)"}
NEUTRAL_RULE = "rgba(127,127,127,0.28)"  # reads on both GitHub themes

FOOTER_EYEBROW = "SAGAR GUPTA  |  AWS PROFESSIONAL SERVICES"
FOOTER_LINES = ["Thanks for visiting", "More at sagargupta.online"]
FOOTER_DISCLAIMER_INK = "#a8b4c1"
WAVE = "M0 110 C 140 80, 280 140, 420 110 S 700 80, 840 110"
# The comet: a dot that leads and a tail behind it. Both are dashes of the
# same wave, measured in the same pathLength units and moved by the same
# offsets, so they cannot drift apart (they used to run at 211 and 255 px/s).
WAVE_UNITS = 1000
COMET_TAIL = 142  # 120px of the wave's 845px
COMET_DOT = 0.1  # a dash this short is drawn as its round cap: the dot
COMET_REST = 300  # where the head sits in a still frame
COMET_SECONDS = 4


def _mono_style(tracking: float) -> str:
    return f"<style>.m{{font-family:{kit.MONO};font-weight:700;letter-spacing:{tracking:g}px}}</style>"


def _sweep(gradient_id: str, edge: str, middle: str) -> str:
    """A light that fades in and out along its length, for a rect that runs a rule."""
    return (
        f'<linearGradient id="{gradient_id}" x1="0" x2="1"><stop offset="0" stop-color="{edge}" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="{middle}"/><stop offset="1" stop-color="{edge}" stop-opacity="0"/></linearGradient>'
    )


def _slide(distance: float, dur: float, additive: bool = False) -> str:
    end = ' additive="sum"' if additive else ""
    return (
        f'<animateTransform attributeName="transform" type="translate" values="0 0;{distance:g} 0" '
        f'dur="{dur:g}s" repeatCount="indefinite"{end}/>'
    )


# ---------------------------------------------------------------- section headers
def _kicker(number: str, subtitle: str) -> str:
    return f"{number}  /  {subtitle.upper()}"


def render_header(number: str, title: str, subtitle: str, theme: str) -> str:
    w, h = WIDE, 64
    dark = theme == "dark"
    ink = kit.INK if dark else LIGHT_INK
    kicker = kit.BLUE_LIGHT if dark else LIGHT_KICKER
    edge = kit.SKY if dark else LIGHT_EDGE
    return "".join(
        [
            kit.svg_open(w, h, title),
            f"<defs>{_sweep('sweep', edge, kicker)}</defs>",
            f'<rect x="0" y="12" width="4" height="30" rx="2" fill="{kit.BLUE}"/>',
            f'<text x="18" y="24" fill="{kicker}" font-family="{kit.MONO}" font-size="11" font-weight="700" '
            f'letter-spacing="2">{kit.esc(_kicker(number, subtitle))}</text>',
            f'<text x="18" y="46" fill="{ink}" font-family="{kit.SANS}" font-size="24" font-weight="700">{kit.esc(title)}</text>',
            f'<line x1="0" y1="{h - 4}" x2="{w}" y2="{h - 4}" stroke="{RULES[theme]}" stroke-width="1"/>',
            f'<rect x="-160" y="{h - 5}" width="160" height="2" fill="url(#sweep)">{_slide(1000, 4.5)}</rect>',
            f'<circle cx="{w - 8}" cy="30" r="3" fill="{HEADER_DOTS[theme]}"/>',
            kit.SVG_CLOSE,
        ]
    )


def render_header_phone(number: str, title: str, subtitle: str, theme: str) -> str:
    dark = theme == "dark"
    color = kit.BLUE_LIGHT if dark else LIGHT_KICKER
    edge = kit.SKY if dark else LIGHT_EDGE
    card = mobile.Card(title, color)
    card.y = 10
    # the engine balances what it wraps, so a kicker never leaves one word on its last line
    card.lines(
        _kicker(number, subtitle), size=mobile.MICRO, color=color, weight=700, mono=True
    )
    card.y += 2
    card.lines(title, size=20, weight=750, color=kit.INK if dark else LIGHT_INK_PHONE)
    w, h = card.width, int(card.y + 14)
    # No frame: the header sits on the page like the desktop one, with its accent
    # bar and the light that runs along its rule. The sans stack is an attribute
    # on the root so the kicker's own mono attribute wins.
    return (
        f'{kit.svg_open(w, h, title)[:-1]} font-family="{kit.SANS}">'
        f"<defs>{_sweep('sweep', edge, color)}</defs>"
        f'<rect x="0" y="12" width="4" height="{card.y - 14:g}" rx="2" fill="{color}"/>'
        + "".join(card.parts)
        + f'<line x1="0" y1="{h - 4}" x2="{w}" y2="{h - 4}" stroke="{RULES[theme]}" stroke-width="1"/>'
        f'<rect x="-120" y="{h - 5}" width="120" height="2" fill="url(#sweep)">{_slide(w + 120, 3.6)}</rect>'
        + kit.SVG_CLOSE
    )


def render_divider() -> str:
    w, h = WIDE, 14
    return "".join(
        [
            kit.svg_open(w, h, "divider"),
            f"<defs>{_sweep('pulse', kit.BLUE, kit.BLUE_LIGHT)}</defs>",
            f'<line x1="0" y1="7" x2="{w}" y2="7" stroke="{NEUTRAL_RULE}" stroke-width="1"/>',
            f'<circle cx="{w / 2:g}" cy="7" r="2.5" fill="{kit.BLUE_EITHER}"/>',
            f'<rect x="-220" y="6" width="220" height="2" fill="url(#pulse)">{_slide(1060, 3.6)}</rect>',
            kit.SVG_CLOSE,
        ]
    )


# ---------------------------------------------------------------- buttons
def _button_label(label: str, has_icon: bool, w: int) -> str:
    # escaped: a label is data from ctx and may one day hold an ampersand
    content = kit.esc(label.upper())
    if has_icon:
        return f'<text class="m" x="40" y="28" fill="{kit.INK}" font-size="12">{content}</text>'
    return f'<text class="m" x="{w / 2:g}" y="28" text-anchor="middle" fill="{kit.INK}" font-size="12">{content}</text>'


def render_connect_button(label: str, icon_path: str | None, index: int) -> str:
    """One 128px link button; its tint flashes in turn with the others in the row."""
    w, h = 128, 44
    outline = f'x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="22"'
    icon = (
        '<svg x="12" y="12" width="20" height="20" viewBox="0 0 24 24">'
        f'<path d="{kit.esc(icon_path)}" fill="rgba(255,255,255,0.9)"/></svg>'
        if icon_path
        else ""
    )
    return "".join(
        [
            kit.svg_open(w, h, label),
            _mono_style(0.4),
            f'<rect {outline} fill="{kit.CARD}" stroke="{kit.BLUE_LIGHT}66"/>',
            f'<rect {outline} fill="{kit.BLUE}22" opacity="0">'
            '<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;0.1;0.2;1" dur="5s" '
            f'begin="{index * 0.5:.1f}s" repeatCount="indefinite"/></rect>',
            icon,
            _button_label(label, bool(icon_path), w),
            kit.SVG_CLOSE,
        ]
    )


def cta_labels(ctx: dict) -> dict[str, tuple[str, bool]]:
    """{file stem: (label, primary)} for the wide buttons, counted from ctx.

    The portfolio button is left out while the project count is unknown: a
    made-up number is worse than a missing link.
    """
    labels: dict[str, tuple[str, bool]] = {}
    count = int(ctx.get("project_count") or 0)
    if count:
        labels["cta-portfolio"] = (f"View all {count} projects", True)
    tools = len(ctx.get("tools") or [])
    labels["cta-community"] = (f"See all {tools} community tools", False)
    labels["cta-profile"] = ("Back to profile", False)
    return labels


def render_cta(label: str, primary: bool) -> str:
    w, h = 250, 48
    outline = f'x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="24"'
    return "".join(
        [
            kit.svg_open(w, h, label),
            _mono_style(1.4),
            f'<rect {outline} fill="{kit.BLUE if primary else kit.CARD}" stroke="{kit.BLUE_LIGHT}88"/>',
            f'<text class="m" x="{w / 2:g}" y="29" text-anchor="middle" fill="#ffffff" font-size="11.5">{kit.esc(label.upper())}</text>',
            f'<rect {outline} fill="#ffffff" opacity="0">'
            '<animate attributeName="opacity" values="0;0.12;0" dur="3s" repeatCount="indefinite"/></rect>',
            kit.SVG_CLOSE,
        ]
    )


# ---------------------------------------------------------------- get-this-card strips
def get_card_label(repo: str, card: str) -> str:
    return f"Get the {card} for your own profile: Sagargupta16/{repo}"


def render_get_this_card(repo: str, card: str) -> str:
    """A slim strip naming the public action that makes this kind of card."""
    w, h = WIDE, 40
    this = "THESE" if card.endswith("cards") else "THIS"
    return "".join(
        [
            kit.svg_open(w, h, get_card_label(repo, card)),
            _mono_style(1.3),
            '<defs><linearGradient id="sweep" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset="0.5" stop-color="#fff" stop-opacity="0.07"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<clipPath id="c"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="12"/></clipPath></defs>',
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{kit.CARD}" stroke="{kit.BLUE_LIGHT}40"/>',
            f'<circle cx="22" cy="20" r="3.5" fill="{kit.GREEN}"><animate attributeName="opacity" values="1;0.35;1" dur="1.8s" repeatCount="indefinite"/></circle>',
            f'<text class="m" x="36" y="24" fill="rgba(255,255,255,0.6)" font-size="{kit.MICRO:g}">GET {this} {kit.esc(card.upper())} FOR YOUR PROFILE</text>',
            f'<text class="m" x="{w - 22}" y="24" text-anchor="end" fill="{kit.BLUE_LIGHT}" font-size="{kit.MICRO:g}">SAGARGUPTA16/{kit.esc(repo.upper())}  -&gt;</text>',
            f'<g clip-path="url(#c)"><rect x="-160" y="0" width="140" height="{h}" fill="url(#sweep)" transform="skewX(-20)">'
            f"{_slide(1200, 5, additive=True)}</rect></g>",
            kit.SVG_CLOSE,
        ]
    )


def render_get_this_card_phone(card: str) -> str:
    phone = mobile.Card(f"Get the {card} for your own profile")
    phone.lines(f"Get the {card} {ARROW}", size=14, color=kit.BLUE_LIGHT, weight=650)
    phone.lines("Add it to your own profile README.", size=12, color=kit.BODY)
    return phone.finish()


# ---------------------------------------------------------------- footer
def _comet_stroke(color: str, width: float, dash: float, lead: float) -> str:
    """One dash of the wave, placed against the comet's head.

    The head runs from 0 to WAVE_UNITS + COMET_TAIL, so the tail has left the
    card when the loop restarts. A dash offset of `lead - head` starts this
    dash `lead` units behind the head: the tail's length for the tail, 0 for
    the dot.
    """
    end = WAVE_UNITS + COMET_TAIL
    return (
        f'<path d="{WAVE}" fill="none" stroke="{color}" stroke-width="{width:g}" stroke-linecap="round" '
        f'pathLength="{WAVE_UNITS}" stroke-dasharray="{dash:g} {2 * end}" stroke-dashoffset="{lead - COMET_REST:g}">'
        f'<animate attributeName="stroke-dashoffset" values="{lead:g};{lead - end:g}" dur="{COMET_SECONDS}s" '
        'repeatCount="indefinite"/></path>'
    )


def render_footer(disclaimer: str) -> str:
    w, h = WIDE, 172
    return "".join(
        [
            kit.svg_open(w, h, f"{'. '.join(FOOTER_LINES)}. {disclaimer}".strip()),
            f"<style>.s{{font-family:{kit.SANS};font-weight:800}}.m{{font-family:{kit.MONO};font-weight:700;letter-spacing:2px}}"
            f".d{{font-family:{kit.SANS};font-weight:500}}</style>",
            # an opaque card like every other one: on GitHub's light page a transparent
            # footer drew its white lines on white
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{kit.RADIUS}" fill="{kit.BG}" stroke="rgba(255,255,255,0.08)"/>',
            f'<text class="m" x="{w / 2:g}" y="34" text-anchor="middle" fill="{kit.BLUE_LIGHT}" font-size="{kit.MICRO:g}">{kit.esc(FOOTER_EYEBROW)}</text>',
            kit.rotating(FOOTER_LINES, w / 2, 78, "s", 30, kit.INK, anchor="middle"),
            f'<path d="{WAVE}" fill="none" stroke="rgba(127,127,127,0.25)" stroke-width="1.2"/>',
            _comet_stroke(kit.BLUE_LIGHT, 2, COMET_TAIL, COMET_TAIL),  # the tail
            _comet_stroke(kit.SKY, 7, COMET_DOT, 0),  # the dot at its head
            f'<text class="d" x="{w / 2:g}" y="158" text-anchor="middle" fill="{FOOTER_DISCLAIMER_INK}" font-size="11">{kit.esc(disclaimer)}</text>',
            kit.SVG_CLOSE,
        ]
    )


def render_footer_phone(disclaimer: str) -> str:
    card = mobile.Card(
        f"Thanks for visiting. Explore Sagar Gupta's portfolio. {disclaimer}".strip()
    )
    card.label("Thanks for visiting")
    card.lines("Explore the projects and the work behind them.", color=kit.BODY)
    card.y += 10
    card.lines(f"Visit my portfolio {ARROW}", size=16, weight=700)
    card.lines(
        "SAGARGUPTA.ONLINE",
        size=mobile.MICRO,
        color=kit.BLUE_LIGHT,
        weight=700,
        mono=True,
    )
    if disclaimer:
        card.y += 10
        card.lines(disclaimer, size=12, color=kit.META)
    return card.finish()


# ---------------------------------------------------------------- the lane
def render(data: dict, ctx: dict) -> dict[str, str]:
    """Return {file name: svg text} for the headers, buttons, strips, footer and divider at both widths."""
    files: dict[str, str] = {}
    for key, number, title, subtitle in ctx["headers"]:
        for theme in THEMES:
            files[f"header-{key}-{theme}.svg"] = render_header(
                number, title, subtitle, theme
            )
            files[f"header-{key}-{theme}-mobile.svg"] = render_header_phone(
                number, title, subtitle, theme
            )
    for index, button in enumerate(ctx["connect"]):
        files[f"connect-{button['key']}.svg"] = render_connect_button(
            button["label"], button.get("icon"), index
        )
    for name, (label, primary) in cta_labels(ctx).items():
        files[f"{name}.svg"] = render_cta(label, primary)
    for key, repo, card in ctx["get_cards"]:
        files[f"get-{key}.svg"] = render_get_this_card(repo, card)
        files[f"get-{key}-mobile.svg"] = render_get_this_card_phone(card)
    disclaimer = ctx.get("disclaimer") or ""
    files["footer.svg"] = render_footer(disclaimer)
    files["footer-mobile.svg"] = render_footer_phone(disclaimer)
    files["divider.svg"] = render_divider()
    return files
