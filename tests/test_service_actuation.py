import asyncio
import errno
import json
import os
import tempfile
import unittest
from pathlib import Path

from tartarus.bindings import parse_binding_text
from tartarus.config import NO_LEDS, default_config, save_config
from tartarus.devmode import DRIVER_MODE, NORMAL_MODE, set_mode_report
from tartarus.lighting import effect_reports, leds_report
from tartarus.linux.discovery import TartarusNodes
from tartarus.linux.evdev import EV_KEY

from tests.test_service import KEY_1, KEY_ESC, Rig, until
from tests.test_service_lighting import FakeSender

KEY_LEFTALT = 56  # the top button's factory code
KEY_F13 = 183
DRIVER = set_mode_report(DRIVER_MODE)
NORMAL = set_mode_report(NORMAL_MODE)
NODES = TartarusNodes(event=["/dev/input/event11", "/dev/input/event14"], hidraw="/dev/hidraw8",
                      depth="/dev/hidraw7")


def depth_report(**keys):
    data = bytearray(24)
    data[0] = 0x06
    for control, depth in keys.items():
        data[int(control[1:])] = depth
    return bytes(data)


class FakeHidraw:
    """Interface 1's hidraw node, backed by a pipe so loop.add_reader works on it."""

    def __init__(self, path):
        self.path = path
        self._r, self._w = os.pipe()
        self.fd = self._r
        self.queue = []
        self.gone = False
        self.closed = False

    def push(self, report):
        self.queue.append(report)
        os.write(self._w, b"x")

    def unplug(self):
        self.gone = True
        os.write(self._w, b"x")

    def read_report(self):
        if self.gone:
            raise OSError(errno.ENODEV, "No such device")
        if not self.queue:
            return None
        os.read(self._r, 1)
        return self.queue.pop(0)

    def close(self):
        if not self.closed:
            os.close(self._r)
            os.close(self._w)
            self.closed = True


class ActuationServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"
        c = default_config()
        c.profiles[0].bindings["k01"] = parse_binding_text("Esc")
        c.profiles[0].bindings["top_button"] = parse_binding_text("F13")
        save_config(self.path, c)
        self.readers = []
        self.open_error = None

    def tearDown(self):
        self._tmp.cleanup()

    def run_async(self, coro):
        return asyncio.run(asyncio.wait_for(coro, 5))

    def open_hidraw(self, path):
        if self.open_error is not None:
            raise self.open_error
        reader = FakeHidraw(path)
        self.readers.append(reader)
        return reader

    async def connected(self, sender=None, nodes=NODES):
        self.sender = sender or FakeSender()
        rig = Rig(self.path, send_feature=self.sender, open_hidraw=self.open_hidraw)
        await rig.service.start()
        rig.nodes = nodes
        await until(lambda: rig.service.state()["connected"])
        return rig

    def reports(self):
        return [report for _, report in self.sender.sent]

    def test_connect_enters_driver_mode(self):
        async def go():
            rig = await self.connected()
            self.assertEqual(self.sender.sent[0], ("/dev/hidraw8", DRIVER))
            self.assertEqual(self.reports(), [DRIVER] + effect_reports("spectrum", "#00ff00", 100)
                             + [leds_report(NO_LEDS)])
            self.assertEqual(rig.service.state()["actuation"],
                             {"enabled": True, "status": "on", "default_mm": 1.5, "min_mm": 1.5, "max_mm": 3.6,
                              "min_gap_mm": 0.5})
            self.assertEqual(self.readers[0].path, "/dev/hidraw7")
            self.readers[0].push(depth_report(k01=20))
            await until(lambda: rig.emitter.out)
            self.assertEqual(rig.emitter.out, [("key", KEY_ESC, True)])
            await rig.service.stop()

        self.run_async(go())

    def test_driver_mode_status_failure_falls_back(self):
        async def go():
            with self.assertLogs("tartarus", "WARNING") as logs:
                rig = await self.connected(FakeSender(status=0x05))
            self.assertTrue(any("driver mode" in line for line in logs.output))
            self.assertEqual(rig.service.state()["actuation"]["status"], "unavailable")
            self.assertEqual(self.readers, [])
            rig.devices[0].push((EV_KEY, KEY_1, 1))
            await until(lambda: rig.emitter.out)
            self.assertEqual(rig.emitter.out, [("key", KEY_ESC, True)])
            await rig.service.stop()

        self.run_async(go())

    def test_no_depth_node_falls_back(self):
        async def go():
            rig = await self.connected(nodes=TartarusNodes(event=NODES.event, hidraw=NODES.hidraw, depth=None))
            self.assertNotIn(DRIVER, self.reports())
            self.assertEqual(rig.service.state()["actuation"]["status"], "unavailable")
            await rig.service.stop()

        self.run_async(go())

    def test_depth_open_failure_restores_normal_mode(self):
        async def go():
            self.open_error = OSError(errno.EACCES, "denied")
            rig = await self.connected()
            self.assertEqual(self.reports()[:2], [DRIVER, NORMAL])
            self.assertEqual(rig.service.state()["actuation"]["status"], "unavailable")
            await rig.service.stop()
            self.assertEqual(self.reports().count(NORMAL), 1)

        self.run_async(go())

    def test_stop_sends_normal_mode_after_release(self):
        async def go():
            rig = await self.connected()
            log = []
            key = rig.emitter.key
            rig.emitter.key = lambda code, down: (log.append(("key", code, down)), key(code, down))
            sender = self.sender
            rig.service._send_feature = lambda path, report: (log.append(("send", report)), sender(path, report))[1]
            for dev in rig.devices:
                dev.ungrab = lambda: log.append(("ungrab",))
            self.readers[0].push(depth_report(k01=200))
            await until(lambda: log)
            await rig.service.stop()
            self.assertEqual(log, [("key", KEY_ESC, True), ("key", KEY_ESC, False), ("send", NORMAL),
                                   ("ungrab",), ("ungrab",)])
            self.assertTrue(self.readers[0].closed)

        self.run_async(go())

    def test_depth_read_error_disconnects_and_reconnects_in_driver_mode(self):
        async def go():
            rig = await self.connected()
            self.readers[0].push(depth_report(k01=200))
            await until(lambda: rig.emitter.out)
            self.readers[0].unplug()
            await until(lambda: len(self.readers) == 2)
            await until(lambda: rig.service.state()["connected"])
            self.assertEqual(rig.emitter.out, [("key", KEY_ESC, True), ("key", KEY_ESC, False)])
            self.assertTrue(self.readers[0].closed)
            self.assertEqual(self.reports().count(DRIVER), 2)
            await rig.service.stop()

        self.run_async(go())

    def test_resume_reenters_driver_mode(self):
        async def go():
            rig = await self.connected()
            rig.service._resume.check = lambda boottime, monotonic: True
            await until(lambda: len(rig.devices) >= 4)
            await until(lambda: rig.service.state()["connected"])
            rig.service._resume.check = lambda boottime, monotonic: False
            reports = self.reports()
            first_normal = reports.index(NORMAL)
            self.assertIn(DRIVER, reports[first_normal:])
            await rig.service.stop()

        self.run_async(go())

    def test_actuation_keys_evdev_dropped_in_driver_mode(self):
        async def go():
            rig = await self.connected()
            with self.assertLogs("tartarus", "INFO") as logs:
                rig.devices[0].push((EV_KEY, KEY_1, 1), (EV_KEY, KEY_1, 0), (EV_KEY, KEY_1, 1))
                rig.devices[0].push((EV_KEY, KEY_LEFTALT, 1))
                await until(lambda: rig.emitter.out)
            self.assertEqual(rig.emitter.out, [("key", KEY_F13, True)])
            self.assertEqual(sum("factory key" in line for line in logs.output), 1)
            await rig.service.stop()

        self.run_async(go())

    def test_set_adjustable_actuation_toggles_at_runtime(self):
        async def go():
            rig = await self.connected()
            self.readers[0].push(depth_report(k01=200))
            await until(lambda: rig.emitter.out)
            self.sender.sent.clear()
            rig.service.set_adjustable_actuation(False)
            self.assertEqual(rig.emitter.out, [("key", KEY_ESC, True), ("key", KEY_ESC, False)])
            self.assertEqual(self.reports(), [NORMAL])
            self.assertTrue(self.readers[0].closed)
            self.assertEqual(rig.service.state()["actuation"]["status"], "off")
            self.assertEqual(rig.service.state()["actuation"]["enabled"], False)
            self.assertIs(json.loads(self.path.read_text())["adjustable_actuation"], False)
            rig.service.set_adjustable_actuation(True)
            self.assertEqual(self.reports(), [NORMAL, DRIVER])
            self.assertEqual(rig.service.state()["actuation"]["status"], "on")
            with self.assertRaises(ValueError):
                rig.service.set_adjustable_actuation("yes")
            await rig.service.stop()

        self.run_async(go())

    def test_set_actuation(self):
        async def go():
            rig = await self.connected()
            svc = rig.service
            svc.set_actuation("default", "k01", 2.5)
            self.assertEqual(json.loads(self.path.read_text())["profiles"][0]["actuation"], {"k01": 2.5})
            self.assertEqual(svc.state()["profiles"][0]["actuation"], {"k01": 2.5})
            self.readers[0].push(depth_report(k01=119))
            self.readers[0].push(depth_report(k01=120))
            await until(lambda: rig.emitter.out)
            self.assertEqual(rig.emitter.out, [("key", KEY_ESC, True)])
            svc.set_actuation("default", "k02", 2.6000000000000005)
            self.assertEqual(svc.state()["profiles"][0]["actuation"], {"k01": 2.5, "k02": 2.6})
            svc.set_actuation("default", "k01", 1.5)
            self.assertEqual(json.loads(self.path.read_text())["profiles"][0]["actuation"], {"k02": 2.6})
            before = self.path.read_bytes()
            for args in (("default", "k01", 3.7), ("default", "k21", 2.0), ("default", "top_button", 2.0),
                         ("default", "k01", 2.55), ("default", "k01", True), ("nope", "k01", 2.0)):
                with self.assertRaises(ValueError, msg=args):
                    svc.set_actuation(*args)
            self.assertEqual(self.path.read_bytes(), before)
            await svc.stop()

        self.run_async(go())

    def test_set_all_actuation(self):
        async def go():
            rig = await self.connected()
            svc = rig.service
            svc.set_all_actuation("default", 2.0)
            self.assertEqual(json.loads(self.path.read_text())["profiles"][0]["actuation"],
                             {f"k{i:02d}": 2.0 for i in range(1, 21)})
            with self.assertRaises(ValueError):
                svc.set_all_actuation("default", 1.4)
            svc.set_all_actuation("default", 1.5)
            self.assertEqual(json.loads(self.path.read_text())["profiles"][0]["actuation"], {})
            await svc.stop()

        self.run_async(go())

    def test_actuation_off_at_connect(self):
        async def go():
            data = json.loads(self.path.read_text())
            data["adjustable_actuation"] = False
            self.path.write_text(json.dumps(data))
            rig = await self.connected()
            self.assertNotIn(DRIVER, self.reports())
            self.assertEqual(rig.service.state()["actuation"]["status"], "off")
            await rig.service.stop()
            self.assertNotIn(NORMAL, self.reports())

        self.run_async(go())

    def test_status_none_when_disconnected(self):
        async def go():
            rig = Rig(self.path, open_hidraw=self.open_hidraw)
            await rig.service.start()
            self.assertIsNone(rig.service.state()["actuation"]["status"])
            await rig.service.stop()

        self.run_async(go())


if __name__ == "__main__":
    unittest.main()
