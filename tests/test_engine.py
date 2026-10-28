import asyncio
import dataclasses
import unittest

from tartarus.bindings import parse_binding_text
from tartarus.codes import code_for
from tartarus.config import Secondary, default_profile, default_config, factory_bindings
from tartarus.engine import RemapEngine

KEY_1 = 2  # factory code of k01
KEY_2 = 3  # factory code of k02
KEY_SPACE = 57  # k20
KEY_UP, KEY_RIGHT = 103, 106
KEY_B = 48  # not sent by the keypad's factory map

ESC, CTRL, SHIFT = code_for("Esc"), code_for("Ctrl"), code_for("Shift")
C, V, W, A, B, E, F5, Z = (code_for(n) for n in ("C", "V", "W", "A", "B", "E", "F5", "Z"))
RMB = code_for("RMB")
RIGHT = code_for("Right")


class FakeEmitter:
    def __init__(self):
        self.events = []

    def key(self, code, down):
        self.events.append(("key", code, down))

    def wheel(self, delta):
        self.events.append(("wheel", delta))

    def sync(self):
        pass

    def steam_action(self, action):
        self.events.append(("steam", action))


def profile(dpad_mode="4way", **texts):
    base = default_profile(default_config())
    bindings = factory_bindings()  # the tests press factory keys
    bindings.update({control: parse_binding_text(text) for control, text in texts.items()})
    return dataclasses.replace(base, dpad_mode=dpad_mode, bindings=bindings)


def down(code):
    return ("key", code, True)


def up(code):
    return ("key", code, False)


class EngineTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.out = FakeEmitter()
        self.sleeps = []

    async def fake_sleep(self, seconds):
        self.sleeps.append(seconds)
        await asyncio.sleep(0)

    def engine(self, prof, **kw):
        return RemapEngine(self.out, prof, sleep=self.fake_sleep, **kw)

    async def settle(self):
        for _ in range(50):
            await asyncio.sleep(0)

    async def test_key_binding_holds(self):
        e = self.engine(profile(k01="Esc"))
        e.handle_key(KEY_1, 1)
        self.assertEqual(self.out.events, [down(ESC)])
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [down(ESC), up(ESC)])

    async def test_shortcut_taps_once(self):
        e = self.engine(profile(k01="Ctrl+C"))
        e.handle_key(KEY_1, 1)
        self.assertEqual(self.out.events, [down(CTRL), down(C), up(C), up(CTRL)])
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [down(CTRL), down(C), up(C), up(CTRL)])

    async def test_repeat_events_ignored(self):
        e = self.engine(profile(k01="Ctrl+C"))
        e.handle_key(KEY_1, 1)
        for _ in range(3):
            e.handle_key(KEY_1, 2)
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [down(CTRL), down(C), up(C), up(CTRL)])

    async def test_combo_holds_all(self):
        e = self.engine(profile(k01="hold:W+A"))
        e.handle_key(KEY_1, 1)
        self.assertEqual(self.out.events, [down(W), down(A)])
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [down(W), down(A), up(A), up(W)])

    async def test_shared_output_refcounted(self):
        e = self.engine(profile(k01="Shift", k02="Shift"))
        e.handle_key(KEY_1, 1)
        e.handle_key(KEY_2, 1)
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [down(SHIFT)])
        e.handle_key(KEY_2, 0)
        self.assertEqual(self.out.events, [down(SHIFT), up(SHIFT)])

    async def test_tap_does_not_release_held_code(self):
        e = self.engine(profile(k01="Ctrl", k02="Ctrl+C"))
        e.handle_key(KEY_1, 1)
        e.handle_key(KEY_2, 1)
        self.assertEqual(self.out.events, [down(CTRL), down(C), up(C)])

    async def test_set_profile_releases_held(self):
        e = self.engine(profile(k01="Esc"))
        e.handle_key(KEY_1, 1)
        e.set_profile(profile(k01="F5"))
        self.assertEqual(self.out.events, [down(ESC), up(ESC)])
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [down(ESC), up(ESC)])

    async def test_release_all(self):
        e = self.engine(profile(k01="hold:W+A", k02="RMB"))
        e.handle_key(KEY_1, 1)
        e.handle_key(KEY_2, 1)
        self.out.events.clear()
        e.release_all()
        self.assertEqual(sorted(self.out.events), sorted([up(W), up(A), up(RMB)]))
        e.handle_key(KEY_1, 0)
        e.handle_key(KEY_2, 0)
        self.assertEqual(len(self.out.events), 3)

    async def test_macro_runs_steps_and_ignores_retrigger(self):
        e = self.engine(profile(k01="A, B"))
        e.handle_key(KEY_1, 1)
        e.handle_key(KEY_1, 0)
        e.handle_key(KEY_1, 1)
        await self.settle()
        self.assertEqual(self.out.events, [down(A), up(A), down(B), up(B)])
        self.assertEqual(self.sleeps, [0.015, 0.015, 0.015])

    async def test_macro_cancelled_by_release_all(self):
        e = self.engine(profile(k01="Ctrl+C, Ctrl+V"))
        e.handle_key(KEY_1, 1)
        await asyncio.sleep(0)
        e.release_all()
        await self.settle()
        self.assertEqual(self.out.events[:2], [down(CTRL), down(C)])
        held = {}
        for _, code, is_down in self.out.events:
            held[code] = is_down
        self.assertFalse(any(held.values()))
        self.assertNotIn(down(V), self.out.events)

    async def test_unknown_code_passthrough(self):
        e = self.engine(profile())
        e.handle_key(KEY_B, 1)
        e.handle_key(KEY_B, 0)
        self.assertEqual(self.out.events, [down(KEY_B), up(KEY_B)])

    async def test_disable(self):
        e = self.engine(profile(k01="disable"))
        e.handle_key(KEY_1, 1)
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [])

    async def test_steam_api_and_keys_modes(self):
        e = self.engine(profile(k01="steam:menu"))
        e.handle_key(KEY_1, 1)
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [("steam", "menu")])
        self.out.events.clear()
        e = self.engine(profile(k01="steam:menu"), steam_mode="keys")
        e.handle_key(KEY_1, 1)
        one = code_for("1")
        self.assertEqual(self.out.events, [down(CTRL), down(one), up(one), up(CTRL)])
        self.out.events.clear()
        e = self.engine(profile(k01="steam:qam"), steam_mode="disabled")
        e.handle_key(KEY_1, 1)
        self.assertEqual(self.out.events, [])

    async def test_steam_keyboard(self):
        e = self.engine(profile(k01="steam:keyboard"))
        e.handle_key(KEY_1, 1)
        self.assertEqual(self.out.events, [("steam", "keyboard")])
        self.out.events.clear()
        # No key opens Steam's on-screen keyboard, so "keys" mode sends nothing.
        e = self.engine(profile(k01="steam:keyboard"), steam_mode="keys")
        e.handle_key(KEY_1, 1)
        self.assertEqual(self.out.events, [])

    async def test_wheel_input_and_output(self):
        e = self.engine(profile(wheel_up="F5", k01="WheelDown"))
        e.handle_wheel(1)
        await self.settle()
        self.assertEqual(self.out.events, [down(F5), up(F5)])
        self.out.events.clear()
        e.handle_key(KEY_1, 1)
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [("wheel", -1)])

    async def test_wheel_notch_holds_key_long_enough_for_games(self):
        e = self.engine(profile(wheel_up="F5"))
        e.handle_wheel(1)
        self.assertEqual(self.out.events, [down(F5)])
        await self.settle()
        self.assertEqual(self.out.events, [down(F5), up(F5)])
        self.assertEqual(self.sleeps, [0.03])

    async def test_quick_notches_each_tap_once(self):
        e = self.engine(profile(wheel_up="F5"))
        e.handle_wheel(1)
        e.handle_wheel(2)
        await self.settle()
        self.assertEqual(self.out.events, [down(F5), up(F5)] * 3)

    async def test_release_all_drops_pending_notches(self):
        e = self.engine(profile(wheel_up="F5"))
        e.handle_wheel(3)
        await asyncio.sleep(0)
        e.release_all()
        await self.settle()
        self.assertEqual(self.out.events, [down(F5), up(F5)])

    async def test_factory_wheel_passes_through(self):
        e = self.engine(profile())
        e.handle_wheel(1)
        e.handle_wheel(-1)
        self.assertEqual(self.out.events, [("wheel", 1), ("wheel", -1)])

    async def test_dpad_8way_transition(self):
        e = self.engine(profile("8way", dpad_up="W", dpad_up_right="E"))
        e.handle_key(KEY_UP, 1)
        self.assertEqual(self.out.events, [down(W)])
        e.handle_key(KEY_RIGHT, 1)
        self.assertEqual(self.out.events, [down(W), up(W), down(E)])
        e.handle_key(KEY_UP, 0)
        self.assertEqual(self.out.events, [down(W), up(W), down(E), up(E), down(RIGHT)])

    async def test_dpad_4way_union(self):
        e = self.engine(profile(dpad_up="W", dpad_right="D"))
        e.handle_key(KEY_UP, 1)
        e.handle_key(KEY_RIGHT, 1)
        e.handle_key(KEY_UP, 0)
        D = code_for("D")
        self.assertEqual(self.out.events, [down(W), down(D), up(W)])

    async def test_passthrough_mode(self):
        e = self.engine(profile(k01="Esc", wheel_up="F5"))
        e.passthrough = True
        e.handle_key(KEY_1, 1)
        e.handle_key(KEY_1, 0)
        e.handle_wheel(1)
        self.assertEqual(self.out.events, [down(KEY_1), up(KEY_1), ("wheel", 1)])

    async def test_passthrough_toggle_releases_held(self):
        e = self.engine(profile(k01="Esc"))
        e.handle_key(KEY_1, 1)
        e.passthrough = True
        e.handle_key(KEY_1, 0)
        self.assertEqual(self.out.events, [down(ESC), up(ESC)])
        self.assertTrue(e.passthrough)


    # --- depth (driver mode) ---

    @staticmethod
    def depths(**keys):
        out = bytearray(20)
        for control, depth in keys.items():
            out[int(control[1:]) - 1] = depth
        return bytes(out)

    async def test_depth_press_and_release(self):
        e = self.engine(profile(k01="Esc"))
        e.handle_depth(self.depths(k01=16))
        self.assertEqual(self.out.events, [down(ESC)])
        e.handle_depth(self.depths(k01=7))
        self.assertEqual(self.out.events, [down(ESC), up(ESC)])

    async def test_depth_uses_k01_binding_types(self):
        e = self.engine(profile(k02="A, B", k03="steam:menu"))
        e.handle_depth(self.depths(k02=40, k03=40))
        await self.settle()
        self.assertEqual(self.out.events, [("steam", "menu"), down(A), up(A), down(B), up(B)])

    async def test_depth_ignored_in_passthrough(self):
        e = self.engine(profile(k01="Esc"))
        e.passthrough = True
        e.handle_depth(self.depths(k01=200))
        e.handle_depth(self.depths(k01=0))
        self.assertEqual(self.out.events, [])

    async def test_depth_held_into_passthrough_does_not_fire_after(self):
        e = self.engine(profile(k01="Esc"))
        e.passthrough = True
        e.handle_depth(self.depths(k01=200))
        e.passthrough = False
        e.handle_depth(self.depths(k01=210))
        self.assertEqual(self.out.events, [])

    async def test_release_all_blocks_until_rearm(self):
        prof = profile(k01="Esc")
        e = self.engine(prof)
        e.handle_depth(self.depths(k01=200))
        self.assertEqual(self.out.events, [down(ESC)])
        e.set_profile(prof)
        self.assertEqual(self.out.events, [down(ESC), up(ESC)])
        e.handle_depth(self.depths(k01=210))
        e.handle_depth(self.depths(k01=5))
        self.assertEqual(self.out.events, [down(ESC), up(ESC)])
        e.handle_depth(self.depths(k01=16))
        self.assertEqual(self.out.events, [down(ESC), up(ESC), down(ESC)])

    async def test_actuation_point_from_profile(self):
        prof = profile(k01="Esc")
        prof.actuation = {"k01": 2.5}
        e = self.engine(prof)
        e.handle_depth(self.depths(k01=119))
        self.assertEqual(self.out.events, [])
        e.handle_depth(self.depths(k01=120))
        e.handle_depth(self.depths(k01=112))
        self.assertEqual(self.out.events, [down(ESC)])
        e.handle_depth(self.depths(k01=111))
        self.assertEqual(self.out.events, [down(ESC), up(ESC)])

    async def test_unchanged_bytes_do_nothing(self):
        e = self.engine(profile(k01="Esc"))
        e.handle_depth(self.depths(k01=100))
        e.handle_depth(self.depths(k01=100))
        self.assertEqual(self.out.events, [down(ESC)])


    # --- secondary function ---

    @staticmethod
    def crouch_prone(b_text="Z"):
        prof = profile(k05="C")
        prof.secondary = {"k05": Secondary(parse_binding_text(b_text), 3.6)}
        return prof

    async def test_secondary_crouch_prone(self):
        e = self.engine(self.crouch_prone())
        e.handle_depth(self.depths(k05=20))
        self.assertEqual(self.out.events, [down(C)])
        e.handle_depth(self.depths(k05=255))
        self.assertEqual(self.out.events, [down(C), up(C), down(Z)])
        e.handle_depth(self.depths(k05=200))
        e.handle_depth(self.depths(k05=0))
        self.assertEqual(self.out.events, [down(C), up(C), down(Z), up(Z)])

    async def test_release_all_with_b_held(self):
        e = self.engine(self.crouch_prone())
        e.handle_depth(self.depths(k05=255))
        e.release_all()
        self.assertEqual(self.out.events, [down(Z), up(Z)])
        e.handle_depth(self.depths(k05=254))
        e.handle_depth(self.depths(k05=7))
        self.assertEqual(self.out.events, [down(Z), up(Z)])
        e.handle_depth(self.depths(k05=20))
        self.assertEqual(self.out.events, [down(Z), up(Z), down(C)])

    async def test_b_macro(self):
        e = self.engine(self.crouch_prone("A, B"))
        e.handle_depth(self.depths(k05=255))
        await self.settle()
        self.assertEqual(self.out.events, [down(A), up(A), down(B), up(B)])


if __name__ == "__main__":
    unittest.main()
