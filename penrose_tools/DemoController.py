"""
Demo Controller - autonomous demo mode for the Penrose tiling generator.

Cycles through visual behaviors (shader changes, color randomization,
gamma randomization, golden-ratio panning) when activated via --demo flag.
Pauses on user input and resumes after configurable idle timeout.
"""

import math
import time
import logging
import configparser
from enum import Enum

from . import events

logger = logging.getLogger(__name__)

GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))  # ≈ 2.39996 rad ≈ 137.508°
MIN_IDLE_TIMEOUT = 10.0  # seconds


class DemoAction(Enum):
    CHANGE_SHADER = 'change_shader'
    RANDOMIZE_COLORS = 'randomize_colors'
    RANDOMIZE_GAMMA = 'randomize_gamma'


ACTION_CYCLE = [
    DemoAction.CHANGE_SHADER,
    DemoAction.RANDOMIZE_COLORS,
    DemoAction.RANDOMIZE_GAMMA,
]


class DemoController:
    """Manages autonomous demo mode behavior."""

    def __init__(self, renderer, tween_engine, config_path, idle_timeout_minutes=2.0):
        self.renderer = renderer
        self.tween_engine = tween_engine
        self.config_path = config_path

        # Idle timeout in seconds, clamped to minimum
        timeout_seconds = idle_timeout_minutes * 60.0
        if timeout_seconds <= 0:
            logger.warning(f"Idle timeout {idle_timeout_minutes}m <= 0, clamping to {MIN_IDLE_TIMEOUT}s")
            timeout_seconds = MIN_IDLE_TIMEOUT
        self.idle_timeout = timeout_seconds

        self.active = True
        self.paused = False
        self.last_input_time = time.time()

        # Panning state
        self.pan_angle = 0.0
        self.pan_direction_timer = 0.0
        self.pan_direction_interval = 8.0  # seconds between direction changes
        self.pan_speed = 0.02

        # Action scheduling
        self.action_timer = 0.0
        self.action_index = 0
        self.action_interval = self._read_timer_from_config()

    def _read_timer_from_config(self):
        """Read the timer interval from config.ini, default 10s."""
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path)
            return float(config.get('Settings', 'timer', fallback='10'))
        except Exception:
            return 10.0

    def on_user_input(self):
        """Called on any keyboard or mouse event. Pauses demo, resets idle timer."""
        if not self.active:
            return
        self.paused = True
        self.last_input_time = time.time()

    def update(self, dt):
        """Called each frame. Manages idle detection, panning, and action scheduling."""
        if not self.active:
            return

        # Clamp negative dt
        if dt < 0:
            dt = 0.0

        if self.paused:
            # Check if idle timeout has elapsed
            elapsed_since_input = time.time() - self.last_input_time
            if elapsed_since_input >= self.idle_timeout:
                self.paused = False
                logger.info("Demo resuming after idle timeout")
            else:
                return

        # Update panning
        self._update_panning(dt)

        # Update action scheduling
        self.action_timer += dt
        if self.action_timer >= self.action_interval:
            self.action_timer = 0.0
            self._execute_action()
            self._schedule_next_action()

    def _update_panning(self, dt):
        """Move camera along golden-ratio path."""
        self.pan_direction_timer += dt
        if self.pan_direction_timer >= self.pan_direction_interval:
            self.pan_direction_timer = 0.0
            self.pan_angle += GOLDEN_ANGLE

        dx = math.cos(self.pan_angle)
        dy = math.sin(self.pan_angle)
        self.renderer.move_direction(dx, dy, speed=self.pan_speed)

    def _schedule_next_action(self):
        """Advance to the next action in the cycle."""
        self.action_index = (self.action_index + 1) % len(ACTION_CYCLE)

    def _execute_action(self):
        """Fire the current scheduled event through the event system."""
        action = ACTION_CYCLE[self.action_index]
        logger.info(f"Demo executing action: {action.value}")

        if action == DemoAction.CHANGE_SHADER:
            events.toggle_shader_event.set()
        elif action == DemoAction.RANDOMIZE_COLORS:
            events.randomize_colors_event.set()
        elif action == DemoAction.RANDOMIZE_GAMMA:
            events.update_event.set()
