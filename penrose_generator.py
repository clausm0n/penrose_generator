# penrose_generator.py
# Only export Bluetooth components if not in local mode
import os
import sys

# On Linux (Raspberry Pi), prefer EGL over GLX for hardware-accelerated GLES
if sys.platform == 'linux' and 'PYOPENGL_PLATFORM' not in os.environ:
    os.environ['PYOPENGL_PLATFORM'] = 'egl'
if not os.environ.get('PENROSE_LOCAL_MODE'):
    try:
        from .PenroseBluetoothServer import run_bluetooth_server
        __all__ = ['Operations', 'run_server',
                   'ProceduralRenderer', 'run_bluetooth_server']
    except ImportError:
        __all__ = ['Operations', 'run_server',
                   'ProceduralRenderer']
else:
    __all__ = ['Operations', 'run_server',
               'ProceduralRenderer']

import numpy as np
import glfw
from OpenGL.GL import *
from threading import Thread
from collections import OrderedDict
from penrose_tools import Operations, run_server, GUIOverlay
from penrose_tools.ProceduralRenderer import ProceduralRenderer
from penrose_tools.TweenEngine import TweenEngine
from penrose_tools.DemoController import DemoController
import logging
import configparser
import signal
import argparse
import asyncio
from penrose_tools.events import update_event, toggle_shader_event, randomize_colors_event, shutdown_event, toggle_regions_event, toggle_gui_event, reset_viewport_event, randomize_gamma_event
from threading import Timer
import random
import time
# Configuration and initialization
CONFIG_PATH = 'config.ini'
DEFAULT_CONFIG = {
    'zoom': 1.0,
    'gamma': [1.0, 0.7, 0.5, 0.3, 0.1],
    'color1': [205, 255, 255],
    'color2': [0, 0, 255],
    'cycle' : [False,False,False],
    'timer' : 10,
    'shader_settings': {
        'no_effect': True,
        'region_blend': True,
        'rainbow': True,
        'pulse': True,
        'sparkle': True,
    },
    'vertex_offset': 0.0001
}

op = Operations()
gui_visible = False
fullscreen_mode = False
running = True
width = 0
height = 0
gui_overlay = None
renderer = None  # Global renderer reference
audio_manager = None  # Global audio manager reference
tween_engine = None  # Global tween engine reference
demo_controller = None  # Global demo controller reference
depth_camera_manager = None  # Global depth camera reference
_pending_gamma = None  # Queued gamma value during fade transitions
_pending_shader = False  # Queued shader switch during fade transitions

# Check if Bluetooth is available
try:
    from penrose_tools.PenroseBluetoothServer import run_bluetooth_server
    BLUETOOTH_AVAILABLE = True
except ImportError:
    BLUETOOTH_AVAILABLE = False

# Check if camera capture is available
try:
    from penrose_tools.CameraManager import CameraManager
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False

# Check if depth camera is available (uses OpenNI2)
try:
    from penrose_tools.DepthCameraManager import DepthCameraManager, DEPTH_CAMERA_AVAILABLE
except ImportError:
    DEPTH_CAMERA_AVAILABLE = False

# Check if audio feedback is available (requires signalflow)
try:
    from penrose_tools.AudioManager import AudioManager, SIGNALFLOW_AVAILABLE as AUDIO_AVAILABLE
except ImportError:
    AUDIO_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Penrose_Generator')

