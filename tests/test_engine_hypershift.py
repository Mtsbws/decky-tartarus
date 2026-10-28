import asyncio
import dataclasses
import itertools
import unittest

from tartarus.actuation import mm_to_depth
from tartarus.bindings import parse_binding_text
from tartarus.codes import code_for
from tartarus.config import Hypershift, Secondary, profile_from_starter
from tartarus.devmap import FACTORY_CODES
from tartarus.starters import STARTERS

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

    def engine(self, prof, **kw):
        return RemapEngine(self.out, prof, sleep=lambda seconds: asyncio.sleep(0), **kw)

    async def settle(self):
        for _ in range(50):
            await asyncio.sleep(0)

    def check_clean(self, e):
        self.assertEqual(e._counts, {})

    async def test_on_layer_callback(self):
        calls = []
        e = self.engine(hs_profile(k09="F1"), on_layer=calls.append)
        e.handle_key(K19, 1)
        self.assertEqual(calls, [True])
        e.handle_key(K19, 0)
        self.assertEqual(calls, [True, False])
        e.handle_key(K19, 1)
        e.release_all()
        self.assertEqual(calls, [True, False, True, False])
        e.release_all()
        self.assertEqual(calls, [True, False, True, False])

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
        e.handle_key(K09, 0)
        e.handle_key(K19, 0)
        self.check_clean(e)

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

    # --- depth (driver mode) ---

    depths = staticmethod(__import__("tests.test_engine", fromlist=["EngineTest"]).EngineTest.depths)

    def depth_engine(self, standard_secondary=None, standard_mm=None, entry_text="F1",
                     entry_mm=None, entry_secondary=None):
        p = hs_profile(k09=entry_text) if entry_text else hs_profile()
        layer = p.hypershift
        if entry_mm is not None:
            layer.actuation["k09"] = entry_mm
        if entry_secondary is not None:
            layer.secondary["k09"] = Secondary(parse_binding_text(entry_secondary[0]), entry_secondary[1])
        if standard_secondary is not None:
            p.secondary["k09"] = Secondary(parse_binding_text(standard_secondary[0]), standard_secondary[1])
        if standard_mm is not None:
            p.actuation["k09"] = standard_mm
        return self.engine(p)

    async def test_layer_actuation_point(self):
        e = self.depth_engine(entry_mm=2.5)
        e.handle_depth(self.depths(k19=200))
        e.handle_depth(self.depths(k19=200, k09=60))
        self.assertEqual(self.out.events, [])
        e.handle_depth(self.depths(k19=200, k09=130))
        self.assertEqual(self.out.events, [down(F1)])

    async def test_layer_secondary_function(self):
        e = self.depth_engine(entry_secondary=("F3", 3.6))
        e.handle_depth(self.depths(k19=200))
        e.handle_depth(self.depths(k19=200, k09=130))
        e.handle_depth(self.depths(k19=200, k09=255))
        self.assertEqual(self.out.events, [down(F1), up(F1), down(F3)])

    async def test_fall_through_keeps_standard_secondary(self):
        Z = code_for("Z")
        e = self.depth_engine(entry_text=None, standard_secondary=("Z", 3.6))
        e.handle_depth(self.depths(k19=200))
        e.handle_depth(self.depths(k19=200, k09=130))
        e.handle_depth(self.depths(k19=200, k09=255))
        self.assertEqual(self.out.events, [down(E), up(E), down(Z)])

    async def test_entry_without_secondary_has_none(self):
        e = self.depth_engine(standard_secondary=("Z", 3.6))
        e.handle_depth(self.depths(k19=200))
        e.handle_depth(self.depths(k19=200, k09=255))
        self.assertEqual(self.out.events, [down(F1)])

    async def test_depth_press_keeps_its_layer_points(self):
        e = self.depth_engine(standard_mm=2.5, entry_mm=1.5)
        e.handle_depth(self.depths(k09=60))
        self.assertEqual(self.out.events, [])
        e.handle_depth(self.depths(k09=60, k19=200))
        self.assertEqual(self.out.events, [])
        e.handle_depth(self.depths(k09=61, k19=200))
        self.assertEqual(self.out.events, [down(F1)])

    async def test_depth_press_started_standard_stays_standard(self):
        e = self.depth_engine(standard_mm=2.5, entry_mm=1.5)
        e.handle_depth(self.depths(k09=130))
        self.assertEqual(self.out.events, [down(E)])
        e.handle_depth(self.depths(k09=130, k19=200))
        e.handle_depth(self.depths(k09=135, k19=200))
        e.handle_depth(self.depths(k09=135, k19=0))
        e.handle_depth(self.depths(k09=0, k19=0))
        self.assertEqual(self.out.events, [down(E), up(E)])
        self.check_clean(e)

    async def test_set_profile_while_hypershift_held(self):
        p = hs_profile(k09="F1")
        e = self.engine(p)
        e.handle_depth(self.depths(k19=200))
        e.handle_depth(self.depths(k19=200, k09=200))
        self.assertEqual(self.out.events, [down(F1)])
        e.set_profile(p)
        self.assertEqual(self.out.events, [down(F1), up(F1)])
        e.handle_depth(self.depths(k19=200, k09=210))
        self.assertEqual(self.out.events, [down(F1), up(F1)])
        e.handle_depth(self.depths(k19=0, k09=0))
        e.handle_depth(self.depths(k19=200, k09=0))
        e.handle_depth(self.depths(k19=200, k09=200))
        self.assertEqual(self.out.events, [down(F1), up(F1), down(F1)])

    # --- the MMO starter's layer ---

    def mmo(self):
        return profile_from_starter(next(s for s in STARTERS if s.slug == "mmo"), "p4", "MMO", (True, False, False))

    async def test_mmo_hypershift_layer_sends_ctrl_number(self):
        CTRL, ONE, K02 = code_for("Ctrl"), code_for("1"), PHYS["k02"]
        e = self.engine(self.mmo())
        e.handle_key(K19, 1)
        e.handle_key(K02, 1)
        e.handle_key(K02, 0)
        self.assertEqual(self.out.events, [down(CTRL), down(ONE), up(ONE), up(CTRL)])
        e.handle_key(K19, 0)
        e.handle_key(K02, 1)
        e.handle_key(K02, 0)
        self.assertEqual(self.out.events[4:], [down(ONE), up(ONE)])
        self.check_clean(e)

    async def test_mmo_k18_secondary_falls_through_on_the_layer(self):
        M, B_KEY = code_for("M"), code_for("B")
        shallow, deep = mm_to_depth(1.5), mm_to_depth(3.0)
        for held in (0, 200):
            with self.subTest(hypershift_held=bool(held)):
                self.out = FakeEmitter()
                e = self.engine(self.mmo())
                e.handle_depth(self.depths(k19=held))
                e.handle_depth(self.depths(k19=held, k18=shallow))
                self.assertEqual(self.out.events, [down(M)])
                e.handle_depth(self.depths(k19=held, k18=deep))
                self.assertEqual(self.out.events, [down(M), up(M), down(B_KEY)])

    def test_mmo_k19_has_no_secondary(self):
        self.assertNotIn("k19", self.mmo().secondary)

