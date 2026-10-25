import asyncio
import errno
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from tartarus.bindings import parse_binding_text
from tartarus.config import active_profile, load_config
from tartarus.devmap import ALL_CONTROLS
from tartarus.linux.discovery import TartarusNodes
from tartarus.linux.evdev import EV_KEY, EV_REL, EV_SYN, REL_WHEEL, REL_WHEEL_HI_RES
from tartarus.service import ResumeDetector, TartarusService

ROOT = Path(__file__).resolve().parent.parent
KEY_1, KEY_ESC = 2, 1


class FakeEmitter:
    def __init__(self):
        self.out = []
        self.closed = False

    def key(self, code, down):
        self.out.append(("key", code, down))

    def wheel(self, delta):
        self.out.append(("wheel", delta))

    def sync(self):
        pass

    def steam_action(self, action):
        self.out.append(("steam", action))

    def close(self):
        self.closed = True


class FakeDevice:
    """An event node backed by a pipe, so loop.add_reader works on it."""

    def __init__(self, path, grab_error=None):
        self.path = path
        self.name = "Razer Razer Tartarus Pro"
        self._r, self._w = os.pipe()
        self.fd = self._r
        self.grab_error = grab_error
        self.grabbed = False
        self.closed = False
        self.queue = []
        self.gone = False

    def push(self, *events):
        self.queue.extend(events)
        os.write(self._w, b"x")

    def unplug(self):
        self.gone = True
        os.write(self._w, b"x")

    def grab(self):
        if self.grab_error is not None:
            raise OSError(self.grab_error, os.strerror(self.grab_error))
        self.grabbed = True

    def ungrab(self):
        self.grabbed = False

    def read_events(self):
        os.read(self._r, 64)
        if self.gone:
            raise OSError(errno.ENODEV, "No such device")
        events, self.queue = self.queue, []
        return events

    def close(self):
        if not self.closed:
            os.close(self._r)
            os.close(self._w)
            self.closed = True


class Rig:
    """A service wired to fakes: nodes come and go by setting rig.nodes."""

    def __init__(self, settings_path, grab_error=None, emitter_error=None, **service_kwargs):
        self.nodes = None
        self.devices = []
        self.events = []
        self.emitter = FakeEmitter()
        self.grab_error = grab_error

        async def emit(event, *args):
            self.events.append((event,) + args)

        def open_device(path):
            dev = FakeDevice(path, self.grab_error)
            self.devices.append(dev)
            return dev

        def make_emitter(on_steam):
            if emitter_error is not None:
                raise emitter_error
            return self.emitter

        service_kwargs.setdefault("send_feature", lambda path, report: 0x02)  # never touch real hidraw
        self.service = TartarusService(settings_path, emit, find=lambda: self.nodes,
                                       open_device=open_device, make_emitter=make_emitter,
                                       **service_kwargs)
        self.service.POLL_INTERVAL = 0.01
        self.service.RESUME_INTERVAL = 0.01