# --- Arcade stick/button input via Linux evdev ---
import sys
if sys.platform == 'linux':
    import struct
    import select

    class ArcadeInput:
        """Reads a DragonRise USB arcade encoder and fires penrose events.

        Physical-to-logical axis remap (board is rotated):
            Board LEFT  -> Pan UP
            Board RIGHT -> Pan DOWN
            Board DOWN  -> Pan LEFT
            Board UP    -> Pan RIGHT

        Buttons:
            BTN_BASE4 (code 297) -> randomize colors
            BTN_BASE5 (code 298) -> randomize gamma
            BTN_BASE6 (code 299) -> change shader
            BTN_BASE3 (code 296) -> reset viewport
        """
        EVENT_FORMAT = "llHHi"
        EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
        AXIS_CENTER = 128
        AXIS_DEADZONE = 30

        # Button code -> event mapping
        BUTTON_MAP = {
            297: 'randomize_colors',   # BTN_BASE4 (button 3 on board)
            298: 'randomize_gamma',     # BTN_BASE5 (button 4)
            299: 'toggle_shader',       # BTN_BASE6 (button 5)
            296: 'reset_viewport',      # BTN_BASE3 (button 6)
        }

        def __init__(self):
            self.fd = None
            self.device_name = None
            self.axis_x = self.AXIS_CENTER
            self.axis_y = self.AXIS_CENTER
            self._open_device()

        def _open_device(self):
            for i in range(20):
                path = f"/dev/input/event{i}"
                if not os.path.exists(path):
                    continue
                try:
                    with open(f"/sys/class/input/event{i}/device/name", "r") as f:
                        name = f.read().strip()
                except FileNotFoundError:
                    continue
                if "DragonRise" in name or "Generic   USB  Joystick" in name:
                    try:
                        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                        self.device_name = name
                        logger.info(f"Arcade controller found: {path} ({name})")
                        return
                    except PermissionError:
                        logger.warning(f"Arcade controller at {path} - permission denied (run with sudo)")
            logger.info("No arcade controller found - arcade input disabled")

        def poll(self):
            """Poll for arcade inputs. Returns (pan_x, pan_y, button_events).

            pan_x/pan_y are -1, 0, or 1 (remapped to real-space directions).
            button_events is a list of event name strings for buttons pressed this frame.
            """
            button_events = []
            if self.fd is None:
                return 0, 0, button_events

            try:
                readable, _, _ = select.select([self.fd], [], [], 0)
            except (ValueError, OSError):
                return 0, 0, button_events

            if not readable:
                px, py, _ = self._get_pan()
                return px, py, button_events

            try:
                data = os.read(self.fd, self.EVENT_SIZE * 32)
            except OSError:
                px, py, _ = self._get_pan()
                return px, py, button_events

            for offset in range(0, len(data) - self.EVENT_SIZE + 1, self.EVENT_SIZE):
                _, _, ev_type, code, value = struct.unpack_from(self.EVENT_FORMAT, data, offset)
                if ev_type == 0x03:  # ABS axis
                    if code == 0x00:    # ABS_X
                        self.axis_x = value
                    elif code == 0x01:  # ABS_Y
                        self.axis_y = value
                elif ev_type == 0x01 and value == 1:  # KEY press
                    event_name = self.BUTTON_MAP.get(code)
                    if event_name:
                        button_events.append(event_name)
                        logger.info(f"Arcade button: {event_name}")

            px, py, _ = self._get_pan()
            return px, py, button_events

        def _get_pan(self):
            """Convert raw axes to remapped -1/0/1 pan directions.

            Board orientation remap:
                Raw LEFT  (X low)  -> pan_y +1 (UP)
                Raw RIGHT (X high) -> pan_y -1 (DOWN)
                Raw DOWN  (Y high) -> pan_x -1 (LEFT)
                Raw UP    (Y low)  -> pan_x +1 (RIGHT)
            """
            pan_x = 0
            pan_y = 0
            dx = self.axis_x - self.AXIS_CENTER
            dy = self.axis_y - self.AXIS_CENTER
            if abs(dx) > self.AXIS_DEADZONE:
                pan_y = -1 if dx > 0 else 1   # left->up, right->down
            if abs(dy) > self.AXIS_DEADZONE:
                pan_x = 1 if dy < 0 else -1   # up->right, down->left
            return (pan_x, pan_y, [])

        def close(self):
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
else:
    class ArcadeInput:
        """Stub for non-Linux platforms."""
        def __init__(self):
            pass
        def poll(self):
            return 0, 0, []
        def close(self):
            pass

class CycleManager:
    def __init__(self, config_path, update_event, toggle_shader_event, randomize_colors_event):
        self.config_path = config_path
        self.update_event = update_event
        self.toggle_shader_event = toggle_shader_event
        self.randomize_colors_event = randomize_colors_event
        self.timer_thread = None
        self.running = True
        
    def randomize_gamma(self):
        config = configparser.ConfigParser()
        config.read(self.config_path)
        new_gamma = [random.uniform(-1.0, 1.0) for _ in range(5)]
        config['Settings']['gamma'] = ', '.join(map(str, new_gamma))
        with open(self.config_path, 'w') as configfile:
            config.write(configfile)
        self.update_event.set()

    def check_cycles(self):
        while self.running:
            try:
                config = configparser.ConfigParser()
                config.read(self.config_path)
                cycle_str = config['Settings'].get('cycle', '[False, False, False]')
                timer_str = config['Settings'].get('timer', '30')
                
                # Parse cycle settings
                cycle = eval(cycle_str)  # Safely evaluate string to list
                timer = int(timer_str)
                
                if any(cycle):  # If any cycle is enabled
                    if cycle[0]:  # Cycle Effects
                        self.toggle_shader_event.set()
                    
                    if cycle[1]:  # Randomize Gamma
                        self.randomize_gamma()
                    
                    if cycle[2]:  # Cycle Colors
                        self.randomize_colors_event.set()
                    
                    # Add offset to prevent all events happening at once
                    base_sleep = timer
                    if cycle[1]:  # Gamma offset
                        base_sleep += 1
                    if cycle[2]:  # Colors offset
                        base_sleep += 2
                
                time.sleep(max(timer, 5))  # Minimum 5 second delay
                
            except Exception as e:
                logger.error(f"Error in cycle check: {e}")
                time.sleep(5)  # Wait before retry on error

    def start(self):
        self.timer_thread = Thread(target=self.check_cycles, daemon=True)
        self.timer_thread.start()

    def stop(self):
        self.running = False
        if self.timer_thread:
            self.timer_thread.join()

