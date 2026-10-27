import asyncio
import dataclasses
import itertools
import unittest

from tartarus.bindings import parse_binding_text
from tartarus.codes import code_for
from tartarus.config import Hypershift
from tartarus.devmap import FACTORY_CODES

from tartarus.engine import RemapEngine
from tests.test_engine import FakeEmitter, C, E, W, A, B, F5, profile, down, up, KEY_UP, KEY_RIGHT

PHYS = {control: code for code, control in FACTORY_CODES.items()}
K19, K09, K08, TOP = PHYS["k19"], PHYS["k09"], PHYS["k08"], PHYS["top_button"]
F1, F2, F3, ALT = (code_for(n) for n in ("F1", "F2", "F3", "Alt"))


def hs_profile(dpad_mode="4way", **layer_texts):
    """k19 is the Hypershift key; layer_texts are the layer's bindings by control id."""
    p = profile(dpad_mode=dpad_mode, k19="hypershift")
    layer = Hypershift(bindings={c: parse_binding_text(t) for c, t in layer_texts.items()})
    return dataclasses.replace(p, hypershift=layer)


class HypershiftEngineTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.out = FakeEmitter()

    def engine(self, prof):
        return RemapEngine(self.out, prof, sleep=lambda seconds: asyncio.sleep(0))

    async def settle(self):
        for _ in range(50):
            await asyncio.sleep(0)

    def check_clean(self, e):
        self.assertEqual(e._counts, {})

    async def test_layer_binding_while_held(self):
        e = self.engine(hs_profile(k09="F1"))
        e.handle_key(K19, 1)
        e.handle_key(K09, 1)
        e.handle_key(K09, 0)
        e.handle_key(K19, 0)
        self.assertEqual(self.out.events, [down(F1), up(F1)])
        self.check_clean(e)

    async def test_fall_through_uses_standard(self):
        e = self.engine(hs_profile(k09="F1"))
        e.handle_key(K19, 1)
        e.handle_key(K08, 1)
        e.handle_key(K08, 0)
        e.handle_key(K19, 0)
        self.assertEqual(self.out.events, [down(W), up(W)])
        self.check_clean(e)

    async def test_disable_entry_does_nothing(self):
        e = self.engine(hs_profile(k09="disable"))
        e.handle_key(K19, 1)
        e.handle_key(K09, 1)
        e.handle_key(K09, 0)
        e.handle_key(K19, 0)
        self.assertEqual(self.out.events, [])
        self.check_clean(e)

    async def test_standard_press_survives_hypershift_down(self):
        e = self.engine(hs_profile(k09="F1"))
        e.handle_key(K09, 1)
        e.handle_key(K19, 1)
        e.handle_key(K09, 0)
        e.handle_key(K19, 0)
        self.assertEqual(self.out.events, [down(E), up(E)])
        self.check_clean(e)

    async def test_layer_binding_released_after_hypershift_up(self):
        e = self.engine(hs_profile(k09="F1"))
        e.handle_key(K19, 1)
        e.handle_key(K09, 1)
        e.handle_key(K19, 0)
        self.assertEqual(self.out.events, [down(F1)])
        e.handle_key(K09, 0)
        self.assertEqual(self.out.events, [down(F1), up(F1)])
        e.handle_key(K09, 1)
        e.handle_key(K09, 0)
        self.assertEqual(self.out.events, [down(F1), up(F1), down(E), up(E)])
        self.check_clean(e)

    async def test_every_order_of_two_presses(self):
        names = ("hd", "hu", "ed", "eu")
        for order in itertools.permutations(names):
            if order.index("hd") > order.index("hu") or order.index("ed") > order.index("eu"):
                continue
            with self.subTest(order=order):
                self.out.events.clear()
                e = self.engine(hs_profile(k09="F1"))
                for step in order:
                    code = K19 if step[0] == "h" else K09
                    e.handle_key(code, 1 if step[1] == "d" else 0)
                layered = order.index("hd") < order.index("ed") < order.index("hu")
                out = F1 if layered else E
                self.assertEqual(self.out.events, [down(out), up(out)])
                self.check_clean(e)

    async def test_macro_entry_runs_and_finishes(self):
        e = self.engine(hs_profile(k09="A, B"))
        e.handle_key(K19, 1)
        e.handle_key(K09, 1)
        e.handle_key(K19, 0)
        e.handle_key(K09, 0)
        await self.settle()
        self.assertEqual(self.out.events, [down(A), up(A), down(B), up(B)])
        self.check_clean(e)

    async def test_wheel_uses_layer_at_step(self):
        e = self.engine(hs_profile(wheel_up="F5"))
        e.handle_wheel(1)
        e.handle_key(K19, 1)
        e.handle_wheel(1)
        e.handle_key(K19, 0)
        e.handle_wheel(1)
        self.assertEqual(self.out.events, [("wheel", 1), down(F5), up(F5), ("wheel", 1)])
        self.check_clean(e)

    async def test_dpad_direction_entry_and_press_rule(self):
        e = self.engine(hs_profile(dpad_up="F2"))
        up_code = code_for("Up")
        e.handle_key(KEY_UP, 1)
        e.handle_key(K19, 1)
        e.handle_key(KEY_UP, 0)
        self.assertEqual(self.out.events, [down(up_code), up(up_code)])
        self.out.events.clear()
        e.handle_key(KEY_UP, 1)
        e.handle_key(KEY_UP, 0)
        self.assertEqual(self.out.events, [down(F2), up(F2)])
        e.handle_key(K19, 0)
        self.check_clean(e)

    async def test_dpad_8way_diagonal_uses_new_layer(self):
        e = self.engine(hs_profile(dpad_mode="8way", dpad_up_right="F3"))
        up_code = code_for("Up")
        e.handle_key(K19, 1)
        e.handle_key(KEY_UP, 1)
        e.handle_key(KEY_RIGHT, 1)
        self.assertEqual(self.out.events, [down(up_code), up(up_code), down(F3)])
        e.handle_key(KEY_RIGHT, 0)
        e.handle_key(KEY_UP, 0)
        e.handle_key(K19, 0)
        self.check_clean(e)

    async def test_release_all_resets_layer(self):
        e = self.engine(hs_profile(k09="F1"))
        e.handle_key(K19, 1)
        e.handle_key(K09, 1)
        e.release_all()
        self.assertEqual(self.out.events, [down(F1), up(F1)])
        self.out.events.clear()
        e.handle_key(K09, 1)  # 19 is still physically down, but the layer is standard
        self.assertEqual(self.out.events, [down(E)])
        e.handle_key(K09, 0)
        e.handle_key(K19, 0)
        self.check_clean(e)

    async def test_no_hypershift_key_no_layer(self):
        p = dataclasses.replace(profile(), hypershift=Hypershift(bindings={"k09": parse_binding_text("F1")}))
        e = self.engine(p)
        e.handle_key(K19, 1)
        e.handle_key(K09, 1)
        self.assertEqual(self.out.events, [down(C), down(E)])

    async def test_top_button_as_hypershift_key(self):
        p = profile(top_button="hypershift")
        p = dataclasses.replace(p, hypershift=Hypershift(bindings={"k09": parse_binding_text("F1")}))
        e = self.engine(p)
        e.handle_key(TOP, 1)
        e.handle_key(K09, 1)
        e.handle_key(K09, 0)
        e.handle_key(TOP, 0)
        self.assertEqual(self.out.events, [down(F1), up(F1)])
        self.check_clean(e)
