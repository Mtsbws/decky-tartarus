import os
import tempfile
import unittest
from functools import reduce

from tartarus.devmode import DRIVER_MODE, NORMAL_MODE, set_mode_report
from tartarus.linux.hidraw import HidrawReader


class DevmodeTest(unittest.TestCase):
    def test_set_mode_report(self):
        r = set_mode_report(DRIVER_MODE)
        self.assertEqual(r[5:10], bytes([0x02, 0x00, 0x04, 0x03, 0x00]))
        self.assertEqual(len(r), 90)
        self.assertEqual(r[88], reduce(lambda a, b: a ^ b, r[2:88]))
        self.assertEqual(set_mode_report(NORMAL_MODE)[5:10], bytes([0x02, 0x00, 0x04, 0x00, 0x00]))
        with self.assertRaises(ValueError):
            set_mode_report(0x02)


class HidrawReaderTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "hidraw")
        os.mkfifo(path)
        self.reader = HidrawReader(path)
        self.w = os.open(path, os.O_WRONLY)

    def tearDown(self):
        self.reader.close()
        if self.w is not None:
            os.close(self.w)
        self._tmp.cleanup()

    def test_reads_written_report(self):
        os.write(self.w, b"\x06\x10\x00")
        self.assertEqual(self.reader.read_report(), b"\x06\x10\x00")
        self.assertIsInstance(self.reader.fd, int)

    def test_empty_is_none(self):
        self.assertIsNone(self.reader.read_report())

    def test_closed_writer_raises(self):
        os.close(self.w)
        self.w = None
        with self.assertRaises(OSError):
            self.reader.read_report()

    def test_close_is_idempotent(self):
        self.reader.close()
        self.reader.close()


if __name__ == "__main__":
    unittest.main()
