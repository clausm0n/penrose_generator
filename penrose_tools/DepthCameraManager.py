"""
Background-threaded Orbbec depth camera capture.
Provides thread-safe access to the latest depth frame.
Optional module -- gracefully unavailable if no driver is found.

Capture backends (tried in order):
  1. Native OrbbecSDK v1 via ctypes -- ARM64-native on Apple Silicon
  2. OpenNI2 (python-openni2) -- works on x86_64 or via Rosetta
  3. x86_64 bridge subprocess -- Rosetta fallback for ARM64 Macs
"""

import logging
import mmap
import os
import struct
import subprocess
import sys
import threading
import time

import numpy as np

logger = logging.getLogger('DepthCameraManager')

# ---------------------------------------------------------------------------
# Backend detection (priority order)
# ---------------------------------------------------------------------------
_BACKEND = None  # 'orbbec_native', 'openni2', 'bridge'

# 1) Try native OrbbecSDK (ARM64 + x86_64 universal on macOS)
try:
    from penrose_tools.orbbec_native import ORBBEC_NATIVE_AVAILABLE
    if ORBBEC_NATIVE_AVAILABLE:
        _BACKEND = 'orbbec_native'
        logger.info("Using native OrbbecSDK backend (ARM64)")
except Exception as _e:
    logger.debug(f"OrbbecSDK native not available: {_e}")

# 2) Try OpenNI2
if _BACKEND is None:
    _RUNTIME_BASE = os.path.join(os.path.dirname(__file__), 'openni2_runtime')
    if sys.platform == 'darwin':
        _OPENNI2_REDIST = os.path.join(_RUNTIME_BASE, 'macos')
    elif sys.platform == 'win32':
        _OPENNI2_REDIST = os.path.join(_RUNTIME_BASE, 'win64')
    else:
        _OPENNI2_REDIST = _RUNTIME_BASE

    try:
        from openni import openni2
        openni2.initialize(_OPENNI2_REDIST)
        _BACKEND = 'openni2'
        logger.info("Using OpenNI2 backend")
    except Exception as _e:
        openni2 = None
        logger.debug(f"OpenNI2 native init failed: {_e}")

# 3) Rosetta bridge fallback for macOS arm64
if _BACKEND is None and sys.platform == 'darwin':
    import platform as _platform
    if _platform.machine() == 'arm64':
        _BRIDGE_PYTHON = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            '.venv_x86', 'bin', 'python3')
        _BRIDGE_SCRIPT = os.path.join(
            os.path.dirname(__file__), 'depth_capture_bridge.py')
        # Need _OPENNI2_REDIST for bridge mode
        if '_OPENNI2_REDIST' not in dir():
            _OPENNI2_REDIST = os.path.join(
                os.path.dirname(__file__), 'openni2_runtime', 'macos')
        if os.path.exists(_BRIDGE_PYTHON) and os.path.exists(_BRIDGE_SCRIPT):
            _BACKEND = 'bridge'
            logger.info("Using x86_64 bridge for depth camera (Rosetta)")

OPENNI2_AVAILABLE = _BACKEND is not None
# Legacy alias so penrose_generator.py import check still works
DEPTH_CAMERA_AVAILABLE = OPENNI2_AVAILABLE

_BRIDGE_HEADER_SIZE = 16  # uint32 counter + uint32 width + uint32 height + reserved


