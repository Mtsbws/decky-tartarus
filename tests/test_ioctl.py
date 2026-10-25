import unittest

from tartarus.linux import ioctl
from tartarus.linux.evdev import EV_KEY, EV_REL, INPUT_EVENT, REL_WHEEL
from tartarus.linux.uinput import UinputEmitter


class IoctlTest(unittest.TestCase):
    def test_numbers_match_linux_headers(self):
        self.assertEqual(ioctl.EVIOCGRAB, 0x40044590)
        self.assertEqual(ioctl.UI_SET_EVBIT, 0x40045564)
        self.assertEqual(ioctl.UI_SET_KEYBIT, 0x40045565)
        self.assertEqual(ioctl.UI_DEV_SETUP, 0x405C5503)
        self.assertEqual(ioctl.UI_DEV_CREATE, 0x5501)
        self.assertEqual(ioctl.HIDIOCSFEATURE(91), 0xC05B4806)
        self.assertEqual(ioctl.EVIOCGNAME(256), 0x81004506)

    def test_more_numbers(self):
        self.assertEqual(ioctl.UI_SET_RELBIT, 0x40045566)
        self.assertEqual(ioctl.UI_DEV_DESTROY, 0x5502)
        self.assertEqual(ioctl.HIDIOCGFEATURE(91), 0xC05B4807)
        self.assertEqual(ioctl.EVIOCGBIT(1, 96), 0x80604521)

    def test_input_event_size(self):
        self.assertEqual(INPUT_EVENT.size, 24)


class FakeDevice:
    def __init__(self):
        self.events = []
        self.syncs = 0

    def emit(self, type_, code, value):
        self.events.append((type_, code, value))

    def syn(self):
        self.syncs += 1

    def close(self):
        pass


class EmitterTest(unittest.TestCase):
    def setUp(self):
        self.kbd, self.mouse, self.steam = FakeDevice(), FakeDevice(), []
        self.out = UinputEmitter(self.steam.append, keyboard=self.kbd, mouse=self.mouse)

    def test_buttons_to_mouse_keys_to_keyboard(self):
        self.out.key(0x111, True)  # BTN_RIGHT
        self.out.key(1, True)  # KEY_ESC
        self.out.key(1, False)
        self.assertEqual(self.mouse.events, [(EV_KEY, 0x111, 1)])
        self.assertEqual(self.kbd.events, [(EV_KEY, 1, 1), (EV_KEY, 1, 0)])

    def test_wheel_and_steam(self):
        self.out.wheel(-1)
        self.out.steam_action("qam")
        self.out.sync()
        self.assertEqual(self.mouse.events, [(EV_REL, REL_WHEEL, -1)])
        self.assertEqual(self.steam, ["qam"])
        self.assertEqual((self.kbd.syncs, self.mouse.syncs), (1, 1))


if __name__ == "__main__":
    unittest.main()
