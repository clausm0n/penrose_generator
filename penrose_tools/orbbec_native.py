"""
Native Python ctypes wrapper for the OrbbecSDK v1 C API.

Provides direct ARM64-native access to Orbbec Astra depth cameras
on Apple Silicon without requiring Rosetta or OpenNI2.

Only wraps the subset of the API needed for depth frame capture:
  Context → Pipeline → Config → StreamProfile → Frame
"""

import ctypes
import ctypes.util
import logging
import os
import sys

logger = logging.getLogger('OrbbecNative')

# ---------------------------------------------------------------------------
# Library loading
# ---------------------------------------------------------------------------
_SDK_LIB_DIR = os.path.join(os.path.dirname(__file__), 'orbbec_sdk', 'lib')

def _load_sdk():
    """Load the OrbbecSDK shared library and its dependencies."""
    if sys.platform != 'darwin':
        raise OSError("OrbbecSDK native wrapper currently supports macOS only")

    lib_path = os.path.join(_SDK_LIB_DIR, 'libOrbbecSDK.dylib')
    if not os.path.exists(lib_path):
        raise OSError(f"OrbbecSDK library not found at {lib_path}")

    # Load dependencies first so @loader_path resolves correctly
    for dep in ('libob_usb.dylib', 'liblive555.dylib'):
        dep_path = os.path.join(_SDK_LIB_DIR, dep)
        if os.path.exists(dep_path):
            ctypes.cdll.LoadLibrary(dep_path)

    return ctypes.cdll.LoadLibrary(lib_path)


# ---------------------------------------------------------------------------
# Opaque pointer types
# ---------------------------------------------------------------------------
class _Opaque(ctypes.Structure):
    pass

ob_context_p = ctypes.POINTER(_Opaque)
ob_device_p = ctypes.POINTER(_Opaque)
ob_device_list_p = ctypes.POINTER(_Opaque)
ob_device_info_p = ctypes.POINTER(_Opaque)
ob_pipeline_p = ctypes.POINTER(_Opaque)
ob_config_p = ctypes.POINTER(_Opaque)
ob_frame_p = ctypes.POINTER(_Opaque)
ob_stream_profile_p = ctypes.POINTER(_Opaque)
ob_stream_profile_list_p = ctypes.POINTER(_Opaque)
ob_sensor_list_p = ctypes.POINTER(_Opaque)
ob_error_p = ctypes.POINTER(_Opaque)

# Pointer-to-pointer for error out params
ob_error_pp = ctypes.POINTER(ob_error_p)

# ---------------------------------------------------------------------------
# Enum constants (matching ObTypes.h)
# ---------------------------------------------------------------------------
# ob_sensor_type
OB_SENSOR_DEPTH = 3

# ob_stream_type
OB_STREAM_DEPTH = 3

# ob_format
OB_FORMAT_Y16 = 8
OB_FORMAT_Y11 = 11
OB_FORMAT_UNKNOWN = 0xff

# ob_log_severity
OB_LOG_SEVERITY_WARN = 2
OB_LOG_SEVERITY_ERROR = 3
OB_LOG_SEVERITY_OFF = 5

# ob_frame_type
OB_FRAME_DEPTH = 3

# Special matching constants
OB_WIDTH_ANY = 0
OB_HEIGHT_ANY = 0
OB_FPS_ANY = 0
OB_FORMAT_ANY = OB_FORMAT_UNKNOWN
OB_PROFILE_DEFAULT = 0


# ---------------------------------------------------------------------------
# Error handling helper
# ---------------------------------------------------------------------------
def _check_error(err_p):
    """Check an ob_error pointer and raise if non-null."""
    if err_p:
        try:
            msg = _lib.ob_error_message(err_p)
            func = _lib.ob_error_function(err_p)
            text = f"OrbbecSDK error in {func.decode('utf-8', errors='replace')}: " \
                   f"{msg.decode('utf-8', errors='replace')}"
        except Exception:
            text = "OrbbecSDK error (could not read details)"
        finally:
            try:
                _lib.ob_delete_error(err_p)
            except Exception:
                pass
        raise RuntimeError(text)


