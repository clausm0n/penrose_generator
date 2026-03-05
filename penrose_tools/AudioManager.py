# penrose_tools/AudioManager.py
"""
Reactive audio feedback for the Penrose generator using SignalFlow.

Ethereal, installation-quality sound design:
  - Pan (WASD): detuned unison drone with sub-octave warmth and LFO breathing
  - Tile click: soft resonant burst with tonal sine layer
  - Gamma change: slow swept noise with tonal anchor
  - Color change: lush pad chord (pentatonic, consonant intervals, 4-voice unison)
  - Shader change: glass chime with harmonic partials
  - Pulse shader: rolling drone with filter sweep matching visual wave rate
  - Eye spy: breathing drone with allpass chorus and coverage-driven timbre

All patches include inline FDN reverb for cohesive acoustic space.
All audio runs on SignalFlow's own thread; public methods are thread-safe.
"""

import logging
import math
import os
import sys
import threading
import time as _time

# On Windows, add the bundled prebuilt signalflow binaries to the search path
if sys.platform == "win32":
    _bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "signalflow_win64")
    if os.path.isdir(_bundled) and _bundled not in sys.path:
        os.add_dll_directory(_bundled + os.sep + "signalflow")
        sys.path.insert(0, _bundled)

try:
    from signalflow import (
        AudioGraph, AudioGraphConfig,
        Patch, Constant, Smooth,
        SineOscillator, SawOscillator, TriangleOscillator,
        WhiteNoise, PinkNoise,
        SVFilter, ASREnvelope,
        ChannelMixer, StereoPanner,
        Tanh,
        SineLFO, TriangleLFO,
        AllpassDelay, FeedbackDelayNetwork,
    )
    SIGNALFLOW_AVAILABLE = True
except ImportError:
    SIGNALFLOW_AVAILABLE = False

logger = logging.getLogger('AudioManager')


# ---------------------------------------------------------------------------
# Sound patches (self-contained SignalFlow subgraphs)
# ---------------------------------------------------------------------------

