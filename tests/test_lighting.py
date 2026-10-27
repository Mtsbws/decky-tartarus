import unittest
from functools import reduce

from tartarus.lighting import (
    BREATHING_TRANSACTION_ID,
    EFFECTS,
    TRANSACTION_ID,
    build_report,
    effect_reports,
    leds_report,
)


def _hex(text: str) -> bytes:
    return bytes.fromhex(text.replace(" ", ""))


def _report(head: str, crc: int) -> bytes:
    """A 90-byte report from the findings' hex prefix and CRC."""
    raw = _hex(head)
    return raw + bytes(88 - len(raw)) + bytes([crc, 0])


# Class/id/args per effect, from the spike findings table (colour #112233, defaults).
FINDINGS = {
    "static": (TRANSACTION_ID, "0f 02", "01 05 01 00 00 01 11 22 33"),
    "breathing": (BREATHING_TRANSACTION_ID, "0f 02", "01 05 02 01 00 01 11 22 33"),
    "spectrum": (TRANSACTION_ID, "0f 02", "01 05 03 00 00 00"),
    "wave": (TRANSACTION_ID, "0f 02", "01 05 04 01 28 00"),
    "reactive": (TRANSACTION_ID, "0f 02", "01 05 05 00 02 01 11 22 33"),
    "starlight": (TRANSACTION_ID, "0f 02", "01 05 07 00 02 01 11 22 33"),
}


class ReportTest(unittest.TestCase):
    def test_report_layout_and_crc(self):
        report = build_report(0x0F, 0x02, _hex("01 05 01 00 00 01 00 ff 00"))
        self.assertEqual(len(report), 90)
        self.assertEqual(report[88], reduce(lambda a, b: a ^ b, report[2:88], 0))
        # static green, sent in the spike
        self.assertEqual(report, _report("00 1f 00 00 00 09 0f 02 01 05 01 00 00 01 00 ff 00", 0xFF))

    def test_brightness_report_matches_spike(self):
        self.assertEqual(effect_reports("spectrum", "#000000", 100)[1],
                         _report("00 1f 00 00 00 03 0f 04 01 00 ff", 0xF6))
        self.assertEqual(effect_reports("spectrum", "#000000", 100)[0],
                         _report("00 1f 00 00 00 06 0f 02 01 05 03 00 00 00", 0x0C))

    def test_effect_bytes_match_findings(self):
        self.assertEqual(set(FINDINGS), set(EFFECTS))
        for effect, (txid, cls_id, args) in FINDINGS.items():
            with self.subTest(effect=effect):
                reports = effect_reports(effect, "#112233", 100)
                self.assertEqual(len(reports), 2)
                report = reports[0]
                self.assertEqual(report[1], txid)
                self.assertEqual(report[5], len(_hex(args)))
                self.assertEqual(report[6:8], _hex(cls_id))
                self.assertEqual(report[8:8 + report[5]], _hex(args))
                self.assertEqual(reports[1][1], TRANSACTION_ID)
                self.assertEqual(reports[1][5:11], _hex("03 0f 04 01 00 ff"))

    def test_brightness_scaling(self):
        for percent, value in ((100, 255), (0, 0), (50, 128), (20, 51)):
            with self.subTest(percent=percent):
                self.assertEqual(effect_reports("static", "#ffffff", percent)[1][10], value)

    def test_rejects_bad_input(self):
        for args in (("static", "#zzzzzz", 50), ("ripple", "#00ff00", 50), ("static", "#00ff00", 101),
                     ("static", "#00ff00", -1), ("static", "00ff00", 50), ("static", "#0f0", 50),
                     ("static", "#00ff00", True), ("static", "#00ff00", 50.0)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    effect_reports(*args)

    def test_uppercase_colour_accepted(self):
        self.assertEqual(effect_reports("static", "#AABBCC", 100)[0][14:17], _hex("aa bb cc"))

    def test_breathing_uses_txid_3f(self):
        reports = effect_reports("breathing", "#00ff00", 100)
        self.assertEqual(reports[0][1], 0x3F)
        self.assertEqual(reports[1][1], 0x1F)

    def test_never_set_device_mode(self):
        for effect in EFFECTS:
            for report in effect_reports(effect, "#00ff00", 70):
                with self.subTest(effect=effect):
                    self.assertNotEqual(report[6:8], b"\x00\x04")

    def test_leds_report(self):
        r = leds_report((True, False, True))
        self.assertEqual(r[5:17], bytes([0x09, 0x0F, 0x02, 0x01, 0x0B, 0x01, 0x00, 0x01, 0x01, 0xFF, 0x00, 0xFF]))
        self.assertEqual(r[1], 0x1F)
        self.assertEqual(len(r), 90)
        self.assertEqual(r[88], reduce(lambda a, b: a ^ b, r[2:88]))
        self.assertEqual(leds_report((False, False, False))[14:17], b"\x00\x00\x00")
