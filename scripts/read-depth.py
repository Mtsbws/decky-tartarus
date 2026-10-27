#!/usr/bin/env python3
"""Read-only check: does the Tartarus Pro send key-depth reports in normal mode?

Opens every hidraw node of 1532:0244 read-only and logs each input report it
receives, plus the cached HID report descriptors from sysfs. It never writes
to the keypad: no feature reports, no output reports, no ioctls that reach the
device. Run on the Deck as root (hidraw nodes are root-only):

    sudo python3 read-depth.py [seconds] [log path]

Defaults: 120 seconds, /home/deck/tartarus-depth.log.
"""
import glob
import os
import re
import select
import sys
import time

HID_ID = "HID_ID=0003:00001532:00000244"
_IFACE = re.compile(r":1\.(\d+)/")

PROMPT = """Press slowly (about 2 s down, 2 s up), one at a time, in this order:
  key 01, key 02, key 06, key 14, key 19, key 20 (thumb key),
  the button above the D-pad, D-pad up / right / down / left,
  wheel up, wheel down, wheel click.
Then press key 01 halfway, hold 2 s, release. Ctrl+C ends early."""


def nodes():
    found = []
    for sys_hid in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        device = os.path.join(sys_hid, "device")
        try:
            with open(os.path.join(device, "uevent")) as f:
                if HID_ID not in f.read().splitlines():
                    continue
        except OSError:
            continue
        match = _IFACE.search(os.path.realpath(device) + "/")
        iface = int(match.group(1)) if match else -1
        found.append((iface, "/dev/" + os.path.basename(sys_hid), device))
    return found


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
    log_path = sys.argv[2] if len(sys.argv) > 2 else "/home/deck/tartarus-depth.log"
    found = nodes()
    if not found:
        sys.exit("Tartarus Pro not found")
    log = open(log_path, "w")

    def out(line):
        log.write(line + "\n")

    fds = {}
    for iface, dev, sysdev in found:
        try:
            with open(os.path.join(sysdev, "report_descriptor"), "rb") as f:
                out("descriptor iface %d %s: %s" % (iface, dev, f.read().hex(" ")))
        except OSError as e:
            out("descriptor iface %d %s: unreadable (%s)" % (iface, dev, e))
        fds[os.open(dev, os.O_RDONLY | os.O_NONBLOCK)] = (iface, dev)
    print("Reading %s for %d s, log %s" % (
        ", ".join("iface %d=%s" % v for v in fds.values()), seconds, log_path))
    print(PROMPT)

    start = time.monotonic()
    last = {}
    stats = {}  # (iface, report id, length) -> [count, per-byte max]
    try:
        while time.monotonic() - start < seconds:
            ready, _, _ = select.select(list(fds), [], [], 0.5)
            for fd in ready:
                try:
                    data = os.read(fd, 256)
                except BlockingIOError:
                    continue
                iface, dev = fds[fd]
                if not data or last.get(fd) == data:
                    continue
                last[fd] = data
                out("%9.3f iface %d %s" % (time.monotonic() - start, iface, data.hex(" ")))
                key = (iface, data[0], len(data))
                entry = stats.setdefault(key, [0, [0] * len(data)])
                entry[0] += 1
                entry[1] = [max(a, b) for a, b in zip(entry[1], data)]
    except KeyboardInterrupt:
        pass
    finally:
        for fd in fds:
            os.close(fd)

    out("summary (iface, first byte, length): count, per-byte max")
    print("Summary (iface, first byte, length): count, per-byte max")
    for (iface, rid, length), (count, maxes) in sorted(stats.items()):
        line = "iface %d id %02x len %d: %d reports, max %s" % (
            iface, rid, length, count, " ".join("%02x" % b for b in maxes))
        out(line)
        print(line)
    log.close()


if __name__ == "__main__":
    main()
