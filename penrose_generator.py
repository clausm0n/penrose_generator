# python_generator.py
import os
import numpy as np
import glfw
from OpenGL.GL import *
from threading import Thread
from collections import OrderedDict
from penrose_tools import Operations, Tile, OptimizedRenderer, run_server, run_bluetooth_server
import logging
import configparser
import signal
import argparse
import asyncio
from penrose_tools.events import update_event, toggle_shader_event, randomize_colors_event, shutdown_event, toggle_regions_event, toggle_gui_event

# Configuration and initialization
CONFIG_PATH = 'config.ini'
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

renderer = OptimizedRenderer()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Penrose_Generator')

def initialize_config(path):
    if not os.path.isfile(path):
        print("Config file not found. Creating a new one...")
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

config_data = initialize_config(CONFIG_PATH)
tiles_cache = OrderedDict()

def setup_projection(width, height):
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

def update_toggles(renderer):
    global config_data, running
    logger.debug("Checking for events...")
    logger.debug(f"Events Status - Update: {update_event.is_set()}, Toggle Shader: {toggle_shader_event.is_set()}, Randomize Colors: {randomize_colors_event.is_set()}")
    if randomize_colors_event.is_set():
        logger.info("Randomize Colors Event Detected")
        for i in range(3):
            config_data['color1'][i] = np.random.randint(0, 256)
            config_data['color2'][i] = np.random.randint(0, 256)
        randomize_colors_event.clear()
        op.update_config_file(CONFIG_PATH, **config_data)
        logger.info("Colors randomized successfully.")
    if update_event.is_set():
        logger.info("Update Event Detected")
        update_event.clear()
        config_data = op.read_config_file(CONFIG_PATH)
        logger.info("Configuration updated successfully.")
    if toggle_shader_event.is_set():
        logger.info("Toggle Shader Event Detected")
        toggle_shader_event.clear()
        renderer.shader_manager.next_shader()
        renderer.get_shader_locations()  # Update attribute and uniform locations
        logger.info("Shader toggled successfully.")
    if shutdown_event.is_set():
        logger.info("Shutdown Event Detected")
        running = False
        logger.info("Exiting application.")
        return False

def setup_window(fullscreen=False):
    global width, height
    if not glfw.init():
        raise Exception("GLFW can't be initialized")
    
    # Request OpenGL 2.1 context
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 2)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
    
    # Get the primary monitor
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
        raise Exception("GLFW window can't be created")
    
    glfw.make_context_current(window)
    
    # Print OpenGL version for debugging
    print(f"OpenGL Version: {glGetString(GL_VERSION).decode()}")
    print(f"GLSL Version: {glGetString(GL_SHADING_LANGUAGE_VERSION).decode()}")
    
    # Basic OpenGL setup
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glClearColor(0, 0, 0, 1)
    
    # Setup viewport and projection
    glViewport(0, 0, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    return window

def main():
    global width, height, config_data

    parser = argparse.ArgumentParser(description="Penrose Tiling Generator")
    parser.add_argument('--fullscreen', action='store_true', help='Run in fullscreen mode')
    parser.add_argument('-bt', '--bluetooth', action='store_true', help='Use Bluetooth server instead of HTTP')
    args = parser.parse_args()

    def signal_handler(sig, frame):
        global running
        print('Shutting down application...')
        running = False
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        logger.info("Starting the penrose generator script.")
        window = setup_window(fullscreen=args.fullscreen)
        last_time = glfw.get_time()

        if args.bluetooth:
            server_thread = Thread(target=run_bluetooth_server, 
                                args=(CONFIG_PATH, update_event, toggle_shader_event,
                                        randomize_colors_event, shutdown_event),
                                daemon=True)
            server_thread.start()
            logger.info("Bluetooth server started.")
        else:
            # HTTP server
            server_thread = Thread(target=run_server, daemon=True)
            server_thread.start()
            logger.info("HTTP server started.")

        while not glfw.window_should_close(window) and running:
            glfw.poll_events()
            glClear(GL_COLOR_BUFFER_BIT)

            # Check if any relevant event is set
            if any(event.is_set() for event in [update_event, toggle_shader_event, randomize_colors_event]):
                update_toggles(renderer)

            renderer.render_tiles(width, height, config_data)
            glfw.swap_buffers(window)

            # Frame rate control
            while glfw.get_time() < last_time + 1.0 / 60.0:
                pass
            last_time = glfw.get_time()

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        glfw.terminate()
        shutdown_event.set()
        logger.info("Application has been terminated.")

if __name__ == '__main__':
    main()
