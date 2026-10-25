import json
import tempfile
import unittest
from pathlib import Path

from tartarus.bindings import Binding, binding_to_dict, parse_binding_text
from tartarus.config import (
    SCHEMA_VERSION,
    active_profile,
    default_config,
    load_config,
    save_config,
)
from tartarus.devmap import ALL_CONTROLS, FACTORY_CODES, FACTORY_OUTPUT


def _stored(bindings: dict) -> dict:
    return {
        "version": SCHEMA_VERSION,
        "active_profile": "default",
        "profiles": [{"id": "default", "name": "Default", "dpad_mode": "4way", "bindings": bindings}],
        "lighting": {"effect": "static", "color": "#ff0000", "brightness": 40},
    }


class DevmapTest(unittest.TestCase):
    def test_every_control_has_factory_output(self):
        self.assertEqual(set(FACTORY_OUTPUT), set(ALL_CONTROLS))
        for control, text in FACTORY_OUTPUT.items():
            with self.subTest(control=control):
                parse_binding_text(text)

    def test_factory_codes_match_spike_table(self):
        self.assertEqual(FACTORY_CODES[2], "k01")       # KEY_1
        self.assertEqual(FACTORY_CODES[57], "k20")      # KEY_SPACE
        self.assertEqual(FACTORY_CODES[56], "top_button")  # KEY_LEFTALT
        self.assertEqual(FACTORY_CODES[0x112], "wheel_click")  # BTN_MIDDLE
        self.assertEqual(FACTORY_CODES[103], "dpad_up")
        self.assertEqual(len(FACTORY_CODES), 26)
        self.assertEqual(FACTORY_OUTPUT["dpad_up_right"], "hold:Up+Right")


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "settings.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_does_not_follow_planted_tmp_symlink(self):
        # The folder is the deck user's and the backend is root: a symlink planted
        # where the temp file goes must not make root write through it.
        victim = self.dir / "victim"
        victim.write_text("untouched")
        (self.dir / "settings.tmp").symlink_to(victim)
        save_config(self.path, default_config())
        self.assertEqual(victim.read_text(), "untouched")
        self.assertEqual(load_config(self.path), default_config())
        self.assertEqual(oct(self.path.stat().st_mode & 0o777), oct(0o644))

    def _write(self, data):
        self.path.write_text(data if isinstance(data, str) else json.dumps(data))

    def _backups(self):
        return list(self.dir.glob("settings.json.corrupt-*"))

    def test_missing_file_gives_defaults(self):
        c = load_config(self.path)
        p = active_profile(c)
        self.assertEqual(set(p.bindings), set(ALL_CONTROLS))
        self.assertEqual(p.dpad_mode, "4way")
        self.assertEqual(c, default_config())

    def test_round_trip(self):
        c = default_config()
        active_profile(c).bindings["k01"] = Binding("key", ("Esc",))
        save_config(self.path, c)
        self.assertEqual(load_config(self.path), c)

    def test_missing_control_filled_from_factory(self):
        self._write(_stored({"k01": {"type": "key", "keys": ["Esc"]}}))
        p = active_profile(load_config(self.path))
        self.assertEqual(set(p.bindings), set(ALL_CONTROLS))
        self.assertEqual(p.bindings["k05"], parse_binding_text(FACTORY_OUTPUT["k05"]))

    def test_unknown_control_dropped(self):
        self._write(_stored({"thumb": {"type": "key", "keys": ["Esc"]}}))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertNotIn("thumb", active_profile(c).bindings)

    def test_bad_binding_falls_back_per_control(self):
        self._write(_stored({
            "k01": {"type": "key", "keys": ["Esc"]},
            "k02": {"type": "key", "keys": ["Nope"]},
        }))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        p = active_profile(c)
        self.assertEqual(p.bindings["k01"], Binding("key", ("Esc",)))
        self.assertEqual(p.bindings["k02"], parse_binding_text(FACTORY_OUTPUT["k02"]))
        self.assertEqual(c.lighting.effect, "static")
        self.assertEqual(self._backups(), [])

    def test_corrupt_file_backed_up(self):
        self._write("{nope")
        with self.assertLogs("tartarus", "WARNING"):
            self.assertEqual(load_config(self.path), default_config())
        self.assertEqual(len(self._backups()), 1)
        self.assertFalse(self.path.exists())

    def test_wrong_version_backed_up(self):
        data = _stored({})
        data["version"] = 99
        self._write(data)
        with self.assertLogs("tartarus", "WARNING"):
            self.assertEqual(load_config(self.path), default_config())
        self.assertEqual(len(self._backups()), 1)
        self.assertFalse(self.path.exists())

    def test_save_is_atomic(self):
        save_config(self.path, default_config())
        self.assertTrue(self.path.exists())
        self.assertEqual(list(self.dir.glob("*.tmp")), [])
        stored = json.loads(self.path.read_text())
        self.assertEqual(stored["profiles"][0]["bindings"]["k01"], binding_to_dict(parse_binding_text("1")))


if __name__ == "__main__":
    unittest.main()
