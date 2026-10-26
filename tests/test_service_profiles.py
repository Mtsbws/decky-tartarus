import asyncio
import tempfile
import unittest
from pathlib import Path

from tartarus.bindings import parse_binding_text
from tartarus.config import Config, Game, Profile, default_config, factory_bindings, load_config, save_config
from tartarus.linux.evdev import EV_KEY, EV_SYN

from tests.test_service import KEY_1, KEY_ESC, TWO_NODES, Rig, until

RUNESCAPE = 1343400


def write_settings(path):
    c = default_config()
    mmo = factory_bindings()
    mmo["k01"] = parse_binding_text("Esc")
    c.profiles.append(Profile(id="p2", name="MMO", dpad_mode="4way", bindings=mmo,
                            leds=(True, False, False)))
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
