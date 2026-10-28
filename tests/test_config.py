import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tartarus.bindings import Binding, binding_label, binding_to_dict, parse_binding_text
from tartarus.config import (
    LED_ORDER,
    NO_LEDS,
    SCHEMA_VERSION,
    Game,
    Hypershift,
    Profile,
    Secondary,
    clean_name,
    default_config,
    default_profile,
    first_run_config,
    factory_bindings,
    steamos_bindings,
    hypershift_key,
    load_config,
    new_profile_id,
    next_leds,
    profile_for_app,
    save_config,
)
from tartarus.actuation import gap_ok
from tartarus.devmap import ALL_CONTROLS, FACTORY_CODES, FACTORY_OUTPUT


def _stored(profiles, games=None) -> dict:
    """A v2 settings file. `profiles` is a list of dicts, or a bindings dict for the Default alone."""
    if isinstance(profiles, dict):
        profiles = [_entry("default", "Default", bindings=profiles)]
    return {
        "version": SCHEMA_VERSION,
        "profiles": profiles,
        "games": games or {},
        "lighting": {"effect": "static", "color": "#ff0000", "brightness": 40},
    }


def _entry(pid, name, leds=None, bindings=None) -> dict:
    return {"id": pid, "name": name, "leds": leds if leds is not None else [False, False, False],
            "dpad_mode": "4way", "bindings": bindings or {}}


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
        p = default_profile(c)
        self.assertEqual(set(p.bindings), set(ALL_CONTROLS))
        self.assertEqual(p.dpad_mode, "4way")
        self.assertEqual(c, first_run_config())

    def test_missing_file_gives_the_starters(self):
        c = load_config(self.path)
        self.assertEqual([p.name for p in c.profiles], ["Default", "FPS \u2013 WASD", "FPS \u2013 D-pad", "MMO"])
        self.assertEqual([p.id for p in c.profiles], ["default", "p2", "p3", "p4"])
        leds = [p.leds for p in c.profiles]
        self.assertEqual(len(set(leds)), 4)
        self.assertEqual(leds[0], NO_LEDS)
        self.assertEqual(c, first_run_config())

    def test_corrupt_file_is_moved_aside_and_gets_the_starters(self):
        self._write("{nope")
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertEqual(len(self._backups()), 1)
        self.assertEqual([p.name for p in c.profiles], ["Default", "FPS \u2013 WASD", "FPS \u2013 D-pad", "MMO"])

    def test_existing_file_gets_no_starters(self):
        save_config(self.path, default_config())
        c = load_config(self.path)
        self.assertEqual([p.name for p in c.profiles], ["Default"])
        save_config(self.path, c)
        self.assertEqual([p.name for p in load_config(self.path).profiles], ["Default"])

    def test_deleted_starter_stays_deleted(self):
        c = first_run_config()
        c.profiles = [p for p in c.profiles if p.name != "MMO"]
        save_config(self.path, c)
        self.assertEqual([p.name for p in load_config(self.path).profiles],
                         ["Default", "FPS \u2013 WASD", "FPS \u2013 D-pad"])

    def test_default_profile_is_made_for_steamos(self):
        p = default_profile(default_config())
        text = {control: binding_label(b) for control, b in p.bindings.items()}
        # Enter, Backspace and Esc under the resting fingers; the thumb moves and opens the Steam menu.
        self.assertEqual((text["k12"], text["k13"], text["k14"]), ("Backspace", "Enter", "Esc"))
        self.assertEqual((text["k07"], text["k09"]), ("F6", "F7"))
        # Steam's menus ignore Shift+F6/F7 (triggers); key 11's factory CapsLock would stick, so it is off.
        self.assertEqual(p.bindings["k11"], Binding("disable"))
        self.assertEqual(text["k15"], "F")  # factory key
        self.assertFalse([c for c, t in text.items() if t in ("Shift+F6", "Shift+F7")])
        self.assertEqual((text["k03"], text["k04"]), ("Quick Access", "Keyboard"))
        self.assertEqual(text["top_button"], "Steam menu")
        # One key per function: F3 would repeat Backspace in Steam, CapsLock would stick.
        self.assertEqual([c for c, t in text.items() if t in ("Enter", "Esc", "Backspace", "F3", "CapsLock")],
                         ["k12", "k13", "k14"])
        self.assertEqual((text["k01"], text["k02"], text["k05"]), ("1", "2", "5"))  # factory keys
        self.assertEqual(p.bindings["wheel_up"], Binding("media", ("Vol+",)))
        self.assertEqual(p.bindings["dpad_up"], Binding("key", ("Up",)))  # unlisted: factory key
        self.assertEqual(p.bindings["k17"], Binding("key", ("Z",)))

    def test_round_trip(self):
        c = default_config()
        default_profile(c).bindings["k01"] = Binding("key", ("Esc",))
        save_config(self.path, c)
        self.assertEqual(load_config(self.path), c)

    def test_missing_control_filled_from_factory(self):
        self._write(_stored({"k01": {"type": "key", "keys": ["Esc"]}}))
        p = default_profile(load_config(self.path))
        self.assertEqual(set(p.bindings), set(ALL_CONTROLS))
        self.assertEqual(p.bindings["k05"], parse_binding_text(FACTORY_OUTPUT["k05"]))

    def test_unknown_control_dropped(self):
        self._write(_stored({"thumb": {"type": "key", "keys": ["Esc"]}}))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertNotIn("thumb", default_profile(c).bindings)

    def test_bad_binding_falls_back_per_control(self):
        self._write(_stored({
            "k01": {"type": "key", "keys": ["Esc"]},
            "k02": {"type": "key", "keys": ["Nope"]},
        }))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        p = default_profile(c)
        self.assertEqual(p.bindings["k01"], Binding("key", ("Esc",)))
        self.assertEqual(p.bindings["k02"], parse_binding_text(FACTORY_OUTPUT["k02"]))
        self.assertEqual(c.lighting.effect, "static")
        self.assertEqual(self._backups(), [])

    def test_adjustable_actuation_round_trips_and_defaults_on(self):
        self.assertTrue(load_config(self.path).adjustable_actuation)  # no file
        c = default_config()
        c.adjustable_actuation = False
        save_config(self.path, c)
        self.assertIs(load_config(self.path).adjustable_actuation, False)
        for raw in (None, "yes"):
            data = json.loads(self.path.read_text())
            if raw is None:
                del data["adjustable_actuation"]
            else:
                data["adjustable_actuation"] = raw
            self.path.write_text(json.dumps(data))
            self.assertIs(load_config(self.path).adjustable_actuation, True, raw)

    def test_lighting_enabled_defaults_true_for_old_file(self):
        self._write(_stored([_entry("default", "Default")]))
        self.assertIs(load_config(self.path).lighting.enabled, True)

    def test_lighting_enabled_round_trip(self):
        c = default_config()
        c.lighting.enabled = False
        save_config(self.path, c)
        self.assertIs(json.loads(self.path.read_text())["lighting"]["enabled"], False)
        self.assertIs(load_config(self.path).lighting.enabled, False)

    def test_hypershift_lights_round_trip_and_defaults(self):
        self._write(_stored([_entry("default", "Default")]))
        lighting = load_config(self.path).lighting
        self.assertEqual((lighting.hypershift, lighting.hypershift_color), (False, "#ff6000"))
        c = default_config()
        c.lighting.hypershift = True
        c.lighting.hypershift_color = "#00ff80"
        save_config(self.path, c)
        self.assertEqual(json.loads(self.path.read_text())["lighting"]["hypershift"],
                         {"enabled": True, "color": "#00ff80"})
        lighting = load_config(self.path).lighting
        self.assertEqual((lighting.hypershift, lighting.hypershift_color), (True, "#00ff80"))

    def test_hypershift_lights_bad_values_mean_defaults(self):
        for raw in ("x", {"enabled": "yes", "color": "red"}, {"enabled": 1, "color": 5}):
            data = _stored([_entry("default", "Default")])
            data["lighting"]["hypershift"] = raw
            self._write(data)
            lighting = load_config(self.path).lighting
            self.assertEqual((lighting.hypershift, lighting.hypershift_color), (False, "#ff6000"), raw)

    def test_lighting_enabled_not_bool_means_true(self):
        data = _stored([_entry("default", "Default")])
        data["lighting"]["enabled"] = "no"
        self._write(data)
        lighting = load_config(self.path).lighting
        self.assertIs(lighting.enabled, True)
        self.assertEqual((lighting.effect, lighting.color, lighting.brightness), ("static", "#ff0000", 40))

    def test_actuation_round_trip(self):
        c = default_config()
        default_profile(c).actuation = {"k01": 2.5, "k20": 3.6}
        save_config(self.path, c)
        self.assertEqual(json.loads(self.path.read_text())["profiles"][0]["actuation"], {"k01": 2.5, "k20": 3.6})
        self.assertEqual(load_config(self.path), c)

    def test_v2_file_without_actuation_loads(self):
        self._write(_stored({}))
        self.assertEqual(default_profile(load_config(self.path)).actuation, {})

    def test_bad_actuation_dropped(self):
        bad = {"k01": 1.4, "k02": 2.55, "k03": "2", "top_button": 2.0, "k99": 2.0, "k04": True}
        entry = _entry("default", "Default")
        entry["actuation"] = dict(bad, k05=2.6000000000000005, k06=1.5)
        self._write(_stored([entry]))
        with self.assertLogs("tartarus", "WARNING") as logs:
            c = load_config(self.path)
        self.assertEqual(default_profile(c).actuation, {"k05": 2.6})
        self.assertEqual(len(logs.records), len(bad))
        for raw in ([2.5], "k01", None):
            entry["actuation"] = raw
            self._write(_stored([entry]))
            self.assertEqual(default_profile(load_config(self.path)).actuation, {}, raw)

    def test_secondary_round_trip(self):
        c = default_config()
        default_profile(c).secondary = {"k05": Secondary(parse_binding_text("Z"), 3.6)}
        save_config(self.path, c)
        stored = json.loads(self.path.read_text())["profiles"][0]["secondary"]
        self.assertEqual(stored, {"k05": {"binding": binding_to_dict(parse_binding_text("Z")), "actuation": 3.6}})
        self.assertEqual(load_config(self.path), c)

    def test_v2_file_without_secondary_loads(self):
        self._write(_stored({}))
        self.assertEqual(default_profile(load_config(self.path)).secondary, {})

    def test_bad_secondary_dropped(self):
        z = binding_to_dict(parse_binding_text("Z"))
        bad = {
            "top_button": {"binding": z, "actuation": 3.6},
            "k99": {"binding": z, "actuation": 3.6},
            "k01": {"binding": {"type": "nope"}, "actuation": 3.6},
            "k02": {"binding": z, "actuation": 3.7},
            "k03": {"binding": z, "actuation": 2.0},  # A 1.6: gap 0.4
            "k04": {"binding": z},
            "k06": [z, 3.6],
            "k07": {"binding": z, "actuation": 2.0},  # A 1.7 dropped as bad, so 1.5: kept
            "k08": {"binding": z, "actuation": 1.9},  # A 1.4 dropped as bad, so 1.5: gap 0.4
        }
        entry = _entry("default", "Default")
        entry["actuation"] = {"k03": 1.6, "k05": 1.6, "k07": 1.75, "k08": 1.4}
        entry["secondary"] = dict(bad, k05={"binding": z, "actuation": 2.1000000000000005})
        self._write(_stored([entry]))
        with self.assertLogs("tartarus", "WARNING") as logs:
            c = load_config(self.path)
        p = default_profile(c)
        self.assertTrue(gap_ok(1.6, 2.1))
        self.assertEqual(p.secondary, {"k05": Secondary(parse_binding_text("Z"), 2.1),
                                       "k07": Secondary(parse_binding_text("Z"), 2.0)})
        secondary_logs = [r for r in logs.records if "secondary" in r.getMessage()]
        self.assertEqual(len(secondary_logs), len(bad) - 1)
        for raw in ([z], "k01", None):
            entry["secondary"] = raw
            self._write(_stored([entry]))
            self.assertEqual(default_profile(load_config(self.path)).secondary, {}, raw)

    def test_hypershift_round_trip(self):
        c = default_config()
        p = c.profiles[0]
        p.bindings["k19"] = Binding("hypershift")
        p.hypershift.bindings.update({"k05": parse_binding_text("F1"), "dpad_up": parse_binding_text("F2")})
        p.hypershift.actuation["k05"] = 2.0
        p.hypershift.secondary["k05"] = Secondary(parse_binding_text("F3"), 3.0)
        save_config(self.path, c)
        q = load_config(self.path).profiles[0]
        self.assertEqual(hypershift_key(q), "k19")
        self.assertEqual(q.hypershift, p.hypershift)

    def test_file_without_hypershift_loads_empty(self):
        # a v2 file written before this change: no "hypershift" key anywhere
        entry = _entry("default", "Default", bindings={"k01": binding_to_dict(parse_binding_text("Q"))})
        entry["actuation"] = {"k01": 2.0}
        self._write(_stored([entry]))
        q = load_config(self.path).profiles[0]
        self.assertEqual(q.hypershift, Hypershift())
        self.assertIsNone(hypershift_key(q))

    def test_parse_extra_hypershift_keys_reset(self):
        hs = {"type": "hypershift"}
        self._write(_stored({"wheel_up": hs, "k03": hs, "k07": hs}))
        with self.assertLogs("tartarus", "WARNING"):
            q = load_config(self.path).profiles[0]
        self.assertEqual(hypershift_key(q), "k03")
        self.assertEqual(q.bindings["k07"], parse_binding_text("Q"))
        self.assertEqual(q.bindings["wheel_up"], parse_binding_text("WheelUp"))

    def test_parse_drops_bad_layer_entries(self):
        f1 = binding_to_dict(parse_binding_text("F1"))
        entry = _entry("default", "Default", bindings={"k19": {"type": "hypershift"}})
        entry["hypershift"] = {
            "bindings": {"k19": f1, "k02": {"type": "hypershift"}, "k99": f1, "k05": f1},
            "actuation": {"k06": 2.0, "k05": 1.55},
            "secondary": {"k05": {"binding": f1, "actuation": 1.7}},  # 0.2 mm deeper than the layer point
        }
        self._write(_stored([entry]))
        with self.assertLogs("tartarus", "WARNING"):
            q = load_config(self.path).profiles[0]
        self.assertEqual(hypershift_key(q), "k19")
        self.assertEqual(set(q.hypershift.bindings), {"k05"})
        self.assertEqual(q.hypershift.actuation, {})
        self.assertEqual(q.hypershift.secondary, {})

    def test_hypershift_key_loses_its_secondary(self):
        z = binding_to_dict(parse_binding_text("Z"))
        entry = _entry("default", "Default", bindings={"k19": {"type": "hypershift"}})
        entry["secondary"] = {"k19": {"binding": z, "actuation": 3.6}}
        self._write(_stored([entry]))
        with self.assertLogs("tartarus", "WARNING"):
            q = load_config(self.path).profiles[0]
        self.assertEqual(hypershift_key(q), "k19")
        self.assertNotIn("k19", q.secondary)

    def test_hypershift_copy_is_independent(self):
        h = Hypershift(bindings={"k05": parse_binding_text("F1")})
        h2 = h.copy()
        h2.bindings["k06"] = parse_binding_text("F2")
        self.assertEqual(set(h.bindings), {"k05"})

    def test_hypershift_type_secondary_dropped(self):
        hs = {"type": "hypershift"}
        f1 = binding_to_dict(parse_binding_text("F1"))
        entry = _entry("default", "Default", bindings={"k19": hs})
        entry["secondary"] = {"k05": {"binding": hs, "actuation": 3.0}}
        entry["hypershift"] = {"bindings": {"k06": f1},
                               "secondary": {"k06": {"binding": hs, "actuation": 3.0}}}
        self._write(_stored([entry]))
        with self.assertLogs("tartarus", "WARNING") as logs:
            q = load_config(self.path).profiles[0]
        self.assertEqual(q.secondary, {})
        self.assertEqual(q.hypershift.secondary, {})
        self.assertEqual(q.hypershift.bindings, {"k06": parse_binding_text("F1")})
        self.assertEqual(len(logs.records), 2)

    def test_corrupt_file_backed_up(self):
        self._write("{nope")
        with self.assertLogs("tartarus", "WARNING"):
            self.assertEqual(load_config(self.path), first_run_config())
        self.assertEqual(len(self._backups()), 1)
        self.assertFalse(self.path.exists())

    def test_wrong_version_backed_up(self):
        data = _stored({})
        data["version"] = 3
        self._write(data)
        with self.assertLogs("tartarus", "WARNING"):
            self.assertEqual(load_config(self.path), first_run_config())
        self.assertEqual(len(self._backups()), 1)
        self.assertFalse(self.path.exists())

    def _v1(self, profiles=None, active="b"):
        if profiles is None:
            profiles = [
                {"id": "a", "name": "A", "dpad_mode": "4way", "bindings": {"k01": {"type": "key", "keys": ["Esc"]}}},
                {"id": "b", "name": "B", "dpad_mode": "8way", "bindings": {"k01": {"type": "key", "keys": ["F1"]}}},
            ]
        return {"version": 1, "active_profile": active, "profiles": profiles,
                "lighting": {"effect": "static", "color": "#ff0000", "brightness": 40}}

    def test_migrates_v1_active_profile(self):
        self._write(self._v1())
        with self.assertLogs("tartarus", "INFO") as logs:
            c = load_config(self.path)
        bindings = factory_bindings()
        bindings["k01"] = Binding("key", ("F1",))
        self.assertEqual(c.profiles, [Profile("default", "Default", "8way", bindings, NO_LEDS)])
        self.assertEqual(c.games, {})
        self.assertEqual((c.lighting.effect, c.lighting.color, c.lighting.brightness), ("static", "#ff0000", 40))
        self.assertTrue(any("'a'" in line and "WARNING" in line for line in logs.output))

    def test_migrates_v1_missing_active_uses_first(self):
        self._write(self._v1(active="zzz"))
        with self.assertLogs("tartarus", "INFO"):
            c = load_config(self.path)
        self.assertEqual(default_profile(c).bindings["k01"], Binding("key", ("Esc",)))
        self.assertEqual(default_profile(c).dpad_mode, "4way")

    def test_migration_writes_backup_and_v2_file(self):
        self._write(json.dumps(self._v1(), indent=1))
        original = self.path.read_text()
        backup = self.dir / "settings.json.v1-backup"
        with self.assertLogs("tartarus", "INFO"):
            first = load_config(self.path)
        self.assertEqual(backup.read_text(), original)
        stored = json.loads(self.path.read_text())
        self.assertEqual(stored["version"], 2)
        self.assertNotIn("active_profile", stored)
        self.assertEqual(load_config(self.path), first)
        self.assertEqual(backup.read_text(), original)
        self.assertEqual(self._backups(), [])

    def test_migration_backup_does_not_follow_symlink(self):
        victim = self.dir / "victim"
        victim.write_text("untouched")
        backup = self.dir / "settings.json.v1-backup"
        backup.symlink_to(victim)
        self._write(self._v1())
        original = self.path.read_text()
        with self.assertLogs("tartarus", "INFO"):
            load_config(self.path)
        self.assertEqual(victim.read_text(), "untouched")
        self.assertFalse(backup.is_symlink())
        self.assertEqual(backup.read_text(), original)

    def test_migration_survives_write_failure(self):
        self._write(self._v1())
        with mock.patch("tartarus.config._write_atomic", side_effect=OSError("disk full")):
            with self.assertLogs("tartarus", "WARNING") as logs:
                c = load_config(self.path)
        self.assertEqual(default_profile(c).dpad_mode, "8way")
        self.assertEqual(json.loads(self.path.read_text())["version"], 1)
        self.assertTrue(any("disk full" in line for line in logs.output))

    def test_v1_file_gets_no_starters(self):
        self._write(self._v1())
        with self.assertLogs("tartarus", "INFO"):
            c = load_config(self.path)
        self.assertEqual(len(c.profiles), 1)
        self.assertEqual(len(load_config(self.path).profiles), 1)

    def test_v1_without_profiles_is_corrupt(self):
        self._write(self._v1(profiles=[]))
        with self.assertLogs("tartarus", "WARNING"):
            self.assertEqual(load_config(self.path), first_run_config())
        self.assertEqual(len(self._backups()), 1)
        self.assertFalse(self.path.exists())

    def test_v2_round_trip(self):
        c = default_config()
        c.profiles.append(Profile("p2", "MMO", "8way", factory_bindings(), (True, False, False)))
        c.games["1343400"] = Game("RuneScape", "p2")
        save_config(self.path, c)
        self.assertEqual(load_config(self.path), c)

    def test_default_config_shape(self):
        c = default_config()
        self.assertEqual(c.profiles, [Profile("default", "Default", "4way", steamos_bindings(), NO_LEDS)])
        self.assertEqual(c.games, {})
        self.assertEqual(c.version, 2)

    def test_default_parsed_first_and_kept(self):
        self._write(_stored([_entry("p2", "MMO", [True, False, False]), _entry("default", "Default")]))
        c = load_config(self.path)
        self.assertEqual([p.id for p in c.profiles], ["default", "p2"])
        self._write(_stored([_entry("p2", "MMO", [True, False, False])]))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertEqual(c.profiles[0], Profile("default", "Default", "4way", steamos_bindings(), NO_LEDS))
        self.assertEqual([p.id for p in c.profiles], ["default", "p2"])

    def test_profiles_beyond_eight_skipped(self):
        leds = [[True, False, False], [False, True, False], [False, False, True], [True, True, False],
                [True, False, True], [False, True, True], [True, True, True], [True, False, False],
                [False, True, False]]
        entries = [_entry("default", "Default")] + [_entry(f"p{i}", f"P{i}", leds[i - 2]) for i in range(2, 11)]
        self._write(_stored(entries))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertEqual([p.id for p in c.profiles], ["default"] + [f"p{i}" for i in range(2, 9)])

    def test_duplicate_ids_and_names_skipped(self):
        self._write(_stored([
            _entry("default", "Default"),
            _entry("p2", "MMO", [True, False, False]),
            _entry("p2", "Other", [False, True, False]),
            _entry("p3", "mmo", [False, False, True]),
        ]))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertEqual([(p.id, p.name) for p in c.profiles], [("default", "Default"), ("p2", "MMO")])

    def test_bad_name_skipped_default_renamed(self):
        self._write(_stored([
            _entry("default", "  "),
            _entry("p2", "", [True, False, False]),
            _entry("p3", "x" * 25, [False, True, False]),
            _entry("p4", " FPS ", [False, False, True]),
        ]))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertEqual([(p.id, p.name) for p in c.profiles], [("default", "Default"), ("p4", "FPS")])

    def test_bad_or_duplicate_leds_reassigned(self):
        self._write(_stored([
            _entry("default", "Default", [True, True, True]),
            _entry("p2", "A", [True, False, False]),
            _entry("p3", "B", [True, False, False]),
            _entry("p4", "C", "x"),
        ]))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertEqual([p.leds for p in c.profiles],
                         [NO_LEDS, (True, False, False), (False, True, False), (False, False, True)])

    def test_bad_assignments_dropped(self):
        ok = {"name": "RS", "profile": "p2"}
        self._write(_stored(
            [_entry("default", "Default"), _entry("p2", "MMO", [True, False, False])],
            {"1343400": ok, "12": {"name": "X", "profile": "nope"}, "abc": ok, "-1": ok,
             "4294967296": ok, "0": ok, "5": {"name": "D", "profile": "default"}},
        ))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertEqual(c.games, {"1343400": Game("RS", "p2")})

    def test_unhashable_assignment_profile_dropped(self):
        self._write(_stored(
            [_entry("default", "Default"), _entry("p2", "MMO", [True, False, False])],
            {"1": {"name": "A", "profile": ["p2"]}, "2": {"name": "B", "profile": {"x": 1}},
             "3": {"name": "C", "profile": "p2"}},
        ))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertEqual(c.games, {"3": Game("C", "p2")})

    def test_bad_leds_before_valid_do_not_steal_pattern(self):
        self._write(_stored([
            _entry("default", "Default"),
            _entry("p2", "A", "x"),
            _entry("p3", "B", [True, False, False]),
        ]))
        with self.assertLogs("tartarus", "WARNING"):
            c = load_config(self.path)
        self.assertEqual([p.leds for p in c.profiles], [NO_LEDS, (False, True, False), (True, False, False)])

    def test_non_string_game_name_falls_back_to_key(self):
        self._write(_stored(
            [_entry("default", "Default"), _entry("p2", "MMO", [True, False, False])],
            {"1343400": {"name": 7, "profile": "p2"}},
        ))
        self.assertEqual(load_config(self.path).games, {"1343400": Game("1343400", "p2")})

    def test_profile_for_app(self):
        c = default_config()
        mmo = Profile("p2", "MMO", "8way", factory_bindings(), (True, False, False))
        c.profiles.append(mmo)
        c.games["1343400"] = Game("RuneScape", "p2")
        self.assertIs(profile_for_app(c, 1343400), mmo)
        self.assertIs(profile_for_app(c, 99), c.profiles[0])
        self.assertIs(profile_for_app(c, None), c.profiles[0])

    def test_next_leds_and_clean_name(self):
        c = default_config()
        self.assertEqual(next_leds(c), (True, False, False))
        with self.assertRaises(ValueError):
            clean_name(c, " Default ")
        self.assertEqual(clean_name(c, " default ", exclude_id="default"), "default")
        with self.assertRaises(ValueError):
            clean_name(c, "x" * 25)
        with self.assertRaises(ValueError):
            clean_name(c, "  ")

    def test_next_leds_exhausted_and_new_profile_id(self):
        c = default_config()
        self.assertEqual(new_profile_id(c), "p2")
        for i, leds in enumerate(LED_ORDER, start=2):
            c.profiles.append(Profile(f"p{i}", f"P{i}", "4way", factory_bindings(), leds))
        with self.assertRaises(ValueError):
            next_leds(c)
        del c.profiles[2]
        self.assertEqual(new_profile_id(c), "p3")

    def test_save_is_atomic(self):
        save_config(self.path, default_config())
        self.assertTrue(self.path.exists())
        self.assertEqual(list(self.dir.glob("*.tmp")), [])
        stored = json.loads(self.path.read_text())
        self.assertEqual(stored["profiles"][0]["bindings"]["k14"], binding_to_dict(parse_binding_text("Esc")))


if __name__ == "__main__":
    unittest.main()
