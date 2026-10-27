import asyncio
import errno
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tartarus.config import NO_LEDS, load_config
from tartarus.lighting import EFFECTS, effect_reports, leds_report
from tartarus.linux import hidraw, ioctl
from tartarus.linux.discovery import TartarusNodes

from tests.test_service import TWO_NODES, Rig, until


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
        self.assertEqual(state["lighting"], {"effect": "spectrum", "color": "#00ff00", "brightness": 100})
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
        self.assertEqual(rig.service.state()["lighting"], {"effect": "static", "color": "#123456", "brightness": 30})

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
                # (TWO_NODES has no depth node, so connect also warns that analog keys are unavailable).
                self.assertEqual(len([line for line in logs.output if "analog keys" not in line]), 4)
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
