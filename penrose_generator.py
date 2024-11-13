import os
import numpy as np
import glfw
from OpenGL.GL import *
from threading import Thread
from collections import OrderedDict
from penrose_tools import Operations, Tile, Effects,OptimizedRenderer, run_server, run_bluetooth_server
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


def update_toggles(shaders):
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
        shaders.next_shader()
        logger.info("Shader toggled successfully.")
    if shutdown_event.is_set():
        logger.info("Shutdown Event Detected")
        running = False
        logger.info("Exiting application.")
        return False

def render_tiles(shaders, width, height):
    global config_data, tiles_cache
    current_time = glfw.get_time() * 1000  # Convert to milliseconds

    gamma_values = config_data['gamma']
    scale_value = config_data['scale']
    color1 = tuple(config_data["color1"])
    color2 = tuple(config_data["color2"])
    config_key = (tuple(gamma_values), width, height, scale_value, color1, color2)
    
    if config_key not in tiles_cache:
        tiles_cache.clear()
        print("Cache cleared")
        print("Rendering tiles...", gamma_values, scale_value, color1, color2)
        tiles_objects = op.tiling(gamma_values, width, height, scale_value)
        op.calculate_neighbors(tiles_objects)
        tiles_cache[config_key] = tiles_objects

    visible_tiles = tiles_cache[config_key]
    center = complex(width // 2, height // 2)
    shader_func = shaders.current_shader()

    for tile in visible_tiles:
        try:
            modified_color = shader_func(tile, current_time, visible_tiles, color1, color2, width, height,scale_value)
            vertices = op.to_canvas(tile.vertices, scale_value, center,3)
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
    global width, height, config_data, renderer

    parser = argparse.ArgumentParser(description="Penrose Tiling Generator")
    parser.add_argument('--fullscreen', action='store_true', help='Run in fullscreen mode')
    parser.add_argument('-bt', '--bluetooth', action='store_true', help='Use Bluetooth server instead of HTTP')
    args = parser.parse_args()

    try:
        logger.info("Starting the penrose generator script.")
        window = setup_window(fullscreen=args.fullscreen)
        
        # Initialize renderer after OpenGL context is created
        renderer = OptimizedRenderer()
        
        if args.bluetooth:
            server_thread = Thread(target=run_bluetooth_server, 
                                args=(CONFIG_PATH, update_event, toggle_shader_event,
                                        randomize_colors_event, shutdown_event),
                                daemon=True)
            server_thread.start()
            logger.info("Bluetooth server started.")
        else:
            server_thread = Thread(target=run_server, daemon=True)
            server_thread.start()
            logger.info("HTTP server started.")

        last_time = glfw.get_time()
        while not glfw.window_should_close(window) and running:
            glfw.poll_events()
            glClear(GL_COLOR_BUFFER_BIT)

            if any(event.is_set() for event in [update_event, toggle_shader_event, randomize_colors_event]):
                update_toggles(renderer.shader_manager)

            renderer.render_tiles(width, height, config_data)
            glfw.swap_buffers(window)

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