class DepthCameraManager:
    """
    Captures depth frames from an Orbbec camera on a daemon background thread
    via the OpenNI2 driver.  Thread-safe: the latest depth frame is guarded
    by a lock.
    """

    def __init__(self, width=640, height=480, fps=30,
                 depth_min_mm=500, depth_max_mm=4000, invert=True):
        if not OPENNI2_AVAILABLE:
            logger.warning("OpenNI2 not available -- DepthCameraManager disabled")

        self._requested_width = width
        self._requested_height = height
        self._requested_fps = fps

        # Depth processing parameters
        self.depth_min_mm = depth_min_mm
        self.depth_max_mm = depth_max_mm
        self.invert = invert

        # Smoothing
        self.temporal_smoothing = 0.3
        self._prev_depth = None

        # Threshold: pixels below this value become 0 (binary silhouette)
        self.threshold = 0.64
        self.threshold_enabled = True

        self._thread = None
        self._running = False
        self._lock = threading.Lock()

        self._depth_frame = None
        self._depth_timestamp = 0.0
        self._frame_count = 0

        self._callbacks = []
        self._callbacks_lock = threading.Lock()

        self._device = None
        self._stream = None
        self._init_event = threading.Event()
        self._init_ok = False

        # Bridge subprocess state
        self._bridge_proc = None
        self._bridge_shm_path = None
        self._bridge_ctrl_path = None
        self._bridge_mm = None
        self._bridge_fd = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, timeout=10.0):
        """Start the capture thread and wait for the depth stream to produce
        its first frame.  Returns True on success."""
        if not OPENNI2_AVAILABLE:
            logger.warning("Cannot start -- no depth camera backend available")
            return False

        if self._running:
            return True

        self._init_event.clear()
        self._init_ok = False
        self._running = True

        if _BACKEND == 'orbbec_native':
            target = self._native_capture_loop
            name = "DepthCameraManager-Native"
        elif _BACKEND == 'bridge':
            target = self._bridge_capture_loop
            name = "DepthCameraManager-Bridge"
        else:
            target = self._capture_loop
            name = "DepthCameraManager"

        self._thread = threading.Thread(target=target, name=name, daemon=True)
        self._thread.start()
        logger.info(
            f"Started depth capture thread "
            f"({self._requested_width}x{self._requested_height}@{self._requested_fps}fps)"
            f" [{_BACKEND}]")

        if not self._init_event.wait(timeout=timeout):
            logger.error("Depth camera init timed out")
            self._running = False
            return False

        if not self._init_ok:
            logger.error("Depth camera stream failed to start")
            self._running = False
            return False

        return True

    def stop(self):
        """Signal the capture thread to stop and wait for it to finish."""
        if not self._running:
            return
        self._running = False

        # Signal bridge to stop
        if self._bridge_ctrl_path:
            try:
                with open(self._bridge_ctrl_path, 'w') as f:
                    f.write('stop')
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None

        # Clean up bridge resources
        self._cleanup_bridge()

        logger.info("Depth capture thread stopped")

    def _cleanup_bridge(self):
        if self._bridge_mm:
            try:
                self._bridge_mm.close()
            except Exception:
                pass
            self._bridge_mm = None
        if self._bridge_fd is not None:
            try:
                os.close(self._bridge_fd)
            except Exception:
                pass
            self._bridge_fd = None
        if self._bridge_proc and self._bridge_proc.poll() is None:
            self._bridge_proc.terminate()
            try:
                self._bridge_proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._bridge_proc.kill()
            self._bridge_proc = None
        # Clean up temp files
        for path in (self._bridge_shm_path, self._bridge_ctrl_path):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass
        self._bridge_shm_path = None
        self._bridge_ctrl_path = None

    @property
    def is_running(self):
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def is_available(self):
        return OPENNI2_AVAILABLE

    # ------------------------------------------------------------------
    # Frame access (thread-safe)
    # ------------------------------------------------------------------

    def get_depth(self):
        """Return (depth_frame_copy, timestamp) or (None, 0.0).
        Depth frame is a float32 array with values in [0, 1]."""
        with self._lock:
            if self._depth_frame is not None:
                return self._depth_frame.copy(), self._depth_timestamp
            return None, 0.0

    def get_depth_no_copy(self):
        """Return latest depth frame WITHOUT copying -- caller must not mutate."""
        with self._lock:
            return self._depth_frame, self._depth_timestamp

    @property
    def frame_count(self):
        return self._frame_count

    # ------------------------------------------------------------------
    # Callback system
    # ------------------------------------------------------------------

    def add_callback(self, fn):
        with self._callbacks_lock:
            self._callbacks.append(fn)

    def remove_callback(self, fn):
        with self._callbacks_lock:
            self._callbacks = [cb for cb in self._callbacks if cb is not fn]

    # ------------------------------------------------------------------
    # Native OrbbecSDK capture loop (ARM64-native via ctypes)
    # ------------------------------------------------------------------

    def _native_capture_loop(self):
        try:
            from penrose_tools.orbbec_native import OrbbecDepthCamera

            cam = OrbbecDepthCamera(
                width=self._requested_width,
                height=self._requested_height,
                fps=self._requested_fps,
            )
            cam.open()
            logger.info(
                f"Native OrbbecSDK: {cam.actual_width}x{cam.actual_height}")

            # Wait for first frame
            first_frame = None
            for _ in range(100):
                if not self._running:
                    cam.close()
                    return
                result = cam.read_depth_frame(timeout_ms=200)
                if result is not None:
                    first_frame = result
                    break

            if first_frame is None:
                logger.error("Native OrbbecSDK: no frames received")
                self._init_ok = False
                self._init_event.set()
                cam.close()
                return

            logger.info("Native OrbbecSDK: first frame received")
            self._init_ok = True
            self._init_event.set()

            # Main capture loop
            _last_fps_log = time.monotonic()
            _fps_frame_count = 0

            while self._running:
                result = cam.read_depth_frame(timeout_ms=100)
                if result is None:
                    continue

                raw_depth, w, h, value_scale = result
                depth_data = self._process_native_frame(
                    raw_depth, w, h, value_scale)
                if depth_data is None:
                    continue

                ts = time.monotonic()
                _fps_frame_count += 1

                with self._lock:
                    self._depth_frame = depth_data
                    self._depth_timestamp = ts
                    self._frame_count += 1

                elapsed = ts - _last_fps_log
                if elapsed >= 5.0:
                    fps = _fps_frame_count / elapsed
                    logger.info(
                        f"Depth capture (native): {fps:.1f} fps "
                        f"(total frames: {self._frame_count})")
                    _last_fps_log = ts
                    _fps_frame_count = 0

                with self._callbacks_lock:
                    callbacks = list(self._callbacks)
                for cb in callbacks:
                    try:
                        cb(depth_data, ts)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

        except Exception as e:
            logger.error(f"Native capture loop error: {e}")
            self._init_ok = False
            self._init_event.set()
            self._running = False
        finally:
            try:
                cam.close()
            except Exception:
                pass

    def _process_native_frame(self, raw_uint16, w, h, value_scale):
        """Convert a native OrbbecSDK uint16 depth frame to normalised float32."""
        try:
            # Convert to depth values using the SDK-provided scale factor
            depth_vals = raw_uint16.astype(np.float32) * value_scale

            # Mask for valid depth pixels (non-zero)
            valid = depth_vals > 0

            # On first frame, detect if values are raw sensor units (not mm)
            # and calibrate the range accordingly
            if not hasattr(self, '_raw_unit_mode'):
                self._raw_unit_mode = False
                if value_scale <= 1.0 and np.any(valid):
                    max_val = np.max(depth_vals[valid])
                    if max_val < self.depth_min_mm:
                        self._raw_unit_mode = True
                        self._raw_max_observed = float(max_val)
                        # Set range to raw sensor units
                        self.depth_min_mm = 0
                        self.depth_max_mm = int(max_val)
                        logger.info(f"Raw sensor units detected (max={max_val:.0f})"
                                    f" - range set to 0-{self.depth_max_mm}")

            # Track the max observed value in raw mode for HUD display
            if self._raw_unit_mode and np.any(valid):
                frame_max = float(np.max(depth_vals[valid]))
                self._raw_max_observed = max(
                    getattr(self, '_raw_max_observed', 0), frame_max)

            # Normalize using configured range (works for both mm and raw units)
            depth_range = self.depth_max_mm - self.depth_min_mm
            if depth_range <= 0:
                depth_range = 1
            depth_normalized = np.zeros((h, w), dtype=np.float32)
            depth_normalized[valid] = np.clip(
                (depth_vals[valid] - self.depth_min_mm) / depth_range,
                0.0, 1.0)

            if self.invert:
                depth_normalized[valid] = 1.0 - depth_normalized[valid]

            # Flip vertically (camera row 0 = top, OpenGL row 0 = bottom)
            # and horizontally (mirror so output matches real-world orientation)
            depth_normalized = np.ascontiguousarray(depth_normalized[::-1, ::-1])

            if self.temporal_smoothing > 0.0 and self._prev_depth is not None:
                if self._prev_depth.shape == depth_normalized.shape:
                    alpha = self.temporal_smoothing
                    depth_normalized = (alpha * self._prev_depth
                                        + (1.0 - alpha) * depth_normalized)

            self._prev_depth = depth_normalized.copy()

            # Binary threshold
            if self.threshold_enabled and self.threshold > 0:
                depth_normalized = np.where(
                    depth_normalized >= self.threshold, 1.0, 0.0
                ).astype(np.float32)

            return depth_normalized

        except Exception as e:
            logger.error(f"Native frame processing error: {e}")
            return None

    # ------------------------------------------------------------------
    # Bridge capture loop (reads from x86_64 subprocess via mmap)
    # ------------------------------------------------------------------

    def _bridge_capture_loop(self):
        import tempfile
        try:
            # Create temp files for shared memory and control
            tmp_dir = tempfile.gettempdir()
            self._bridge_shm_path = os.path.join(tmp_dir, f'depth_shm_{os.getpid()}.bin')
            self._bridge_ctrl_path = os.path.join(tmp_dir, f'depth_ctrl_{os.getpid()}.txt')

            # Remove stale control file
            if os.path.exists(self._bridge_ctrl_path):
                os.unlink(self._bridge_ctrl_path)

            # Launch bridge subprocess with sudo
            cmd = [
                'sudo', '-n',  # non-interactive sudo (must have NOPASSWD or cached)
                _BRIDGE_PYTHON,
                _BRIDGE_SCRIPT,
                '--redist', _OPENNI2_REDIST,
                '--shm', self._bridge_shm_path,
                '--ctrl', self._bridge_ctrl_path,
                '--depth-min', str(self.depth_min_mm),
                '--depth-max', str(self.depth_max_mm),
                '--invert', str(int(self.invert)),
                '--threshold', str(self.threshold),
            ]

            logger.info(f"Launching bridge: {' '.join(cmd)}")
            self._bridge_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            # Wait for the shared memory file to appear with valid data
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                if not self._running:
                    return
                if self._bridge_proc.poll() is not None:
                    # Process exited — read output for diagnostics
                    out = self._bridge_proc.stdout.read().decode(errors='replace')
                    logger.error(f"Bridge process exited: {out}")
                    self._init_ok = False
                    self._init_event.set()
                    return
                if os.path.exists(self._bridge_shm_path):
                    size = os.path.getsize(self._bridge_shm_path)
                    if size > _BRIDGE_HEADER_SIZE:
                        break
                time.sleep(0.1)
            else:
                logger.error("Bridge: shared memory file never appeared")
                self._init_ok = False
                self._init_event.set()
                return

            # Open memory-mapped file
            self._bridge_fd = os.open(self._bridge_shm_path, os.O_RDONLY)
            file_size = os.fstat(self._bridge_fd).st_size
            self._bridge_mm = mmap.mmap(
                self._bridge_fd, file_size, access=mmap.ACCESS_READ)

            # Read header
            counter, w, h = struct.unpack_from('III', self._bridge_mm, 0)
            logger.info(f"Bridge connected: {w}x{h}, counter={counter}")

            if counter == 0:
                # Wait for first frame
                for _ in range(100):
                    if not self._running:
                        return
                    counter, = struct.unpack_from('I', self._bridge_mm, 0)
                    if counter > 0:
                        break
                    time.sleep(0.1)

            if counter == 0:
                logger.error("Bridge: no frames received")
                self._init_ok = False
                self._init_event.set()
                return

            self._init_ok = True
            self._init_event.set()
            logger.info("Bridge: first frame received, streaming")

            # Main read loop
            last_counter = 0
            _last_fps_log = time.monotonic()
            _fps_frame_count = 0
            frame_bytes = w * h * 4

            while self._running:
                if self._bridge_proc.poll() is not None:
                    logger.error("Bridge process died unexpectedly")
                    break

                counter, = struct.unpack_from('I', self._bridge_mm, 0)
                if counter == last_counter:
                    time.sleep(0.001)
                    continue

                last_counter = counter
                raw = self._bridge_mm[_BRIDGE_HEADER_SIZE:
                                      _BRIDGE_HEADER_SIZE + frame_bytes]
                depth_data = np.frombuffer(raw, dtype=np.float32).reshape(
                    (h, w)).copy()

                ts = time.monotonic()
                _fps_frame_count += 1

                with self._lock:
                    self._depth_frame = depth_data
                    self._depth_timestamp = ts
                    self._frame_count += 1

                elapsed = ts - _last_fps_log
                if elapsed >= 5.0:
                    fps = _fps_frame_count / elapsed
                    logger.info(
                        f"Depth capture (bridge): {fps:.1f} fps "
                        f"(total frames: {self._frame_count})")
                    _last_fps_log = ts
                    _fps_frame_count = 0

                with self._callbacks_lock:
                    callbacks = list(self._callbacks)
                for cb in callbacks:
                    try:
                        cb(depth_data, ts)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

        except Exception as e:
            logger.error(f"Bridge capture loop error: {e}")
            self._init_ok = False
            self._init_event.set()
            self._running = False

    # ------------------------------------------------------------------
    # Native capture loop (runs on background thread)
    # ------------------------------------------------------------------

    def _capture_loop(self):
        try:
            self._device = openni2.Device.open_any()
            info = self._device.get_device_info()
            logger.info(
                f"Opened depth camera: {info.name} "
                f"(vendor={info.vendor}, uri={info.uri})")

            self._stream = self._device.create_depth_stream()
            self._stream.start()
            logger.info("Depth stream started")

            # Read first frame to confirm camera is working
            logger.info("Waiting for first depth frame...")
            first_frame_ok = False
            for _ in range(30):  # ~10 s at 30 fps
                if not self._running:
                    break
                try:
                    frame = self._stream.read_frame()
                    if frame is not None:
                        first_frame_ok = True
                        w, h = frame.width, frame.height
                        logger.info(
                            f"First depth frame received: {w}x{h} — camera is streaming")
                        break
                except Exception:
                    time.sleep(0.1)

            if not first_frame_ok:
                logger.error("Never received a valid depth frame")
                self._init_ok = False
                self._init_event.set()
                return

            self._init_ok = True
            self._init_event.set()

            # Main capture loop
            _last_fps_log = time.monotonic()
            _fps_frame_count = 0
            while self._running:
                try:
                    frame = self._stream.read_frame()
                    if frame is None:
                        continue

                    depth_data = self._process_frame(frame)
                    if depth_data is None:
                        continue

                    ts = time.monotonic()
                    _fps_frame_count += 1

                    with self._lock:
                        self._depth_frame = depth_data
                        self._depth_timestamp = ts
                        self._frame_count += 1

                    elapsed = ts - _last_fps_log
                    if elapsed >= 5.0:
                        fps = _fps_frame_count / elapsed
                        logger.info(
                            f"Depth capture: {fps:.1f} fps "
                            f"(total frames: {self._frame_count})")
                        _last_fps_log = ts
                        _fps_frame_count = 0

                    with self._callbacks_lock:
                        callbacks = list(self._callbacks)
                    for cb in callbacks:
                        try:
                            cb(depth_data, ts)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

                except Exception as e:
                    if self._running:
                        logger.warning(f"Frame capture error: {e}")
                    time.sleep(0.01)

        except Exception as e:
            logger.error(f"Failed to initialize depth camera: {e}")
            self._init_ok = False
            self._init_event.set()
            self._running = False
        finally:
            if self._stream:
                try:
                    self._stream.stop()
                except Exception:
                    pass
            if self._device:
                try:
                    self._device.close()
                except Exception:
                    pass
            logger.info("Depth camera resources released")

    def _process_frame(self, frame):
        """Convert an OpenNI2 depth frame to a normalized float32 array."""
        try:
            w, h = frame.width, frame.height
            buf = frame.get_buffer_as_uint16()
            depth_data = np.array(buf, dtype=np.uint16).reshape((h, w))

            # OpenNI2 depth values are in millimeters; 0 means no reading
            depth_float = depth_data.astype(np.float32)

            # Mask for valid depth pixels (non-zero and within range)
            valid = depth_float > 0

            # Normalize valid pixels into [0, 1] based on depth range
            depth_normalized = np.zeros_like(depth_float)
            depth_normalized[valid] = np.clip(
                (depth_float[valid] - self.depth_min_mm)
                / (self.depth_max_mm - self.depth_min_mm),
                0.0, 1.0)

            if self.invert:
                # Only invert valid pixels — background stays at 0
                depth_normalized[valid] = 1.0 - depth_normalized[valid]

            # Flip vertically BEFORE smoothing: OpenNI2 row 0 is at top,
            # OpenGL textures have row 0 at bottom. Must flip before
            # temporal smoothing so prev_depth and current are same orientation.
            depth_normalized = np.ascontiguousarray(depth_normalized[::-1, :])

            if self.temporal_smoothing > 0.0 and self._prev_depth is not None:
                if self._prev_depth.shape == depth_normalized.shape:
                    alpha = self.temporal_smoothing
                    depth_normalized = (alpha * self._prev_depth
                                        + (1.0 - alpha) * depth_normalized)

            self._prev_depth = depth_normalized.copy()

            # Binary threshold: zero out pixels below cutoff for clean silhouette
            if self.threshold_enabled and self.threshold > 0:
                depth_normalized = np.where(
                    depth_normalized >= self.threshold, 1.0, 0.0
                ).astype(np.float32)

            return depth_normalized

        except Exception as e:
            logger.error(f"Depth frame processing error: {e}")
            return None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_depth_range(self, min_mm, max_mm):
        self.depth_min_mm = min_mm
        self.depth_max_mm = max_mm
        logger.info(f"Depth range set to {min_mm}-{max_mm}mm")

    def set_invert(self, invert):
        self.invert = invert
        logger.info(f"Depth invert: {invert}")

    def set_threshold(self, level, enabled=True):
        self.threshold = np.clip(level, 0.0, 1.0)
        self.threshold_enabled = enabled
        logger.info(f"Depth threshold: {self.threshold:.2f} (enabled={enabled})")

    def set_temporal_smoothing(self, smoothing):
        self.temporal_smoothing = np.clip(smoothing, 0.0, 1.0)
        logger.info(f"Temporal smoothing: {self.temporal_smoothing}")

    def resize_for_mask(self, depth_frame, target_size):
        """Resize a depth frame to (target_size, target_size) float32."""
        h, w = depth_frame.shape
        if h == target_size and w == target_size:
            return depth_frame

        try:
            from PIL import Image
            img = Image.fromarray(
                (depth_frame * 255.0).astype(np.uint8), mode='L')
            img = img.resize((target_size, target_size), Image.BILINEAR)
            return np.array(img, dtype=np.float32) / 255.0
        except ImportError:
            min_dim = min(h, w)
            y0 = (h - min_dim) // 2
            x0 = (w - min_dim) // 2
            cropped = depth_frame[y0:y0 + min_dim, x0:x0 + min_dim]
            step = max(1, min_dim // target_size)
            ds = cropped[::step, ::step]
            result = np.zeros((target_size, target_size), dtype=np.float32)
            ch = min(target_size, ds.shape[0])
            cw = min(target_size, ds.shape[1])
            result[:ch, :cw] = ds[:ch, :cw]
            return result

    def __del__(self):
        if self._running:
            self.stop()