def initialize_config(path):
    if not os.path.isfile(path):
        print("Config file not found. Creating a new one...")
        config = configparser.ConfigParser()
        config['Settings'] = {
            'zoom': str(DEFAULT_CONFIG['zoom']),
            'gamma': ', '.join(map(str, DEFAULT_CONFIG['gamma'])),
            'color1': ', '.join(map(str, DEFAULT_CONFIG['color1'])),
            'color2': ', '.join(map(str, DEFAULT_CONFIG['color2'])),
            'cycle': ', '.join(map(str, DEFAULT_CONFIG['cycle'])),
            'timer': str(DEFAULT_CONFIG['timer']),
            'shader_settings': str(DEFAULT_CONFIG['shader_settings']),
            'vertex_offset': str(DEFAULT_CONFIG['vertex_offset'])
        }
        with open(path, 'w') as configfile:
            config.write(configfile)
    
    # Load config and ensure proper types
    config_data = op.read_config_file(path)
    if 'vertex_offset' not in config_data:
        config_data['vertex_offset'] = DEFAULT_CONFIG['vertex_offset']
    else:
        config_data['vertex_offset'] = float(config_data['vertex_offset'])
    return config_data

config_data = initialize_config(CONFIG_PATH)
tiles_cache = OrderedDict()

def setup_window(fullscreen=False):
    global width, height
    if not glfw.init():
        raise Exception("GLFW can't be initialized")

    # Context strategies: try desktop GL 3.2 Core (macOS/desktop), then OpenGL ES 3.1/3.0
    # (Raspberry Pi hardware GPU), then desktop GL fallbacks (software).
    contexts_to_try = [
        {"major": 3, "minor": 2, "profile": glfw.OPENGL_CORE_PROFILE, "forward_compat": True, "es": False, "label": "GL 3.2 Core"},
        {"major": 3, "minor": 1, "profile": None, "forward_compat": False, "es": True, "label": "GLES 3.1"},
        {"major": 3, "minor": 0, "profile": None, "forward_compat": False, "es": True, "label": "GLES 3.0"},
        {"major": 2, "minor": 0, "profile": None, "forward_compat": False, "es": True, "label": "GLES 2.0"},
    ]

    # Get the primary monitor
    primary_monitor = glfw.get_primary_monitor()
    window = None
    used_es = False

    for ctx in contexts_to_try:
        glfw.default_window_hints()
        if ctx["es"]:
            glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_ES_API)
            # Force EGL context — GLX on Pi uses software Mesa, EGL uses hardware V3D
            glfw.window_hint(glfw.CONTEXT_CREATION_API, glfw.EGL_CONTEXT_API)
        else:
            glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_API)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, ctx["major"])
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, ctx["minor"])
        if ctx["forward_compat"]:
            glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
        if ctx["profile"]:
            glfw.window_hint(glfw.OPENGL_PROFILE, ctx["profile"])

        if fullscreen:
            video_mode = glfw.get_video_mode(primary_monitor)
            width, height = video_mode.size.width, video_mode.size.height
            window = glfw.create_window(width, height, "Penrose Tiling", primary_monitor, None)
        else:
            width, height = 1280, 720
            window = glfw.create_window(width, height, "Penrose Tiling", None, None)

        if window:
            used_es = ctx["es"]
            glfw.make_context_current(window)
            gl_renderer = glGetString(GL_RENDERER)
            gl_version = glGetString(GL_VERSION)
            logger.info(f"OpenGL context created: {ctx['label']}")
            logger.info(f"GL Renderer: {gl_renderer}")
            logger.info(f"GL Version: {gl_version}")
            break
        else:
            logger.debug(f"Failed to create context: {ctx['label']}")

    if not window:
        glfw.terminate()
        raise Exception("GLFW window can't be created (no supported OpenGL context)")

    if fullscreen:
        glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_HIDDEN)
    
    # Register key callback
    glfw.set_key_callback(window, key_callback)
    
    # Register scroll callback for zoom
    glfw.set_scroll_callback(window, scroll_callback)

    # Register mouse callbacks for tile interaction
    glfw.set_mouse_button_callback(window, mouse_button_callback)
    glfw.set_cursor_pos_callback(window, cursor_position_callback)
    glfw.set_cursor_enter_callback(window, cursor_enter_callback)
    
    # Disable MSAA (not supported in GLES)
    if not used_es:
        glfw.window_hint(glfw.SAMPLES, 4)
        glDisable(GL_MULTISAMPLE)

    return window, used_es

def toggle_fullscreen(window):
    """Toggle between fullscreen and windowed mode."""
    global fullscreen_mode, width, height

    # Get the primary monitor
    primary_monitor = glfw.get_primary_monitor()

    if not fullscreen_mode:
        # Switch to fullscreen
        video_mode = glfw.get_video_mode(primary_monitor)
        width, height = video_mode.size.width, video_mode.size.height
        glfw.set_window_monitor(window, primary_monitor, 0, 0, width, height, video_mode.refresh_rate)
        glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_HIDDEN)
        fullscreen_mode = True
        logger.info("Switched to fullscreen mode")
    else:
        # Switch to windowed mode
        width, height = 1280, 720
        glfw.set_window_monitor(window, None, 100, 100, width, height, 0)
        glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_NORMAL)
        fullscreen_mode = False
        logger.info("Switched to windowed mode")

    # Update viewport using framebuffer size (HiDPI/Retina)
    fb_width, fb_height = glfw.get_framebuffer_size(window)
    glViewport(0, 0, fb_width, fb_height)

