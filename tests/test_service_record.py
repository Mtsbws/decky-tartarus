import asyncio
import tempfile
import unittest
from pathlib import Path

from tartarus.linux.evdev import EV_KEY, EV_SYN
from tartarus.service import STEAM_ACTION_MODE

from tests.test_service import TWO_NODES, Rig, until

KEY_1, KEY_LEFTCTRL, KEY_C = 2, 29, 46


class FakeEngine:
    def __init__(self):
        self.passthrough = False

    def release_all(self):
        pass

    def set_profile(self, profile):
        pass


class RecordTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"

    def tearDown(self):
        self._tmp.cleanup()

    def run_async(self, coro):
        return asyncio.run(asyncio.wait_for(coro, 5))

    def results(self, rig):
        return [e for e in rig.events if e[0] == "record_result"]

    def test_record_restores_passthrough(self):
        async def go():
            rig = Rig(self.path)
            rig.service._engine = engine = FakeEngine()
            rig.service._loop = asyncio.get_running_loop()
            rig.service.record_start()
            self.assertIs(engine.passthrough, True)
            rig.service.record_cancel()
            self.assertIs(engine.passthrough, False)
            rig.service.record_cancel()  # a second cancel is harmless
            await asyncio.sleep(0.01)
            self.assertEqual(self.results(rig), [])

        self.run_async(go())

    def test_keypad_press_records_factory_name_once(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            rig.service.record_start()
            kbd = rig.devices[0]
            kbd.push((EV_KEY, KEY_1, 1), (EV_SYN, 0, 0), (EV_KEY, KEY_1, 0), (EV_SYN, 0, 0))
            await until(lambda: self.results(rig))
            self.assertEqual(self.results(rig), [("record_result", {"type": "key", "keys": ["1"]})])
            self.assertFalse(rig.service._engine.passthrough)
            # Recording is over: a second press is remapped again and records nothing.
            kbd.push((EV_KEY, KEY_1, 1), (EV_KEY, KEY_1, 0))
            await asyncio.sleep(0.05)
            self.assertEqual(len(self.results(rig)), 1)
            await rig.service.stop()

        self.run_async(go())

    def test_other_keyboard_records_shortcut_without_grab(self):
        async def go():
            rig = Rig(self.path)
            rig.service._list_keyboards = lambda: ["/dev/input/event3"]
            await rig.service.start()
            rig.service.record_start()
            other = rig.devices[-1]
            self.assertEqual(other.path, "/dev/input/event3")
            self.assertFalse(other.grabbed)
            other.push((EV_KEY, KEY_LEFTCTRL, 1), (EV_KEY, KEY_C, 1), (EV_KEY, KEY_C, 0), (EV_KEY, KEY_LEFTCTRL, 0))
            await until(lambda: self.results(rig))
            self.assertEqual(self.results(rig), [("record_result", {"type": "shortcut", "keys": ["Ctrl", "C"]})])
            self.assertTrue(other.closed)
            await rig.service.stop()

        self.run_async(go())

    def test_record_timeout_emits_null(self):
        async def go():
            rig = Rig(self.path)
            rig.service.RECORD_TIMEOUT = 0.02
            await rig.service.start()
            rig.service.record_start()
            await until(lambda: self.results(rig))
            self.assertEqual(self.results(rig), [("record_result", None)])
            self.assertFalse(rig.service._engine.passthrough)
            await rig.service.stop()

        self.run_async(go())

    def test_steam_action_is_emitted(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            rig.service._on_steam("qam")
            await until(lambda: ("steam_action", "qam") in rig.events)
            await rig.service.stop()

        self.assertEqual(STEAM_ACTION_MODE, "api")
        self.run_async(go())


if __name__ == "__main__":
    unittest.main()
