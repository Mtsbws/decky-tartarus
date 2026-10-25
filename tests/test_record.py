import unittest

from tartarus.bindings import Binding
from tartarus.record import RecordCapture


def run(capture, events):
    results = [capture.feed(name, is_down) for name, is_down in events]
    return results


class RecordTest(unittest.TestCase):
    def test_single_key(self):
        r = RecordCapture()
        self.assertEqual(run(r, [("F5", True), ("F5", False)]), [None, Binding("key", ("F5",))])

    def test_combo_orders_modifiers(self):
        r = RecordCapture()
        results = run(r, [("C", True), ("Ctrl", True), ("C", False), ("Ctrl", False)])
        self.assertEqual(results, [None, None, None, Binding("shortcut", ("Ctrl", "C"))])

    def test_modifier_order(self):
        r = RecordCapture()
        events = [("Alt", True), ("X", True), ("Shift", True), ("Ctrl", True)]
        events += [(n, False) for n, _ in events]
        self.assertEqual(run(r, events)[-1], Binding("shortcut", ("Ctrl", "Shift", "Alt", "X")))

    def test_modifier_alone(self):
        r = RecordCapture()
        self.assertEqual(run(r, [("Shift", True), ("Shift", False)])[-1], Binding("modifier", ("Shift",)))

    def test_mouse_and_media_alone(self):
        self.assertEqual(run(RecordCapture(), [("RMB", True), ("RMB", False)])[-1], Binding("mouse", ("RMB",)))
        self.assertEqual(run(RecordCapture(), [("Mute", True), ("Mute", False)])[-1], Binding("media", ("Mute",)))

    def test_stray_release_ignored(self):
        r = RecordCapture()
        self.assertIsNone(r.feed("A", False))
        self.assertEqual(run(r, [("B", True), ("B", False)]), [None, Binding("key", ("B",))])

    def test_repeated_down_counts_once(self):
        r = RecordCapture()
        results = run(r, [("A", True), ("A", True), ("A", False)])
        self.assertEqual(results[-1], Binding("key", ("A",)))

    def test_unknown_name_ignored(self):
        r = RecordCapture()
        self.assertIsNone(r.feed("Nope", True))
        self.assertEqual(run(r, [("A", True), ("A", False)])[-1], Binding("key", ("A",)))


if __name__ == "__main__":
    unittest.main()
