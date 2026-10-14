"""Create static companions for the profile generators' SVG animations.

Finite entrances finish, decorative loops retain their base state, and rotating
text chooses its first phrase. These rules preserve content that would disappear
if animation elements were simply deleted.
"""

from pathlib import Path
import re
from typing import Iterator
import xml.etree.ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ANIMATION_TAGS = {"animate", "animateTransform", "animateMotion", "set"}
KEYFRAMES = re.compile(r"@(?:-\w+-)?keyframes\s+([\w-]+)", re.IGNORECASE)
MOTION_PROPERTY = re.compile(r"^(?:-\w+-)?(?:animation|transition)(?:-|$)")
NUMBER = r"[-+]?(?:\d*\.?\d+)(?:[eE][-+]?\d+)?"
PATH_START = re.compile(rf"^\s*[Mm]\s*({NUMBER})[\s,]+({NUMBER})")

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _css_blocks(css: str) -> Iterator[tuple[str, str]]:
    """Walk the generated stylesheets without truncating nested keyframes."""
    cursor = 0
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    while (opening := css.find("{", cursor)) != -1:
        depth = 1
        closing = opening + 1
        quote = ""
        while closing < len(css) and depth:
            character = css[closing]
            if quote:
                if character == "\\":
                    closing += 1
                elif character == quote:
                    quote = ""
            elif character in "\"'":
                quote = character
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
            closing += 1
        if depth:
            raise ValueError("Unbalanced CSS block in SVG")
        yield css[cursor:opening].strip(), css[opening + 1 : closing - 1]
        cursor = closing


def _declarations(style: str) -> dict[str, str]:
    declarations = {}
    for declaration in style.split(";"):
        property_name, separator, value = declaration.partition(":")
        if separator:
            declarations[property_name.strip()] = value.strip()
    return declarations


def _style_text(declarations: dict[str, str]) -> str:
    return ";".join(f"{name}:{value}" for name, value in declarations.items())


def _final_keyframe(body: str) -> dict[str, str]:
    last_position = -1.0
    final = {}
    for selectors, declarations in _css_blocks(body):
        for selector in selectors.split(","):
            selector = selector.strip()
            position = {"from": 0.0, "to": 100.0}.get(selector)
            if position is None and selector.endswith("%"):
                position = float(selector[:-1])
            if position is not None and position >= last_position:
                final = _declarations(declarations)
                last_position = position
    return final


def _keyframes(css: str) -> dict[str, dict[str, str]]:
    frames = {}
    for selector, body in _css_blocks(css):
        match = KEYFRAMES.fullmatch(selector)
        if match:
            frames[match.group(1)] = _final_keyframe(body)
        elif selector.startswith("@"):
            frames.update(_keyframes(body))
    return frames


def _static_declarations(style: str, frames: dict[str, dict[str, str]]) -> str:
    declarations = _declarations(style)
    animation = " ".join(
        value
        for name, value in declarations.items()
        if re.fullmatch(r"(?:-\w+-)?animation(?:-name)?", name)
    )
    iteration_count = declarations.get("animation-iteration-count", "")
    if "infinite" not in f"{animation} {iteration_count}".split():
        for name in re.findall(r"[\w-]+", animation):
            if name in frames:
                declarations.update(frames[name])
    return _style_text(
        {
            name: value
            for name, value in declarations.items()
            if not MOTION_PROPERTY.match(name)
        }
    )


def _static_stylesheet(css: str, frames: dict[str, dict[str, str]]) -> str:
    rules = []
    for selector, body in _css_blocks(css):
        if KEYFRAMES.fullmatch(selector):
            continue
        if selector.startswith("@"):
            body = _static_stylesheet(body, frames)
        else:
            body = _static_declarations(body, frames)
        if body:
            rules.append(f"{selector}{{{body}}}")
    return "".join(rules)


def _remove_css_motion(root: ET.Element) -> None:
    styles = [node for node in root.iter() if _tag(node) == "style"]
    frames = {}
    for style in styles:
        frames.update(_keyframes(style.text or ""))
    for style in styles:
        style.text = _static_stylesheet(style.text or "", frames)
    for node in root.iter():
        if "style" in node.attrib:
            static_style = _static_declarations(node.get("style", ""), frames)
            if static_style:
                node.set("style", static_style)
            else:
                del node.attrib["style"]


def _values(animation: ET.Element) -> list[str]:
    return [
        value.strip()
        for value in animation.get("values", "").split(";")
        if value.strip()
    ]


def _end_value(animation: ET.Element) -> str | None:
    if "to" in animation.attrib:
        return animation.get("to")
    values = _values(animation)
    return values[-1] if values else None


