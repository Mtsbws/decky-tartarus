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
from tartarus.config import default_config, default_profile, load_config, save_config
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
        self.assertEqual(set(state), {"connected", "device", "device_id", "steam_mode", "lighting", "actuation", "effects",
                                 "active_profile", "running_app", "max_profiles", "profiles", "led_patterns"})
        self.assertFalse(state["connected"])
        self.assertIsNone(state["device"])
        self.assertIsNone(state["device_id"])
        self.assertEqual(state["steam_mode"], "api")
        self.assertEqual(state["active_profile"], "default")
        self.assertIsNone(state["running_app"])
        self.assertEqual(state["max_profiles"], 8)
        self.assertEqual(state["led_patterns"][0], [True, False, False])
        self.assertEqual(len(state["profiles"]), 4)  # a fresh install: Default and the three starters
        first = state["profiles"][0]
        self.assertEqual((first["id"], first["name"], first["is_default"], first["games"], first["dpad_mode"],
                          first["leds"]),
                         ("default", "Default", True, [], "4way", [False, False, False]))
        self.assertEqual(list(first["bindings"]), list(ALL_CONTROLS))
        self.assertEqual(first["bindings"]["k01"],
                         {"binding": {"type": "key", "keys": ["Esc"]}, "label": "Esc", "factory": "1"})
        self.assertEqual(first["bindings"]["dpad_up_right"]["factory"], "hold:Up+Right")
        for control in ALL_CONTROLS:
            self.assertTrue(first["bindings"][control]["factory"])

    def test_set_binding_persists(self):
        rig = Rig(self.path)
        rig.service.set_binding("default", "k01", parse_binding_text("Esc"))
        self.assertEqual(default_profile(load_config(self.path)).bindings["k01"], parse_binding_text("Esc"))
        self.assertEqual(rig.service.state()["profiles"][0]["bindings"]["k01"]["label"], "Esc")

    def test_set_dpad_mode_persists(self):
        rig = Rig(self.path)
        rig.service.set_dpad_mode("default", "8way")
        self.assertEqual(default_profile(load_config(self.path)).dpad_mode, "8way")

    def test_unknown_control_or_mode_rejected(self):
        rig = Rig(self.path)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            rig.service.set_binding("default", "thumb", parse_binding_text("Esc"))
        with self.assertRaises(ValueError):
            rig.service.set_dpad_mode("default", "2way")
        self.assertEqual(self.path.read_bytes(), before)

    def test_connect_remaps_and_unplug_repolls(self):
        async def go():
            rig = Rig(self.path)
            rig.service.set_binding("default", "k01", parse_binding_text("Esc"))
            rig.service.set_binding("default", "wheel_down", parse_binding_text("WheelDown"))
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            self.assertTrue(all(d.grabbed for d in rig.devices))
            self.assertEqual(rig.service.state()["device"], "Razer Tartarus Pro")
            self.assertEqual(rig.service.state()["device_id"], "1532:0244")
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

    def test_system_keys_dropped(self):
        async def go():
            rig = Rig(self.path)
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            kbd = rig.devices[0]
            kbd.push((EV_KEY, 142, 1), (EV_KEY, 142, 0), (EV_KEY, 116, 1), (EV_KEY, 143, 1),
                     (EV_KEY, 183, 1), (EV_SYN, 0, 0))
            await until(lambda: rig.emitter.out)
            await asyncio.sleep(0.02)
            self.assertEqual(rig.emitter.out, [("key", 183, True)])

            # During Record the engine passes keys through; system keys still go nowhere.
            rig.service.record_start()
            kbd.push((EV_KEY, 142, 1), (EV_KEY, 142, 0), (EV_KEY, KEY_1, 1), (EV_KEY, KEY_1, 0))
            await until(lambda: any(e[0] == "record_result" for e in rig.events))
            results = [e for e in rig.events if e[0] == "record_result"]
            self.assertEqual(results, [("record_result", {"type": "key", "keys": ["1"]})])
            self.assertFalse(any(o[0] == "key" and o[1] in (116, 142, 143) for o in rig.emitter.out))
            await rig.service.stop()

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

    def test_stop_finishes_without_yielding(self):
        # Decky closes the plugin's socket during _unload, and its listener then spins on EOF without
        # ever yielding: a stop() suspended at an await never resumes, and Decky SIGKILLs us 5 s later.
        async def go():
            rig = Rig(self.path)
            rig.service.set_binding("default", "k01", parse_binding_text("Esc"))
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            order = []
            key = rig.emitter.key
            rig.emitter.key = lambda code, down: (order.append(("key", code, down)), key(code, down))
            for dev in rig.devices:
                dev.ungrab = lambda: order.append("ungrab")
            rig.devices[0].push((EV_KEY, KEY_1, 1))
            await until(lambda: ("key", KEY_ESC, True) in order)
            supervisor = rig.service._supervisor

            with self.assertRaises(StopIteration):
                rig.service.stop().send(None)  # runs to the end in one step
            self.assertEqual(order[1:], [("key", KEY_ESC, False), "ungrab", "ungrab"])
            self.assertTrue(all(d.closed for d in rig.devices))
            self.assertTrue(rig.emitter.closed)
            await asyncio.sleep(0)
            self.assertTrue(supervisor.cancelled())

        self.run_async(go())

    def test_stop_cancels_pending_emits(self):
        async def go():
            rig = Rig(self.path)
            started = []

            async def slow_emit(event, *args):
                started.append(event)
                await asyncio.sleep(10)

            rig.service._emit = slow_emit
            await rig.service.start()
            rig.service.set_running_app(5, "X")  # notifies the frontend
            await until(lambda: started)
            pending = set(rig.service._pending)
            self.assertTrue(pending)
            with self.assertRaises(StopIteration):
                rig.service.stop().send(None)
            await asyncio.sleep(0)
            self.assertTrue(all(t.cancelled() for t in pending))
            self.assertEqual(rig.service._pending, set())

        self.run_async(go())


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
        asyncio.run(plugin._uninstall())

    def test_plugin_uninstall_stops_service(self):
        import logging
        decky = types.SimpleNamespace(logger=logging.getLogger("tartarus.test"),
                                      DECKY_PLUGIN_SETTINGS_DIR="/nonexistent")
        plugin = load_main(decky).Plugin()
        stopped = []

        async def stop():
            stopped.append(True)

        plugin.service = types.SimpleNamespace(stop=stop)
        asyncio.run(plugin._uninstall())
        self.assertEqual(stopped, [True])

    def test_plugin_profile_callables(self):
        import logging
        with tempfile.TemporaryDirectory() as tmp:
            async def emit(*args):
                pass

            decky = types.SimpleNamespace(logger=logging.getLogger("tartarus.test"),
                                          DECKY_PLUGIN_SETTINGS_DIR=tmp, emit=emit)
            main = load_main(decky)
            plugin = main.Plugin()
            save_config(Path(tmp) / "settings.json", default_config())  # no starters: the test makes its own "MMO"
            plugin.service = main.TartarusService(Path(tmp) / "settings.json", emit)

            async def go():
                state = await plugin.create_profile("MMO", "default")
                self.assertEqual(state["profiles"][1]["name"], "MMO")
                p2 = state["profiles"][1]["id"]
                ok = await plugin.set_binding_text(p2, "k01", "Esc")
                self.assertTrue(ok["ok"])
                profiles = ok["state"]["profiles"]
                self.assertEqual(profiles[1]["bindings"]["k01"]["label"], "Esc")
                self.assertEqual(profiles[0]["bindings"]["k01"]["label"], "Esc")
                await plugin.set_running_app(1343400, "RuneScape")
                state = await plugin.assign_running_game(p2)
                self.assertEqual(state["active_profile"], p2)
                self.assertEqual(state["running_app"], {"app_id": 1343400, "name": "RuneScape"})
                state = await plugin.set_leds(p2, [False, True, True])
                self.assertEqual(state["profiles"][1]["leds"], [False, True, True])
                state = await plugin.set_adjustable_actuation(False)
                self.assertIs(state["actuation"]["enabled"], False)
                state = await plugin.rename_profile(p2, "Runescape")
                self.assertEqual(state["profiles"][1]["name"], "Runescape")
                state = await plugin.delete_profile(p2)
                self.assertEqual(len(state["profiles"]), 1)
                self.assertEqual(state["active_profile"], "default")

            asyncio.run(go())

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
                ok = await plugin.set_binding_text("default", "k01", "Esc")
                self.assertEqual((ok["ok"], ok["error"]), (True, None))
                self.assertEqual(ok["state"]["profiles"][0]["bindings"]["k01"]["label"], "Esc")
                bad = await plugin.set_binding_text("default", "k01", "NoSuchKey")
                self.assertFalse(bad["ok"])
                self.assertTrue(bad["error"])
                self.assertFalse((await plugin.set_binding_text("default", "thumb", "Esc"))["ok"])
                state = await plugin.set_dpad_mode("default", "8way")
                self.assertEqual(state["profiles"][0]["dpad_mode"], "8way")
                state = await plugin.set_binding("default", "k02", {"type": "key", "keys": ["B"]})
                self.assertEqual(state["profiles"][0]["bindings"]["k02"]["label"], "B")

            asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
