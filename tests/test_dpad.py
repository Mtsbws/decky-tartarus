import unittest

from tartarus.dpad import resolve_dpad

UP, RIGHT, DOWN, LEFT = "dpad_up", "dpad_right", "dpad_down", "dpad_left"


def fs(*items):
    return frozenset(items)


class DpadTest(unittest.TestCase):
    def test_4way_union(self):
        self.assertEqual(resolve_dpad(fs(UP, RIGHT), "4way"), fs(UP, RIGHT))

    def test_8way_diagonal(self):
        self.assertEqual(resolve_dpad(fs(UP, RIGHT), "8way"), fs("dpad_up_right"))
        self.assertEqual(resolve_dpad(fs(DOWN, LEFT), "8way"), fs("dpad_down_left"))

    def test_8way_single(self):
        self.assertEqual(resolve_dpad(fs(LEFT), "8way"), fs(LEFT))

    def test_8way_opposites_cancel(self):
        self.assertEqual(resolve_dpad(fs(UP, DOWN), "8way"), fs())
        self.assertEqual(resolve_dpad(fs(UP, DOWN, LEFT), "8way"), fs(LEFT))
        self.assertEqual(resolve_dpad(fs(UP, RIGHT, DOWN, LEFT), "8way"), fs())

    def test_empty(self):
        for mode in ("4way", "8way"):
            with self.subTest(mode=mode):
                self.assertEqual(resolve_dpad(fs(), mode), fs())


if __name__ == "__main__":
    unittest.main()
