import asyncio
import errno
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tartarus.bindings import parse_binding_text
from tartarus.config import NO_LEDS, SCHEMA_VERSION, load_config
from tartarus.devmap import FACTORY_CODES
from tartarus.lighting import EFFECTS, effect_reports, leds_report
from tartarus.linux import hidraw, ioctl
from tartarus.linux.discovery import TartarusNodes

from tests.test_service import TWO_NODES, Rig, until

HID = "/dev/hidraw8"
K19 = next(code for code, control in FACTORY_CODES.items() if control == "k19")


class FakeSender:
    def __init__(self, status=0x02, error=None):
        self.sent = []
        self.status = status
        self.error = error

    def __call__(self, path, report):
        if self.error is not None:
            raise self.error
        self.sent.append((path, report))
        return self.status


class LightingServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"

    def tearDown(self):
        self._tmp.cleanup()

    def run_async(self, coro):
        return asyncio.run(asyncio.wait_for(coro, 5))

    def test_state_has_lighting(self):
        state = Rig(self.path, send_feature=FakeSender()).service.state()
        self.assertEqual(state["lighting"], {"effect": "spectrum", "color": "#00ff00", "brightness": 100,
                                             "enabled": True, "hypershift": {"enabled": False, "color": "#ff6000"}})
        self.assertEqual(state["effects"], list(EFFECTS))

    def test_set_lighting_persists_and_applies(self):
        async def go():
            sender = FakeSender()
            rig = Rig(self.path, send_feature=sender)
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            sender.sent.clear()
            rig.service.set_lighting("breathing", "#ff0000", 40)
            self.assertEqual(sender.sent, [("/dev/hidraw8", r) for r in effect_reports("breathing", "#ff0000", 40)
                                           + [leds_report(NO_LEDS)]])
            await rig.service.stop()

        self.run_async(go())
        lighting = load_config(self.path).lighting
        self.assertEqual((lighting.effect, lighting.color, lighting.brightness), ("breathing", "#ff0000", 40))

    def test_set_lighting_while_disconnected_only_saves(self):
        sender = FakeSender()
        rig = Rig(self.path, send_feature=sender)
        rig.service.set_lighting("static", "#0000ff", 20)
        self.assertEqual(sender.sent, [])
        self.assertEqual(load_config(self.path).lighting.effect, "static")
        self.assertEqual(rig.service.state()["lighting"]["color"], "#0000ff")

    def test_lighting_reapplied_on_connect(self):
        async def go():
            sender = FakeSender()
            rig = Rig(self.path, send_feature=sender)
            rig.service.set_lighting("wave", "#00ff00", 70)
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            expected = [("/dev/hidraw8", r) for r in effect_reports("wave", "#00ff00", 70) + [leds_report(NO_LEDS)]]
            self.assertEqual(sender.sent, expected)
            # Resume reconnects, and the lighting goes out again.
            rig.service._resume.check = lambda boottime, monotonic: True
            await until(lambda: len(sender.sent) >= 6)
            self.assertEqual(sender.sent[3:6], expected)
            await rig.service.stop()

        self.run_async(go())

    def test_bad_lighting_rejected(self):
        sender = FakeSender()
        rig = Rig(self.path, send_feature=sender)
        rig.service.set_lighting("static", "#123456", 30)
        before = self.path.read_text()
        for args in (("ripple", "#00ff00", 50), ("static", "#zzzzzz", 50), ("static", "#00ff00", 101)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    rig.service.set_lighting(*args)
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(rig.service.state()["lighting"], {"effect": "static", "color": "#123456", "brightness": 30,
                                                           "enabled": True, "hypershift": {"enabled": False, "color": "#ff6000"}})

    async def connected(self, sender):
        rig = Rig(self.path, send_feature=sender)
        await rig.service.start()
        rig.nodes = TWO_NODES
        await until(lambda: rig.service.state()["connected"])
        return rig

    def hypershift_rig(self, sender):
        async def make():
            rig = await self.connected(sender)
            rig.service.set_binding("default", "k19", parse_binding_text("hypershift"))
            return rig
        return make

    def test_hypershift_lights_sent_and_restored(self):
        async def go():
            sender = FakeSender()
            rig = await self.hypershift_rig(sender)()
            rig.service.set_lighting("wave", "#00ff00", 70)
            rig.service.set_hypershift_lights(True, "#12ab34")
            sender.sent.clear()
            rig.service._engine.handle_key(K19, 1)
            self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("static", "#12ab34", 70)])
            sender.sent.clear()
            rig.service._engine.handle_key(K19, 0)
            self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("wave", "#00ff00", 70)])
            await rig.service.stop()

        self.run_async(go())

    def test_hypershift_lights_off_or_lighting_off_send_nothing(self):
        async def go():
            sender = FakeSender()
            rig = await self.hypershift_rig(sender)()
            for lights, lighting in ((False, True), (True, False)):
                rig.service.set_hypershift_lights(lights, "#ff6000")
                rig.service.set_lighting_enabled(lighting)
                sender.sent.clear()
                rig.service._engine.handle_key(K19, 1)
                rig.service._engine.handle_key(K19, 0)
                self.assertEqual(sender.sent, [])
            await rig.service.stop()

        self.run_async(go())

    def test_hypershift_send_failure_is_logged_not_raised(self):
        async def go():
            sender = FakeSender()
            rig = await self.hypershift_rig(sender)()
            rig.service.set_hypershift_lights(True, "#ff6000")
            sender.error = OSError(errno.EIO, "gone")
            rig.service._engine.handle_key(K19, 1)
            rig.service._engine.handle_key(K19, 0)
            await rig.service.stop()

        self.run_async(go())

    def test_on_layer_never_raises_into_the_engine(self):
        async def go():
            sender = FakeSender()
            rig = await self.hypershift_rig(sender)()
            rig.service.set_hypershift_lights(True, "#ff6000")
            sender.error = RuntimeError("bug")
            with self.assertLogs("tartarus", level="ERROR"):
                rig.service._engine.handle_key(K19, 1)
            sender.error = None
            sender.sent.clear()
            rig.service._engine.handle_key(K19, 0)
            self.assertEqual(sender.sent, [(HID, r) for r in rig.service._lighting_reports()])
            await rig.service.stop()

        self.run_async(go())

    def test_hypershift_lights_change_while_held(self):
        async def go():
            sender = FakeSender()
            rig = await self.hypershift_rig(sender)()
            rig.service.set_lighting("wave", "#00ff00", 70)
            rig.service.set_hypershift_lights(True, "#12ab34")
            rig.service._engine.handle_key(K19, 1)
            sender.sent.clear()
            rig.service.set_hypershift_lights(True, "#aa0000")
            self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("static", "#aa0000", 70)])
            sender.sent.clear()
            rig.service.set_lighting("static", "#0000ff", 40)  # shown lights stay Hypershift
            self.assertEqual(sender.sent[-1 - len(effect_reports("static", "#aa0000", 40)):-1],
                             [(HID, r) for r in effect_reports("static", "#aa0000", 40)])  # then the LEDs
            sender.sent.clear()
            rig.service.set_hypershift_lights(False, "#aa0000")  # turned off: standard lights back
            self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("static", "#0000ff", 40)])
            sender.sent.clear()
            rig.service._engine.handle_key(K19, 0)
            self.assertEqual(sender.sent, [])
            await rig.service.stop()

        self.run_async(go())

    def test_invalid_stored_lighting_keeps_hypershift_lights(self):
        self.path.write_text(json.dumps({"version": SCHEMA_VERSION, "profiles": [], "lighting": {"effect": "bogus",
                             "hypershift": {"enabled": True, "color": "#12ab34"}}}))
        rig = Rig(self.path, send_feature=FakeSender())
        lighting = rig.service._config.lighting
        self.assertEqual((lighting.effect, lighting.hypershift, lighting.hypershift_color),
                         ("spectrum", True, "#12ab34"))

    def test_set_lighting_keeps_hypershift_lights(self):
        rig = Rig(self.path, send_feature=FakeSender())
        rig.service.set_hypershift_lights(True, "#12ab34")
        rig.service.set_lighting("static", "#0000ff", 20)
        self.assertEqual(rig.service.state()["lighting"]["hypershift"], {"enabled": True, "color": "#12ab34"})
        lighting = load_config(self.path).lighting
        self.assertEqual((lighting.hypershift, lighting.hypershift_color), (True, "#12ab34"))

    def test_set_hypershift_lights_validates(self):
        rig = Rig(self.path, send_feature=FakeSender())
        rig.service.set_hypershift_lights(True, "#12ab34")
        before = self.path.read_text()
        for args in (("yes", "#12ab34"), (True, "#ff60"), (1, "#12ab34"), (True, 5)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    rig.service.set_hypershift_lights(*args)
        self.assertEqual(self.path.read_text(), before)

    def test_lighting_off_sends_brightness_zero_and_keeps_brightness(self):
        async def go():
            sender = FakeSender()
            rig = await self.connected(sender)
            rig.service.set_lighting("static", "#ff0000", 40)
            sender.sent.clear()
            rig.service.set_lighting_enabled(False)
            self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("static", "#ff0000", 0)
                                           + [leds_report(NO_LEDS)]])
            self.assertEqual(rig.service.state()["lighting"],
                             {"effect": "static", "color": "#ff0000", "brightness": 40, "enabled": False, "hypershift": {"enabled": False, "color": "#ff6000"}})
            await rig.service.stop()

        self.run_async(go())
        lighting = load_config(self.path).lighting
        self.assertEqual((lighting.brightness, lighting.enabled), (40, False))

    def test_lighting_on_resends_stored(self):
        async def go():
            sender = FakeSender()
            rig = await self.connected(sender)
            rig.service.set_lighting("static", "#ff0000", 40)
            rig.service.set_lighting_enabled(False)
            sender.sent.clear()
            rig.service.set_lighting_enabled(True)
            self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("static", "#ff0000", 40)
                                           + [leds_report(NO_LEDS)]])
            self.assertIs(rig.service.state()["lighting"]["enabled"], True)
            await rig.service.stop()

        self.run_async(go())

    def test_set_lighting_while_off_stays_dark(self):
        async def go():
            sender = FakeSender()
            rig = await self.connected(sender)
            rig.service.set_lighting_enabled(False)
            sender.sent.clear()
            rig.service.set_lighting("wave", "#00ff00", 70)
            self.assertEqual(sender.sent, [(HID, r) for r in effect_reports("wave", "#00ff00", 0)
                                           + [leds_report(NO_LEDS)]])
            self.assertEqual(rig.service.state()["lighting"],
                             {"effect": "wave", "color": "#00ff00", "brightness": 70, "enabled": False,
                              "hypershift": {"enabled": False, "color": "#ff6000"}})
            await rig.service.stop()

        self.run_async(go())

    def test_lighting_off_survives_reconnect_resume_and_restart(self):
        async def go():
            sender = FakeSender()
            rig = Rig(self.path, send_feature=sender)
            rig.service.set_lighting_enabled(False)
            self.assertEqual(sender.sent, [])
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            expected = [(HID, r) for r in effect_reports("spectrum", "#00ff00", 0) + [leds_report(NO_LEDS)]]
            self.assertEqual(sender.sent, expected)
            rig.service._resume.check = lambda boottime, monotonic: True
            await until(lambda: len(sender.sent) >= 6)
            self.assertEqual(sender.sent[3:6], expected)
            await rig.service.stop()
            self.assertIs(Rig(self.path, send_feature=FakeSender()).service.state()["lighting"]["enabled"], False)

        self.run_async(go())

    def test_set_lighting_enabled_rejects_non_bool(self):
        sender = FakeSender()
        rig = Rig(self.path, send_feature=sender)
        rig.service.set_lighting("static", "#123456", 30)
        before = self.path.read_bytes()
        for value in ("yes", 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    rig.service.set_lighting_enabled(value)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(sender.sent, [])
        self.assertIs(rig.service.state()["lighting"]["enabled"], True)

    def test_stored_unknown_effect_falls_back_to_default(self):
        self.path.write_text(json.dumps({"version": 1, "active_profile": "default",
                                         "profiles": [{"id": "default", "name": "Default", "dpad_mode": "4way",
                                                       "bindings": {}}],
                                         "lighting": {"effect": "ripple", "color": "#ff0000", "brightness": 50}}))
        with self.assertLogs("tartarus", "WARNING"):
            rig = Rig(self.path, send_feature=FakeSender())
        self.assertEqual(rig.service.state()["lighting"]["effect"], "spectrum")

    def test_send_failure_is_logged_not_raised(self):
        async def go():
            for sender in (FakeSender(status=0x03), FakeSender(error=OSError(errno.EACCES, "denied"))):
                rig = Rig(self.path, send_feature=sender)
                await rig.service.start()
                with self.assertLogs("tartarus", "WARNING") as logs:
                    rig.nodes = TWO_NODES
                    await until(lambda: rig.service.state()["connected"])
                    rig.service.set_lighting("static", "#00ff00", 100)  # must not raise
                # Connect and set_lighting each warn once for lighting and once for the LEDs
                # (TWO_NODES has no depth node, so connect also warns that adjustable actuation is unavailable).
                self.assertEqual(len([line for line in logs.output if "adjustable actuation" not in line]), 4)
                await rig.service.stop()

        self.run_async(go())

    def test_no_hidraw_skips_lighting(self):
        async def go():
            sender = FakeSender()
            rig = Rig(self.path, send_feature=sender)
            await rig.service.start()
            with self.assertLogs("tartarus", "WARNING"):
                rig.nodes = TartarusNodes(event=TWO_NODES.event, hidraw=None)
                await until(lambda: rig.service.state()["connected"])
            self.assertEqual(sender.sent, [])
            await rig.service.stop()

        self.run_async(go())


class HidrawTest(unittest.TestCase):
    def test_send_feature_sets_then_gets(self):
        calls = []

        def fake_ioctl(fd, request, buf):
            calls.append((fd, request, bytes(buf)))
            if request == ioctl.HIDIOCGFEATURE(91):
                buf[1] = 0x02

        report = effect_reports("static", "#00ff00", 100)[0]
        with mock.patch.object(hidraw.os, "open", return_value=42) as fake_open, \
                mock.patch.object(hidraw.os, "close") as fake_close, \
                mock.patch.object(hidraw.fcntl, "ioctl", side_effect=fake_ioctl), \
                mock.patch.object(hidraw.time, "sleep"):
            status = hidraw.send_feature("/dev/hidraw8", report)
        self.assertEqual(status, 0x02)
        fake_open.assert_called_once_with("/dev/hidraw8", os.O_RDWR)
        fake_close.assert_called_once_with(42)
        self.assertEqual([c[1] for c in calls], [ioctl.HIDIOCSFEATURE(91), ioctl.HIDIOCGFEATURE(91)])
        self.assertEqual(calls[0][2], b"\x00" + report)
