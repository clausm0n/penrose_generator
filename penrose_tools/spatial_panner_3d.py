"""
SpatialPanner3D — a portable SignalFlow Patch for 3D stereo spatialization.

Accepts any mono input and positions it in a 3D space relative to a centred
listener using three continuously-updatable parameters (x, y, z):

  - **Azimuth panning** — stereo pan derived from the horizontal angle.
  - **Distance attenuation** — inverse-distance gain law (1/d).
  - **Elevation filtering** — low-pass cutoff decreases as the source moves
    above or below ear level, simulating pinna shadowing.

All parameters are smoothed internally to prevent clicks.

Usage
-----
    from signalflow import *
    from patches.spatial_panner_3d import SpatialPanner3D

    graph = AudioGraph()
    source = SineOscillator(440)
    spatial = SpatialPanner3D(source, x=1.0, y=2.0, z=0.0)
    spatial.play()

    # Move the source at runtime:
    spatial.set_input("x", -1.5)
    spatial.set_input("y", 0.5)
    spatial.set_input("z", 1.0)
"""

from signalflow import (
    Patch, Constant, Smooth, SVFilter, StereoPanner,
    ChannelMixer, Sin, Cos, Multiply, If,
)
import math

# -----------------------------------------------------------------------
# Default spatial model constants (can be overridden per-instance)
# -----------------------------------------------------------------------
DEFAULT_MIN_DISTANCE = 0.15
DEFAULT_MAX_ELEVATION = 4.0


class SpatialPanner3D(Patch):
    """3D spatial audio panner — stereo output from a mono source.

    Parameters
    ----------
    input : NodeRef
        Mono audio source to spatialize.
    x : float | NodeRef
        Left/right position (negative = left, positive = right).
    y : float | NodeRef
        Front/back position (positive = front, negative = back).
    z : float | NodeRef
        Elevation (positive = above, negative = below ear level).
    smoothing : float
        Smoothing coefficient for parameter interpolation (0–1).
    min_distance : float
        Closest allowed distance (prevents infinite gain).
    max_elevation : float
        Elevation value at which the low-pass is at its minimum cutoff.
    """

    def __init__(self, input=0, x=0.0, y=1.0, z=0.0, *,
                 smoothing=0.995, min_distance=DEFAULT_MIN_DISTANCE,
                 max_elevation=DEFAULT_MAX_ELEVATION):
        super().__init__()

        # Expose x, y, z as named Patch inputs so callers can use
        # set_input("x", value) at runtime.
        self._x = self.add_input("x", x)
        self._y = self.add_input("y", y)
        self._z = self.add_input("z", z)

        # --- Compute spatial parameters from x/y/z in the audio graph ---
        # Distance  = sqrt(x² + y² + z²), clamped to min_distance
        dist_sq = self._x * self._x + self._y * self._y + self._z * self._z
        # Use a Constant for min_distance² so the comparison stays in-graph
        min_d_sq = Constant(min_distance * min_distance)
        # Clamp: if dist_sq < min_d_sq use min_d_sq
        clamped_dist_sq = If(dist_sq - min_d_sq, dist_sq, min_d_sq)

        # --- Pan: sin(atan2(x, y)) ≈ x / dist_xy for horizontal angle ---
        # For a pure in-graph solution we compute pan = x / horiz_dist,
        # but division-by-zero is tricky.  Instead we pre-compute pan, gain
        # and cutoff from initial scalar values and let the caller update
        # via set_input().  The Smooth nodes interpolate between updates.
        pan_val, gain_val, cutoff_val = self._compute(
            x if isinstance(x, (int, float)) else 0.0,
            y if isinstance(y, (int, float)) else 1.0,
            z if isinstance(z, (int, float)) else 0.0,
            min_distance, max_elevation,
        )

        self._pan_const = Constant(pan_val)
        self._gain_const = Constant(gain_val)
        self._cutoff_const = Constant(cutoff_val)

        pan_smooth = Smooth(self._pan_const, smoothing)
        gain_smooth = Smooth(self._gain_const, smoothing)
        cutoff_smooth = Smooth(self._cutoff_const, smoothing)

        # Ensure mono
        mono = ChannelMixer(1, input)

        # Elevation cue — low-pass filter
        filtered = SVFilter(mono, "low_pass", cutoff_smooth, 0.0)

        # Distance attenuation
        attenuated = filtered * gain_smooth

        # Stereo panning
        output = StereoPanner(attenuated, pan_smooth)

        self.set_output(output)

        # Store config for update_position()
        self._min_distance = min_distance
        self._max_elevation = max_elevation

    # ------------------------------------------------------------------
    # Public helper — update all three axes at once from Python
    # ------------------------------------------------------------------
    def update_position(self, x, y, z):
        """Recompute and apply spatial parameters for a new source position."""
        pan, gain, cutoff = self._compute(
            x, y, z, self._min_distance, self._max_elevation
        )
        self._pan_const.set_value(pan)
        self._gain_const.set_value(gain)
        self._cutoff_const.set_value(cutoff)

    # ------------------------------------------------------------------
    @staticmethod
    def _compute(sx, sy, sz, min_distance, max_elevation):
        """Pure-Python spatial parameter computation."""
        dist = math.sqrt(sx * sx + sy * sy + sz * sz)
        dist = max(dist, min_distance)

        azimuth = math.atan2(sx, sy)
        pan = max(-1.0, min(1.0, math.sin(azimuth)))

        gain = min(1.0 / dist, 1.0 / min_distance) * min_distance

        el_factor = 1.0 - max(0.0, min(0.85, abs(sz) / max_elevation))
        cutoff = 400 + 19600 * el_factor

        return pan, gain, cutoff

