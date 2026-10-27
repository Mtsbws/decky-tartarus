import asyncio
import tempfile
import unittest
from pathlib import Path

from tartarus.config import NO_LEDS, Game, Profile, default_config, factory_bindings, save_config
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


if __name__ == "__main__":
    unittest.main()
