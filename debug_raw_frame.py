"""
Raw frame dumper - bypasses DepthCameraManager to inspect raw OrbbecSDK frame data.
Saves the first valid frame as a numpy file for inspection.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from penrose_tools.orbbec_native import OrbbecDepthCamera

print("Opening camera...")
cam = OrbbecDepthCamera(width=640, height=480, fps=30)
cam.open()
print(f"Camera opened: {cam.actual_width}x{cam.actual_height}")

# Grab a few frames to let the camera settle
for i in range(10):
    result = cam.read_depth_frame(timeout_ms=500)
    if result is not None:
        arr, w, h, scale = result
        print(f"Frame {i}: {w}x{h}, scale={scale}, "
              f"min={arr.min()}, max={arr.max()}, "
              f"nonzero={np.count_nonzero(arr)}/{arr.size}")

# Now grab a frame and analyze it thoroughly
print("\n--- Detailed frame analysis ---")
result = cam.read_depth_frame(timeout_ms=1000)
if result is None:
    print("ERROR: No frame received")
    cam.close()
    sys.exit(1)

arr, w, h, scale = result
print(f"Shape: {arr.shape}, dtype: {arr.dtype}")
print(f"Min: {arr.min()}, Max: {arr.max()}, Mean: {arr.mean():.1f}")
print(f"Nonzero: {np.count_nonzero(arr)}/{arr.size} ({100*np.count_nonzero(arr)/arr.size:.1f}%)")
print(f"Scale: {scale}")

# Check for column patterns
print(f"\n--- Column analysis ---")
for stride in [2, 3, 4]:
    for offset in range(stride):
        cols = arr[:, offset::stride]
        nz = np.count_nonzero(cols)
        mean_nz = np.mean(cols[cols > 0]) if nz > 0 else 0
        print(f"  stride={stride} offset={offset}: mean_nonzero={mean_nz:.1f}, "
              f"nonzero={nz}/{cols.size} ({100*nz/cols.size:.1f}%)")

# Check even vs odd columns
even = arr[:, 0::2]
odd = arr[:, 1::2]
print(f"\nEven cols: mean={even.mean():.1f}, nonzero={np.count_nonzero(even)}")
print(f"Odd cols:  mean={odd.mean():.1f}, nonzero={np.count_nonzero(odd)}")
print(f"Even==Odd: {np.mean(even == odd):.1%}")

# Check left half vs right half
left = arr[:, :w//2]
right = arr[:, w//2:]
print(f"\nLeft half:  mean={left.mean():.1f}, nonzero={np.count_nonzero(left)}")
print(f"Right half: mean={right.mean():.1f}, nonzero={np.count_nonzero(right)}")
print(f"Left==Right: {np.mean(left == right):.1%}")
print(f"Left==flip(Right): {np.mean(left == right[:, ::-1]):.1%}")

# Print sample rows
mid = h // 2
print(f"\nSample row {mid}:")
print(f"  cols 0-19:  {arr[mid, :20].tolist()}")
print(f"  cols {w//2}-{w//2+19}: {arr[mid, w//2:w//2+20].tolist()}")

# Check row patterns
print(f"\n--- Row analysis ---")
even_rows = arr[0::2, :]
odd_rows = arr[1::2, :]
print(f"Even rows: mean={even_rows.mean():.1f}")
print(f"Odd rows:  mean={odd_rows.mean():.1f}")
print(f"Even==Odd rows: {np.mean(even_rows == odd_rows):.1%}")

# Save for manual inspection
np.save('/tmp/orbbec_raw_frame.npy', arr)
print(f"\nRaw frame saved to /tmp/orbbec_raw_frame.npy")

cam.close()
print("Done.")
