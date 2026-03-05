"""
Tween Engine - time-based interpolation of numeric values with configurable easing.

Provides smooth transitions for colors, brightness, and other visual properties.
No OpenGL dependency; pure logic module.
"""

import logging

logger = logging.getLogger(__name__)

# --- Easing functions ---

def linear(t):
    return t

def ease_in(t):
    return t * t

def ease_out(t):
    return t * (2 - t)

def ease_in_out(t):
    return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t

EASING_FUNCTIONS = {
    'linear': linear,
    'ease_in': ease_in,
    'ease_out': ease_out,
    'ease_in_out': ease_in_out,
}


class Tween:
    """A single interpolation from start_value to end_value over duration."""

    def __init__(self, start_value, end_value, duration, easing='ease_in_out', on_complete=None):
        # Validate type compatibility
        if type(start_value) != type(end_value):
            raise ValueError(
                f"Mismatched start/end types: {type(start_value).__name__} vs {type(end_value).__name__}"
            )
        if isinstance(start_value, (list, tuple)) and len(start_value) != len(end_value):
            raise ValueError(
                f"Mismatched lengths: start has {len(start_value)}, end has {len(end_value)}"
            )

        # Clamp duration to minimum
        if duration <= 0:
            duration = 0.001

        self.start_value = start_value
        self.end_value = end_value
        self.duration = duration
        self.elapsed = 0.0
        self.on_complete = on_complete
        self._done = False
        self._callback_fired = False

        # Resolve easing function
        if easing in EASING_FUNCTIONS:
            self._easing_fn = EASING_FUNCTIONS[easing]
        else:
            logger.warning(f"Unknown easing '{easing}', falling back to ease_in_out")
            self._easing_fn = EASING_FUNCTIONS['ease_in_out']

    def update(self, dt):
        """Advance the tween by dt seconds. Returns True when complete."""
        if self._done:
            return True

        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.elapsed = self.duration
            self._done = True
            self._fire_callback()
            return True
        return False

    def _fire_callback(self):
        if self.on_complete and not self._callback_fired:
            self._callback_fired = True
            try:
                self.on_complete()
            except Exception as e:
                logger.error(f"Tween on_complete callback raised: {e}")

    @property
    def value(self):
        """Current interpolated value (scalar, list, or tuple)."""
        if self._done:
            return self.end_value

        t = self.elapsed / self.duration
        t = max(0.0, min(1.0, t))
        eased = self._easing_fn(t)

        return self._interpolate(self.start_value, self.end_value, eased)

    @property
    def done(self):
        return self._done

    @staticmethod
    def _interpolate(start, end, t):
        if isinstance(start, (int, float)):
            return start + (end - start) * t
        elif isinstance(start, list):
            return [s + (e - s) * t for s, e in zip(start, end)]
        elif isinstance(start, tuple):
            return tuple(s + (e - s) * t for s, e in zip(start, end))
        else:
            return start + (end - start) * t


class TweenEngine:
    """Manages a collection of named tweens, updated each frame."""

    def __init__(self):
        self.tweens = {}
        self.brightness_multiplier = 1.0

    def start(self, name, start_value, end_value, duration, easing='ease_in_out', on_complete=None):
        """Create or replace a named tween."""
        logger.info(f"Tween START '{name}': {start_value} -> {end_value} over {duration}s ({easing})")
        self.tweens[name] = Tween(start_value, end_value, duration, easing, on_complete)

    def cancel(self, name):
        """Cancel a tween by name."""
        self.tweens.pop(name, None)

    def update(self, dt):
        """Advance all active tweens by dt seconds, fire callbacks on completion."""
        completed = []
        for name, tween in list(self.tweens.items()):
            if tween.update(dt):
                completed.append((name, tween))
        # Only remove tweens that are still the same object (not replaced by a callback)
        for name, original_tween in completed:
            if self.tweens.get(name) is original_tween:
                logger.debug(f"Tween COMPLETE '{name}'")
                del self.tweens[name]
            else:
                logger.debug(f"Tween '{name}' was replaced by callback, keeping new tween")

    def get(self, name, default=None):
        """Get the current value of a named tween, or default if not active."""
        tween = self.tweens.get(name)
        if tween is not None:
            return tween.value
        return default

    def is_active(self, name):
        """Check if a named tween is currently active."""
        return name in self.tweens