def scroll_callback(window, xoffset, yoffset):
    """Handle mouse scroll for zoom."""
    global renderer, demo_controller
    if demo_controller:
        demo_controller.on_user_input()
    if renderer:
        if yoffset > 0:
            renderer.zoom_by(1.15)  # Zoom in
        elif yoffset < 0:
            renderer.zoom_by(0.85)  # Zoom out

def mouse_button_callback(window, button, action, mods):
    """Handle mouse clicks for tile interaction."""
    global renderer, width, height, audio_manager, demo_controller
    if demo_controller:
        demo_controller.on_user_input()
    if renderer and renderer.interaction_manager and action == glfw.PRESS:
        if button == glfw.MOUSE_BUTTON_LEFT:
            mx, my = glfw.get_cursor_pos(window)
            px, py = renderer.screen_to_pentagrid(mx, my, width, height)
            renderer.interaction_manager.handle_click(px, py)
            if audio_manager:
                audio_manager.on_click(renderer.interaction_manager.click_mode, px, py)

def cursor_position_callback(window, xpos, ypos):
    """Handle cursor movement for tile hover."""
    global renderer, width, height, demo_controller
    if demo_controller:
        demo_controller.on_user_input()
    if renderer and renderer.interaction_manager:
        px, py = renderer.screen_to_pentagrid(xpos, ypos, width, height)
        renderer.interaction_manager.update_hover(px, py)
        # Dirty tracking handles GPU upload — no full re-upload needed here

def cursor_enter_callback(window, entered):
    """Clear hover when cursor leaves the window."""
    global renderer
    if not entered and renderer and renderer.interaction_manager:
        renderer.interaction_manager.clear_hover()

def _start_gamma_fade(new_gamma):
    """Start a fade-to-black → apply gamma → fade-back-in sequence."""
    global config_data, tween_engine, renderer, _pending_gamma, audio_manager
    logger.info(f"_start_gamma_fade called, tween_engine={tween_engine is not None}")
    if not tween_engine:
        # No tween engine, apply immediately
        config_data['gamma'] = new_gamma
        op.update_config_file(CONFIG_PATH, **config_data)
        return
    # If a brightness tween is already active (mid-fade), queue the gamma
    if tween_engine.is_active('brightness'):
        _pending_gamma = new_gamma
        return
    _pending_gamma = None
    captured_gamma = list(new_gamma)
    def on_fade_out_complete():
        global config_data, _pending_gamma
        # Apply the newest gamma (could have been updated during fade)
        gamma_to_apply = _pending_gamma if _pending_gamma is not None else captured_gamma
        _pending_gamma = None
        config_data['gamma'] = list(gamma_to_apply)
        renderer.set_gamma(list(gamma_to_apply))
        op.update_config_file(CONFIG_PATH, **config_data)
        # Fade back in
        tween_engine.start('brightness', 0.0, 1.0, 0.5, 'ease_out',
                           on_complete=on_fade_in_complete)
    def on_fade_in_complete():
        tween_engine.brightness_multiplier = 1.0
    # Start fade to black
    tween_engine.start('brightness', 1.0, 0.0, 0.5, 'ease_in',
                       on_complete=on_fade_out_complete)

def _start_shader_fade():
    """Start a fade-to-black → switch shader → fade-back-in sequence."""
    global tween_engine, renderer, _pending_shader, audio_manager
    logger.info(f"_start_shader_fade called, tween_engine={tween_engine is not None}")
    if not tween_engine:
        # No tween engine, switch immediately
        if renderer:
            renderer.next_effect()
        return
    # If a brightness tween is already active (mid-fade), queue the shader switch
    if tween_engine.is_active('brightness'):
        _pending_shader = True
        return
    _pending_shader = False
    def on_fade_out_complete():
        global _pending_shader
        if renderer:
            effect_idx = renderer.next_effect()
            if audio_manager:
                audio_manager.on_effect_change(effect_idx)
        # If another shader switch was queued, it will be handled on next event
        _pending_shader = False
        # Fade back in
        tween_engine.start('brightness', 0.0, 1.0, 0.5, 'ease_out',
                           on_complete=on_fade_in_complete)
    def on_fade_in_complete():
        tween_engine.brightness_multiplier = 1.0
    # Start fade to black
    tween_engine.start('brightness', 1.0, 0.0, 0.5, 'ease_in',
                       on_complete=on_fade_out_complete)

