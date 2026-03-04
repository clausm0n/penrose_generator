"""
Background-threaded webcam capture using OpenCV.
Provides thread-safe access to the latest captured frame.
Optional module -- gracefully unavailable if cv2 is not installed.
"""

import logging
import threading
import time

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False

import numpy as np

logger = logging.getLogger('CameraManager')


class CameraManager:
    """
    Captures frames from a webcam on a daemon background thread.
    Thread-safe: the latest frame is guarded by a lock.
    """

    def __init__(self, camera_index=0, width=640, height=480, fps=30):
        if not OPENCV_AVAILABLE:
            logger.warning("OpenCV not available -- CameraManager disabled")

        self._camera_index = camera_index
        self._requested_width = width
        self._requested_height = height
        self._requested_fps = fps

        self._thread = None
        self._running = False
        self._lock = threading.Lock()

        self._frame = None
        self._frame_timestamp = 0.0
        self._frame_count = 0

        self._callbacks = []
        self._callbacks_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the capture thread. No-op if already running or OpenCV missing."""
        if not OPENCV_AVAILABLE:
            logger.warning("Cannot start -- OpenCV not installed")
            return False

        if self._running:
            return True

        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="CameraManager",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"Started capture thread (camera={self._camera_index}, "
            f"{self._requested_width}x{self._requested_height}@{self._requested_fps}fps)"
        )
        return True

    def stop(self):
        """Signal the capture thread to stop and wait for it to finish."""
        if not self._running:
            return
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        logger.info("Capture thread stopped")

    @property
    def is_running(self):
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def is_available(self):
        """True if OpenCV is installed (camera may still fail to open)."""
        return OPENCV_AVAILABLE

    # ------------------------------------------------------------------
    # Frame access (thread-safe)
    # ------------------------------------------------------------------

    def get_frame(self):
        """Return (frame_copy, timestamp) or (None, 0.0)."""
        with self._lock:
            if self._frame is not None:
                return self._frame.copy(), self._frame_timestamp
            return None, 0.0

    def get_frame_no_copy(self):
        """Return latest frame WITHOUT copying -- caller must not mutate it."""
        with self._lock:
            return self._frame, self._frame_timestamp

    @property
    def frame_count(self):
        return self._frame_count

    # ------------------------------------------------------------------
    # Callback system
    # ------------------------------------------------------------------

    def add_callback(self, fn):
        """Register a callback: fn(frame, timestamp). Runs on capture thread."""
        with self._callbacks_lock:
            self._callbacks.append(fn)

    def remove_callback(self, fn):
        """Unregister a previously added callback."""
        with self._callbacks_lock:
            self._callbacks = [cb for cb in self._callbacks if cb is not fn]

    # ------------------------------------------------------------------
    # Capture loop (runs on background thread)
    # ------------------------------------------------------------------

    def _capture_loop(self):
        cap = cv2.VideoCapture(self._camera_index)

        if not cap.isOpened():
            logger.error(f"Failed to open camera {self._camera_index}")
            self._running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._requested_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._requested_height)
        cap.set(cv2.CAP_PROP_FPS, self._requested_fps)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        logger.info(f"Camera opened: {actual_w}x{actual_h}@{actual_fps:.1f}fps")

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Frame read failed, retrying...")
                    time.sleep(0.1)
                    continue

                ts = time.monotonic()

                with self._lock:
                    self._frame = frame
                    self._frame_timestamp = ts
                    self._frame_count += 1

                with self._callbacks_lock:
                    callbacks = list(self._callbacks)
                for cb in callbacks:
                    try:
                        cb(frame, ts)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
        finally:
            cap.release()
            logger.info("Camera released")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_grayscale(self):
        """Return latest frame as float32 grayscale in [0, 1].
        Returns (grayscale_array, timestamp) or (None, 0.0)."""
        frame, ts = self.get_frame_no_copy()
        if frame is None:
            return None, 0.0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        return gray, ts
