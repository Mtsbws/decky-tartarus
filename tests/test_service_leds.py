import asyncio
import tempfile
import unittest
from pathlib import Path

from tartarus.config import (LED_ORDER, NO_LEDS, Game, Profile, default_config, factory_bindings, find_profile,
                             load_config, save_config)
from tartarus.lighting import effect_reports, leds_report

from tests.test_service import TWO_NODES, Rig, until
from tests.test_service_lighting import FakeSender

P2_LEDS = (True, False, False)


def write_settings(path):
    c = default_config()
    c.profiles.append(Profile(id="p2", name="MMO", dpad_mode="4way", bindings=factory_bindings(), leds=P2_LEDS))
    c.games = {"5": Game(name="X", profile="p2")}
    save_config(path, c)


class LedServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"
        write_settings(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def run_async(self, coro):
        return asyncio.run(asyncio.wait_for(coro, 5))

    async def connected(self, sender):
        rig = Rig(self.path, send_feature=sender)
        await rig.service.start()
        rig.nodes = TWO_NODES
        await until(lambda: rig.service.state()["connected"])
        return rig

    def reports(self, sender):
        return [report for _, report in sender.sent]

    def test_connect_sends_leds_after_lighting(self):
        async def go():
            sender = FakeSender()
            rig = await self.connected(sender)
            self.assertEqual(self.reports(sender),
                             effect_reports("spectrum", "#00ff00", 100) + [leds_report(NO_LEDS)])
            await rig.service.stop()

        self.run_async(go())

    def test_switch_sends_active_leds(self):
        async def go():
            sender = FakeSender()
            rig = await self.connected(sender)
            rig.service.set_running_app(5, "X")
            self.assertEqual(self.reports(sender)[-1], leds_report(P2_LEDS))
            count = len(sender.sent)
            rig.service.set_running_app(5, "X")
            self.assertEqual(len(sender.sent), count)
            rig.service.set_running_app(None, None)
            self.assertEqual(self.reports(sender)[-1], leds_report(NO_LEDS))
            await rig.service.stop()

        self.run_async(go())

    def test_set_lighting_resends_leds(self):
        async def go():
            sender = FakeSender()
            rig = await self.connected(sender)
            rig.service.set_running_app(5, "X")
            sender.sent.clear()
            rig.service.set_lighting("static", "#ff0000", 40)
            self.assertEqual(self.reports(sender),
                             effect_reports("static", "#ff0000", 40) + [leds_report(P2_LEDS)])
            await rig.service.stop()

        self.run_async(go())

    def test_resume_resends_leds(self):
        async def go():
            sender = FakeSender()
            rig = await self.connected(sender)
            rig.service._resume.check = lambda boottime, monotonic: True
            await until(lambda: len(rig.devices) >= 4)
            await until(lambda: rig.service.state()["connected"])
            await until(lambda: self.reports(sender).count(leds_report(NO_LEDS)) >= 2)
            self.assertEqual(self.reports(sender).count(leds_report(NO_LEDS)), 2)
            await rig.service.stop()

        self.run_async(go())

    def test_led_failure_is_logged_not_raised(self):
        async def go():
            sender = FakeSender()
            rig = await self.connected(sender)
            sender.status = 0x05
            with self.assertLogs("tartarus", "WARNING"):
                rig.service.set_running_app(5, "X")
            self.assertEqual(rig.service.state()["active_profile"], "p2")
            await rig.service.stop()

        self.run_async(go())

    def test_no_send_while_disconnected(self):
        sender = FakeSender()
        rig = Rig(self.path, send_feature=sender)
        rig.service.set_running_app(5, "X")
        rig.service.set_running_app(None, None)
        self.assertEqual(sender.sent, [])

    def test_set_leds_persists_and_sends_when_active(self):
        async def go():
            sender = FakeSender()
            rig = await self.connected(sender)
            sender.sent.clear()
            rig.service.set_leds("p2", [False, True, True])  # p2 isn't active: nothing sent
            self.assertEqual(sender.sent, [])
            self.assertEqual(find_profile(load_config(self.path), "p2").leds, (False, True, True))
            rig.service.set_running_app(5, "X")
            rig.service.set_leds("p2", [True, True, True])
            self.assertEqual(self.reports(sender)[-1], leds_report((True, True, True)))
            self.assertEqual(find_profile(load_config(self.path), "p2").leds, (True, True, True))
            await rig.service.stop()

        self.run_async(go())

    def test_set_leds_rejects(self):
        sender = FakeSender()
        rig = Rig(self.path, send_feature=sender)
        p3 = rig.service.create_profile("Shooter", "default")  # takes the next free pattern, (False, True, False)
        before = self.path.read_text()
        cases = [("default", [True, True, True]), ("p2", [False, True, False]), ("p2", [False, False, False]),
                 ("p2", [1, 0, 0]), ("p2", [0, 1, 1]), ("p2", [True, False]), ("p2", (True, True, True, False)),
                 ("p2", "TFT"), ("nope", [True, True, True])]
        for profile_id, leds in cases:
            with self.subTest(profile_id=profile_id, leds=leds):
                with self.assertRaises(ValueError):
                    rig.service.set_leds(profile_id, leds)
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(sender.sent, [])
        profiles = {p["id"]: p["leds"] for p in rig.service.state()["profiles"]}
        self.assertEqual(profiles, {"default": [False, False, False], "p2": [True, False, False],
                                    p3: [False, True, False]})

    def test_state_lists_patterns(self):
        state = Rig(self.path).service.state()
        self.assertEqual(state["led_patterns"], [list(p) for p in LED_ORDER])
        self.assertEqual([p["leds"] for p in state["profiles"]], [[False, False, False], [True, False, False]])

    def test_state_orders_profiles_by_lights_after_default(self):
        service = Rig(self.path).service
        p3 = service.create_profile("FPS", "default")  # gets the next free pattern, green
        service.set_leds("p2", [False, False, True])  # orange → blue: p2 moves below p3
        state = service.state()
        self.assertEqual([p["id"] for p in state["profiles"]], ["default", p3, "p2"])
        self.assertTrue(state["profiles"][0]["is_default"])


if __name__ == "__main__":
    unittest.main()