def key_callback(window, key, scancode, action, mods):
    global config_data, gui_overlay, fullscreen_mode, width, height, renderer, audio_manager, tween_engine, demo_controller, depth_camera_manager
    if demo_controller:
        demo_controller.on_user_input()
    if action == glfw.PRESS or action == glfw.REPEAT:
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif key == glfw.KEY_LEFT_BRACKET:
            if renderer:
                renderer.set_edge_thickness(renderer.edge_thickness - 0.1)
        elif key == glfw.KEY_RIGHT_BRACKET:
            if renderer:
                renderer.set_edge_thickness(renderer.edge_thickness + 0.1)
        # Camera zoom/reset controls (panning handled via per-frame polling for 8-way input)
        elif renderer:
            if key == glfw.KEY_PAGE_UP:
                renderer.zoom_by(1.1)
            elif key == glfw.KEY_PAGE_DOWN:
                renderer.zoom_by(0.9)
            elif key == glfw.KEY_HOME:
                renderer.reset()
    if action == glfw.PRESS:
        if key == glfw.KEY_F1:
            if gui_overlay:
                gui_overlay.toggle_visibility()
        elif key == glfw.KEY_F11:
            toggle_fullscreen(window)
        if key == glfw.KEY_SPACE:
            if renderer:
                _start_shader_fade()
        elif key == glfw.KEY_TAB:
            # Cycle interaction mode: select → ripple → symmetry
            if renderer and renderer.interaction_manager:
                mode = renderer.interaction_manager.cycle_click_mode()
                mode_names = ['select', 'ripple', 'symmetry']
                logger.info(f"Interaction mode: {mode_names[mode]}")
        elif key == glfw.KEY_C:
            # Clear all interaction state
            if renderer and renderer.interaction_manager:
                renderer.interaction_manager.clear_all()
                logger.info("Cleared all interactions")
        elif key == glfw.KEY_M:
            # Toggle depth mask layer
            if renderer:
                renderer.depth_mask_enabled = not renderer.depth_mask_enabled
                if not renderer.depth_mask_enabled and renderer.overlay_renderer:
                    renderer.overlay_renderer.set_mask_enabled(False)
                logger.info(f"Depth mask layer: {'ON' if renderer.depth_mask_enabled else 'OFF'}")
        elif key == glfw.KEY_R:
            logger.info("KEY R pressed: setting randomize_colors_event")
            randomize_colors_event.set()
            if audio_manager:
                audio_manager.on_color_change(config_data.get('color1', [128,128,128]),
                                              config_data.get('color2', [128,128,128]))
        elif key == glfw.KEY_G:
            if renderer:
                import random as _rnd
                new_gamma = [_rnd.uniform(0.0, 1.0) for _ in range(5)]
                _start_gamma_fade(new_gamma)
                logger.info(f"Gamma randomized: {new_gamma}")
                if audio_manager:
                    audio_manager.on_gamma_change()
        elif key == glfw.KEY_UP:
            renderer.zoom_by(1.15)
        elif key == glfw.KEY_DOWN:
            renderer.zoom_by(0.85)
        elif key in [glfw.KEY_1, glfw.KEY_2, glfw.KEY_3]:
            if 'cycle' not in config_data:
                config_data['cycle'] = '[False, False, False]'
            try:
                cycle_list = eval(config_data['cycle'])
                if not isinstance(cycle_list, list) or len(cycle_list) != 3:
                    cycle_list = [False, False, False]
            except:
                cycle_list = [False, False, False]
            if key == glfw.KEY_1:
                cycle_list[0] = not cycle_list[0]
            elif key == glfw.KEY_2:
                cycle_list[1] = not cycle_list[1]
            elif key == glfw.KEY_3:
                cycle_list[2] = not cycle_list[2]
            config_data['cycle'] = str(cycle_list)
            op.update_config_file(CONFIG_PATH, **config_data)
            update_event.set()
            logger.info(f"Cycle settings updated to: {config_data['cycle']}")

        # Depth camera range controls
        elif key == glfw.KEY_EQUAL and depth_camera_manager:
            raw = getattr(depth_camera_manager, '_raw_unit_mode', False)
            step = 10 if raw else 500
            depth_camera_manager.set_depth_range(
                depth_camera_manager.depth_min_mm,
                depth_camera_manager.depth_max_mm + step)
            unit = "raw" if raw else "mm"
            logger.info(f"Depth range: {depth_camera_manager.depth_min_mm}-"
                        f"{depth_camera_manager.depth_max_mm} {unit}")
        elif key == glfw.KEY_MINUS and depth_camera_manager:
            raw = getattr(depth_camera_manager, '_raw_unit_mode', False)
            step = 10 if raw else 500
            floor = 10 if raw else 1000
            depth_camera_manager.set_depth_range(
                depth_camera_manager.depth_min_mm,
                max(floor, depth_camera_manager.depth_max_mm - step))
            unit = "raw" if raw else "mm"
            logger.info(f"Depth range: {depth_camera_manager.depth_min_mm}-"
                        f"{depth_camera_manager.depth_max_mm} {unit}")
        elif key == glfw.KEY_COMMA and depth_camera_manager:
            raw = getattr(depth_camera_manager, '_raw_unit_mode', False)
            step = 5 if raw else 100
            depth_camera_manager.set_depth_range(
                max(0, depth_camera_manager.depth_min_mm - step),
                depth_camera_manager.depth_max_mm)
            unit = "raw" if raw else "mm"
            logger.info(f"Depth range: {depth_camera_manager.depth_min_mm}-"
                        f"{depth_camera_manager.depth_max_mm} {unit}")
        elif key == glfw.KEY_PERIOD and depth_camera_manager:
            raw = getattr(depth_camera_manager, '_raw_unit_mode', False)
            step = 5 if raw else 100
            depth_camera_manager.set_depth_range(
                min(depth_camera_manager.depth_min_mm + step,
                    depth_camera_manager.depth_max_mm - step),
                depth_camera_manager.depth_max_mm)
            unit = "raw" if raw else "mm"
            logger.info(f"Depth range: {depth_camera_manager.depth_min_mm}-"
                        f"{depth_camera_manager.depth_max_mm} {unit}")
        elif key == glfw.KEY_I and depth_camera_manager:
            depth_camera_manager.set_invert(not depth_camera_manager.invert)
            logger.info(f"Depth invert: {depth_camera_manager.invert}")

