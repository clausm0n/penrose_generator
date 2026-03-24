#!/usr/bin/env python3
"""
Arcade input tester with tkinter GUI for Raspberry Pi.
Opens all input devices, filters joystick noise with a deadzone,
and displays live button/axis state on the Pi's screen.

Run with: DISPLAY=:0 sudo python3 test_inputs.py
"""

import struct
import os
import select
import tkinter as tk

# --- Input event constants ---

EV_TYPES = {
    0x00: "SYN", 0x01: "KEY", 0x02: "REL", 0x03: "ABS",
    0x04: "MSC", 0x11: "LED", 0x15: "FF",
}

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

ABS_NAMES = {
    0x00: "ABS_X", 0x01: "ABS_Y", 0x02: "ABS_Z",
    0x03: "ABS_RX", 0x04: "ABS_RY", 0x05: "ABS_RZ",
    0x10: "ABS_HAT0X", 0x11: "ABS_HAT0Y",
}

EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

# DragonRise boards typically report 0-255 with 128 as center
AXIS_CENTER = 128
AXIS_DEADZONE = 20  # ignore jitter within +/- this range of center


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
                pass
    return fds


class InputTesterGUI:
    MAX_LOG = 50
    POLL_MS = 16  # ~60hz

    def __init__(self):
        self.fds = open_all_devices()
        self.axis_state = {}      # axis_name -> current value
        self.axis_last_sent = {}  # axis_name -> last value that passed deadzone
        self.button_state = {}    # btn_name -> True/False
        self.event_count = 0

        self.root = tk.Tk()
        self.root.title("Arcade Input Tester")
        self.root.configure(bg="#1a1a2e")
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self._build_ui()

        if not self.fds:
            self._log("ERROR: No input devices found. Run with sudo.")
        else:
            for fd, (path, name) in self.fds.items():
                self._log(f"Opened: {path} - {name}")
            self._log("Waiting for input...")

        self.root.after(self.POLL_MS, self._poll_inputs)

    def _build_ui(self):
        # Title
        tk.Label(
            self.root, text="ARCADE INPUT TESTER", font=("monospace", 24, "bold"),
            bg="#1a1a2e", fg="#e94560"
        ).pack(pady=(20, 10))

        # Main content: left = live state, right = event log
        content = tk.Frame(self.root, bg="#1a1a2e")
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Left panel - live state
        left = tk.Frame(content, bg="#16213e", relief=tk.RIDGE, bd=2)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Label(
            left, text="LIVE STATE", font=("monospace", 16, "bold"),
            bg="#16213e", fg="#0f3460"
        ).pack(pady=(10, 5))

        # Joystick visualizer
        stick_frame = tk.Frame(left, bg="#16213e")
        stick_frame.pack(pady=10)

        tk.Label(
            stick_frame, text="STICK", font=("monospace", 12),
            bg="#16213e", fg="#999999"
        ).pack()

        self.stick_canvas = tk.Canvas(
            stick_frame, width=160, height=160, bg="#0a0a1a",
            highlightthickness=1, highlightbackground="#333"
        )
        self.stick_canvas.pack(pady=5)
        # crosshair
        self.stick_canvas.create_line(80, 0, 80, 160, fill="#333")
        self.stick_canvas.create_line(0, 80, 160, 80, fill="#333")
        # deadzone circle
        r = int(160 * AXIS_DEADZONE / 255)
        self.stick_canvas.create_oval(80 - r, 80 - r, 80 + r, 80 + r, outline="#333", dash=(2, 2))
        # dot
        self.stick_dot = self.stick_canvas.create_oval(76, 76, 84, 84, fill="#e94560")

        self.stick_label = tk.Label(
            stick_frame, text="X: 128  Y: 128", font=("monospace", 11),
            bg="#16213e", fg="#cccccc"
        )
        self.stick_label.pack()

        # Buttons display
        tk.Label(
            left, text="BUTTONS", font=("monospace", 12),
            bg="#16213e", fg="#999999"
        ).pack(pady=(15, 5))

        self.button_frame = tk.Frame(left, bg="#16213e")
        self.button_frame.pack(pady=5, padx=10)
        self.button_labels = {}

        # Extra axes display
        tk.Label(
            left, text="EXTRA AXES", font=("monospace", 12),
            bg="#16213e", fg="#999999"
        ).pack(pady=(15, 5))

        self.axes_frame = tk.Frame(left, bg="#16213e")
        self.axes_frame.pack(pady=5, padx=10)
        self.axis_bars = {}

        # Right panel - event log
        right = tk.Frame(content, bg="#16213e", relief=tk.RIDGE, bd=2)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        tk.Label(
            right, text="EVENT LOG", font=("monospace", 16, "bold"),
            bg="#16213e", fg="#0f3460"
        ).pack(pady=(10, 5))

        self.log_text = tk.Text(
            right, font=("monospace", 11), bg="#0a0a1a", fg="#00ff88",
            state=tk.DISABLED, wrap=tk.NONE, relief=tk.FLAT,
            insertbackground="#00ff88"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Event counter at bottom
        self.counter_label = tk.Label(
            self.root, text="Events: 0", font=("monospace", 12),
            bg="#1a1a2e", fg="#666666"
        )
        self.counter_label.pack(pady=(0, 15))

    def _log(self, text):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        # Trim to MAX_LOG lines
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > self.MAX_LOG:
            self.log_text.delete("1.0", f"{lines - self.MAX_LOG}.0")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _update_stick(self):
        x = self.axis_state.get("ABS_X", AXIS_CENTER)
        y = self.axis_state.get("ABS_Y", AXIS_CENTER)
        # Map 0-255 to canvas 0-160
        cx = int(x / 255 * 160)
        cy = int(y / 255 * 160)
        self.stick_canvas.coords(self.stick_dot, cx - 4, cy - 4, cx + 4, cy + 4)
        # Color: green in deadzone, red outside
        dx, dy = abs(x - AXIS_CENTER), abs(y - AXIS_CENTER)
        color = "#e94560" if dx > AXIS_DEADZONE or dy > AXIS_DEADZONE else "#555555"
        self.stick_canvas.itemconfig(self.stick_dot, fill=color)
        self.stick_label.config(text=f"X: {x:<4d} Y: {y:<4d}")

    def _update_button(self, name, pressed):
        self.button_state[name] = pressed
        if name not in self.button_labels:
            lbl = tk.Label(
                self.button_frame, text=name, font=("monospace", 12, "bold"),
                width=16, relief=tk.RAISED, bd=2, bg="#333333", fg="#aaaaaa"
            )
            col = len(self.button_labels) % 4
            row = len(self.button_labels) // 4
            lbl.grid(row=row, column=col, padx=3, pady=3)
            self.button_labels[name] = lbl

        lbl = self.button_labels[name]
        if pressed:
            lbl.config(bg="#e94560", fg="#ffffff", relief=tk.SUNKEN)
        else:
            lbl.config(bg="#333333", fg="#aaaaaa", relief=tk.RAISED)

    def _update_axis_bar(self, name, value):
        if name not in self.axis_bars:
            frame = tk.Frame(self.axes_frame, bg="#16213e")
            row = len(self.axis_bars)
            frame.grid(row=row, column=0, sticky="ew", pady=2)
            lbl = tk.Label(frame, text=name, font=("monospace", 10), bg="#16213e",
                           fg="#999999", width=12, anchor="w")
            lbl.pack(side=tk.LEFT)
            canvas = tk.Canvas(frame, width=200, height=16, bg="#0a0a1a",
                               highlightthickness=0)
            canvas.pack(side=tk.LEFT, padx=5)
            bar = canvas.create_rectangle(0, 0, 0, 16, fill="#0f3460")
            val_lbl = tk.Label(frame, text="0", font=("monospace", 10),
                               bg="#16213e", fg="#cccccc", width=5)
            val_lbl.pack(side=tk.LEFT)
            self.axis_bars[name] = (canvas, bar, val_lbl)

        canvas, bar, val_lbl = self.axis_bars[name]
        w = int(value / 255 * 200)
        canvas.coords(bar, 0, 0, w, 16)
        val_lbl.config(text=str(value))

    def _in_deadzone(self, axis_name, value):
        return abs(value - AXIS_CENTER) <= AXIS_DEADZONE

    def _poll_inputs(self):
        if not self.fds:
            self.root.after(self.POLL_MS, self._poll_inputs)
            return

        try:
            readable, _, _ = select.select(list(self.fds.keys()), [], [], 0)
        except (ValueError, OSError):
            self.root.after(self.POLL_MS, self._poll_inputs)
            return

        for fd in readable:
            try:
                data = os.read(fd, EVENT_SIZE * 32)
            except OSError:
                continue
            for offset in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                _, _, ev_type, code, value = struct.unpack_from(EVENT_FORMAT, data, offset)

                if ev_type == 0x00 or ev_type == 0x04:
                    continue

                if ev_type == 0x03:  # ABS axis
                    axis_name = ABS_NAMES.get(code, f"ABS_{code}")
                    self.axis_state[axis_name] = value

                    if axis_name in ("ABS_X", "ABS_Y"):
                        # Only log stick moves that escape deadzone
                        prev = self.axis_last_sent.get(axis_name, AXIS_CENTER)
                        was_in = self._in_deadzone(axis_name, prev)
                        now_in = self._in_deadzone(axis_name, value)
                        if was_in and now_in:
                            self._update_stick()
                            continue  # skip log, just jitter
                        self.axis_last_sent[axis_name] = value
                        self._update_stick()
                    else:
                        # Other axes (Z, RZ, etc) - filter same way
                        prev = self.axis_last_sent.get(axis_name, AXIS_CENTER)
                        if self._in_deadzone(axis_name, prev) and self._in_deadzone(axis_name, value):
                            self._update_axis_bar(axis_name, value)
                            continue
                        self.axis_last_sent[axis_name] = value
                        self._update_axis_bar(axis_name, value)

                    self.event_count += 1
                    dir_str = str(value)
                    if axis_name in ("ABS_X", "ABS_HAT0X"):
                        if value < AXIS_CENTER - AXIS_DEADZONE: dir_str = f"{value} LEFT"
                        elif value > AXIS_CENTER + AXIS_DEADZONE: dir_str = f"{value} RIGHT"
                        else: dir_str = f"{value} CENTER"
                    elif axis_name in ("ABS_Y", "ABS_HAT0Y"):
                        if value < AXIS_CENTER - AXIS_DEADZONE: dir_str = f"{value} UP"
                        elif value > AXIS_CENTER + AXIS_DEADZONE: dir_str = f"{value} DOWN"
                        else: dir_str = f"{value} CENTER"
                    self._log(f"#{self.event_count:<5d}  {axis_name:16s}  {dir_str}")

                elif ev_type == 0x01:  # KEY
                    btn_name = KEY_NAMES.get(code, f"KEY_{code}")
                    val_str = {0: "RELEASED", 1: "PRESSED", 2: "HELD"}.get(value, str(value))
                    pressed = value >= 1
                    self._update_button(btn_name, pressed)
                    self.event_count += 1
                    self._log(f"#{self.event_count:<5d}  {btn_name:16s}  {val_str}")

                else:
                    type_str = EV_TYPES.get(ev_type, f"0x{ev_type:02x}")
                    self.event_count += 1
                    self._log(f"#{self.event_count:<5d}  {type_str}  code={code}  val={value}")

        self.counter_label.config(text=f"Events: {self.event_count}")
        self.root.after(self.POLL_MS, self._poll_inputs)

    def run(self):
        self.root.mainloop()
        for fd in self.fds:
            os.close(fd)


if __name__ == "__main__":
    app = InputTesterGUI()
    app.run()