def _numeric_opacity(value: str) -> float:
    return float(value[:-1]) / 100 if value.endswith("%") else float(value)


def _visible_opacity(animation: ET.Element) -> str:
    values = _values(animation) or [animation.get("to", "1")]
    return max(values, key=_numeric_opacity)


def _assign(target: ET.Element, animation: ET.Element, value: str) -> None:
    attribute = animation.get("attributeName", "")
    style = _declarations(target.get("style", ""))
    if animation.get("attributeType", "").lower() == "css" or attribute in style:
        style[attribute] = value
        target.set("style", _style_text(style))
    else:
        target.set(attribute, value)


def _finish_transform(target: ET.Element, animation: ET.Element) -> None:
    looping = animation.get("repeatCount") == "indefinite"
    if looping:
        # Preserve anchors and off-card decorative scans. Moving text packets in
        # architecture diagrams have no anchor; their destination is meaningful.
        if "transform" in target.attrib or not any(
            _tag(child) == "text" for child in target.iter()
        ):
            return
    value = _end_value(animation)
    if value is None:
        return
    transform = f"{animation.get('type', 'translate')}({value})"
    if animation.get("additive") == "sum" and target.get("transform"):
        transform = f"{target.get('transform')} {transform}"
    target.set("transform", transform)


def _position_motion(target: ET.Element, animation: ET.Element) -> None:
    # Moving particles can cross labels. Freezing a dot at a path endpoint can
    # permanently cover that label, so omit decorative motion in static cards.
    if not any(_tag(child) == "text" for child in target.iter()):
        target.set("display", "none")
        return
    match = PATH_START.match(animation.get("path", ""))
    if match:
        transform = f"translate({match.group(1)} {match.group(2)})"
        if target.get("transform"):
            transform = f"{target.get('transform')} {transform}"
        target.set("transform", transform)


def _freeze_attribute(target: ET.Element, animation: ET.Element) -> None:
    attribute = animation.get("attributeName")
    if not attribute:
        return
    if animation.get("repeatCount") != "indefinite":
        value = _end_value(animation)
        if value is not None:
            _assign(target, animation, value)
    elif attribute == "opacity":
        style = _declarations(target.get("style", ""))
        base = style.get("opacity", target.get("opacity", ""))
        if not base or _numeric_opacity(base) == 0:
            _assign(target, animation, _visible_opacity(animation))


def _remove_element(parent: ET.Element, element: ET.Element) -> None:
    if element.tail:
        index = list(parent).index(element)
        if index:
            previous = parent[index - 1]
            previous.tail = (previous.tail or "") + element.tail
        else:
            parent.text = (parent.text or "") + element.tail
    parent.remove(element)


def make_static_svg(source: str) -> str:
    """Return an animation-free SVG with the profile's essential content visible."""
    root = ET.fromstring(source)
    _remove_css_motion(root)
    parents = {child: parent for parent in root.iter() for child in parent}
    identifiers = {node.get("id"): node for node in root.iter() if node.get("id")}
    rotating_locations = set()

    for animation in list(root.iter()):
        kind = _tag(animation)
        if kind not in ANIMATION_TAGS:
            continue
        parent = parents[animation]
        href = animation.get("href", animation.get(f"{{{XLINK_NS}}}href"))
        target = identifiers.get(href[1:]) if href and href.startswith("#") else parent
        if href and not href.startswith("#"):
            target = None
        if target is not None:
            if kind == "animateTransform":
                _finish_transform(target, animation)
            elif kind == "animateMotion":
                _position_motion(target, animation)
            elif (
                _tag(target) == "text"
                and animation.get("attributeName") == "opacity"
                and animation.get("repeatCount") == "indefinite"
            ):
                location = (
                    parents.get(target),
                    target.get("x", "0"),
                    target.get("y", "0"),
                    target.get("transform", ""),
                )
                opacity = (
                    "0"
                    if location in rotating_locations
                    else _visible_opacity(animation)
                )
                _assign(target, animation, opacity)
                rotating_locations.add(location)
            else:
                _freeze_attribute(target, animation)
        _remove_element(parent, animation)

    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def write_static_variants(directory: Path) -> dict[str, str]:
    """Write immediate SVG companions and return source-to-static filenames."""
    variants = {}
    for source in sorted(directory.glob("*.svg")):
        if source.stem.endswith("-static"):
            continue
        destination = source.with_stem(f"{source.stem}-static")
        destination.write_text(
            make_static_svg(source.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        variants[source.name] = destination.name
    return variants
