"""
x86_64 depth capture bridge process.

This script runs under Rosetta (x86_64 Python) to interface with the
Orbbec Astra's x86_64-only OpenNI2 driver.  It captures depth frames and
writes them to a shared memory-mapped file so the main arm64 process can
read them without architecture mixing.

Protocol:
  - Shared file layout (header + frame data):
      [0:4]   uint32  frame_counter  (incremented each new frame)
      [4:8]   uint32  width
      [8:12]  uint32  height
      [12:16] float32 reserved
      [16:]   float32[height, width]  normalised depth in [0,1]

  - The bridge writes atomically by updating the counter last.
  - A control file is used for stop signalling.
"""

import mmap
import os
import struct
import sys
import time

import numpy as np

HEADER_SIZE = 16  # 4 uint32s


def run_bridge(redist_path, shm_path, ctrl_path,
               width=640, height=480, fps=30,
               depth_min_mm=500, depth_max_mm=4000,
               invert=True, threshold=0.64):
    from openni import openni2

    openni2.initialize(redist_path)
    print(f"[bridge] OpenNI2 initialized from {redist_path}", flush=True)

    dev = openni2.Device.open_any()
    info = dev.get_device_info()
    print(f"[bridge] Device: {info.name} (vendor={info.vendor})", flush=True)

    stream = dev.create_depth_stream()
    stream.start()
    print("[bridge] Depth stream started", flush=True)

    # Read first frame to get actual dimensions
    frame = stream.read_frame()
    actual_w, actual_h = frame.width, frame.height
    print(f"[bridge] Frame size: {actual_w}x{actual_h}", flush=True)

    # Create shared memory file
    frame_bytes = actual_w * actual_h * 4  # float32
    total_size = HEADER_SIZE + frame_bytes

    with open(shm_path, 'wb') as f:
        f.write(b'\x00' * total_size)

    fd = os.open(shm_path, os.O_RDWR)
    mm = mmap.mmap(fd, total_size)

    # Write initial header (counter=0, width, height)
    struct.pack_into('III', mm, 0, 0, actual_w, actual_h)
    mm.flush()

    counter = 0
    prev_depth = None
    temporal_smoothing = 0.3
    print("[bridge] Capturing...", flush=True)

    try:
        while True:
            # Check control file for stop signal
            if os.path.exists(ctrl_path):
                try:
                    with open(ctrl_path, 'r') as f:
                        if f.read().strip() == 'stop':
                            print("[bridge] Stop signal received", flush=True)
                            break
                except Exception:
                    pass

            try:
                frame = stream.read_frame()
                if frame is None:
                    continue

                buf = frame.get_buffer_as_uint16()
                depth_data = np.array(buf, dtype=np.uint16).reshape(
                    (frame.height, frame.width))

                depth_float = depth_data.astype(np.float32)
                valid = depth_float > 0

                depth_norm = np.zeros_like(depth_float)
                depth_norm[valid] = np.clip(
                    (depth_float[valid] - depth_min_mm)
                    / (depth_max_mm - depth_min_mm),
                    0.0, 1.0)

                if invert:
                    depth_norm[valid] = 1.0 - depth_norm[valid]

                # Flip vertically (OpenNI2 row 0 = top, OpenGL row 0 = bottom)
                depth_norm = np.ascontiguousarray(depth_norm[::-1, :])

                # Temporal smoothing
                if temporal_smoothing > 0.0 and prev_depth is not None:
                    if prev_depth.shape == depth_norm.shape:
                        alpha = temporal_smoothing
                        depth_norm = (alpha * prev_depth
                                      + (1.0 - alpha) * depth_norm)
                prev_depth = depth_norm.copy()

                # Binary threshold
                if threshold > 0:
                    depth_norm = np.where(
                        depth_norm >= threshold, 1.0, 0.0
                    ).astype(np.float32)

                # Write frame data first, then update counter
                mm[HEADER_SIZE:HEADER_SIZE + frame_bytes] = \
                    depth_norm.tobytes()
                counter += 1
                struct.pack_into('I', mm, 0, counter)
                mm.flush()

            except Exception as e:
                print(f"[bridge] Frame error: {e}", flush=True)
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("[bridge] Interrupted", flush=True)
    finally:
        mm.close()
        os.close(fd)
        stream.stop()
        dev.close()
        openni2.unload()
        print("[bridge] Cleanup done", flush=True)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--redist', required=True, help='OpenNI2 redist path')
    p.add_argument('--shm', required=True, help='Shared memory file path')
    p.add_argument('--ctrl', required=True, help='Control file path')
    p.add_argument('--depth-min', type=int, default=500)
    p.add_argument('--depth-max', type=int, default=4000)
    p.add_argument('--invert', type=int, default=1)
    p.add_argument('--threshold', type=float, default=0.64)
    args = p.parse_args()

    run_bridge(
        args.redist, args.shm, args.ctrl,
        depth_min_mm=args.depth_min,
        depth_max_mm=args.depth_max,
        invert=bool(args.invert),
        threshold=args.threshold,
    )
