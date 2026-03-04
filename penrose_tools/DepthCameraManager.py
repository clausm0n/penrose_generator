"""
Background-threaded Orbbec depth camera capture using OpenNI2.
Provides thread-safe access to the latest depth frame.
Optional module -- gracefully unavailable if OpenNI2 is not installed.
"""

import logging
import os
import threading
import time

import numpy as np

# Path to the minimal OpenNI2 runtime bundled with the project.
# Contains OpenNI2.dll and the Orbbec driver in OpenNI2/Drivers/.
_OPENNI2_REDIST = os.path.join(
    os.path.dirname(__file__), 'openni2_runtime')

try:
    from openni import openni2
    openni2.initialize(_OPENNI2_REDIST)
    OPENNI2_AVAILABLE = True
except Exception:
    openni2 = None
    OPENNI2_AVAILABLE = False

logger = logging.getLogger('DepthCameraManager')

# Legacy alias so penrose_generator.py import check still works
DEPTH_CAMERA_AVAILABLE = OPENNI2_AVAILABLE


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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, timeout=10.0):
        """Start the capture thread and wait for the depth stream to produce
        its first frame.  Returns True on success."""
        if not OPENNI2_AVAILABLE:
            logger.warning("Cannot start -- OpenNI2 not available")
            return False

        if self._running:
            return True

        self._init_event.clear()
        self._init_ok = False
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="DepthCameraManager",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"Started depth capture thread "
            f"({self._requested_width}x{self._requested_height}@{self._requested_fps}fps)")

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
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        logger.info("Depth capture thread stopped")

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
    # Capture loop (runs on background thread)
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
