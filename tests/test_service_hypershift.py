import asyncio
import tempfile
import unittest
from pathlib import Path

from tartarus.bindings import parse_binding_text
from tartarus.config import Secondary
from tartarus.linux.evdev import EV_KEY, EV_SYN

from tests.test_service import TWO_NODES, Rig, until

KEY_C, KEY_E, KEY_F1 = 46, 18, 59


class ServiceHypershiftTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"
        self.rig = Rig(self.path)
        self.service = self.rig.service

    def tearDown(self):
        self._tmp.cleanup()

    def hs(self, key="k19"):
        self.service.set_binding("default", key, parse_binding_text("hypershift"))

    def profile(self):
        return self.service._edit_target("default")

    def layer_state(self):
        return self.service.state()["profiles"][0]["hypershift"]

    def test_choose_hypershift_key(self):
        self.hs()
        state = self.service.state()["profiles"][0]
        self.assertEqual(state["hypershift"]["key"], "k19")
        self.assertEqual(state["bindings"]["k19"]["label"], "Hypershift")

    def test_moving_the_key_resets_the_old_one(self):
        self.hs("k19")
        self.hs("k05")
        state = self.service.state()["profiles"][0]
        self.assertEqual(state["hypershift"]["key"], "k05")
        self.assertEqual(self.profile().bindings["k19"], parse_binding_text("C"))

    def test_key_loses_secondary_and_entry(self):
        self.service.set_secondary("default", "k05", 2.5)
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        self.service.set_secondary("default", "k05.h", 3.0)
        self.assertIn("k05", self.profile().hypershift.secondary)
        self.hs("k05")
        p = self.profile()
        self.assertNotIn("k05", p.secondary)
        self.assertNotIn("k05", p.hypershift.bindings)
        self.assertNotIn("k05", p.hypershift.actuation)
        self.assertNotIn("k05", p.hypershift.secondary)

    def test_key_keeps_standard_actuation(self):
        self.service.set_actuation("default", "k05", 2.0)
        self.hs("k05")
        self.assertEqual(self.profile().actuation["k05"], 2.0)

    def test_other_binding_turns_hypershift_off_keeps_layer(self):
        self.hs("k19")
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        self.service.set_binding("default", "k19", parse_binding_text("C"))
        self.assertIsNone(self.layer_state()["key"])
        self.assertIn("k05", self.layer_state()["bindings"])

    def test_hypershift_type_rejected_elsewhere(self):
        self.hs("k19")
        for control in ("k05.h", "k05.b", "wheel_up", "dpad_up"):
            with self.assertRaises(ValueError, msg=control):
                self.service.set_binding("default", control, parse_binding_text("hypershift"))
        with self.assertRaisesRegex(ValueError, "Only keys 01-20 and the top button"):
            self.service.set_binding("default", "dpad_up", parse_binding_text("hypershift"))
        self.assertEqual(self.layer_state()["key"], "k19")

    def test_entry_on_key_rejected(self):
        self.hs("k19")
        with self.assertRaisesRegex(ValueError, "The Hypershift key has no Hypershift binding"):
            self.service.set_binding("default", "k19.h", parse_binding_text("F1"))

    def test_secondary_on_key_rejected(self):
        self.hs("k19")
        with self.assertRaisesRegex(ValueError, "The Hypershift key has no secondary function"):
            self.service.set_secondary("default", "k19", 2.5)
        self.service.set_secondary("default", "k05", 2.5)
        self.hs("k05")
        with self.assertRaises(ValueError):
            self.service.set_binding("default", "k05.b", parse_binding_text("F1"))

    def test_new_entry_copies_standard_depth(self):
        self.service.set_actuation("default", "k05", 2.4)
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        p = self.profile()
        self.assertEqual(p.hypershift.actuation["k05"], 2.4)
        self.assertEqual(p.hypershift.secondary, {})

    def test_new_entry_at_default_depth_stores_no_actuation(self):
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        self.assertEqual(self.profile().hypershift.actuation, {})

    def test_layer_actuation_needs_entry(self):
        with self.assertRaisesRegex(ValueError, "k06 has no Hypershift binding"):
            self.service.set_actuation("default", "k06.h", 2.0)
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        with self.assertRaises(ValueError):
            self.service.set_actuation_keys("default", ["k05.h", "k06"], 2.0)
        with self.assertRaises(ValueError):
            self.service.set_actuation_keys("default", ["k05.h", "k06.h"], 2.0)
        self.service.set_actuation_keys("default", ["k05.h"], 2.0)
        self.assertEqual(self.profile().hypershift.actuation["k05"], 2.0)
        self.assertEqual(self.profile().actuation, {})

    def test_layer_actuation_moves_layer_secondary(self):
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        self.service.set_secondary("default", "k05.h", 2.5)
        self.service.set_actuation("default", "k05.h", 2.4)
        p = self.profile()
        self.assertEqual(p.hypershift.secondary["k05"].actuation, 2.9)
        self.assertEqual(p.hypershift.actuation["k05"], 2.4)
        self.assertEqual((p.actuation, p.secondary), ({}, {}))

    def test_layer_secondary_and_its_binding(self):
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        self.service.set_secondary("default", "k05.h", 3.0)
        self.service.set_binding("default", "k05.h.b", parse_binding_text("F3"))
        sec = self.layer_state()["secondary"]["k05"]
        self.assertEqual((sec["label"], sec["actuation"]), ("F3", 3.0))
        self.service.set_secondary("default", "k05.h", None)
        self.assertEqual(self.layer_state()["secondary"], {})

    def test_layer_secondary_needs_entry(self):
        with self.assertRaisesRegex(ValueError, "k05 has no Hypershift binding"):
            self.service.set_secondary("default", "k05.h", 3.0)
        with self.assertRaises(ValueError):
            self.service.set_binding("default", "k05.h.b", parse_binding_text("F3"))

    def test_clear_entry(self):
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        self.service.set_actuation("default", "k05.h", 2.0)
        self.service.set_secondary("default", "k05.h", 3.0)
        self.service.clear_hypershift_entry("default", "k05.h")
        p = self.profile().hypershift
        self.assertEqual((p.bindings, p.actuation, p.secondary), ({}, {}, {}))
        self.service.clear_hypershift_entry("default", "k05.h")

    def test_create_profile_copies_hypershift_deeply(self):
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        new_id = self.service.create_profile("Copy", "default")
        self.service.set_binding(new_id, "k06.h", parse_binding_text("F2"))
        self.service.set_secondary(new_id, "k05.h", 3.0)
        source = self.profile().hypershift
        self.assertEqual(list(source.bindings), ["k05"])
        self.assertEqual(source.secondary, {})
        copy = self.service._edit_target(new_id).hypershift
        self.assertEqual(sorted(copy.bindings), ["k05", "k06"])

    def test_state_layer_shape(self):
        self.service.set_binding("default", "k05.h", parse_binding_text("F1"))
        self.service.set_secondary("default", "k05.h", 3.0)
        layer = self.layer_state()
        self.assertEqual(layer["bindings"]["k05"], {"binding": {"type": "key", "keys": ["F1"]}, "label": "F1"})
        self.assertEqual(layer["secondary"]["k05"]["actuation"], 3.0)
        self.assertEqual(set(layer), {"key", "bindings", "actuation", "secondary"})

    def test_layer_edit_reaches_engine(self):
        async def go():
            rig = Rig(self.path)
            rig.service.set_binding("default", "k19", parse_binding_text("hypershift"))
            await rig.service.start()
            rig.nodes = TWO_NODES
            await until(lambda: rig.service.state()["connected"])
            rig.service.set_binding("default", "k09.h", parse_binding_text("F1"))
            kbd = rig.devices[0]
            kbd.push((EV_KEY, KEY_C, 1), (EV_SYN, 0, 0), (EV_KEY, KEY_E, 1), (EV_SYN, 0, 0))
            await until(lambda: ("key", KEY_F1, True) in rig.emitter.out)
            await rig.service.stop()

        asyncio.run(asyncio.wait_for(go(), 5))


if __name__ == "__main__":
    unittest.main()
