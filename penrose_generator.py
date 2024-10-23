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
import asyncio

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
    print("Updating toggles...", update_event.is_set(), toggle_shader_event.is_set(), toggle_regions_event.is_set(), toggle_gui_event.is_set(), randomize_colors_event.is_set())
    if randomize_colors_event.is_set():
        for i in range(3):
            config_data['color1'][i] = np.random.randint(0, 256)
            config_data['color2'][i] = np.random.randint(0, 256)
        randomize_colors_event.clear()
        op.update_config_file(CONFIG_PATH, **config_data)
        print("Randomizing colors...")
    if update_event.is_set():
        update_event.clear()
        config_data = op.read_config_file(CONFIG_PATH)
        print("config_data updated...")
    if toggle_shader_event.is_set():
        toggle_shader_event.clear()
        shaders.next_shader()
    if shutdown_event.is_set():
        running = False
        print("Exiting...")
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
            logging.error(f"Error rendering tile: {e}")
            shaders.reset_state()
            continue

def setup_window(fullscreen=False):
    global width, height
    if not glfw.init():
        raise Exception("GLFW can't be initialized")
    
    # Get the primary monitor
    primary_monitor = glfw.get_primary_monitor()
    
    if fullscreen:
        # Get the video mode of the primary monitor
        video_mode = glfw.get_video_mode(primary_monitor)
        width, height = video_mode.size.width, video_mode.size.height
        
        # Create a fullscreen window
        window = glfw.create_window(width, height, "Penrose Tiling", primary_monitor, None)
    else:
        # Set the window size to 720p for windowed mode
        width, height = 1280, 720
        window = glfw.create_window(width, height, "Penrose Tiling", None, None)

    if not window:
        glfw.terminate()
        raise Exception("GLFW window can't be created")
    
    glfw.make_context_current(window)
    setup_projection(width, height)

    # Show the mouse cursor in windowed mode, hide it in fullscreen
    glfw.set_input_mode(window, glfw.CURSOR, 
                        glfw.CURSOR_HIDDEN if fullscreen else glfw.CURSOR_NORMAL)

    # Set up basic OpenGL configuration
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glClearColor(0, 0, 0, 1)  # Set clear color to black

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
        logging.info("Starting the penrose generator script.")
        window = setup_window(fullscreen=args.fullscreen)
        shaders = Shader()
        last_time = glfw.get_time()

        if args.bluetooth:
            # Instantiate BluetoothServer with required parameters
            from penrose_tools.BluetoothServer import BluetoothServer
            bluetooth_server = BluetoothServer(
                config_path=CONFIG_PATH,
                update_event=update_event,
                toggle_shader_event=toggle_shader_event,
                randomize_colors_event=randomize_colors_event,
                shutdown_event=shutdown_event
            )
            bluetooth_server.publish()
            logging.info("Bluetooth server started.")
        else:
            # HTTP server
            server_thread = Thread(target=run_server, daemon=True)
            server_thread.start()
            logging.info("HTTP server started.")

        while not glfw.window_should_close(window) and running:
            glfw.poll_events()
            glClear(GL_COLOR_BUFFER_BIT)

            # Check if any relevant event is set
            if any(event.is_set() for event in [update_event, toggle_shader_event, randomize_colors_event]):
                update_toggles(shaders)

            render_tiles(shaders, width, height)
            glfw.swap_buffers(window)

            # Frame rate control
            while glfw.get_time() < last_time + 1.0 / 60.0:
                pass
            last_time = glfw.get_time()

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise
    finally:
        glfw.terminate()
        shutdown_event.set()
        logging.info("Application has been terminated.")

if __name__ == '__main__':
    main()