def main():
    global width, height, config_data, gui_overlay, fullscreen_mode, renderer, audio_manager, tween_engine, demo_controller, depth_camera_manager

    parser = argparse.ArgumentParser(description="Penrose Tiling Generator")
    parser.add_argument('--fullscreen', action='store_true', help='Run in fullscreen mode')
    parser.add_argument('-bt', '--bluetooth', action='store_true', help='Use Bluetooth server instead of HTTP')
    parser.add_argument('--local', action='store_true', help='Run in local mode without server components')
    parser.add_argument('--camera', action='store_true', help='Enable webcam capture for interaction/depth processing')
    parser.add_argument('--depth-camera', action='store_true', help='Enable Orbbec depth camera for depth-based tile coloring')
    parser.add_argument('--audio', action='store_true', help='Enable reactive audio feedback (requires signalflow)')
    parser.add_argument('--audio-mode', choices=['stereo', 'surround'], default='stereo', help='Audio output mode: stereo or 5.1 surround')
    parser.add_argument('--demo', action='store_true', help='Enable autonomous demo mode')
    parser.add_argument('--demo-idle', type=float, default=2.0, help='Idle timeout in minutes before demo resumes (default: 2.0)')
    parser.add_argument('--render-scale', type=float, default=0.5, help='Render resolution scale (0.25-1.0, default 0.5 = half res)')
    args = parser.parse_args()

    # Set environment variable for local mode
    if args.local:
        os.environ['PENROSE_LOCAL_MODE'] = '1'

    # Check if bluetooth was requested but not available
    if args.bluetooth and not BLUETOOTH_AVAILABLE:
        logger.warning("Bluetooth support not available. Running in local mode.")
        args.local = True
        args.bluetooth = False

    # Check if camera was requested but not available
    if args.camera and not CAMERA_AVAILABLE:
        logger.warning("Camera support not available (opencv-python not installed). Continuing without camera.")
        args.camera = False

    # Initialize variables that may be used in finally block
    cycle_manager = None
    gui_overlay = None
    camera_manager = None
    arcade_input = ArcadeInput()

    try:
        logger.info("Starting the penrose generator script.")
        logger.info("Using GPU procedural renderer (infinite mode)")
        window, using_gles = setup_window(fullscreen=args.fullscreen)

        # Set initial fullscreen state
        fullscreen_mode = args.fullscreen

        # Initialize OpenGL settings
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0, 0, 0, 1)

        # Setup viewport using framebuffer size (differs from window size on HiDPI/Retina)
        fb_width, fb_height = glfw.get_framebuffer_size(window)
        glViewport(0, 0, fb_width, fb_height)

        # Set shared GL config before any renderer init
        from penrose_tools import gl_config
        gl_config.use_gles = using_gles

        # Initialize ProceduralRenderer after OpenGL context is created
        renderer = ProceduralRenderer()
        renderer.render_scale = max(0.25, min(1.0, args.render_scale))
        logger.info(f"Render scale: {renderer.render_scale} ({int(renderer.render_scale*100)}% resolution)")
        initial_zoom = float(config_data.get('zoom', 1.0))
        renderer.set_zoom(initial_zoom)
        renderer.zoom = initial_zoom  # Skip interpolation for initial value

        # Initialize tween engine for smooth visual transitions
        tween_engine = TweenEngine()
        renderer.tween_engine = tween_engine

        # Initialize demo controller if --demo flag is set
        if args.demo:
            demo_controller = DemoController(renderer, tween_engine, CONFIG_PATH, idle_timeout_minutes=args.demo_idle)
            logger.info(f"Demo mode enabled (idle timeout: {args.demo_idle} minutes)")

        # Initialize GUI overlay
        gui_overlay = GUIOverlay()
        # Initialize OpenGL resources immediately while context is available
        gui_overlay.initialize_gl_resources()
        
        # Initialize server only if not in local mode
        if not args.local:
            if args.bluetooth:
                server_thread = Thread(target=run_bluetooth_server, 
                                    args=(CONFIG_PATH, update_event, toggle_shader_event,
                                         randomize_colors_event, shutdown_event),
                                    daemon=True)
            else:
                server_thread = Thread(target=run_server, daemon=True)
            
            server_thread.start()
            cycle_manager = CycleManager(CONFIG_PATH, update_event, toggle_shader_event, randomize_colors_event)
            cycle_manager.start()
            logger.info(f"{'Bluetooth' if args.bluetooth else 'HTTP'} server started.")
        else:
            logger.info("Running in local mode - no server components initialized")

        # Initialize camera capture if requested
        camera_manager = None
        depth_camera_manager = None

        if args.camera:
            if CAMERA_AVAILABLE:
                camera_manager = CameraManager(camera_index=0, width=640, height=480, fps=30)
                if camera_manager.start():
                    logger.info("Camera capture started")
                else:
                    logger.warning("Failed to start camera capture")
                    camera_manager = None
            else:
                logger.warning("--camera requested but CameraManager not available (install opencv-python)")

        if args.depth_camera:
            if DEPTH_CAMERA_AVAILABLE:
                depth_camera_manager = DepthCameraManager(
                    width=640, height=480, fps=30,
                    depth_min_mm=500, depth_max_mm=4000,
                    invert=True  # Closer objects are brighter
                )
                if depth_camera_manager.start():
                    logger.info("Depth camera capture started")
                    logger.info("Depth range: 500-4000mm, inverted (closer=brighter)")
                    # Enable depth mask layer (works with any active effect)
                    renderer.depth_mask_enabled = True
                    logger.info("Depth mask layer enabled (works with any effect)")
                else:
                    logger.warning("Failed to start depth camera capture")
                    depth_camera_manager = None
            else:
                logger.warning("--depth-camera requested but DepthCameraManager not available (install openni package)")

        # Initialize audio feedback if requested
        if args.audio:
            if AUDIO_AVAILABLE:
                try:
                    audio_manager = AudioManager(mode=args.audio_mode)
                    logger.info(f"Audio feedback started (mode={args.audio_mode})")
                except Exception as e:
                    logger.warning(f"Failed to start audio feedback: {e}")
                    audio_manager = None
            else:
                logger.warning("--audio requested but signalflow not installed (pip install signalflow)")

        logger.info("Controls: WASD=pan, PageUp/Down=zoom, Home=reset, SPACE=effect, G=gamma, R=colors, M=depth mask")
        logger.info("Interaction: Click=interact, TAB=cycle mode (select/cascade/ripple/mask_stamp), C=clear")

        last_time = glfw.get_time()
        prev_frame_time = last_time
        while not glfw.window_should_close(window) and running:
            glfw.poll_events()
            glClear(GL_COLOR_BUFFER_BIT)

            # Calculate delta time for tween updates
            current_time = glfw.get_time()
            dt = current_time - prev_frame_time
            dt = max(0.0, min(dt, 0.1))  # Clamp to avoid large jumps
            prev_frame_time = current_time

            # 8-way panning: poll WASD key state every frame for diagonal movement
            if renderer:
                pan_x = 0
                pan_y = 0
                if glfw.get_key(window, glfw.KEY_W) == glfw.PRESS:
                    pan_y += 1
                if glfw.get_key(window, glfw.KEY_S) == glfw.PRESS:
                    pan_y -= 1
                if glfw.get_key(window, glfw.KEY_A) == glfw.PRESS:
                    pan_x -= 1
                if glfw.get_key(window, glfw.KEY_D) == glfw.PRESS:
                    pan_x += 1

                # Arcade stick panning (remapped to real-space orientation)
                arcade_pan_x, arcade_pan_y, arcade_buttons = arcade_input.poll()
                pan_x += arcade_pan_x
                pan_y += arcade_pan_y

                if pan_x != 0 or pan_y != 0:
                    # Normalize diagonal so it doesn't move faster than cardinal
                    length = (pan_x ** 2 + pan_y ** 2) ** 0.5
                    renderer.move_direction(pan_x / length, pan_y / length)

                # Handle arcade button events
                for btn in arcade_buttons:
                    if demo_controller:
                        demo_controller.on_user_input()
                    if btn == 'randomize_colors':
                        randomize_colors_event.set()
                    elif btn == 'randomize_gamma':
                        randomize_gamma_event.set()
                    elif btn == 'toggle_shader':
                        toggle_shader_event.set()
                    elif btn == 'reset_viewport':
                        reset_viewport_event.set()

            # Handle events
            if randomize_colors_event.is_set():
                randomize_colors_event.clear()
                logger.info("COLOR EVENT: randomize_colors_event fired in main loop")
                # Generate two colors with guaranteed hue and lightness separation
                import colorsys
                h1 = np.random.random()
                s1 = np.random.uniform(0.5, 1.0)
                l1 = np.random.uniform(0.3, 0.7)
                # Force color2 hue at least 90° away (0.25 in [0,1])
                h2 = (h1 + np.random.uniform(0.25, 0.75)) % 1.0
                s2 = np.random.uniform(0.5, 1.0)
                # Push lightness to opposite bracket
                l2 = np.random.uniform(0.3, 0.7)
                if abs(l2 - l1) < 0.15:
                    l2 = 1.0 - l1  # flip to opposite end
                r1, g1, b1 = colorsys.hls_to_rgb(h1, l1, s1)
                r2, g2, b2 = colorsys.hls_to_rgb(h2, l2, s2)
                new_c1 = [int(r1 * 255), int(g1 * 255), int(b1 * 255)]
                new_c2 = [int(r2 * 255), int(g2 * 255), int(b2 * 255)]
                # Get current colors (from active tween or config)
                if tween_engine and tween_engine.is_active('color'):
                    current = tween_engine.get('color')
                    old_c1 = [current[0], current[1], current[2]]
                    old_c2 = [current[3], current[4], current[5]]
                else:
                    old_c1 = list(config_data['color1'])
                    old_c2 = list(config_data['color2'])
                # Store final colors for when tween completes
                pending_c1 = list(new_c1)
                pending_c2 = list(new_c2)
                def on_color_complete():
                    config_data['color1'] = pending_c1
                    config_data['color2'] = pending_c2
                    op.update_config_file(CONFIG_PATH, **config_data)
                tween_engine.start(
                    'color',
                    old_c1 + old_c2,
                    new_c1 + new_c2,
                    1.0,
                    'ease_in_out',
                    on_complete=on_color_complete
                )
            if update_event.is_set():
                update_event.clear()
                config_data = op.read_config_file(CONFIG_PATH)
            if toggle_shader_event.is_set():
                toggle_shader_event.clear()
                _start_shader_fade()
            if randomize_gamma_event.is_set():
                randomize_gamma_event.clear()
                if renderer:
                    import random as _rnd
                    new_gamma = [_rnd.uniform(0.0, 1.0) for _ in range(5)]
                    _start_gamma_fade(new_gamma)
                    logger.info(f"Arcade: gamma randomized: {new_gamma}")
                    if audio_manager:
                        audio_manager.on_gamma_change()
            if reset_viewport_event.is_set():
                reset_viewport_event.clear()
                if renderer:
                    renderer.reset()
                    logger.info("Arcade: viewport reset to center")

            # Update viewport with framebuffer size (handles HiDPI/Retina and resizes)
            fb_width, fb_height = glfw.get_framebuffer_size(window)
            glViewport(0, 0, fb_width, fb_height)

            # Process depth camera frames if available
            if depth_camera_manager and depth_camera_manager.is_running:
                depth_frame, _ts = depth_camera_manager.get_depth()
                if depth_frame is not None:
                    # Resize depth frame to mask resolution and upload to renderer
                    mask_resolution = renderer._mask_resolution
                    depth_resized = depth_camera_manager.resize_for_mask(depth_frame, mask_resolution)
                    renderer.upload_external_mask(depth_resized, mask_resolution, mask_resolution)

            # Update audio drones with current state
            if audio_manager:
                audio_manager.update_pan(renderer.velocity_x, renderer.velocity_y)
                # Drive pulse drone when pulse shader is active
                is_pulse = renderer.get_effect_name() == 'pulse'
                audio_manager.update_pulse(
                    active=is_pulse,
                    zoom=renderer.zoom,
                )
                # Drive eye_spy drone from depth camera state
                is_eye_spy = renderer.get_effect_name() == 'eye_spy'
                audio_manager.update_eye_spy(
                    active=is_eye_spy,
                    centroid_x=renderer._depth_centroid[0],
                    centroid_y=renderer._depth_centroid[1],
                    coverage=renderer._depth_coverage,
                    motion=renderer._depth_motion,
                    depth_available=renderer._depth_data_available,
                )

            # Update tween engine before rendering
            tween_engine.update(dt)
            # Sync brightness_multiplier from active brightness tween
            brightness_val = tween_engine.get('brightness')
            if brightness_val is not None:
                tween_engine.brightness_multiplier = brightness_val
            elif not tween_engine.is_active('brightness'):
                tween_engine.brightness_multiplier = 1.0

            # Update demo controller if active
            if demo_controller:
                demo_controller.update(dt)
            
            # Render procedural tiling
            renderer.render(fb_width, fb_height, config_data)

            glfw.swap_buffers(window)

            # Frame rate limiting — sleep to yield CPU to background threads
            frame_target = last_time + 1.0 / 60.0
            remaining = frame_target - glfw.get_time()
            if remaining > 0.001:
                time.sleep(remaining - 0.001)  # sleep most of the wait
            while glfw.get_time() < frame_target:  # spin only the last ~1ms for accuracy
                pass
            last_time = glfw.get_time()

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        # Clean up GUI overlay
        if gui_overlay:
            gui_overlay.cleanup()
        if camera_manager is not None:
            camera_manager.stop()
        if depth_camera_manager is not None:
            depth_camera_manager.stop()
        if audio_manager is not None:
            audio_manager.stop()
        arcade_input.close()
        glfw.terminate()
        if cycle_manager is not None:
            cycle_manager.stop()
        shutdown_event.set()
        logger.info("Application has been terminated.")

if __name__ == '__main__':
    main()