# ---------------------------------------------------------------------------
# Bind C functions
# ---------------------------------------------------------------------------
_lib = None

def _setup_bindings(lib):
    """Declare argument/return types for all SDK functions we use."""

    # --- Error ---
    lib.ob_error_message.argtypes = [ob_error_p]
    lib.ob_error_message.restype = ctypes.c_char_p
    lib.ob_error_function.argtypes = [ob_error_p]
    lib.ob_error_function.restype = ctypes.c_char_p
    lib.ob_error_args.argtypes = [ob_error_p]
    lib.ob_error_args.restype = ctypes.c_char_p
    lib.ob_delete_error.argtypes = [ob_error_p]
    lib.ob_delete_error.restype = None

    # --- Context ---
    lib.ob_create_context.argtypes = [ob_error_pp]
    lib.ob_create_context.restype = ob_context_p
    lib.ob_delete_context.argtypes = [ob_context_p, ob_error_pp]
    lib.ob_delete_context.restype = None
    lib.ob_set_logger_severity.argtypes = [ctypes.c_int, ob_error_pp]
    lib.ob_set_logger_severity.restype = None
    lib.ob_query_device_list.argtypes = [ob_context_p, ob_error_pp]
    lib.ob_query_device_list.restype = ob_device_list_p

    # --- Device list ---
    lib.ob_device_list_device_count.argtypes = [ob_device_list_p, ob_error_pp]
    lib.ob_device_list_device_count.restype = ctypes.c_uint32
    lib.ob_device_list_get_device.argtypes = [ob_device_list_p, ctypes.c_uint32, ob_error_pp]
    lib.ob_device_list_get_device.restype = ob_device_p
    lib.ob_delete_device_list.argtypes = [ob_device_list_p, ob_error_pp]
    lib.ob_delete_device_list.restype = None

    # --- Device ---
    lib.ob_device_get_device_info.argtypes = [ob_device_p, ob_error_pp]
    lib.ob_device_get_device_info.restype = ob_device_info_p
    lib.ob_delete_device.argtypes = [ob_device_p, ob_error_pp]
    lib.ob_delete_device.restype = None

    # --- Device info ---
    lib.ob_device_info_name.argtypes = [ob_device_info_p, ob_error_pp]
    lib.ob_device_info_name.restype = ctypes.c_char_p
    lib.ob_device_info_serial_number.argtypes = [ob_device_info_p, ob_error_pp]
    lib.ob_device_info_serial_number.restype = ctypes.c_char_p
    lib.ob_device_info_firmware_version.argtypes = [ob_device_info_p, ob_error_pp]
    lib.ob_device_info_firmware_version.restype = ctypes.c_char_p
    lib.ob_device_info_connection_type.argtypes = [ob_device_info_p, ob_error_pp]
    lib.ob_device_info_connection_type.restype = ctypes.c_char_p
    lib.ob_delete_device_info.argtypes = [ob_device_info_p, ob_error_pp]
    lib.ob_delete_device_info.restype = None

    # --- Pipeline ---
    lib.ob_create_pipeline.argtypes = [ob_error_pp]
    lib.ob_create_pipeline.restype = ob_pipeline_p
    lib.ob_create_pipeline_with_device.argtypes = [ob_device_p, ob_error_pp]
    lib.ob_create_pipeline_with_device.restype = ob_pipeline_p
    lib.ob_pipeline_start_with_config.argtypes = [ob_pipeline_p, ob_config_p, ob_error_pp]
    lib.ob_pipeline_start_with_config.restype = None
    lib.ob_pipeline_stop.argtypes = [ob_pipeline_p, ob_error_pp]
    lib.ob_pipeline_stop.restype = None
    lib.ob_pipeline_wait_for_frameset.argtypes = [ob_pipeline_p, ctypes.c_uint32, ob_error_pp]
    lib.ob_pipeline_wait_for_frameset.restype = ob_frame_p
    lib.ob_pipeline_get_stream_profile_list.argtypes = [ob_pipeline_p, ctypes.c_int, ob_error_pp]
    lib.ob_pipeline_get_stream_profile_list.restype = ob_stream_profile_list_p
    lib.ob_delete_pipeline.argtypes = [ob_pipeline_p, ob_error_pp]
    lib.ob_delete_pipeline.restype = None

    # --- Config ---
    lib.ob_create_config.argtypes = [ob_error_pp]
    lib.ob_create_config.restype = ob_config_p
    lib.ob_config_enable_stream.argtypes = [ob_config_p, ob_stream_profile_p, ob_error_pp]
    lib.ob_config_enable_stream.restype = None
    lib.ob_delete_config.argtypes = [ob_config_p, ob_error_pp]
    lib.ob_delete_config.restype = None

    # --- Stream profile list ---
    lib.ob_stream_profile_list_get_video_stream_profile.argtypes = [
        ob_stream_profile_list_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ob_error_pp
    ]
    lib.ob_stream_profile_list_get_video_stream_profile.restype = ob_stream_profile_p
    lib.ob_stream_profile_list_get_profile.argtypes = [ob_stream_profile_list_p, ctypes.c_int, ob_error_pp]
    lib.ob_stream_profile_list_get_profile.restype = ob_stream_profile_p
    lib.ob_stream_profile_list_count.argtypes = [ob_stream_profile_list_p, ob_error_pp]
    lib.ob_stream_profile_list_count.restype = ctypes.c_uint32
    lib.ob_delete_stream_profile_list.argtypes = [ob_stream_profile_list_p, ob_error_pp]
    lib.ob_delete_stream_profile_list.restype = None
    lib.ob_delete_stream_profile.argtypes = [ob_stream_profile_p, ob_error_pp]
    lib.ob_delete_stream_profile.restype = None

    # --- Stream profile info ---
    lib.ob_stream_profile_format.argtypes = [ob_stream_profile_p, ob_error_pp]
    lib.ob_stream_profile_format.restype = ctypes.c_int
    lib.ob_video_stream_profile_width.argtypes = [ob_stream_profile_p, ob_error_pp]
    lib.ob_video_stream_profile_width.restype = ctypes.c_uint32
    lib.ob_video_stream_profile_height.argtypes = [ob_stream_profile_p, ob_error_pp]
    lib.ob_video_stream_profile_height.restype = ctypes.c_uint32
    lib.ob_video_stream_profile_fps.argtypes = [ob_stream_profile_p, ob_error_pp]
    lib.ob_video_stream_profile_fps.restype = ctypes.c_uint32

    # --- Frame ---
    lib.ob_frameset_depth_frame.argtypes = [ob_frame_p, ob_error_pp]
    lib.ob_frameset_depth_frame.restype = ob_frame_p
    lib.ob_frame_data.argtypes = [ob_frame_p, ob_error_pp]
    lib.ob_frame_data.restype = ctypes.c_void_p
    lib.ob_frame_data_size.argtypes = [ob_frame_p, ob_error_pp]
    lib.ob_frame_data_size.restype = ctypes.c_uint32
    lib.ob_video_frame_width.argtypes = [ob_frame_p, ob_error_pp]
    lib.ob_video_frame_width.restype = ctypes.c_uint32
    lib.ob_video_frame_height.argtypes = [ob_frame_p, ob_error_pp]
    lib.ob_video_frame_height.restype = ctypes.c_uint32
    lib.ob_frame_format.argtypes = [ob_frame_p, ob_error_pp]
    lib.ob_frame_format.restype = ctypes.c_int
    lib.ob_frame_index.argtypes = [ob_frame_p, ob_error_pp]
    lib.ob_frame_index.restype = ctypes.c_uint64
    lib.ob_depth_frame_get_value_scale.argtypes = [ob_frame_p, ob_error_pp]
    lib.ob_depth_frame_get_value_scale.restype = ctypes.c_float
    lib.ob_delete_frame.argtypes = [ob_frame_p, ob_error_pp]
    lib.ob_delete_frame.restype = None

    return lib


