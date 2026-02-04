# penrose_generator.py
# Only export Bluetooth components if not in local mode
import os
if not os.environ.get('PENROSE_LOCAL_MODE'):
    try:
        from .PenroseBluetoothServer import run_bluetooth_server
        __all__ = ['Operations', 'run_server', 'Effects', 'Tile', 
                   'OptimizedRenderer', 'run_bluetooth_server']
    except ImportError:
        __all__ = ['Operations', 'run_server', 'Effects', 'Tile', 
                   'OptimizedRenderer']
else:
    __all__ = ['Operations', 'run_server', 'Effects', 'Tile', 
               'OptimizedRenderer']

import numpy as np
import glfw
from OpenGL.GL import *
from threading import Thread
from collections import OrderedDict
from penrose_tools import Operations, Tile, OptimizedRenderer, run_server, GUIOverlay
from penrose_tools.ProceduralRenderer import ProceduralRenderer
import logging
import configparser
import signal
import argparse
import asyncio
from penrose_tools.events import update_event, toggle_shader_event, randomize_colors_event, shutdown_event, toggle_regions_event, toggle_gui_event
from threading import Timer
import random
import time
# Configuration and initialization
CONFIG_PATH = 'config.ini'
DEFAULT_CONFIG = {
    'size': 15,
    'scale': 20,
    'gamma': [1.0, 0.7, 0.5, 0.3, 0.1],
    'color1': [205, 255, 255],
    'color2': [0, 0, 255],
    'cycle' : [False,False,False],
    'timer' : 10,
    'shader_settings': {
        'no_effect': True,
        'shift_effect': True,
        'color_wave': True,
        'color_flow': True,
        'region_blend': True,
        'raindrop_ripple': True,
        'koi_pond': True,
        'pixelation_slideshow': True
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
use_procedural = False  # Track renderer mode

# Check if Bluetooth is available
try:
    from penrose_tools.PenroseBluetoothServer import run_bluetooth_server
    BLUETOOTH_AVAILABLE = True
except ImportError:
    BLUETOOTH_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Penrose_Generator')

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
            'size': str(int(DEFAULT_CONFIG['size'])),  # Ensure size is integer
            'scale': str(int(DEFAULT_CONFIG['scale'])),  # Convert scale to integer
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
    
    # Request OpenGL 3.1 context
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
    
    # Get the primary monitor
    primary_monitor = glfw.get_primary_monitor()
    
    if fullscreen:
        video_mode = glfw.get_video_mode(primary_monitor)
        width, height = video_mode.size.width, video_mode.size.height
        window = glfw.create_window(width, height, "Penrose Tiling", primary_monitor, None)
        # Hide cursor in fullscreen mode
        glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_HIDDEN)
    else:
        width, height = 1280, 720
        window = glfw.create_window(width, height, "Penrose Tiling", None, None)

    if not window:
        glfw.terminate()
        raise Exception("GLFW window can't be created")
    
    # Register key callback
    glfw.set_key_callback(window, key_callback)
    
    # Register scroll callback for zoom
    glfw.set_scroll_callback(window, scroll_callback)
    
    glfw.make_context_current(window)
    
    # Enable MSAA (Multi-Sample Anti-Aliasing)
    glfw.window_hint(glfw.SAMPLES, 4)
    
    # After creating the window:
    glDisable(GL_MULTISAMPLE)
    
    return window

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

    # Update viewport
    glViewport(0, 0, width, height)

def update_toggles(shaders):
    global config_data, running
    logger.debug("Checking for events...")
    if randomize_colors_event.is_set():
        logger.info("Randomize Colors Event Detected")
        for i in range(3):
            config_data['color1'][i] = np.random.randint(0, 256)
            config_data['color2'][i] = np.random.randint(0, 256)
        randomize_colors_event.clear()
        op.update_config_file(CONFIG_PATH, **config_data)
    if update_event.is_set():
        logger.info("Update Event Detected")
        update_event.clear()
        config_data = op.read_config_file(CONFIG_PATH)
    if toggle_shader_event.is_set():
        logger.info("Toggle Shader Event Detected - Before toggle")
        toggle_shader_event.clear()
        next_index = shaders.next_shader()
        logger.info(f"Shader switched to index {next_index}")
    if shutdown_event.is_set():
        logger.info("Shutdown Event Detected")
        running = False
        return False

def scroll_callback(window, xoffset, yoffset):
    """Handle mouse scroll for zoom in procedural mode."""
    global renderer, use_procedural
    if use_procedural and renderer:
        if yoffset > 0:
            renderer.zoom_by(1.15)  # Zoom in
        elif yoffset < 0:
            renderer.zoom_by(0.85)  # Zoom out

def key_callback(window, key, scancode, action, mods):
    global config_data, gui_overlay, fullscreen_mode, width, height, renderer, use_procedural
    if action == glfw.PRESS or action == glfw.REPEAT:
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif key == glfw.KEY_LEFT_BRACKET:
            if use_procedural and renderer:
                renderer.set_edge_thickness(renderer.edge_thickness - 0.1)
            else:
                config_data['vertex_offset'] = f"{max(-0.1, float(config_data['vertex_offset']) - 0.0003):.6f}"
                op.update_config_file(CONFIG_PATH, **config_data)
                update_event.set()
        elif key == glfw.KEY_RIGHT_BRACKET:
            if use_procedural and renderer:
                renderer.set_edge_thickness(renderer.edge_thickness + 0.1)
            else:
                config_data['vertex_offset'] = f"{min(0.1, float(config_data['vertex_offset']) + 0.0003):.6f}"
                op.update_config_file(CONFIG_PATH, **config_data)
                update_event.set()
        # Camera controls for procedural mode
        elif use_procedural and renderer:
            if key == glfw.KEY_W:
                renderer.move_direction(0, 1)
            elif key == glfw.KEY_S:
                renderer.move_direction(0, -1)
            elif key == glfw.KEY_A:
                renderer.move_direction(-1, 0)
            elif key == glfw.KEY_D:
                renderer.move_direction(1, 0)
            elif key == glfw.KEY_PAGE_UP:
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
            if use_procedural and renderer:
                renderer.next_effect()
            else:
                toggle_shader_event.set()
        elif key == glfw.KEY_R:
            randomize_colors_event.set()
        elif key == glfw.KEY_G:
            if use_procedural and renderer:
                new_gamma = renderer.randomize_gamma()
                config_data['gamma'] = new_gamma
                op.update_config_file(CONFIG_PATH, **config_data)
                logger.info(f"Gamma randomized: {new_gamma}")
            else:
                config_data['gamma'] = [random.uniform(-1.0, 1.0) for _ in range(5)]
                op.update_config_file(CONFIG_PATH, **config_data)
                update_event.set()
        elif key == glfw.KEY_UP:
            config_data['scale'] = min(config_data['scale'] + 3, 60)
            op.update_config_file(CONFIG_PATH, **config_data)
            update_event.set()
        elif key == glfw.KEY_DOWN:
            config_data['scale'] = max(config_data['scale'] - 3, 30)
            op.update_config_file(CONFIG_PATH, **config_data)
            update_event.set()
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

def main():
    global width, height, config_data, gui_overlay, fullscreen_mode, renderer, use_procedural

    parser = argparse.ArgumentParser(description="Penrose Tiling Generator")
    parser.add_argument('--fullscreen', action='store_true', help='Run in fullscreen mode')
    parser.add_argument('-bt', '--bluetooth', action='store_true', help='Use Bluetooth server instead of HTTP')
    parser.add_argument('--local', action='store_true', help='Run in local mode without server components')
    parser.add_argument('-p', '--procedural', action='store_true', help='Use GPU procedural renderer (infinite zoom)')
    args = parser.parse_args()

    # Set environment variable for local mode
    if args.local:
        os.environ['PENROSE_LOCAL_MODE'] = '1'

    # Track renderer mode
    use_procedural = args.procedural

    # Check if bluetooth was requested but not available
    if args.bluetooth and not BLUETOOTH_AVAILABLE:
        logger.warning("Bluetooth support not available. Running in local mode.")
        args.local = True
        args.bluetooth = False

    try:
        logger.info("Starting the penrose generator script.")
        if use_procedural:
            logger.info("Using GPU procedural renderer (infinite mode)")
        window = setup_window(fullscreen=args.fullscreen)

        # Set initial fullscreen state
        fullscreen_mode = args.fullscreen

        # Initialize OpenGL settings
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0, 0, 0, 1)

        # Setup viewport only - no more matrix mode operations
        glViewport(0, 0, width, height)

        # Initialize renderer after OpenGL context is created
        if use_procedural:
            renderer = ProceduralRenderer()
        else:
            renderer = OptimizedRenderer()

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

        if use_procedural:
            logger.info("Controls: WASD=pan, PageUp/Down=zoom, Home=reset, SPACE=effect, G=gamma, R=colors")

        last_time = glfw.get_time()
        while not glfw.window_should_close(window) and running:
            glfw.poll_events()
            glClear(GL_COLOR_BUFFER_BIT)

            # Handle events
            if use_procedural:
                if randomize_colors_event.is_set():
                    randomize_colors_event.clear()
                    for i in range(3):
                        config_data['color1'][i] = np.random.randint(0, 256)
                        config_data['color2'][i] = np.random.randint(0, 256)
                    op.update_config_file(CONFIG_PATH, **config_data)
                if update_event.is_set():
                    update_event.clear()
                    config_data = op.read_config_file(CONFIG_PATH)
                # Render procedural tiling
                renderer.render(width, height, config_data)
            else:
                if any(event.is_set() for event in [update_event, toggle_shader_event, randomize_colors_event]):
                    update_toggles(renderer.shader_manager)
                # Render traditional tiles
                renderer.render_tiles(width, height, config_data)
                # Render GUI overlay (only for traditional mode)
                gui_overlay.render(width, height, config_data, renderer.shader_manager)

            glfw.swap_buffers(window)

            # Frame rate limiting
            while glfw.get_time() < last_time + 1.0 / 60.0:
                pass
            last_time = glfw.get_time()

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        # Clean up GUI overlay
        if gui_overlay:
            gui_overlay.cleanup()
        glfw.terminate()
        if not args.local:
            cycle_manager.stop()
        shutdown_event.set()
        logger.info("Application has been terminated.")

if __name__ == '__main__':
    main()