if SIGNALFLOW_AVAILABLE:

    def _make_reverb(signal, wet=0.3):
        """Shared reverb chain for consistent acoustic space across all patches.

        3-stage allpass pre-diffusion -> 8-line FDN reverb -> soft limiter.
        """
        diffused = AllpassDelay(signal, delay_time=0.012, feedback=0.5, max_delay_time=0.05)
        diffused = AllpassDelay(diffused, delay_time=0.019, feedback=0.5, max_delay_time=0.05)
        diffused = AllpassDelay(diffused, delay_time=0.027, feedback=0.45, max_delay_time=0.05)
        reverbed = FeedbackDelayNetwork(
            diffused,
            num_delays=8,
            feedback=0.90,
            damping=0.6,
            wet=wet,
            dry=1.0,
            max_delay_time=0.25,
        )
        return Tanh(reverbed * 1.43)

    class PanDrone(Patch):
        """Continuous low drone + filtered noise that responds to camera velocity.

        Ethereal version: detuned unison, sub-octave warmth, slow LFO breathing,
        and inline reverb for spacious installation sound.

        Parameters modulated at runtime:
          - intensity: 0.0 (stopped) to 1.0 (full speed)
          - direction: -1.0 (left) to 1.0 (right) — drives stereo pan
          - pitch_shift: multiplier on base frequency from vertical movement
        """

        def __init__(self, base_freq=55.0):
            super().__init__()
            self._intensity = self.add_input("intensity", 0.0)
            self._direction = self.add_input("direction", 0.0)
            self._pitch_shift = self.add_input("pitch_shift", 1.0)

            freq = Smooth(Constant(base_freq), 0.999) * self._pitch_shift

            # Detuned unison: three triangle oscillators for lush shimmer
            tri1 = TriangleOscillator(freq) * 0.25
            tri2 = TriangleOscillator(freq * 1.003) * 0.20       # +5 cents
            tri3 = TriangleOscillator(freq * 0.997) * 0.20       # -5 cents

            # Sub-octave sine for warmth and weight
            sub = SineOscillator(freq * 0.5) * 0.15

            # Filtered pink noise with LFO-modulated cutoff for breathing texture
            noise = PinkNoise() * 0.12
            noise_cutoff_lfo = SineLFO(0.07, freq * 1.5, freq * 4.0)
            noise_filt = SVFilter(noise, "band_pass",
                                  cutoff=Smooth(noise_cutoff_lfo, 0.998),
                                  resonance=0.55)

            raw_mix = tri1 + tri2 + tri3 + sub + noise_filt

            # Slow amplitude breathing LFO (subtle 15% variation, 20s cycle)
            amp_lfo = SineLFO(0.05, 0.85, 1.0)

            mix = raw_mix * Smooth(self._intensity, 0.998) * amp_lfo * 0.25

            # Stereo pan from movement direction
            panned = StereoPanner(ChannelMixer(1, mix),
                                  Smooth(self._direction, 0.995))

            self.set_output(_make_reverb(panned, wet=0.25))

    class ClickBurst(Patch):
        """Soft resonant burst for tile clicks.

        Ethereal version: longer envelopes, tonal sine layer for warmth,
        inline reverb for spacious decay.

        click_mode determines character:
          0 (select):  warm mid, gentle
          1 (cascade): deep, long
          2 (ripple):  airy, shorter
          3 (mask):    sub drone swell
        """

        _MODE_PARAMS = {
            #  freq, reso,  attack, sustain, release, sine_freq, sine_level
            0: (600,  0.75, 0.03,   0.05,    1.2,     330,       0.08),
            1: (180,  0.85, 0.05,   0.1,     2.0,     110,       0.10),
            2: (1200, 0.70, 0.02,   0.03,    0.8,     660,       0.06),
            3: (70,   0.90, 0.08,   0.15,    2.5,     55,        0.12),
        }

        def __init__(self, click_mode=1, pan=0.0):
            super().__init__()
            params = self._MODE_PARAMS.get(click_mode, self._MODE_PARAMS[1])
            freq, reso, attack, sustain, release, sine_freq, sine_level = params

            env = ASREnvelope(attack, sustain, release)

            # Filtered noise layer (softer than original)
            noise = WhiteNoise()
            filt = SVFilter(noise * env, "band_pass",
                            cutoff=freq, resonance=reso)

            # Tonal sine layer for harmonic warmth
            sine = SineOscillator(sine_freq) * env * sine_level

            combined = filt * 0.18 + sine
            panned = StereoPanner(ChannelMixer(1, combined), pan)
            self.set_output(_make_reverb(panned, wet=0.35))
            self.auto_free = True

    class GammaWhoosh(Patch):
        """Warm breath — a slow, pillowy exhale that melts into reverb.

        Low detuned triangle voices with a long fade-in and very long
        release. Feels like a deep sigh, not a tone.
        """

        def __init__(self):
            super().__init__()
            # Very slow fade in, brief hold, long dissolve
            env = ASREnvelope(0.8, 0.2, 2.0)

            # Low, warm triangle voices — soft and round
            freq = 130.0
            t1 = TriangleOscillator(freq) * 0.10
            t2 = TriangleOscillator(freq * 1.004) * 0.07
            t3 = TriangleOscillator(freq * 0.5) * 0.08  # sub octave

            # Heavily filtered pink noise — just air, no presence
            noise = PinkNoise() * 0.04
            noise_filt = SVFilter(noise, "low_pass", cutoff=400, resonance=0.1)

            mix = (t1 + t2 + t3 + noise_filt) * env

            # Low-pass the whole thing to keep it dark
            output = SVFilter(ChannelMixer(1, mix), "low_pass",
                              cutoff=500, resonance=0.1)

            self.set_output(_make_reverb(output, wet=0.55))
            self.auto_free = True

    class ColorChord(Patch):
        """Warm pad swell — a slow-blooming chord derived from color hue.

        Three detuned triangle voices at consonant intervals, heavily
        low-passed. Fades in like a memory, dissolves into reverb.
        """

        # Just intonation ratios for consonant intervals
        _CONSONANT_RATIOS = [
            1.0, 1.125, 1.2, 1.25, 1.333, 1.5, 1.6, 1.667, 1.875, 2.0,
        ]

        def __init__(self, freq1=330.0, freq2=440.0):
            super().__init__()

            # Drop an octave so it lives in a warm register
            freq1 = freq1 * 0.5
            freq2 = freq2 * 0.5

            # Quantize freq2 to nearest consonant interval relative to freq1
            ratio = freq2 / freq1
            best_ratio = min(self._CONSONANT_RATIOS,
                             key=lambda r: abs(r - ratio))
            freq2 = freq1 * best_ratio

            # Long, slow bloom — takes a full second to arrive
            env = ASREnvelope(1.0, 0.3, 1.8)

            # Detuned triangle voices — round and warm
            t1 = TriangleOscillator(freq1) * 0.10
            t2 = TriangleOscillator(freq1 * 1.003) * 0.07
            t3 = TriangleOscillator(freq2) * 0.08
            t4 = TriangleOscillator(freq2 * 0.997) * 0.06

            mix = (t1 + t2 + t3 + t4) * env

            # Low-pass to remove any brightness
            output = SVFilter(ChannelMixer(1, mix), "low_pass",
                              cutoff=600, resonance=0.1)

            self.set_output(_make_reverb(output, wet=0.50))
            self.auto_free = True

    class EffectSwitch(Patch):
        """Glass chime — pure sine + harmonic partial with soft decay.

        Replaces the harsh metallic click with an ethereal chime.
        """

        _BASE_FREQS = [1200, 1500, 1000, 1800, 900, 2000, 1100]

        def __init__(self, effect_index=0):
            super().__init__()
            freq = self._BASE_FREQS[effect_index % len(self._BASE_FREQS)]

            # Soft chime envelope instead of sharp click
            env = ASREnvelope(0.01, 0.02, 1.5)

            # Pure sine "chime" with a near-3rd harmonic partial
            chime = SineOscillator(freq) * 0.08 * env
            partial = SineOscillator(freq * 2.997) * 0.025 * env

            # Tiny noise click for "glass" transient
            click_env = ASREnvelope(0.001, 0.001, 0.05)
            click = WhiteNoise() * click_env * 0.03
            click_filt = SVFilter(click, "band_pass",
                                  cutoff=freq * 2.0, resonance=0.7)

            output = chime + partial + click_filt
            self.set_output(_make_reverb(output, wet=0.4))
            self.auto_free = True

    class PulseDrone(Patch):
        """Deep rolling drone that matches the radial pulse shader.

        The pulse shader sweeps waves outward at 3 rad/s (~2.1s period).
        This drone uses an LFO at the same rate to gently swell a warm,
        sub-heavy sine bed — deep and organic, not mechanical.

        Parameters modulated at runtime:
          - active: 0.0 (off) or 1.0 (on) — fades the drone in/out
          - wave_size: 0.0-1.0 — maps to filter ceiling and warmth
        """

        def __init__(self, base_freq=45.0):
            super().__init__()
            self._active = self.add_input("active", 0.0)
            self._wave_size = self.add_input("wave_size", 0.5)

            wave_smooth = Smooth(self._wave_size, 0.997)

            freq = Constant(base_freq)

            # Pulse rate LFO: 3 rad/s = ~0.477 Hz — matches shader u_time * 3.0
            pulse_lfo = SineLFO(0.477, 0.0, 1.0)

            # Deep sub foundation — the heaviest voice
            sub = SineOscillator(freq * 0.5) * 0.25

            # Detuned sine unison at fundamental (3 voices, gentle)
            s1 = SineOscillator(freq) * 0.18
            s2 = SineOscillator(freq * 1.003) * 0.12
            s3 = SineOscillator(freq * 0.997) * 0.12

            # Soft triangle octave above for just a hint of presence
            tri = TriangleOscillator(freq * 2.0) * wave_smooth * 0.05

            mix = sub + s1 + s2 + s3 + tri

            # Gentle low-pass filter — stays dark, LFO just breathes it open slightly
            min_cutoff = freq * 2.0
            max_cutoff = Constant(200.0) + wave_smooth * Constant(300.0)
            sweep_cutoff = min_cutoff + pulse_lfo * (max_cutoff - min_cutoff)

            filtered = SVFilter(ChannelMixer(1, mix), "low_pass",
                                cutoff=Smooth(sweep_cutoff, 0.999),
                                resonance=0.15)

            # Subtle amplitude swell with each wave
            amp_pulse = pulse_lfo * 0.15 + 0.85  # range 0.85 - 1.0

            output = filtered * amp_pulse * Smooth(self._active, 0.999) * 0.28

            self.set_output(_make_reverb(output, wet=0.35))

    class EyeSpyDrone(Patch):
        """Persistent drone for the eye_spy shader.

        Ethereal version: detuned unison, slow LFO breathing on filter,
        allpass chorus for spatial width, and inline reverb.

        Tracks the pupil position on XY for stereo panning, and uses
        depth coverage (eye openness) to modulate timbre:
          - pan:      -1..1 from pupil X position
          - coverage: 0..1 eye openness — controls filter cutoff and harmonic richness
          - motion:   0..1 centroid movement — adds vibrato/texture intensity
          - pitch_y:  pupil Y mapped to pitch bend

        Low coverage (squinted) = dark, muffled, low.
        High coverage (wide open) = bright, resonant, harmonically rich.
        """

        def __init__(self, base_freq=65.0):
            super().__init__()
            self._pan = self.add_input("pan", 0.0)
            self._coverage = self.add_input("coverage", 0.3)
            self._motion = self.add_input("motion", 0.0)
            self._pitch_y = self.add_input("pitch_y", 1.0)
            self._active = self.add_input("active", 0.0)

            cov_smooth = Smooth(self._coverage, 0.998)
            mot_smooth = Smooth(self._motion, 0.995)

            freq = Constant(base_freq) * Smooth(self._pitch_y, 0.999)

            # Slow evolving LFO for filter breathing (25s cycle)
            filter_lfo = SineLFO(0.04, 0.8, 1.2)

            # Detuned unison sine fundamental (3 voices)
            sine1 = SineOscillator(freq) * 0.18
            sine2 = SineOscillator(freq * 1.004) * 0.12        # +7 cents
            sine3 = SineOscillator(freq * 0.996) * 0.12        # -7 cents

            # Saw with evolving detune for richness, gated by coverage
            detune_lfo = TriangleLFO(0.03, 1.001, 1.008)       # 33s cycle
            saw = SawOscillator(freq * detune_lfo) * cov_smooth * 0.07

            # Upper partial (3rd harmonic) appears when eye is wide open
            upper = SineOscillator(freq * 3.0) * cov_smooth * cov_smooth * 0.04

            # Pink noise texture driven by motion, with LFO-swept filter
            noise = PinkNoise() * mot_smooth * 0.06
            noise_cutoff = freq * 4.0 * filter_lfo
            noise_filt = SVFilter(noise, "band_pass",
                                  cutoff=Smooth(noise_cutoff, 0.998),
                                  resonance=0.45)

            mix = sine1 + sine2 + sine3 + saw + upper + noise_filt

            # Master filter with LFO-modulated cutoff for breathing
            base_cutoff = Constant(300.0) + cov_smooth * Constant(3700.0)
            modulated_cutoff = base_cutoff * filter_lfo
            filtered = SVFilter(ChannelMixer(1, mix), "low_pass",
                                cutoff=Smooth(modulated_cutoff, 0.999),
                                resonance=0.25)

            # Allpass chorus for spatial width
            chorus_lfo = SineLFO(0.3, 0.003, 0.007)
            chorused = AllpassDelay(filtered, delay_time=chorus_lfo,
                                    feedback=0.3, max_delay_time=0.02)
            output_mix = filtered * 0.6 + chorused * 0.4

            # Master volume: fade with active flag
            output = output_mix * Smooth(self._active, 0.999) * 0.22

            # Stereo pan from pupil X
            panned = StereoPanner(output, Smooth(self._pan, 0.997))
            self.set_output(_make_reverb(panned, wet=0.25))


