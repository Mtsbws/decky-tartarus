import unittest

from tartarus.actuation import DEFAULT_MM, gap_ok, valid_mm
from tartarus.bindings import parse_binding_text
from tartarus.config import NAME_MAX
from tartarus.devmap import ACTUATION_KEYS, ALL_CONTROLS
from tartarus.starters import STARTERS, find_starter


def _starter(starter_id):
    s = find_starter(starter_id)
    assert s is not None, starter_id
    return s


class StarterDefinitionsTest(unittest.TestCase):
    def test_ids_and_names(self):
        self.assertEqual([s.id for s in STARTERS], ["starter:fps-wasd", "starter:fps-dpad", "starter:mmo"])
        self.assertEqual([s.name for s in STARTERS], ["FPS – WASD", "FPS – D-pad", "MMO"])
        for s in STARTERS:
            self.assertLessEqual(len(s.name), NAME_MAX)
        self.assertEqual(find_starter("starter:mmo").name, "MMO")
        self.assertIsNone(find_starter("p2"))
        self.assertIsNone(find_starter("starter:nope"))

    def test_every_binding_parses(self):
        for s in STARTERS:
            with self.subTest(starter=s.id):
                texts = list(s.bindings.items()) + list(s.hypershift.items())
                texts += [(c, text) for c, (text, _) in s.secondary.items()]
                for control, text in texts:
                    self.assertIn(control, ALL_CONTROLS)
                    parse_binding_text(text)
                for control, mm in s.actuation.items():
                    self.assertIn(control, ACTUATION_KEYS)
                    self.assertTrue(valid_mm(mm))
                for control, (_, mm) in s.secondary.items():
                    self.assertIn(control, ACTUATION_KEYS)
                    self.assertTrue(valid_mm(mm))
                    self.assertTrue(gap_ok(s.actuation.get(control, DEFAULT_MM), mm))

    def test_fps_wasd_table(self):
        s = _starter("starter:fps-wasd")
        expected = {"k08": "W", "k12": "A", "k13": "S", "k14": "D", "k11": "Shift", "top_button": "Alt",
                    "dpad_up": "3", "dpad_left": "6", "wheel_click": "N"}
        for control, text in expected.items():
            self.assertEqual(s.bindings[control], text, control)
        self.assertEqual(dict(s.actuation), {"k01": 2.5})
        self.assertEqual(dict(s.hypershift), {})
        self.assertNotIn("Hypershift", s.bindings.values())

    def test_fps_dpad_table(self):
        s = _starter("starter:fps-dpad")
        expected = {"dpad_up": "W", "dpad_right": "D", "dpad_down": "S", "dpad_left": "A",
                    "k02": "1", "k03": "2", "k04": "3", "k05": "4",
                    "k08": "5", "k12": "6", "k13": "F", "k14": "T", "k15": "G", "k18": "X"}
        for control, text in expected.items():
            self.assertEqual(s.bindings[control], text, control)
        self.assertNotIn("Y", s.bindings.values())
        self.assertEqual(dict(s.hypershift), {})

    def test_mmo_table(self):
        s = _starter("starter:mmo")
        expected = {"k19": "Hypershift", "k11": "Shift", "k16": "Ctrl", "k20": "Alt", "top_button": "Space",
                    "k18": "M", "wheel_up": "PageUp", "wheel_down": "PageDown", "wheel_click": "NumLock"}
        for control, text in expected.items():
            self.assertEqual(s.bindings[control], text, control)
        self.assertEqual(dict(s.secondary), {"k18": ("B", 3.0)})
        layer_keys = ["k02", "k03", "k04", "k05", "k07", "k08", "k09", "k10", "k12", "k13", "k14", "k15"]
        layer_texts = ["Ctrl+" + k for k in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "Minus", "Equal")]
        self.assertEqual(dict(s.hypershift), dict(zip(layer_keys, layer_texts)))
        self.assertNotIn("k19", s.hypershift)
        self.assertNotIn("k18", s.hypershift)


if __name__ == "__main__":
    unittest.main()
