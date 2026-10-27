import os
import tempfile
import unittest

from tartarus.linux.discovery import TartarusNodes, find_tartarus, list_keyboards

USB = "devices/pci0000:00/0000:00:08.1/0000:04:00.3/usb1/1-1/1-1.4/1-1.4.2"
# Capability masks copied from the Deck (event11, event13, event14).
KEYS_IFACE0 = "1000000000007 ff9f207ac14057ff febeffdfffefffff fffffffffffffffe"
KEYS_MOUSE = "1f0000 0 0 0 0"


class FakeSys:
    """A sysfs tree shaped like the Deck's: class/* symlinks into devices/.../<usb iface>/<hid>/..."""

    def __init__(self, root):
        self.root = root

    def _write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text + "\n")

    def _link(self, cls, name, target):
        os.makedirs(os.path.join(self.root, "class", cls), exist_ok=True)
        os.symlink(os.path.join("..", "..", target), os.path.join(self.root, "class", cls, name))

    def add_event(self, n, name, iface, hid, vendor="1532", product="0244", keys=KEYS_IFACE0):
        inp = f"{USB}:1.{iface}/0003:{vendor.upper()}:{product.upper()}.{hid}/input/input{n}"
        base = os.path.join(self.root, inp)
        self._write(os.path.join(base, "id", "vendor"), vendor)
        self._write(os.path.join(base, "id", "product"), product)
        self._write(os.path.join(base, "name"), name)
        self._write(os.path.join(base, "capabilities", "key"), keys)
        os.makedirs(os.path.join(base, f"event{n}"))
        os.symlink("..", os.path.join(base, f"event{n}", "device"))
        self._link("input", f"event{n}", f"{inp}/event{n}")

    def add_hidraw(self, n, iface, hid, vendor="1532", product="0244"):
        hid_dir = f"{USB}:1.{iface}/0003:{vendor.upper()}:{product.upper()}.{hid}"
        self._write(os.path.join(self.root, hid_dir, "uevent"),
                    f"DRIVER=hid-generic\nHID_ID=0003:0000{vendor.upper()}:0000{product.upper()}\nHID_NAME=x")
        node = os.path.join(self.root, hid_dir, "hidraw", f"hidraw{n}")
        os.makedirs(node)
        os.symlink(os.path.join("..", ".."), os.path.join(node, "device"))
        self._link("hidraw", f"hidraw{n}", f"{hid_dir}/hidraw/hidraw{n}")

    def add_tartarus(self):
        self.add_event(11, "Razer Razer Tartarus Pro", 0, "0007")
        self.add_event(12, "Razer Razer Tartarus Pro Keyboard", 1, "0008")
        self.add_event(13, "Razer Razer Tartarus Pro", 1, "0008", keys="0")
        self.add_event(14, "Razer Razer Tartarus Pro", 2, "0009", keys=KEYS_MOUSE)
        for n, iface, hid in ((6, 0, "0007"), (7, 1, "0008"), (8, 2, "0009")):
            self.add_hidraw(n, iface, hid)


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.sys = FakeSys(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_finds_all_event_nodes(self):
        self.sys.add_tartarus()
        self.sys.add_event(3, "AT Translated Set 2 keyboard", 0, "0001", vendor="0001", product="0001")
        nodes = find_tartarus(self.root)
        self.assertEqual(nodes.event, ["/dev/input/event11", "/dev/input/event12",
                                       "/dev/input/event13", "/dev/input/event14"])

    def test_picks_lighting_hidraw(self):
        self.sys.add_tartarus()
        self.assertEqual(find_tartarus(self.root), TartarusNodes(
            event=["/dev/input/event11", "/dev/input/event12", "/dev/input/event13", "/dev/input/event14"],
            hidraw="/dev/hidraw8", depth="/dev/hidraw7"))

    def test_depth_node_missing_is_none(self):
        self.sys.add_event(11, "Razer Razer Tartarus Pro", 0, "0007")
        self.sys.add_hidraw(8, 2, "0009")
        nodes = find_tartarus(self.root)
        self.assertEqual(nodes.hidraw, "/dev/hidraw8")
        self.assertIsNone(nodes.depth)

    def test_hidraw_missing_is_none(self):
        self.sys.add_event(11, "Razer Razer Tartarus Pro", 0, "0007")
        self.sys.add_hidraw(6, 0, "0007")
        self.assertIsNone(find_tartarus(self.root).hidraw)

    def test_absent_returns_none(self):
        self.sys.add_event(3, "AT Translated Set 2 keyboard", 0, "0001", vendor="0001", product="0001")
        self.assertIsNone(find_tartarus(self.root))
        self.assertIsNone(find_tartarus(os.path.join(self.root, "nothing")))

    def test_numeric_order(self):
        self.sys.add_event(9, "Razer Razer Tartarus Pro", 0, "0007")
        self.sys.add_event(10, "Razer Razer Tartarus Pro Keyboard", 1, "0008")
        self.assertEqual(find_tartarus(self.root).event, ["/dev/input/event9", "/dev/input/event10"])

    def test_list_keyboards_excludes_tartarus_and_virtual(self):
        self.sys.add_tartarus()
        self.sys.add_event(3, "AT Translated Set 2 keyboard", 0, "0001", vendor="0001", product="0001")
        self.sys.add_event(10, "EndGameGear XM1 Gaming Mouse", 0, "0002", vendor="3367", product="1903",
                           keys=KEYS_MOUSE)
        self.sys.add_event(257, "Decky Tartarus Keyboard", 0, "0003", vendor="1209", product="0001")
        self.sys.add_event(18, "SONiX USB DEVICE Keyboard", 0, "0004", vendor="0c45", product="7663")
        self.assertEqual(list_keyboards(self.root), ["/dev/input/event3", "/dev/input/event18"])


if __name__ == "__main__":
    unittest.main()
