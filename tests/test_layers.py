import unittest

from tartarus.layers import HYPERSHIFT, STANDARD, ControlRef, parse_control


class ParseControlTest(unittest.TestCase):
    def test_standard_and_layer_forms(self):
        self.assertEqual(parse_control("k05"), ControlRef("k05", STANDARD, "a"))
        self.assertEqual(parse_control("k05.b"), ControlRef("k05", STANDARD, "b"))
        self.assertEqual(parse_control("k05.h"), ControlRef("k05", HYPERSHIFT, "a"))
        self.assertEqual(parse_control("k05.h.b"), ControlRef("k05", HYPERSHIFT, "b"))
        self.assertEqual(parse_control("dpad_up.h"), ControlRef("dpad_up", HYPERSHIFT, "a"))

    def test_rejects(self):
        for bad in ("k21", "k05.b.h", "k05.h.h", "wheel_up.b", "dpad_up.h.b", "top_button.b", ""):
            with self.assertRaises(ValueError):
                parse_control(bad)


if __name__ == "__main__":
    unittest.main()
