import importlib.util
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tartarus.bindings import parse_binding_text, binding_label
from tartarus.config import STEAMOS_DEFAULT, profile_from_starter
from tartarus.starters import STARTERS

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("render_layouts", ROOT / "scripts" / "render_layouts.py")
render_layouts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render_layouts)

# The controls a picture shows: keys 01-20, the top button, the D-pad directions and the wheel.
PICTURED = tuple(f"k{i:02d}" for i in range(1, 21)) + (
    "top_button", "dpad_up", "dpad_right", "dpad_down", "dpad_left", "wheel_up", "wheel_down", "wheel_click")


def texts(svg: str) -> set:
    return {el.text for el in ET.fromstring(svg).iter() if el.text}


class RenderLayoutsTest(unittest.TestCase):
    def setUp(self):
        self.pictures = render_layouts.all_pictures()

    def test_svg_is_valid_xml_and_labels_every_control(self):
        for name, svg in self.pictures.items():
            texts(svg)  # parses, or raises
        for s in STARTERS:
            labels = render_layouts.labels_for(profile_from_starter(s, "p9", s.name, (False, False, False)).bindings)
            found = texts(self.pictures[s.slug + ".svg"])
            for control in PICTURED:
                self.assertIn(labels[control], found, f"{s.name} {control}")

    def test_default_picture_matches_steamos_default(self):
        found = texts(self.pictures["default.svg"])
        for control, text in STEAMOS_DEFAULT.items():
            self.assertIn(binding_label(parse_binding_text(text)), found, control)

    def test_labels_are_escaped(self):
        svg = render_layouts.render_svg("Escape test", {"k01": "A&B<"})
        self.assertIn("&amp;", svg)
        self.assertIn("&lt;", svg)
        self.assertIn("A&B<", texts(svg))

    def test_committed_pictures_are_current(self):
        for name, svg in self.pictures.items():
            path = ROOT / "docs" / "layouts" / name
            self.assertTrue(path.exists(), f"{path} is missing; run scripts/render_layouts.py")
            self.assertEqual(path.read_text(encoding="utf-8"), svg,
                             f"{path} is out of date; run scripts/render_layouts.py")

    def test_hypershift_picture_shows_the_layer(self):
        self.assertIn("Ctrl+1", texts(self.pictures["mmo-hypershift.svg"]))
        self.assertNotIn("Ctrl+1", texts(self.pictures["mmo.svg"]))
        self.assertIn("Hypershift", texts(self.pictures["mmo-hypershift.svg"]))

    def test_reference_doc_covers_every_starter(self):
        doc = (ROOT / "docs" / "starter-profiles.md").read_text(encoding="utf-8")
        for name in self.pictures:
            self.assertTrue(f"layouts/{name}" in doc, name)
        for phrase in ("Made for", "starting points", "not been tested in a game"):
            self.assertTrue(phrase in doc, phrase)
        for s in STARTERS:
            self.assertTrue(s.name in doc, s.name)
            for control in s.bindings:
                row = control.split("_")[0] if control.startswith(("dpad", "wheel")) else control
                self.assertTrue(row in doc, f"{s.name} {control}")

    def test_readme_links_the_pictures(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for text in ("docs/layouts/default.svg", "docs/starter-profiles.md",
                     "Call of Duty", "Battlefield", "Wardogs", "World of Warcraft", "RuneScape 3"):
            self.assertTrue(text in readme, text)


if __name__ == "__main__":
    unittest.main()
