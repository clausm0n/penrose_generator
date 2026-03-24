#!/usr/bin/env python3
"""
Test script to display raw input from USB arcade controller on Raspberry Pi.
Opens ALL input devices and prints any signals received. No keyboard needed.
Run with: sudo python3 test_inputs.py
Stop with: Ctrl+C or unplug power.
"""

import struct
import os
import sys
import select
import time
import signal

# Event type names
EV_TYPES = {
    0x00: "SYN", 0x01: "KEY", 0x02: "REL", 0x03: "ABS",
    0x04: "MSC", 0x11: "LED", 0x15: "FF",
}

# Common button/key codes for arcade controllers
KEY_NAMES = {
    256: "BTN_0", 257: "BTN_1", 258: "BTN_2", 259: "BTN_3",
    260: "BTN_4", 261: "BTN_5", 262: "BTN_6", 263: "BTN_7",
    264: "BTN_8", 265: "BTN_9",
    288: "BTN_TRIGGER", 289: "BTN_THUMB", 290: "BTN_THUMB2",
    291: "BTN_TOP", 292: "BTN_TOP2", 293: "BTN_PINKIE",
    294: "BTN_BASE", 295: "BTN_BASE2", 296: "BTN_BASE3",
    297: "BTN_BASE4", 298: "BTN_BASE5", 299: "BTN_BASE6",
    304: "BTN_SOUTH/A", 305: "BTN_EAST/B", 306: "BTN_C",
    307: "BTN_NORTH/X", 308: "BTN_WEST/Y", 309: "BTN_Z",
    310: "BTN_TL", 311: "BTN_TR", 312: "BTN_TL2", 313: "BTN_TR2",
    314: "BTN_SELECT", 315: "BTN_START", 316: "BTN_MODE",
}

# ABS axis names
ABS_NAMES = {
    0x00: "ABS_X", 0x01: "ABS_Y", 0x02: "ABS_Z",
    0x03: "ABS_RX", 0x04: "ABS_RY", 0x05: "ABS_RZ",
    0x10: "ABS_HAT0X", 0x11: "ABS_HAT0Y",
}

# input_event struct: timestamp_sec, timestamp_usec, type, code, value
EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)


def get_device_name(event_num):
    try:
        with open(f"/sys/class/input/event{event_num}/device/name", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "Unknown"


def open_all_devices():
    fds = {}
    for i in range(20):
        path = f"/dev/input/event{i}"
        if os.path.exists(path):
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                name = get_device_name(i)
                fds[fd] = (path, name)
            except PermissionError:
                name = get_device_name(i)
                print(f"  SKIP {path} ({name}) - permission denied")
    return fds


def format_event(ev_type, code, value):
    type_str = EV_TYPES.get(ev_type, f"0x{ev_type:02x}")
    if ev_type == 0x01:  # KEY
        code_str = KEY_NAMES.get(code, f"KEY_{code}")
        val_str = {0: "RELEASED", 1: "PRESSED", 2: "HELD"}.get(value, str(value))
    elif ev_type == 0x03:  # ABS
        code_str = ABS_NAMES.get(code, f"ABS_{code}")
        val_str = str(value)
    elif ev_type == 0x02:  # REL
        code_str = f"REL_{code}"
        val_str = str(value)
    else:
        code_str = str(code)
        val_str = str(value)
    return type_str, code_str, val_str


def main():
    print("=" * 60)
    print("  ARCADE INPUT TESTER")
    print("  Scanning all /dev/input/event* devices")
    print("=" * 60)
    print()

    fds = open_all_devices()

    if not fds:
        print("No input devices could be opened.")
        print("Make sure to run with: sudo python3 test_inputs.py")
        sys.exit(1)

    print()
    print("Monitoring devices:")
    for fd, (path, name) in fds.items():
        print(f"  {path} - {name}")
    print()
    print("-" * 60)
    print("Waiting for input... (Ctrl+C to quit)")
    print("-" * 60)
    print()

    event_count = 0

    try:
        while True:
            readable, _, _ = select.select(list(fds.keys()), [], [], 1.0)
            for fd in readable:
                try:
                    data = os.read(fd, EVENT_SIZE * 16)
                except OSError:
                    continue
                for offset in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                    _, _, ev_type, code, value = struct.unpack_from(EVENT_FORMAT, data, offset)
                    if ev_type == 0x00:  # skip SYN
                        continue
                    if ev_type == 0x04:  # skip MSC (noise)
                        continue
                    type_str, code_str, val_str = format_event(ev_type, code, value)
                    _, name = fds[fd]
                    event_count += 1
                    print(f"#{event_count:<5d}  [{name}]  {type_str:4s}  {code_str:16s}  {val_str}")
    except KeyboardInterrupt:
        print(f"\nDone. {event_count} events captured.")
    finally:
        for fd in fds:
            os.close(fd)


if __name__ == "__main__":
    main()
