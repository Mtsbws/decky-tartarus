#!/usr/bin/env python3
"""Deck checks for the analog and profile-LED follow-up. Run as root, one step at a time:

    sudo python3 deck-probe.py getmode           # ask the device mode (00/84), changes nothing
    sudo python3 deck-probe.py setmode 03        # driver mode (00/04 03 00), as Synapse does
    sudo python3 deck-probe.py setmode 00        # back to normal mode (00/04 00 00)
    sudo python3 deck-probe.py led FF 00 00      # profile LEDs (0F/02 01 0B 01 00 01 01 R G B)
    sudo python3 deck-probe.py read 60           # read-only: log input reports for 60 s;
                                                 # grabs the event nodes (stop the plugin first)
    sudo python3 deck-probe.py frame FF6000      # custom frame (0F/02 then 0F/03), all 21 cells that colour
    sudo python3 deck-probe.py frame FF0000 5    # only cell 5 (0-20) in that colour, the rest 26 26 26
    sudo python3 deck-probe.py frametime 20      # 20 x (static effect + brightness, then the two frame
                                                 # reports); prints mean/max ms per switch

Only these fixed commands exist; the bytes match the Synapse captures
(docs/superpowers/synapse-capture-findings.md).
"""
import fcntl
import glob
import os
import re
import select
import struct
import sys
import time

HID_ID = "HID_ID=0003:00001532:00000244"
_IFACE = re.compile(r":1\.(\d+)/")
TXID = 0x1F
LOG = "/home/deck/tartarus-probe.log"


def _ioc(direction, nr, size):
    return (direction << 30) | (size << 16) | (ord("H") << 8) | nr


def HIDIOCSFEATURE(n):
    return _ioc(3, 0x06, n)


def HIDIOCGFEATURE(n):
    return _ioc(3, 0x07, n)


EVIOCGRAB = (1 << 30) | (4 << 16) | (ord("E") << 8) | 0x90
EVENT = struct.Struct("llHHi")


def event_nodes():
    found = []
    for sys_ev in sorted(glob.glob("/sys/class/input/event*")):
        try:
            with open(os.path.join(sys_ev, "device", "id", "vendor")) as f:
                vendor = f.read().strip()
            with open(os.path.join(sys_ev, "device", "id", "product")) as f:
                product = f.read().strip()
        except OSError:
            continue
        if (vendor, product) == ("1532", "0244"):
            found.append("/dev/input/" + os.path.basename(sys_ev))
    return found


def nodes():
    found = {}
    for sys_hid in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        device = os.path.join(sys_hid, "device")
        try:
            with open(os.path.join(device, "uevent")) as f:
                if HID_ID not in f.read().splitlines():
                    continue
        except OSError:
            continue
        match = _IFACE.search(os.path.realpath(device) + "/")
        if match:
            found[int(match.group(1))] = "/dev/" + os.path.basename(sys_hid)
    return found


def report(command_class, command_id, args):
    r = bytearray(90)
    r[1] = TXID
    r[5] = len(args)
    r[6] = command_class
    r[7] = command_id
    r[8:8 + len(args)] = args
    crc = 0
    for b in r[2:88]:
        crc ^= b
    r[88] = crc
    return bytes(r)


def send(path, rep, quiet=False):
    buf = b"\x00" + rep
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.ioctl(fd, HIDIOCSFEATURE(len(buf)), buf)
        time.sleep(0.001)
        resp = bytearray(len(buf))
        fcntl.ioctl(fd, HIDIOCGFEATURE(len(buf)), resp)
    finally:
        os.close(fd)
    if quiet:
        return resp[1]
    line = "sent %s  reply status %02x: %s" % (rep[:16].hex(" "), resp[1], bytes(resp[1:17]).hex(" "))
    print(line)
    with open(LOG, "a") as f:
        f.write("%.3f %s\n" % (time.time(), line))
    return resp[1]


# effect_reports("static", "#00ff00", 100) from py_modules/tartarus/lighting.py, copied as arguments
STATIC_GREEN = [
    report(0x0F, 0x02, bytes.fromhex("010501000001" "00ff00")),
    report(0x0F, 0x04, bytes.fromhex("0100ff")),
]


def frame_reports(rgb, index=None):
    """The custom-frame pair: 0F/02 selects the frame, 0F/03 carries 21 RGB cells."""
    cells = b"".join(rgb if index in (None, i) else b"\x26\x26\x26" for i in range(21))
    return [report(0x0F, 0x02, bytes.fromhex("000008000000")),
            report(0x0F, 0x03, bytes.fromhex("0000000014") + cells)]