# ---------------------------------------------------------------------------
# Main AudioManager class
# ---------------------------------------------------------------------------

class AudioManager:
    """Manages reactive audio for the Penrose generator.

    Parameters
    ----------
    mode : str
        'stereo' or 'surround' — selects spatial panner type.
    """

    def __init__(self, mode='stereo'):
        if not SIGNALFLOW_AVAILABLE:
            raise RuntimeError("signalflow is not installed")

        self.mode = mode
        self.logger = logger
        self._lock = threading.Lock()

        # Initialize audio graph
        config = AudioGraphConfig()
        config.output_buffer_size = 256
        self.graph = AudioGraph(config=config, start=True)
        self.logger.info(f"AudioManager started (mode={mode})")

        # Persistent pan drone (always alive, intensity modulated)
        self._drone = PanDrone()
        self._drone.play()
        self._drone_active = False

        # Persistent pulse drone (always alive, activated when pulse effect is on)
        self._pulse_drone = PulseDrone()
        self._pulse_drone.play()

        # Persistent eye_spy drone (always alive, activated when eye_spy effect is on)
        self._eye_drone = EyeSpyDrone()
        self._eye_drone.play()
        self._eye_spy_active = False

    # ------------------------------------------------------------------
    # Pan events
    # ------------------------------------------------------------------
    def on_pan(self, dx, dy):
        """Called when a pan key is pressed. dx/dy are direction (-1, 0, 1)."""
        pass  # Drone is updated continuously via update_pan

    def update_pan(self, velocity_x, velocity_y):
        """Called every frame with current camera velocity.
        Modulates the drone intensity and direction."""
        speed = math.sqrt(velocity_x ** 2 + velocity_y ** 2)
        intensity = min(1.0, speed * 20.0)  # Scale up small velocities

        # Direction for stereo pan: use horizontal velocity
        direction = max(-1.0, min(1.0, velocity_x * 10.0))

        # Pitch shift from vertical movement (moving up = slightly higher)
        pitch = 1.0 + velocity_y * 2.0
        pitch = max(0.5, min(2.0, pitch))

        with self._lock:
            try:
                self._drone.set_input("intensity", intensity)
                self._drone.set_input("direction", direction)
                self._drone.set_input("pitch_shift", pitch)
            except Exception:
                pass  # Silently handle if graph is shutting down

    # ------------------------------------------------------------------
    # Tile click
    # ------------------------------------------------------------------
    def on_click(self, click_mode, px, py):
        """Fire a resonant burst for a tile click.

        click_mode: 0=select, 1=cascade, 2=ripple, 3=mask_stamp
        px, py: pentagrid coordinates of click
        """
        # Map pentagrid position to stereo pan (-1 to 1)
        pan = max(-1.0, min(1.0, px * 0.1))

        with self._lock:
            try:
                burst = ClickBurst(click_mode=click_mode, pan=pan)
                burst.play()
            except Exception as e:
                self.logger.debug(f"Click sound error: {e}")

    # ------------------------------------------------------------------
    # Gamma change
    # ------------------------------------------------------------------
    def on_gamma_change(self):
        """Fire a swept bandpass whoosh for gamma randomization."""
        with self._lock:
            try:
                whoosh = GammaWhoosh()
                whoosh.play()
            except Exception as e:
                self.logger.debug(f"Gamma sound error: {e}")

    # ------------------------------------------------------------------
    # Color change
    # ------------------------------------------------------------------
    def on_color_change(self, color1, color2):
        """Fire a tonal chord derived from the new colors.

        color1, color2: [R, G, B] lists (0-255)
        """
        # Derive frequencies from color hue
        freq1 = self._color_to_freq(color1)
        freq2 = self._color_to_freq(color2)

        with self._lock:
            try:
                chord = ColorChord(freq1=freq1, freq2=freq2)
                chord.play()
            except Exception as e:
                self.logger.debug(f"Color sound error: {e}")

    # ------------------------------------------------------------------
    # Effect/shader change
    # ------------------------------------------------------------------
    def on_effect_change(self, effect_index):
        """Fire a metallic click tuned to the effect index."""
        with self._lock:
            try:
                click = EffectSwitch(effect_index=effect_index)
                click.play()
            except Exception as e:
                self.logger.debug(f"Effect sound error: {e}")

    # ------------------------------------------------------------------
    # Pulse shader — per-frame update
    # ------------------------------------------------------------------
    def update_pulse(self, active, zoom=1.0):
        """Called every frame to drive the pulse drone.

        Parameters
        ----------
        active : bool
            True when pulse effect is the current shader.
        zoom : float
            Current camera zoom level — maps to wave_size
            (zoomed out = larger waves = richer sound).
        """
        with self._lock:
            try:
                if not active:
                    self._pulse_drone.set_input("active", 0.0)
                    return
                # Map zoom to wave_size: zoomed out (small zoom) = big waves
                wave_size = max(0.0, min(1.0, 1.0 / (zoom + 0.5)))
                self._pulse_drone.set_input("wave_size", wave_size)
                self._pulse_drone.set_input("active", 1.0)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Eye spy shader — per-frame update
    # ------------------------------------------------------------------
    def update_eye_spy(self, active, centroid_x, centroid_y, coverage, motion,
                       depth_available=False):
        """Called every frame to drive the eye_spy drone.

        Parameters
        ----------
        active : bool
            True when eye_spy effect is the current shader.
        centroid_x : float
            Pupil X in UV space (0-1, 0.5 = center).
        centroid_y : float
            Pupil Y in UV space (0-1, 0.5 = center).
        coverage : float
            Eye openness (0-1, fraction of active depth pixels).
        motion : float
            Smoothed centroid motion magnitude (0-1).
        depth_available : bool
            True when depth camera is providing data.
        """
        if not active:
            with self._lock:
                try:
                    self._eye_drone.set_input("active", 0.0)
                except Exception:
                    pass
            return

        # When no depth camera, replicate the shader's idle pupil animation
        # (see eye_spy.frag lines 143-145: sin/cos orbit)
        if not depth_available:
            t = _time.monotonic()
            centroid_x = 0.5 + math.sin(t * 0.5) * 0.25
            centroid_y = 0.5 + math.cos(t * 0.7) * 0.2
            coverage = 0.3  # shader default openness
            motion = 0.15   # gentle baseline texture

        # Map centroid UV to stereo pan (-1..+1)
        pan = (centroid_x - 0.5) * 2.0
        pan = max(-1.0, min(1.0, pan))

        # Map centroid Y to pitch bend: top=higher, bottom=lower
        # UV 0.0 = top of frame, 1.0 = bottom — invert so up = higher
        pitch_y = 1.0 + (0.5 - centroid_y) * 0.5
        pitch_y = max(0.7, min(1.4, pitch_y))

        with self._lock:
            try:
                self._eye_drone.set_input("pan", pan)
                self._eye_drone.set_input("coverage", coverage)
                self._eye_drone.set_input("motion", motion)
                self._eye_drone.set_input("pitch_y", pitch_y)
                self._eye_drone.set_input("active", 1.0)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def stop(self):
        """Stop the audio graph and release resources."""
        with self._lock:
            try:
                self.graph.stop()
                self.logger.info("AudioManager stopped")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    # Pentatonic scale semitones (C D E G A) across two octaves from A3
    _PENTATONIC = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24]

    @staticmethod
    def _color_to_freq(color):
        """Convert an RGB color to a musical frequency on a pentatonic scale.

        Uses the hue angle to select a note from a two-octave pentatonic
        scale rooted at A3 (220 Hz). Pentatonic tuning avoids dissonance
        and complements the Penrose geometric aesthetic.
        """
        r, g, b = [c / 255.0 for c in color[:3]]

        # Simple hue extraction
        cmax = max(r, g, b)
        cmin = min(r, g, b)
        delta = cmax - cmin

        if delta < 0.001:
            hue = 0.0
        elif cmax == r:
            hue = ((g - b) / delta) % 6
        elif cmax == g:
            hue = (b - r) / delta + 2
        else:
            hue = (r - g) / delta + 4
        hue /= 6.0  # Normalize to 0-1

        # Map hue to pentatonic scale degree
        scale = AudioManager._PENTATONIC
        index = int(hue * len(scale)) % len(scale)
        semitone = scale[index]
        return 220.0 * (2.0 ** (semitone / 12.0))