# ---------------------------------------------------------------------------
# High-level Python API
# ---------------------------------------------------------------------------

class OrbbecDepthCamera:
    """
    High-level wrapper for capturing depth frames from an Orbbec camera
    using the native OrbbecSDK C API via ctypes.
    """

    def __init__(self, width=640, height=480, fps=30):
        self._width = width
        self._height = height
        self._fps = fps
        self._pipeline = None
        self._depth_profile = None
        self._profile_list = None
        self._config = None
        self._actual_width = 0
        self._actual_height = 0
        self._value_scale = 1.0
        self._started = False
        self._first_frame_logged = False

    def open(self):
        """Initialize SDK, find device, configure and start the depth pipeline."""
        global _lib
        if _lib is None:
            _lib = _setup_bindings(_load_sdk())

        err = ob_error_p()

        # Suppress verbose SDK logging
        _lib.ob_set_logger_severity(OB_LOG_SEVERITY_WARN, ctypes.byref(err))
        _check_error(err)

        # Create pipeline (auto-detects first device)
        self._pipeline = _lib.ob_create_pipeline(ctypes.byref(err))
        _check_error(err)
        if not self._pipeline:
            raise RuntimeError("Failed to create pipeline (no device?)")

        # Get depth stream profiles
        self._profile_list = _lib.ob_pipeline_get_stream_profile_list(
            self._pipeline, OB_SENSOR_DEPTH, ctypes.byref(err))
        _check_error(err)

        # Log all available depth profiles
        _fmt_names = {
            0: 'YUYV', 1: 'YUY2', 2: 'UYVY', 3: 'NV12', 4: 'NV21',
            5: 'MJPG', 6: 'H264', 7: 'H265', 8: 'Y16', 9: 'Y8',
            10: 'Y10', 11: 'Y11', 12: 'Y12', 13: 'GRAY', 15: 'I420',
            22: 'RGB', 23: 'BGR', 25: 'BGRA', 28: 'Z16', 31: 'RGBA',
            0xff: 'UNKNOWN',
        }
        count = _lib.ob_stream_profile_list_count(
            self._profile_list, ctypes.byref(err))
        _check_error(err)
        print(f"\n[OrbbecSDK] Available depth profiles: {count}")
        for i in range(count):
            p = _lib.ob_stream_profile_list_get_profile(
                self._profile_list, i, ctypes.byref(err))
            if err:
                _lib.ob_delete_error(err)
                err = ob_error_p()
                continue
            pw = _lib.ob_video_stream_profile_width(p, ctypes.byref(err))
            ph = _lib.ob_video_stream_profile_height(p, ctypes.byref(err))
            pfps = _lib.ob_video_stream_profile_fps(p, ctypes.byref(err))
            pfmt = _lib.ob_stream_profile_format(p, ctypes.byref(err))
            fmt_name = _fmt_names.get(pfmt, f'?({pfmt})')
            print(f"  [{i}] {pw}x{ph} @{pfps}fps fmt={fmt_name}")
            _lib.ob_delete_stream_profile(p, ctypes.byref(err))

        # Try profiles in priority order:
        # 1) Requested WxH, Y16, requested fps
        # 2) Requested WxH, Y16, any fps
        # 3) Requested WxH, Y11, requested fps  (Astra Pro uses Y11)
        # 4) Requested WxH, Y11, any fps
        # 5) Any resolution, Y16, any fps
        # 6) Any resolution, Y11, any fps
        # 7) Requested WxH, ANY format, any fps
        # 8) Default profile
        profile_attempts = [
            (self._width, OB_HEIGHT_ANY, OB_FORMAT_Y16, self._fps,
             f"{self._width}xANY Y16 @{self._fps}"),
            (self._width, OB_HEIGHT_ANY, OB_FORMAT_Y16, OB_FPS_ANY,
             f"{self._width}xANY Y16 @ANY"),
            (self._width, OB_HEIGHT_ANY, OB_FORMAT_Y11, self._fps,
             f"{self._width}xANY Y11 @{self._fps}"),
            (self._width, OB_HEIGHT_ANY, OB_FORMAT_Y11, OB_FPS_ANY,
             f"{self._width}xANY Y11 @ANY"),
            (OB_WIDTH_ANY, OB_HEIGHT_ANY, OB_FORMAT_Y16, OB_FPS_ANY,
             "ANYxANY Y16 @ANY"),
            (OB_WIDTH_ANY, OB_HEIGHT_ANY, OB_FORMAT_Y11, OB_FPS_ANY,
             "ANYxANY Y11 @ANY"),
            (self._width, OB_HEIGHT_ANY, OB_FORMAT_ANY, OB_FPS_ANY,
             f"{self._width}xANY ANY @ANY"),
        ]

        self._depth_profile = None
        for w_req, h_req, fmt, fps_req, desc in profile_attempts:
            err2 = ob_error_p()
            profile = _lib.ob_stream_profile_list_get_video_stream_profile(
                self._profile_list, w_req, h_req, fmt, fps_req,
                ctypes.byref(err2))
            if err2:
                _lib.ob_delete_error(err2)
                print(f"[OrbbecSDK] Profile {desc} not available")
                continue
            if profile:
                self._depth_profile = profile
                print(f"[OrbbecSDK] Matched profile: {desc}")
                break

        if not self._depth_profile:
            # Last resort: default profile (may not be Y16)
            err2 = ob_error_p()
            self._depth_profile = _lib.ob_stream_profile_list_get_profile(
                self._profile_list, OB_PROFILE_DEFAULT, ctypes.byref(err2))
            _check_error(err2)
            print("[OrbbecSDK] Using default depth profile (Y16 not available)")

        # Read actual profile dimensions and format
        self._actual_width = _lib.ob_video_stream_profile_width(
            self._depth_profile, ctypes.byref(err))
        _check_error(err)
        self._actual_height = _lib.ob_video_stream_profile_height(
            self._depth_profile, ctypes.byref(err))
        _check_error(err)
        actual_fps = _lib.ob_video_stream_profile_fps(
            self._depth_profile, ctypes.byref(err))
        _check_error(err)
        actual_fmt = _lib.ob_stream_profile_format(
            self._depth_profile, ctypes.byref(err))
        _check_error(err)
        fmt_name = _fmt_names.get(actual_fmt, f'?({actual_fmt})')

        print(f"[OrbbecSDK] Selected: {self._actual_width}x{self._actual_height} "
              f"@{actual_fps}fps fmt={fmt_name}({actual_fmt})")
        logger.info(f"Depth profile: {self._actual_width}x{self._actual_height}@{actual_fps}fps fmt={fmt_name}")

        # Y11/Y12 on Astra Pro packs depth+IR side by side in one frame
        # The left half is depth, right half is IR - always extract left half
        self._y11_interleaved = actual_fmt in (11, 12)  # Y11 or Y12
        self._col_doubled = False   # Will be auto-detected on first frame
        self._row_doubled = False   # Will be auto-detected on first frame
        if self._y11_interleaved:
            print(f"[OrbbecSDK] Y11/Y12 format: will extract left half (depth only)")

        # Create config and enable depth stream
        self._config = _lib.ob_create_config(ctypes.byref(err))
        _check_error(err)
        _lib.ob_config_enable_stream(self._config, self._depth_profile, ctypes.byref(err))
        _check_error(err)

        # Start pipeline
        _lib.ob_pipeline_start_with_config(self._pipeline, self._config, ctypes.byref(err))
        _check_error(err)

        self._started = True
        logger.info("OrbbecSDK depth pipeline started (native)")

    def read_depth_frame(self, timeout_ms=100):
        """
        Wait for and return a single depth frame.

        Returns:
            tuple: (data_ptr, width, height, value_scale) or None if timeout.
                   data_ptr is a ctypes void pointer to uint16 pixel data.
                   Pixel value * value_scale = distance in mm.
        """
        if not self._started:
            return None

        err = ob_error_p()
        frameset = _lib.ob_pipeline_wait_for_frameset(
            self._pipeline, timeout_ms, ctypes.byref(err))
        _check_error(err)

        if not frameset:
            return None

        try:
            depth_frame = _lib.ob_frameset_depth_frame(frameset, ctypes.byref(err))
            _check_error(err)

            if not depth_frame:
                return None

            try:
                w = _lib.ob_video_frame_width(depth_frame, ctypes.byref(err))
                _check_error(err)
                h = _lib.ob_video_frame_height(depth_frame, ctypes.byref(err))
                _check_error(err)
                scale = _lib.ob_depth_frame_get_value_scale(depth_frame, ctypes.byref(err))
                _check_error(err)

                data_ptr = _lib.ob_frame_data(depth_frame, ctypes.byref(err))
                _check_error(err)
                data_size = _lib.ob_frame_data_size(depth_frame, ctypes.byref(err))
                _check_error(err)

                if not data_ptr or data_size == 0:
                    return None

                # Copy the data out before we release the frame
                import numpy as np

                # Get actual frame format
                fmt = _lib.ob_frame_format(depth_frame, ctypes.byref(err))
                _check_error(err)

                expected_y16 = w * h * 2
                if data_size != expected_y16:
                    print(
                        f"[OrbbecSDK] Frame data_size={data_size} vs expected Y16 "
                        f"{w}x{h}x2={expected_y16}, format={fmt}")

                # Copy raw bytes
                buf = (ctypes.c_uint8 * data_size).from_address(data_ptr)
                raw = np.frombuffer(buf, dtype=np.uint8).copy()

                # Handle different pixel formats
                if fmt == 8:  # OB_FORMAT_Y16
                    arr = raw.view(np.uint16).reshape((h, w))
                elif fmt == 11:  # OB_FORMAT_Y11 - SDK typically delivers as uint16
                    arr = raw.view(np.uint16).reshape((h, w))
                elif fmt == 28:  # OB_FORMAT_Z16
                    arr = raw.view(np.uint16).reshape((h, w))
                elif fmt == 0:  # OB_FORMAT_YUYV - 4 bytes per 2 pixels
                    # Extract just the Y (luminance) channel as depth proxy
                    # YUYV: [Y0, U, Y1, V, Y0, U, Y1, V, ...]
                    # Each pair of pixels = 4 bytes
                    n_pixels = w * h
                    if data_size >= n_pixels * 2:
                        yuyv = raw[:n_pixels * 2]
                        # Take every other byte (Y values)
                        y_vals = yuyv[0::2]
                        arr = y_vals.astype(np.uint16).reshape((h, w))
                    else:
                        arr = raw.view(np.uint16).reshape((h, w))
                else:
                    # Fallback: try to interpret as uint16
                    if data_size == expected_y16:
                        arr = raw.view(np.uint16).reshape((h, w))
                    elif data_size == w * h:
                        # 8-bit format
                        arr = raw.reshape((h, w)).astype(np.uint16)
                    else:
                        # Unknown format, try best guess
                        n_pixels_from_data = data_size // 2
                        if n_pixels_from_data > 0:
                            # Infer dimensions from data size
                            arr = raw.view(np.uint16)[:w * h].reshape((h, w)) if data_size >= expected_y16 else None
                            if arr is None:
                                print(f"[OrbbecSDK] Cannot handle format {fmt}, data_size={data_size}")
                                return None
                        else:
                            return None

                is_first = not self._first_frame_logged

                if is_first:
                    print(f"[OrbbecSDK] First frame: {w}x{h}, fmt={fmt}, "
                          f"scale={scale}, range=[{arr.min()}, {arr.max()}], "
                          f"y11_split={self._y11_interleaved}")

                # Y11/Y12: auto-detect repeating pattern on first frame
                if self._y11_interleaved and is_first:
                    # Find the column repeat factor by checking if
                    # slicing by stride N gives columns that match
                    mid_row = arr[h // 2, :]
                    best_stride = 1
                    for stride in (2, 3, 4):
                        if w % stride != 0:
                            continue
                        # Check if col[i] == col[i + w//stride] for all i
                        chunk = w // stride
                        matches = []
                        for s in range(1, stride):
                            m = np.mean(arr[:, :chunk] == arr[:, chunk*s:chunk*(s+1)])
                            matches.append(m)
                        avg_match = np.mean(matches)
                        print(f"[OrbbecSDK] Stride {stride}: "
                              f"chunk={chunk}, match={avg_match:.1%}")
                        if avg_match > 0.8:
                            best_stride = stride

                    self._dedup_stride = best_stride
                    if best_stride > 1:
                        out_w = w // best_stride
                        print(f"[OrbbecSDK] Detected {best_stride}x column "
                              f"repeat - extracting {out_w}x{h}")
                    else:
                        print(f"[OrbbecSDK] No column repeat detected, "
                              f"using full {w}x{h}")

                    # Also check row repeat
                    best_row_stride = 1
                    for stride in (2, 3, 4):
                        if h % stride != 0:
                            continue
                        chunk = h // stride
                        matches = []
                        for s in range(1, stride):
                            m = np.mean(arr[:chunk, :] == arr[chunk*s:chunk*(s+1), :])
                            matches.append(m)
                        avg_match = np.mean(matches)
                        print(f"[OrbbecSDK] Row stride {stride}: "
                              f"chunk={chunk}, match={avg_match:.1%}")
                        if avg_match > 0.8:
                            best_row_stride = stride

                    self._dedup_row_stride = best_row_stride
                    if best_row_stride > 1:
                        out_h = h // best_row_stride
                        print(f"[OrbbecSDK] Detected {best_row_stride}x row "
                              f"repeat - extracting {w}x{out_h}")

                # Apply deduplication
                col_stride = getattr(self, '_dedup_stride', 1)
                if col_stride > 1:
                    arr = arr[:, :w // col_stride]
                    w = arr.shape[1]

                row_stride = getattr(self, '_dedup_row_stride', 1)
                if row_stride > 1:
                    arr = arr[:h // row_stride, :]
                    h = arr.shape[0]

                if is_first:
                    self._first_frame_logged = True
                    print(f"[OrbbecSDK] Final output: {w}x{h}")

                return arr, w, h, scale

            finally:
                _lib.ob_delete_frame(depth_frame, ctypes.byref(err))

        finally:
            _lib.ob_delete_frame(frameset, ctypes.byref(err))

    @property
    def actual_width(self):
        return self._actual_width

    @property
    def actual_height(self):
        return self._actual_height

    def close(self):
        """Stop pipeline and release all resources."""
        if not _lib:
            return

        err = ob_error_p()

        if self._started:
            try:
                _lib.ob_pipeline_stop(self._pipeline, ctypes.byref(err))
            except Exception:
                pass
            self._started = False

        if self._depth_profile:
            try:
                _lib.ob_delete_stream_profile(self._depth_profile, ctypes.byref(err))
            except Exception:
                pass
            self._depth_profile = None

        if self._profile_list:
            try:
                _lib.ob_delete_stream_profile_list(self._profile_list, ctypes.byref(err))
            except Exception:
                pass
            self._profile_list = None

        if self._config:
            try:
                _lib.ob_delete_config(self._config, ctypes.byref(err))
            except Exception:
                pass
            self._config = None

        if self._pipeline:
            try:
                _lib.ob_delete_pipeline(self._pipeline, ctypes.byref(err))
            except Exception:
                pass
            self._pipeline = None

        logger.info("OrbbecSDK resources released")

    def __del__(self):
        self.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()


# ---------------------------------------------------------------------------
# Module-level availability check
# ---------------------------------------------------------------------------
ORBBEC_NATIVE_AVAILABLE = False
try:
    _lib = _setup_bindings(_load_sdk())
    ORBBEC_NATIVE_AVAILABLE = True
    logger.info("OrbbecSDK native library loaded successfully")
except Exception as e:
    logger.debug(f"OrbbecSDK native library not available: {e}")
