import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tartarus.actuation import DEFAULT_MM, gap_ok
from tartarus.bindings import parse_binding_text
from tartarus.config import (Config, Game, Profile, Secondary, default_config, factory_bindings, find_profile, hypershift_key,
                             load_config, save_config)
from tartarus.linux.evdev import EV_KEY, EV_SYN

from tests.test_service import KEY_1, KEY_ESC, TWO_NODES, Rig, until

RUNESCAPE = 1343400


def write_settings(path):
    c = default_config()
    c.profiles[0].bindings = factory_bindings()  # the tests press factory keys on Default too
    mmo = factory_bindings()
    mmo["k01"] = parse_binding_text("Esc")
    c.profiles.append(Profile(id="p2", name="MMO", dpad_mode="4way", bindings=mmo,
                            leds=(True, False, False), actuation={"k02": 2.5},
                            secondary={"k02": Secondary(parse_binding_text("Z"), 3.6)}))
    c.games = {str(RUNESCAPE): Game(name="RuneScape", profile="p2")}
    save_config(path, c)


class ProfileSwitchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"
        write_settings(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def run_async(self, coro):
        return asyncio.run(asyncio.wait_for(coro, 5))

    async def connected(self):
        rig = Rig(self.path)
        await rig.service.start()
        rig.nodes = TWO_NODES
        await until(lambda: rig.service.state()["connected"])
        return rig

    def test_starts_on_default(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            state = rig.service.state()
            self.assertEqual(state["active_profile"], "default")
            self.assertIsNone(state["running_app"])
            await rig.service.stop()

        self.run_async(go())

    def test_failed_name_save_still_switches(self):
        async def go():
            rig = await self.connected()
            with mock.patch("tartarus.service.save_config", side_effect=OSError("disk full")):
                rig.service.set_running_app(RUNESCAPE, "RuneScape Renamed")
            self.assertEqual(rig.service.state()["active_profile"], "p2")
            await rig.service.stop()

        self.run_async(go())

    def test_running_app_switches_and_back(self):
        async def go():
            rig = await self.connected()
            kbd = rig.devices[0]
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            state = rig.service.state()
            self.assertEqual(state["active_profile"], "p2")
            self.assertEqual(state["running_app"], {"app_id": RUNESCAPE, "name": "RuneScape"})
            kbd.push((EV_KEY, KEY_1, 1), (EV_SYN, 0, 0))
            await until(lambda: ("key", KEY_ESC, True) in rig.emitter.out)
            kbd.push((EV_KEY, KEY_1, 0), (EV_SYN, 0, 0))
            await until(lambda: ("key", KEY_ESC, False) in rig.emitter.out)
            rig.service.set_running_app(None, None)
            self.assertEqual(rig.service.state()["active_profile"], "default")
            self.assertIsNone(rig.service.state()["running_app"])
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            rig.service.set_running_app(42, "Other")
            self.assertEqual(rig.service.state()["active_profile"], "default")
            await rig.service.stop()

        self.run_async(go())

    def test_switch_releases_held_key(self):
        async def go():
            rig = await self.connected()
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            rig.devices[0].push((EV_KEY, KEY_1, 1), (EV_SYN, 0, 0))
            await until(lambda: ("key", KEY_ESC, True) in rig.emitter.out)
            rig.service.set_running_app(None, None)
            self.assertEqual([e for e in rig.emitter.out if e[0] == "key"][-1], ("key", KEY_ESC, False))
            await rig.service.stop()

        self.run_async(go())

    def count_set_profile(self, rig):
        calls = []
        original = rig.service._engine.set_profile

        def counting(profile):
            calls.append(profile.id)
            original(profile)

        rig.service._engine.set_profile = counting
        return calls

    def test_same_report_is_a_noop(self):
        async def go():
            rig = await self.connected()
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            await asyncio.sleep(0.01)
            mtime = self.path.stat().st_mtime_ns
            events = len(rig.events)
            calls = self.count_set_profile(rig)
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            await asyncio.sleep(0.01)
            self.assertEqual(self.path.stat().st_mtime_ns, mtime)
            self.assertEqual(len(rig.events), events)
            self.assertEqual(calls, [])
            await rig.service.stop()

        self.run_async(go())

    def test_report_after_restart_switches(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            self.assertEqual(rig.service._engine._profile.id, "p2")
            await rig.service.stop()

        self.run_async(go())

    def test_report_without_engine_only_stores(self):
        async def go():
            rig = Rig(self.path)
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            self.assertEqual(rig.service.state()["active_profile"], "p2")
            await rig.service.start()
            self.assertEqual(rig.service._engine._profile.id, "p2")
            await rig.service.stop()

        self.run_async(go())

    def test_assigned_name_updated_without_set_profile(self):
        async def go():
            rig = await self.connected()
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            calls = self.count_set_profile(rig)
            rig.service.set_running_app(RUNESCAPE, "RuneScape NXT")
            self.assertEqual(load_config(self.path).games[str(RUNESCAPE)].name, "RuneScape NXT")
            self.assertEqual(rig.service.state()["profiles"][1]["games"], ["RuneScape NXT"])
            self.assertEqual(calls, [])
            rig.service.set_running_app(42, "Other")
            self.assertNotIn("42", load_config(self.path).games)
            await rig.service.stop()

        self.run_async(go())

    def test_bad_app_id_rejected(self):
        rig = Rig(self.path)
        for bad in (-1, 2 ** 32, "12", True):
            with self.assertRaises(ValueError):
                rig.service.set_running_app(bad, "x")
        self.assertIsNone(rig.service.state()["running_app"])

    def test_switch_cancels_record(self):
        async def go():
            rig = await self.connected()
            rig.service.record_start()
            self.assertTrue(rig.service._engine.passthrough)
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            await until(lambda: ("record_result", None) in rig.events)
            self.assertFalse(rig.service._engine.passthrough)
            await rig.service.stop()

        self.run_async(go())

    def test_edit_non_active_profile(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            calls = self.count_set_profile(rig)
            rig.service.set_binding("p2", "k01", parse_binding_text("F1"))
            self.assertEqual(load_config(self.path).profiles[1].bindings["k01"], parse_binding_text("F1"))
            self.assertEqual(calls, [])
            rig.service.set_binding("default", "k01", parse_binding_text("F2"))
            self.assertEqual(calls, ["default"])
            with self.assertRaises(ValueError):
                rig.service.set_binding("nope", "k01", parse_binding_text("F1"))
            with self.assertRaises(ValueError):
                rig.service.set_dpad_mode("nope", "8way")
            await rig.service.stop()

        self.run_async(go())


    def keys(self, rig):
        return [e for e in rig.emitter.out if e[0] == "key"]

    def unassign_file(self):
        c = load_config(self.path)
        c.games = {}
        save_config(self.path, c)

    def test_assign_running_game(self):
        async def go():
            self.unassign_file()
            rig = await self.connected()
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            self.assertEqual(rig.service.state()["active_profile"], "default")
            rig.devices[0].push((EV_KEY, KEY_1, 1), (EV_SYN, 0, 0))
            await until(lambda: ("key", KEY_1, True) in rig.emitter.out)
            rig.service.assign_running_game("p2")
            self.assertEqual(self.keys(rig)[-1], ("key", KEY_1, False))
            self.assertEqual(rig.service.state()["active_profile"], "p2")
            self.assertEqual(load_config(self.path).games[str(RUNESCAPE)], Game(name="RuneScape", profile="p2"))
            rig.service.assign_running_game("default")
            self.assertEqual(rig.service.state()["active_profile"], "default")
            self.assertNotIn(str(RUNESCAPE), load_config(self.path).games)
            with self.assertRaises(ValueError):
                rig.service.assign_running_game("nope")
            rig.service.set_running_app(None, None)
            before = self.path.read_bytes()
            rig.service.assign_running_game("p2")
            self.assertEqual(self.path.read_bytes(), before)
            await rig.service.stop()

        self.run_async(go())

    def test_create_profile_copies_and_caps(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            svc = rig.service
            new_id = svc.create_profile(" FPS ", "p2")
            c = load_config(self.path)
            fps, mmo = c.profiles[-1], c.profiles[1]
            self.assertEqual(fps.id, new_id)
            self.assertEqual(fps.name, "FPS")
            self.assertEqual(fps.bindings, mmo.bindings)
            self.assertEqual(fps.dpad_mode, mmo.dpad_mode)
            self.assertEqual(fps.leds, (False, True, False))
            self.assertEqual(fps.actuation, {"k02": 2.5})
            self.assertEqual(fps.secondary, {"k02": Secondary(parse_binding_text("Z"), 3.6)})
            svc.set_binding(new_id, "k01", parse_binding_text("F5"))
            self.assertEqual(load_config(self.path).profiles[1].bindings["k01"], parse_binding_text("Esc"))
            for i in range(8 - len(load_config(self.path).profiles)):
                svc.create_profile(f"P{i}", "default")
            before = self.path.read_bytes()
            for args in (("Extra", "default"), ("mmo", "default"), ("", "default"), ("x" * 25, "default")):
                with self.assertRaises(ValueError):
                    svc.create_profile(*args)
            self.assertEqual(self.path.read_bytes(), before)
            await rig.service.stop()

        self.run_async(go())

    def test_create_clash_and_unknown_source(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                rig.service.create_profile("mmo", "default")
            with self.assertRaises(ValueError):
                rig.service.create_profile("Fine", "nope")
            self.assertEqual(self.path.read_bytes(), before)
            await rig.service.stop()

        self.run_async(go())

    def test_led_reuse_after_delete(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            svc = rig.service
            svc._config.profiles.clear()
            svc._config.profiles.extend(default_config().profiles)
            svc._config.games.clear()
            a = svc.create_profile("A", "default")
            b = svc.create_profile("B", "default")
            c = svc.create_profile("C", "default")
            self.assertEqual([p.leds for p in svc._config.profiles[1:]],
                             [(True, False, False), (False, True, False), (False, False, True)])
            svc.delete_profile(b)
            d = svc.create_profile("D", "default")
            self.assertEqual(svc._config.profiles[-1].leds, (False, True, False))
            await rig.service.stop()

        self.run_async(go())

    def test_rename_profile(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            svc = rig.service
            svc.rename_profile("p2", "Raid")
            c = load_config(self.path)
            self.assertEqual(c.profiles[1].name, "Raid")
            self.assertEqual(c.games[str(RUNESCAPE)].profile, "p2")
            svc.rename_profile("default", "Base")
            self.assertEqual(load_config(self.path).profiles[0].name, "Base")
            self.assertEqual(svc.state()["active_profile"], "default")
            svc.rename_profile("p2", "RAID")
            self.assertEqual(load_config(self.path).profiles[1].name, "RAID")
            with self.assertRaises(ValueError):
                svc.rename_profile("p2", "base")
            with self.assertRaises(ValueError):
                svc.rename_profile("nope", "X")
            await rig.service.stop()

        self.run_async(go())

    def test_rename_does_not_touch_engine(self):
        async def go():
            rig = await self.connected()
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            rig.devices[0].push((EV_KEY, KEY_1, 1), (EV_SYN, 0, 0))
            await until(lambda: ("key", KEY_ESC, True) in rig.emitter.out)
            calls = self.count_set_profile(rig)
            rig.service.rename_profile("p2", "Raid")
            rig.service.create_profile("New", "p2")
            self.assertEqual(calls, [])
            self.assertEqual(self.keys(rig)[-1], ("key", KEY_ESC, True))
            await rig.service.stop()

        self.run_async(go())

    def test_delete_profile(self):
        async def go():
            rig = await self.connected()
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            rig.devices[0].push((EV_KEY, KEY_1, 1), (EV_SYN, 0, 0))
            await until(lambda: ("key", KEY_ESC, True) in rig.emitter.out)
            rig.service.delete_profile("p2")
            self.assertEqual(self.keys(rig)[-1], ("key", KEY_ESC, False))
            self.assertEqual(rig.service.state()["active_profile"], "default")
            c = load_config(self.path)
            self.assertEqual([p.id for p in c.profiles], ["default"])
            self.assertNotIn(str(RUNESCAPE), c.games)
            with self.assertRaises(ValueError):
                rig.service.delete_profile("default")
            with self.assertRaises(ValueError):
                rig.service.delete_profile("nope")
            await rig.service.stop()

        self.run_async(go())

    def test_reassign_via_delete_other_keeps_active(self):
        async def go():
            rig = await self.connected()
            rig.service.create_profile("Other", "default")
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            rig.devices[0].push((EV_KEY, KEY_1, 1), (EV_SYN, 0, 0))
            await until(lambda: ("key", KEY_ESC, True) in rig.emitter.out)
            calls = self.count_set_profile(rig)
            rig.service.delete_profile("p3")
            self.assertEqual(calls, [])
            self.assertEqual(self.keys(rig)[-1], ("key", KEY_ESC, True))
            await rig.service.stop()

        self.run_async(go())

    def test_profile_ops_emit_state(self):
        async def go():
            self.unassign_file()
            rig = await self.connected()
            rig.service.set_running_app(RUNESCAPE, "RuneScape")
            ops = [lambda: rig.service.assign_running_game("p2"),
                   lambda: rig.service.create_profile("New", "default"),
                   lambda: rig.service.rename_profile("p3", "Newer"),
                   lambda: rig.service.delete_profile("p3")]
            for op in ops:
                await asyncio.sleep(0.01)
                n = len([e for e in rig.events if e[0] == "state_changed"])
                op()
                await until(lambda: len([e for e in rig.events if e[0] == "state_changed"]) > n)
            await rig.service.stop()

        self.run_async(go())


class CopyStarterTest(unittest.TestCase):
    """A fresh install's MMO (p4) copied through the service: Review Focus 3 and 4."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"  # no file: a fresh install

    def tearDown(self):
        self._tmp.cleanup()

    def test_copy_of_mmo_keeps_its_layer_and_shares_nothing(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            svc = rig.service
            new_id = svc.create_profile("My MMO", "p4")
            c = load_config(self.path)
            mmo, copy = find_profile(c, "p4"), find_profile(c, new_id)
            self.assertEqual(mmo.name, "MMO")
            self.assertEqual(hypershift_key(copy), "k19")
            self.assertEqual(copy.hypershift, mmo.hypershift)
            self.assertEqual(len(copy.hypershift.bindings), 12)
            self.assertEqual(copy.secondary, {"k18": Secondary(parse_binding_text("B"), 3.0)})
            self.assertTrue(gap_ok(copy.actuation.get("k18", DEFAULT_MM), copy.secondary["k18"].actuation))

            mmo_before = find_profile(c, "p4")
            svc.set_binding(new_id, "k02", parse_binding_text("F5"))
            svc.set_binding(new_id, "k02.h", parse_binding_text("F6"))
            svc.set_actuation(new_id, "k03", 2.0)
            svc.set_secondary(new_id, "k18", None)
            self.assertEqual(find_profile(load_config(self.path), "p4"), mmo_before)
            self.assertEqual(find_profile(svc._config, "p4"), mmo_before)
            await rig.service.stop()

        self.run_async(go())

    def test_failed_copies_change_nothing(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            svc = rig.service
            svc.create_profile("Spare", "p4")  # writes the file
            before = self.path.read_bytes()
            for args in (("MMO", "p4"), ("Fine", "nope")):
                with self.assertRaises(ValueError):
                    svc.create_profile(*args)
            self.assertEqual(self.path.read_bytes(), before)
            for i in range(8 - len(load_config(self.path).profiles)):
                svc.create_profile(f"P{i}", "p4")
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                svc.create_profile("Ninth", "p4")
            self.assertEqual(self.path.read_bytes(), before)
            await rig.service.stop()

        self.run_async(go())

    def test_fresh_install_writes_the_starters_once(self):
        Rig(self.path)
        written = load_config(self.path)
        self.assertEqual([p.name for p in written.profiles], ["Default", "FPS – WASD", "FPS – D-pad", "MMO"])
        before = self.path.read_bytes()
        # A later release with different starters must not reach an install that already has a file.
        with mock.patch("tartarus.config.STARTERS", ()):
            Rig(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_corrupt_file_recovery_writes_the_starters(self):
        self.path.write_text("{not json")
        Rig(self.path)
        self.assertTrue(self.path.exists())
        self.assertEqual(len(load_config(self.path).profiles), 4)
        self.assertEqual(len(list(self.path.parent.glob("settings.json.corrupt-*"))), 1)

    def test_failed_first_write_still_starts(self):
        with mock.patch("tartarus.service.save_config", side_effect=OSError("read-only")):
            rig = Rig(self.path)
        self.assertEqual(len(rig.service.state()["profiles"]), 4)
        self.assertFalse(self.path.exists())

    def run_async(self, coro):
        return asyncio.run(asyncio.wait_for(coro, 5))
