import unittest

from tartarus.bindings import (
    Binding,
    BindingError,
    binding_from_dict,
    binding_label,
    binding_to_dict,
    parse_binding_text,
)
from tartarus.codes import KEYS, category, code_for, name_for


class CodesTest(unittest.TestCase):
    def test_code_lookup_is_case_insensitive(self):
        self.assertEqual(code_for("esc"), 1)
        self.assertEqual(code_for("KP0"), code_for("kp0"))
        self.assertRaises(KeyError, code_for, "Nope")

    def test_name_for_round_trip(self):
        for name, code in KEYS.items():
            self.assertEqual(name_for(code), name)
        self.assertIsNone(name_for(99999))

    def test_categories(self):
        self.assertEqual(category("RAlt"), "modifier")
        self.assertEqual(category("WheelUp"), "mouse")
        self.assertEqual(category("Mute"), "media")
        self.assertEqual(category("F24"), "key")


class BindingTextTest(unittest.TestCase):
    def test_parse_single_key(self):
        self.assertEqual(parse_binding_text("esc"), Binding("key", ("Esc",)))

    def test_parse_modifier(self):
        self.assertEqual(parse_binding_text("Shift"), Binding("modifier", ("Shift",)))

    def test_parse_shortcut(self):
        self.assertEqual(parse_binding_text("ctrl + c"), Binding("shortcut", ("Ctrl", "C")))

    def test_parse_combo(self):
        self.assertEqual(parse_binding_text("hold:W+A"), Binding("combo", ("W", "A")))

    def test_parse_macro(self):
        self.assertEqual(
            parse_binding_text("Ctrl+C, Ctrl+V"),
            Binding("macro", steps=(("Ctrl", "C"), ("Ctrl", "V"))),
        )

    def test_parse_mouse_media(self):
        self.assertEqual(parse_binding_text("LMB").type, "mouse")
        self.assertEqual(parse_binding_text("Vol+").type, "media")

    def test_parse_steam_disable(self):
        self.assertEqual(parse_binding_text("steam:qam"), Binding("steam", action="qam"))
        self.assertEqual(parse_binding_text("disable"), Binding("disable"))

    def test_parse_errors(self):
        for bad in ["", "Ctrl+", "Foo", "steam:x", "hold:"]:
            with self.subTest(text=bad):
                self.assertRaises(BindingError, parse_binding_text, bad)

    def test_dict_round_trip(self):
        for text in ["F5", "Ctrl+Alt+Delete", "hold:W+A", "A, B", "steam:menu", "disable", "RMB"]:
            with self.subTest(text=text):
                b = parse_binding_text(text)
                self.assertEqual(binding_from_dict(binding_to_dict(b)), b)

    def test_from_dict_rejects_unknown(self):
        self.assertRaises(BindingError, binding_from_dict, {"type": "key", "keys": ["Nope"]})

    def test_labels(self):
        self.assertEqual(binding_label(parse_binding_text("hold:W+A")), "W+A (hold)")
        self.assertEqual(binding_label(Binding("steam", action="menu")), "Steam menu")

    def test_hypershift_binding(self):
        b = parse_binding_text(" HyperShift ")
        self.assertEqual(b, Binding("hypershift"))
        self.assertEqual(binding_to_dict(b), {"type": "hypershift"})
        self.assertEqual(binding_from_dict({"type": "hypershift"}), b)
        self.assertEqual(binding_label(b), "Hypershift")


if __name__ == "__main__":
    unittest.main()
