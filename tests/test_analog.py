import unittest

from tartarus.analog import KeyTracker, mm_to_depth, parse_depth_report, valid_mm


class MappingTest(unittest.TestCase):
    def test_mm_to_depth(self):
        for mm, depth in ((1.5, 16), (2.5, 120), (3.6, 251), (2.0, 68), (3.0, 180), (1.6, 26)):
            self.assertEqual(mm_to_depth(mm), depth, mm)
        depths = [mm_to_depth(t / 10) for t in range(15, 37)]
        self.assertEqual(len(depths), 22)
        self.assertEqual(depths, sorted(set(depths)))

    def test_valid_mm(self):
        for mm in (1.5, 3.6, 2.6000000000000005, 2):
            self.assertTrue(valid_mm(mm), mm)
        for mm in (1.4, 3.7, 2.55, True, "2.0", None):
            self.assertFalse(valid_mm(mm), mm)

    def test_parse_depth_report(self):
        report = bytes([0x06] + list(range(1, 24)))
        self.assertEqual(parse_depth_report(report), bytes(range(1, 21)))
        self.assertIsNone(parse_depth_report(bytes([0x01] + [0] * 23)))
        self.assertIsNone(parse_depth_report(bytes([0x06] + [0] * 9)))


class TrackerTest(unittest.TestCase):
    def feed(self, tracker, *depths):
        return [tracker.feed(d) for d in depths]

    def test_single_down_up_with_hysteresis(self):
        t = KeyTracker(16)
        self.assertEqual(self.feed(t, 15, 16, 200, 9, 8, 7, 16),
                         [[], [("a", True)], [], [], [], [("a", False)], [("a", True)]])

    def test_single_fast_jump(self):
        t = KeyTracker(16)
        self.assertEqual(self.feed(t, 0, 255, 0), [[], [("a", True)], [("a", False)]])

    def test_single_reset_blocks_until_rearm(self):
        t = KeyTracker(16)
        t.feed(200)
        t.reset()
        self.assertEqual(self.feed(t, 210, 8, 7, 16), [[], [], [], [("a", True)]])

    def test_reset_while_up_does_not_block(self):
        t = KeyTracker(16)
        t.feed(3)
        t.reset()
        self.assertEqual(t.feed(16), [("a", True)])

    def test_secondary_not_yet(self):
        with self.assertRaises(NotImplementedError):
            KeyTracker(16, 251)


if __name__ == "__main__":
    unittest.main()
