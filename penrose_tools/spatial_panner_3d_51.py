"""
SpatialPanner3D_51 — a portable SignalFlow Patch for 5.1 surround spatialization.

Outputs **6 channels** in SMPTE/ITU order:

    0 – Front Left   (L)    -30°
    1 – Front Right   (R)   +30°
    2 – Centre        (C)     0°
    3 – LFE                  (omnidirectional, ≤120 Hz)
    4 – Surround Left (LS)  -110°
    5 – Surround Right(RS)  +110°

Speaker angles follow **ITU-R BS.775-1**.

Panning algorithm
-----------------
A 2-D **pair-wise VBAP** (Vector-Base Amplitude Panning) is used for the five
main speakers.  The horizontal plane is divided into five sectors by adjacent
speaker pairs.  For a given source azimuth the two speakers that bound the
sector receive sine-law gains; all others are silent.

Additionally:
  - **Distance attenuation** — inverse-distance gain (1/d), normalised.
  - **Elevation filtering**  — LPF cutoff decreases with |z|.
  - **LFE channel**          — always receives a 120 Hz low-passed copy of the
    source, attenuated by distance only (no directional component).

All per-channel gains are smoothed to prevent clicks.

Usage
-----
    from signalflow import *
    from patches.spatial_panner_3d_51 import SpatialPanner3D_51

    graph = AudioGraph()
    source = SineOscillator(440)
    spatial = SpatialPanner3D_51(source, x=1.0, y=2.0, z=0.0)
    spatial.play()

    # Move the source at runtime:
    spatial.update_position(-1.5, 0.5, 1.0)
"""

from signalflow import (
    Patch, Constant, Smooth, SVFilter, ChannelArray, ChannelMixer,
)
import math

# -----------------------------------------------------------------------
# ITU-R BS.775 speaker angles (degrees, 0 = front, positive = right)
# -----------------------------------------------------------------------
SPEAKER_ANGLES_DEG = {
    "L":  -30,
    "R":   30,
    "C":    0,
    "LS": -110,
    "RS":  110,
}

# Ordered list matching output channel index (SMPTE order)
SPEAKER_ORDER = ["L", "R", "C", "LS", "RS"]  # LFE handled separately

# Convert to radians
_SPEAKER_RAD = {k: math.radians(v) for k, v in SPEAKER_ANGLES_DEG.items()}

# Build sorted ring of speakers by angle for sector lookup
_RING = sorted(SPEAKER_ORDER, key=lambda s: _SPEAKER_RAD[s])  # ascending angle

# Default constants
DEFAULT_MIN_DISTANCE = 0.15
DEFAULT_MAX_ELEVATION = 4.0
LFE_CUTOFF_HZ = 120.0
LFE_GAIN = 0.5  # LFE is typically attenuated relative to mains


# -----------------------------------------------------------------------
# VBAP gain computation (2-D pair-wise)
# -----------------------------------------------------------------------
def _normalise_angle(a):
    """Wrap angle to (-π, π]."""
    while a > math.pi:
        a -= 2 * math.pi
    while a <= -math.pi:
        a += 2 * math.pi
    return a


def _angle_between(a, b):
    """Signed shortest arc from a to b in (-π, π]."""
    return _normalise_angle(b - a)


def _vbap_gains(azimuth_rad):
    """Return dict {speaker_name: gain} using pair-wise VBAP on the ring.

    Speakers are sorted by angle.  Adjacent pairs form sectors.  The pair
    whose sector contains *azimuth_rad* receives sine-law gains; all
    others get 0.
    """
    gains = {s: 0.0 for s in SPEAKER_ORDER}
    n = len(_RING)
    az = _normalise_angle(azimuth_rad)

    for i in range(n):
        s1 = _RING[i]
        s2 = _RING[(i + 1) % n]
        a1 = _SPEAKER_RAD[s1]
        a2 = _SPEAKER_RAD[s2]

        span = _angle_between(a1, a2)
        if span <= 0:
            span += 2 * math.pi  # ensure positive arc

        offset = _angle_between(a1, az)
        if offset < 0:
            offset += 2 * math.pi

        if offset <= span + 1e-9:
            # Source is in this sector
            if abs(span) < 1e-12:
                gains[s1] = 1.0
            else:
                g2 = math.sin(offset) / math.sin(span) if abs(math.sin(span)) > 1e-12 else 0.5
                g1 = math.sin(span - offset) / math.sin(span) if abs(math.sin(span)) > 1e-12 else 0.5
                # Clamp to [0, 1]
                g1 = max(0.0, min(1.0, g1))
                g2 = max(0.0, min(1.0, g2))
                # Power-normalise (constant-power panning)
                norm = math.sqrt(g1 * g1 + g2 * g2) or 1.0
                g1 /= norm
                g2 /= norm
                gains[s1] = g1
                gains[s2] = g2
            break

    return gains