async def until(predicate, timeout=1.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not predicate():
        if loop.time() > end:
            raise AssertionError("condition not reached")
        await asyncio.sleep(0.005)


TWO_NODES = TartarusNodes(event=["/dev/input/event11", "/dev/input/event14"], hidraw="/dev/hidraw8")


class ResumeDetectorTest(unittest.TestCase):
    def test_resume_detector(self):
        d = ResumeDetector()
        self.assertFalse(d.check(100.0, 50.0))
        self.assertFalse(d.check(101.0, 51.0))
        self.assertTrue(d.check(105.0, 52.0))
        self.assertFalse(d.check(106.0, 53.0))


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"

    def tearDown(self):
        self._tmp.cleanup()

    def run_async(self, coro):
        return asyncio.run(asyncio.wait_for(coro, 5))

    def test_state_shape(self):
        rig = Rig(self.path)
        state = rig.service.state()
        self.assertEqual(set(state), {"connected", "dpad_mode", "steam_mode", "bindings", "lighting", "effects"})
        self.assertFalse(state["connected"])
        self.assertEqual(state["dpad_mode"], "4way")
        self.assertEqual(state["steam_mode"], "api")
        self.assertEqual(list(state["bindings"]), list(ALL_CONTROLS))
        self.assertEqual(state["bindings"]["k01"], {"binding": {"type": "key", "keys": ["1"]}, "label": "1"})

    def test_set_binding_persists(self):
        rig = Rig(self.path)
        rig.service.set_binding("k01", parse_binding_text("Esc"))
        self.assertEqual(active_profile(load_config(self.path)).bindings["k01"], parse_binding_text("Esc"))
        self.assertEqual(rig.service.state()["bindings"]["k01"]["label"], "Esc")

    def test_set_dpad_mode_persists(self):
        rig = Rig(self.path)
        rig.service.set_dpad_mode("8way")
        self.assertEqual(active_profile(load_config(self.path)).dpad_mode, "8way")

    def test_unknown_control_or_mode_rejected(self):
        rig = Rig(self.path)
        with self.assertRaises(ValueError):
            rig.service.set_binding("thumb", parse_binding_text("Esc"))
        with self.assertRaises(ValueError):
            rig.service.set_dpad_mode("2way")
        self.assertFalse(self.path.exists())

    def test_connect_remaps_and_unplug_repolls(self):
        async def go():
            rig = Rig(self.path)
            rig.service.set_binding("k01", parse_binding_text("Esc"))
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            self.assertTrue(all(d.grabbed for d in rig.devices))
            self.assertIn(("state_changed", rig.service.state()), rig.events)

            kbd, mouse = rig.devices
            kbd.push((EV_KEY, KEY_1, 1), (EV_SYN, 0, 0))
            mouse.push((EV_REL, REL_WHEEL, -1), (EV_REL, REL_WHEEL_HI_RES, -120))
            await until(lambda: len(rig.emitter.out) >= 2)
            self.assertEqual(rig.emitter.out, [("key", KEY_ESC, True), ("wheel", -1)])

            # Unplug while k01 is held: Esc is released, the nodes closed, polling resumes.
            rig.nodes = None
            kbd.unplug()
            await until(lambda: not rig.service.state()["connected"])
            self.assertEqual(rig.emitter.out[-1], ("key", KEY_ESC, False))
            self.assertTrue(all(d.closed for d in rig.devices))

            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            self.assertEqual(len(rig.devices), 4)
            await rig.service.stop()
            self.assertTrue(all(d.closed for d in rig.devices))
            self.assertTrue(rig.emitter.closed)

        self.run_async(go())

    def test_connect_waits_for_all_nodes(self):
        # On a replug the kernel creates the event nodes one by one; a scan can see only some.
        async def go():
            rig = Rig(self.path)
            scans = []
            find = rig.service._find
            rig.service._find = lambda: scans.append(1) or find()
            await rig.service.start()
            rig.nodes = TartarusNodes(event=["/dev/input/event11"], hidraw=None)
            await until(lambda: len(scans) >= 1)
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            self.assertEqual([d.path for d in rig.devices if not d.closed], TWO_NODES.event)
            await rig.service.stop()

        self.run_async(go())

    def test_grab_ebusy_retries(self):
        async def go():
            rig = Rig(self.path, grab_error=errno.EBUSY)
            await rig.service.start()
            rig.nodes = TWO_NODES
            with self.assertLogs("tartarus", "WARNING"):
                await until(lambda: len(rig.devices) >= 4)  # two attempts
            self.assertFalse(rig.service.state()["connected"])
            self.assertTrue(all(d.closed for d in rig.devices[:2]))

            rig.grab_error = None  # the other holder went away
            await until(lambda: rig.service.state()["connected"])
            await rig.service.stop()

        self.run_async(go())

    def test_resume_reconnects(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            rig.service._resume.check = lambda boottime, monotonic: True
            await until(lambda: len(rig.devices) >= 4)
            await until(lambda: rig.service.state()["connected"])
            self.assertTrue(all(d.closed for d in rig.devices[:2]))
            await rig.service.stop()

        self.run_async(go())

    def test_unload_after_failed_start(self):
        async def go():
            rig = Rig(self.path, emitter_error=OSError(errno.ENOENT, "no /dev/uinput"))
            with self.assertRaises(OSError):
                await rig.service.start()
            await rig.service.stop()  # must not raise
            await rig.service.stop()

        self.run_async(go())

    def test_stop_without_start(self):
        rig = Rig(self.path)
        self.run_async(rig.service.stop())


def load_main(fake_decky):
    sys.modules["decky"] = fake_decky
    try:
        spec = importlib.util.spec_from_file_location("tartarus_main", ROOT / "main.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        del sys.modules["decky"]


class PluginTest(unittest.TestCase):
    def test_plugin_unload_after_partial_main(self):
        import logging
        decky = types.SimpleNamespace(logger=logging.getLogger("tartarus.test"),
                                      DECKY_PLUGIN_SETTINGS_DIR="/nonexistent")
        plugin = load_main(decky).Plugin()
        asyncio.run(plugin._unload())  # _main never ran: no service attribute

    def test_plugin_set_binding_text(self):
        import logging
        with tempfile.TemporaryDirectory() as tmp:
            async def emit(*args):
                pass

            decky = types.SimpleNamespace(logger=logging.getLogger("tartarus.test"),
                                          DECKY_PLUGIN_SETTINGS_DIR=tmp, emit=emit)
            main = load_main(decky)
            plugin = main.Plugin()
            plugin.service = main.TartarusService(Path(tmp) / "settings.json", emit)

            async def go():
                ok = await plugin.set_binding_text("k01", "Esc")
                self.assertEqual((ok["ok"], ok["error"]), (True, None))
                self.assertEqual(ok["state"]["bindings"]["k01"]["label"], "Esc")
                bad = await plugin.set_binding_text("k01", "NoSuchKey")
                self.assertFalse(bad["ok"])
                self.assertTrue(bad["error"])
                self.assertFalse((await plugin.set_binding_text("thumb", "Esc"))["ok"])
                state = await plugin.set_dpad_mode("8way")
                self.assertEqual(state["dpad_mode"], "8way")
                state = await plugin.set_binding("k02", {"type": "key", "keys": ["B"]})
                self.assertEqual(state["bindings"]["k02"]["label"], "B")

            asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
