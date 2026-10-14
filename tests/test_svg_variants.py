"""Regression coverage for the profile's reduced-motion images."""

from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.svg_variants import make_static_svg, write_static_variants


SVG_NS = "http://www.w3.org/2000/svg"
NS = {"svg": SVG_NS}
ASSETS = Path(__file__).resolve().parents[1] / "assets" / "svg"


def parse_fragment(content: str) -> ET.Element:
    return ET.fromstring(make_static_svg(f'<svg xmlns="{SVG_NS}">{content}</svg>'))


class StaticSvgTests(unittest.TestCase):
    def test_reveals_finite_entrances_and_completes_drawn_paths(self):
        root = parse_fragment(
            '<g opacity="0"><animate attributeName="opacity" to="1"/>'
            '<animateTransform attributeName="transform" type="translate" '
            'from="-8 0" to="0 0"/><text>Visible label</text></g>'
            '<path stroke-dashoffset="745"><animate '
            'attributeName="stroke-dashoffset" from="745" to="0"/></path>'
            '<clipPath><rect width="0"><animate attributeName="width" '
            'values="0;100"/></rect></clipPath>'
        )
        group = root.find("svg:g", NS)
        self.assertEqual(group.get("opacity"), "1")
        self.assertEqual(group.get("transform"), "translate(0 0)")
        self.assertEqual(root.find("svg:path", NS).get("stroke-dashoffset"), "0")
        self.assertEqual(root.find(".//svg:rect", NS).get("width"), "100")
        self.assertEqual(root.find(".//svg:text", NS).text, "Visible label")

    def test_rotating_phrases_show_only_one_per_location(self):
        root = parse_fragment(
            '<text x="20" y="30" opacity="0">First role'
            '<animate attributeName="opacity" values="0;1;1;0;0" '
            'repeatCount="indefinite"/></text>'
            '<text x="20" y="30" opacity="0">Second role'
            '<animate attributeName="opacity" values="0;0;1;1;0" '
            'repeatCount="indefinite"/></text>'
            '<text x="20" y="70" opacity="0">Another line'
            '<animate attributeName="opacity" values="0;1;0" '
            'repeatCount="indefinite"/></text>'
        )
        texts = root.findall("svg:text", NS)
        self.assertEqual([text.get("opacity") for text in texts], ["1", "0", "1"])
        self.assertEqual(
            [text.text for text in texts],
            [
                "First role",
                "Second role",
                "Another line",
            ],
        )

    def test_preserves_anchored_loop_transforms_and_finite_additive_transforms(self):
        root = parse_fragment(
            '<g transform="translate(20 50)"><animateTransform '
            'attributeName="transform" type="translate" values="0 0;8 0" '
            'repeatCount="indefinite" additive="sum"/></g>'
            '<g transform="translate(40 60)"><animateTransform '
            'attributeName="transform" type="translate" from="0 8" to="0 0" '
            'additive="sum"/></g>'
        )
        first, second = root.findall("svg:g", NS)
        self.assertEqual(first.get("transform"), "translate(20 50)")
        self.assertEqual(second.get("transform"), "translate(40 60) translate(0 0)")

    def test_positions_moving_labels_at_their_destination(self):
        root = parse_fragment(
            '<g opacity="0"><animateTransform attributeName="transform" '
            'type="translate" values="20 20;100 60" repeatCount="indefinite"/>'
            '<animate attributeName="opacity" values="0;1;0" '
            'repeatCount="indefinite"/><text x="0" y="3">Policy</text></g>'
            '<circle r="3"><animateMotion path="M 40 50 L100 50" '
            'repeatCount="indefinite"/></circle>'
        )
        self.assertEqual(root.find("svg:g", NS).get("transform"), "translate(100 60)")
        self.assertEqual(root.find("svg:g", NS).get("opacity"), "1")
        self.assertEqual(root.find("svg:circle", NS).get("display"), "none")

    def test_decorative_motion_cannot_cover_a_stationary_label(self):
        root = parse_fragment(
            '<text x="46" y="95">DATA</text><circle r="4" opacity="0">'
            '<animateMotion path="M46 92 H366" repeatCount="indefinite"/>'
            '<animate attributeName="opacity" values="0;1;0" repeatCount="indefinite"/>'
            "</circle>"
        )
        self.assertEqual(root.find("svg:circle", NS).get("display"), "none")
        self.assertEqual(root.find("svg:text", NS).text, "DATA")

    def test_css_entrances_complete_and_looping_decorations_keep_base_state(self):
        root = parse_fragment(
            "<style>.c{opacity:0;animation:in .5s ease forwards}"
            "@keyframes in{to{opacity:1}}.w0{animation-delay:0.4s}"
            ".grow{transform:scaleX(0);animation:grow 1s ease forwards}"
            "@keyframes grow{to{transform:scaleX(1)}}"
            ".ring{opacity:.6;animation:pulse 2s infinite}"
            "@keyframes pulse{0%{transform:scale(1)}100%{transform:scale(3)}}"
            "</style><rect class='c w0'/><g class='grow'/><circle class='ring'/>"
        )
        css = root.find("svg:style", NS).text
        self.assertIn(".c{opacity:1}", css)
        self.assertIn(".grow{transform:scaleX(1)}", css)
        self.assertIn(".ring{opacity:.6}", css)
        self.assertNotIn("animation", css)
        self.assertNotIn("keyframes", css)
        self.assertNotIn("scale(3)", css)

    def test_handles_inline_css_and_remote_smil_targets(self):
        root = parse_fragment(
            "<style>@keyframes appear{from{opacity:0}to{opacity:1}}</style>"
            '<text id="label" style="opacity:0;animation:appear 1s forwards">'
            'Visible</text><rect id="bar" style="width:0"/>'
            '<animate href="#bar" attributeName="width" attributeType="CSS" to="90"/>'
            '<set href="#label" attributeName="visibility" to="visible"/>'
        )
        text = root.find("svg:text", NS)
        self.assertEqual(text.get("style"), "opacity:1")
        self.assertEqual(text.get("visibility"), "visible")
        self.assertEqual(root.find("svg:rect", NS).get("style"), "width:90")
        self.assertEqual(len(root.findall("svg:animate", NS)), 0)
        self.assertEqual(len(root.findall("svg:set", NS)), 0)

    def test_github_heatmap_and_language_bar_are_visible(self):
        root = ET.fromstring(make_static_svg((ASSETS / "github.svg").read_text()))
        css = root.find("svg:style", NS).text
        self.assertIn(".c{opacity:1}", css)
        self.assertIn("transform:scaleX(1)", css)
        self.assertGreater(len(root.findall("svg:rect", NS)), 300)

    def test_all_existing_cards_keep_labels_and_remove_animation(self):
        for asset in sorted(ASSETS.glob("*.svg")):
            if asset.stem.endswith("-static"):
                continue
            with self.subTest(asset=asset.name):
                source = ET.fromstring(asset.read_text(encoding="utf-8"))
                rendered = make_static_svg(asset.read_text(encoding="utf-8"))
                result = ET.fromstring(rendered)
                self.assertEqual(source.get("aria-label"), result.get("aria-label"))
                source_labels = [
                    "".join(node.itertext())
                    for node in source.findall(".//svg:text", NS)
                ]
                result_labels = [
                    "".join(node.itertext())
                    for node in result.findall(".//svg:text", NS)
                ]
                self.assertEqual(source_labels, result_labels)
                self.assertFalse(
                    any(
                        node.tag.rsplit("}", 1)[-1]
                        in {
                            "animate",
                            "animateTransform",
                            "animateMotion",
                            "set",
                        }
                        for node in result.iter()
                    )
                )
                self.assertNotIn("animation:", rendered)
                self.assertNotIn("@keyframes", rendered)
                self.assertEqual(make_static_svg(rendered), rendered)

    def test_writer_includes_mobile_cards_but_never_recurses_into_variants(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = f'<svg xmlns="{SVG_NS}"><text>Card</text></svg>'
            (directory / "card.svg").write_text(source)
            (directory / "card-mobile.svg").write_text(source)
            (directory / "card-static.svg").write_text(source)
            nested = directory / "nested"
            nested.mkdir()
            (nested / "ignored.svg").write_text(source)

            mapping = write_static_variants(directory)

            self.assertEqual(
                mapping,
                {
                    "card-mobile.svg": "card-mobile-static.svg",
                    "card.svg": "card-static.svg",
                },
            )
            self.assertTrue((directory / "card-mobile-static.svg").exists())
            self.assertFalse((directory / "card-static-static.svg").exists())
            self.assertFalse((nested / "ignored-static.svg").exists())


if __name__ == "__main__":
    unittest.main()