class SpatialPanner3D_51(Patch):
    """5.1 surround spatial panner — 6-channel output from a mono source.

    Parameters
    ----------
    input : NodeRef
        Mono audio source to spatialize.
    x, y, z : float
        Source position in metres (x = left/right, y = front/back, z = up/down).
    smoothing : float
        Smoothing coefficient for gain interpolation (0–1).
    min_distance : float
        Closest allowed distance (prevents infinite gain).
    max_elevation : float
        Elevation at which the LPF reaches minimum cutoff.
    """

    # Channel index constants (SMPTE order)
    CH_L, CH_R, CH_C, CH_LFE, CH_LS, CH_RS = range(6)
    _SPEAKER_TO_CH = {"L": 0, "R": 1, "C": 2, "LS": 4, "RS": 5}

    def __init__(self, input=0, x=0.0, y=1.0, z=0.0, *,
                 smoothing=0.995, min_distance=DEFAULT_MIN_DISTANCE,
                 max_elevation=DEFAULT_MAX_ELEVATION):
        super().__init__()

        self._x = self.add_input("x", x)
        self._y = self.add_input("y", y)
        self._z = self.add_input("z", z)

        # Ensure mono
        mono = ChannelMixer(1, input)

        # --- Compute initial spatial parameters ---
        x0 = x if isinstance(x, (int, float)) else 0.0
        y0 = y if isinstance(y, (int, float)) else 1.0
        z0 = z if isinstance(z, (int, float)) else 0.0

        dist_gain, cutoff, spk_gains = self._compute(
            x0, y0, z0, min_distance, max_elevation
        )

        # --- Elevation cue: global LPF ---
        self._cutoff_const = Constant(cutoff)
        cutoff_smooth = Smooth(self._cutoff_const, smoothing)
        filtered = SVFilter(mono, "low_pass", cutoff_smooth, 0.0)

        # --- Per-speaker gain Constant nodes ---
        self._spk_consts = {}
        speaker_channels = []
        for spk in ["L", "R", "C", "LS", "RS"]:
            c = Constant(spk_gains[spk] * dist_gain)
            self._spk_consts[spk] = c
            speaker_channels.append(filtered * Smooth(c, smoothing))

        # --- LFE channel: 120 Hz LPF, distance-only gain ---
        self._lfe_gain_const = Constant(dist_gain * LFE_GAIN)
        lfe_filtered = SVFilter(mono, "low_pass", LFE_CUTOFF_HZ, 0.0)
        lfe_channel = lfe_filtered * Smooth(self._lfe_gain_const, smoothing)

        # --- Assemble 6-channel output (L, R, C, LFE, LS, RS) ---
        output = ChannelArray([
            speaker_channels[0],  # L
            speaker_channels[1],  # R
            speaker_channels[2],  # C
            lfe_channel,          # LFE
            speaker_channels[3],  # LS
            speaker_channels[4],  # RS
        ])

        self.set_output(output)

        self._min_distance = min_distance
        self._max_elevation = max_elevation

    # ------------------------------------------------------------------
    def update_position(self, x, y, z):
        """Recompute and apply all spatial parameters for a new position."""
        dist_gain, cutoff, spk_gains = self._compute(
            x, y, z, self._min_distance, self._max_elevation
        )
        self._cutoff_const.set_value(cutoff)
        for spk, c in self._spk_consts.items():
            c.set_value(spk_gains[spk] * dist_gain)
        self._lfe_gain_const.set_value(dist_gain * LFE_GAIN)

    # ------------------------------------------------------------------
    @staticmethod
    def _compute(sx, sy, sz, min_distance, max_elevation):
        """Return (distance_gain, lpf_cutoff, {speaker: vbap_gain})."""
        dist = math.sqrt(sx * sx + sy * sy + sz * sz)
        dist = max(dist, min_distance)

        # Distance gain (inverse-distance, normalised so gain=1 at min_distance)
        dist_gain = min(1.0 / dist, 1.0 / min_distance) * min_distance

        # Elevation cue
        el_factor = 1.0 - max(0.0, min(0.85, abs(sz) / max_elevation))
        cutoff = 400 + 19600 * el_factor

        # Azimuth → VBAP speaker gains
        azimuth = math.atan2(sx, sy)  # 0 = front, positive = right
        spk_gains = _vbap_gains(azimuth)

        return dist_gain, cutoff, spk_gains