def frametime(path, count):
    times = {"static": [], "frame": []}
    for _ in range(count):
        for name, reps in (("static", STATIC_GREEN), ("frame", frame_reports(b"\xff\x60\x00"))):
            start = time.monotonic()
            statuses = [send(path, rep, quiet=True) for rep in reps]
            times[name].append((time.monotonic() - start) * 1000)
            if any(s != 0x02 for s in statuses):
                print("%s: statuses %s" % (name, [hex(s) for s in statuses]))
    for name, ms in times.items():
        print("%s switch: mean %.1f ms, max %.1f ms over %d" % (name, sum(ms) / len(ms), max(ms), len(ms)))


def read(found, seconds):
    fds = {os.open(dev, os.O_RDONLY | os.O_NONBLOCK): i for i, dev in found.items()}
    evs = {}
    for dev in event_nodes():
        fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
        fcntl.ioctl(fd, EVIOCGRAB, 1)  # keep the keypad's events away from Steam
        evs[fd] = dev
    print("Reading %s for %d s. Press keys 01-20, top button, D-pad, wheel." % (sorted(fds.values()), seconds))
    start, last, firsts, counts = time.monotonic(), {}, [], {}
    with open(LOG, "a") as log:
        while time.monotonic() - start < seconds:
            ready, _, _ = select.select(list(fds) + list(evs), [], [], 0.5)
            for fd in ready:
                if fd in evs:
                    data = os.read(fd, EVENT.size * 64)
                    for off in range(0, len(data), EVENT.size):
                        _, _, etype, code, value = EVENT.unpack_from(data, off)
                        if etype not in (0, 4):  # count everything but SYN and MSC
                            counts[(evs[fd], etype, code)] = counts.get((evs[fd], etype, code), 0) + 1
                        if etype == 1 and value != 2:  # EV_KEY, no autorepeat
                            line = "%6.1f s  evdev %s key code %d value %d" % (
                                time.monotonic() - start, evs[fd], code, value)
                            print(line)
                            log.write(line + "\n")
                            log.flush()
                    continue
                try:
                    data = os.read(fd, 256)
                except BlockingIOError:
                    continue
                if not data or last.get(fd) == data:
                    continue
                last[fd] = data
                t = time.monotonic() - start
                log.write("%9.3f iface %d %s\n" % (t, fds[fd], data.hex(" ")))
                log.flush()
                if fds[fd] == 1 and data[0] == 0x06:
                    for i, v in enumerate(data[1:], 1):
                        if v > 200 and i not in firsts:
                            firsts.append(i)
                            print("%6.1f s  depth byte %d reached %d" % (t, i, v))
                else:
                    print("%6.1f s  iface %d %s" % (t, fds[fd], data.hex(" ")))
    for fd in list(fds) + list(evs):
        os.close(fd)
    for (dev, etype, code), n in sorted(counts.items()):
        print("evdev %s type %d code %d: %d events" % (dev, etype, code, n))


def main():
    found = nodes()
    if 2 not in found:
        sys.exit("Tartarus Pro not found: %s" % found)
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "getmode":
        send(found[2], report(0x00, 0x84, b"\x00\x00"))
    elif cmd == "setmode" and sys.argv[2:] in (["03"], ["00"]):
        send(found[2], report(0x00, 0x04, bytes([int(sys.argv[2], 16), 0x00])))
    elif cmd == "led" and len(sys.argv) == 5:
        rgb = bytes(int(x, 16) for x in sys.argv[2:5])
        send(found[2], report(0x0F, 0x02, b"\x01\x0b\x01\x00\x01\x01" + rgb))
    elif cmd == "frame" and len(sys.argv) in (3, 4):
        rgb = bytes.fromhex(sys.argv[2].lstrip("#"))
        if len(rgb) != 3:
            sys.exit("frame needs RRGGBB")
        index = int(sys.argv[3]) if len(sys.argv) == 4 else None
        for rep in frame_reports(rgb, index):
            send(found[2], rep)
    elif cmd == "frametime" and len(sys.argv) == 3:
        frametime(found[2], int(sys.argv[2]))
    elif cmd == "read":
        read(found, float(sys.argv[2]) if len(sys.argv) > 2 else 60)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
