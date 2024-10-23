#!/usr/bin/env python3
# penrose_generator.py

import os
import numpy as np
import glfw
from OpenGL.GL import *
from threading import Thread
from collections import OrderedDict
from penrose_tools import Operations, Tile, Shader, run_server, update_event, toggle_shader_event, toggle_regions_event, toggle_gui_event, randomize_colors_event, shutdown_event
import logging
import configparser
import signal
import argparse
import threading

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("penrose_generator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration and initialization
CONFIG_PATH = '/etc/penrose/config.ini'  # Updated path to match bluetooth service
DEFAULT_CONFIG = {
    'size': 15,
    'scale': 15,
    'gamma': [1.0, 0.7, 0.5, 0.3, 0.1],
    'color1': [205, 255, 255],
    'color2': [0, 0, 255]
}

op = Operations()
gui_visible = False
running = True
width = 0
height = 0

def initialize_config(path):
    """Initialize configuration file with default values if it doesn't exist"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.isfile(path):
        logger.info("Config file not found. Creating a new one...")
        config = configparser.ConfigParser()
        config['Settings'] = {
            'size': str(DEFAULT_CONFIG['size']),
            'scale': str(DEFAULT_CONFIG['scale']),
            'gamma': ', '.join(map(str, DEFAULT_CONFIG['gamma'])),
            'color1': ', '.join(map(str, DEFAULT_CONFIG['color1'])),
            'color2': ', '.join(map(str, DEFAULT_CONFIG['color2']))
        }
        with open(path, 'w') as configfile:
            config.write(configfile)
    return op.read_config_file(path)

def setup_projection(width, height):
    """Set up OpenGL projection matrix"""
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

def setup_signal_handlers():
    """Set up signal handlers for IPC"""
    def handle_update_config(signum, frame):
        logger.info("Received config update signal")
        update_event.set()
        
    def handle_toggle_shader(signum, frame):
        logger.info("Received toggle shader signal")
        toggle_shader_event.set()
        
    def handle_randomize_colors(signum, frame):
        logger.info("Received randomize colors signal")
        randomize_colors_event.set()
        
    def handle_shutdown(signum, frame):
        logger.info("Received shutdown signal")
        global running
        running = False
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGUSR1, handle_update_config)
    signal.signal(signal.SIGUSR2, handle_toggle_shader)
    signal.signal(signal.SIGHUP, handle_randomize_colors)
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

def update_toggles(shaders):
    """Handle toggle events"""
    global config_data, running
    
    logger.debug(f"Checking toggles... Update: {update_event.is_set()}, Toggle Shader: {toggle_shader_event.is_set()}, Randomize Colors: {randomize_colors_event.is_set()}")
    
    if randomize_colors_event.is_set():
        for i in range(3):
            config_data['color1'][i] = np.random.randint(0, 256)
            config_data['color2'][i] = np.random.randint(0, 256)
        randomize_colors_event.clear()
        op.update_config_file(CONFIG_PATH, **config_data)
        logger.info("Colors randomized")
        
    if update_event.is_set():
        update_event.clear()
        config_data = op.read_config_file(CONFIG_PATH)
        logger.info("Configuration updated")
        
    if toggle_shader_event.is_set():
        toggle_shader_event.clear()
        shaders.next_shader()
        logger.info("Shader toggled")
        
    if shutdown_event.is_set():
        running = False
        logger.info("Shutdown initiated")
        return False

def render_tiles(shaders, width, height):
    """Render Penrose tiles"""
    global config_data, tiles_cache
    current_time = glfw.get_time() * 1000

    gamma_values = config_data['gamma']
    scale_value = config_data['scale']
    color1 = tuple(config_data["color1"])
    color2 = tuple(config_data["color2"])
    config_key = (tuple(gamma_values), width, height, scale_value, color1, color2)

    if config_key not in tiles_cache:
        tiles_cache.clear()
        logger.info("Cache cleared")
        logger.info(f"Rendering tiles... {gamma_values}, {scale_value}, {color1}, {color2}")
        tiles_objects = op.tiling(gamma_values, width, height, scale_value)
        op.calculate_neighbors(tiles_objects)
        tiles_cache[config_key] = tiles_objects

    visible_tiles = tiles_cache[config_key]
    center = complex(width // 2, height // 2)
    shader_func = shaders.current_shader()

    for tile in visible_tiles:
        try:
            modified_color = shader_func(tile, current_time, visible_tiles, color1, color2, width, height, scale_value)
            vertices = op.to_canvas(tile.vertices, scale_value, center, 3)
            glBegin(GL_POLYGON)
            glColor4ub(*modified_color)
            for vertex in vertices:
                glVertex2f(vertex[0], vertex[1])
            glEnd()
        except Exception as e:
            logger.error(f"Error rendering tile: {e}")
            shaders.reset_state()
            continue

def setup_window(fullscreen=False):
    """Initialize GLFW window"""
    global width, height
    
    if not glfw.init():
        logger.error("GLFW initialization failed")
        raise Exception("GLFW initialization failed")
    
    primary_monitor = glfw.get_primary_monitor()
    
    if fullscreen:
        video_mode = glfw.get_video_mode(primary_monitor)
        width, height = video_mode.size.width, video_mode.size.height
        window = glfw.create_window(width, height, "Penrose Tiling", primary_monitor, None)
    else:
        width, height = 1280, 720
        window = glfw.create_window(width, height, "Penrose Tiling", None, None)

    if not window:
        glfw.terminate()
        logger.error("GLFW window creation failed")
        raise Exception("GLFW window creation failed")
    
    glfw.make_context_current(window)
    setup_projection(width, height)

    glfw.set_input_mode(window, glfw.CURSOR, 
                       glfw.CURSOR_HIDDEN if fullscreen else glfw.CURSOR_NORMAL)

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glClearColor(0, 0, 0, 1)

    return window

def render_loop(window, shaders, last_time):
    """Main rendering loop"""
    global running
    running = True

    while not glfw.window_should_close(window) and running:
        glfw.poll_events()
        glClear(GL_COLOR_BUFFER_BIT)

        if any(event.is_set() for event in [update_event, toggle_shader_event, randomize_colors_event, shutdown_event]):
            update_toggles(shaders)

        render_tiles(shaders, width, height)
        glfw.swap_buffers(window)

        # Frame rate control
        while glfw.get_time() < last_time + 1.0 / 60.0:
            pass
        last_time = glfw.get_time()

def main():
    """Main function"""
    global config_data

    parser = argparse.ArgumentParser(description="Penrose Tiling Generator")
    parser.add_argument('--fullscreen', action='store_true', help='Run in fullscreen mode')
    args = parser.parse_args()

    try:
        logger.info("Starting Penrose Generator")
        
        # Initialize configuration
        config_data = initialize_config(CONFIG_PATH)
        
        # Setup signal handlers for IPC
        setup_signal_handlers()
        
        # Create window and initialize OpenGL
        window = setup_window(fullscreen=args.fullscreen)
        shaders = Shader()
        last_time = glfw.get_time()

        # Create PID file
        pid = os.getpid()
        with open('/var/run/penrose-generator.pid', 'w') as f:
            f.write(str(pid))
        logger.info(f"PID file created: {pid}")

        # Start HTTP server in separate thread
        server_thread = Thread(target=run_server, daemon=True)
        server_thread.start()
        logger.info("HTTP server started")

        # Start render loop
        render_loop(window, shaders, last_time)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        glfw.terminate()
        # Clean up PID file
        try:
            os.remove('/var/run/penrose-generator.pid')
        except:
            pass
        logger.info("Application terminated")

if __name__ == '__main__':
    main()