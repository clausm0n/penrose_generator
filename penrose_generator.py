import os
import numpy as np
import glfw
from OpenGL.GL import *
from threading import Thread
from collections import OrderedDict
from penrose_tools import Operations, Tile, Shader, run_server, update_event, toggle_shader_event, toggle_regions_event, toggle_gui_event, randomize_colors_event, shutdown_event
from logging

# Configuration and initialization
CONFIG_PATH = 'config.ini'
DEFAULT_CONFIG = {
    'width': 500,
    'height': 500,
    'size': 56,
    'scale': 6,
    'gamma': [1.0, 0.7, 0.5, 0.3, 0.1],
    'color1': [205, 255, 255],
    'color2': [0, 0, 255]
}

op = Operations()
gui_visible = False
running = True

def initialize_config(path):
    if not os.path.isfile(path):
        print("Config file not found. Creating a new one...")
        op.write_config_file(*DEFAULT_CONFIG.values())
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

def render_tiles(shaders):
    global config_data, tiles_cache
    width, height = config_data['width'], config_data['height']
    current_time = glfw.get_time() * 1000  # Convert to milliseconds

    gamma_values = config_data['gamma']
    size_value = config_data['size']
    scale_value = config_data['scale']
    color1 = tuple(config_data["color1"])
    color2 = tuple(config_data["color2"])
    config_key = (tuple(gamma_values), size_value, color1, color2)
    
    if config_key not in tiles_cache:
        tiles_cache.clear()
        print("Cache cleared")
        print("Rendering tiles...", gamma_values, size_value, scale_value, color1, color2)
        tiles_data = op.tiling(gamma_values, size_value)
        tiles_objects = [Tile(vertices, color) for vertices, color in tiles_data]
        op.calculate_neighbors(tiles_objects)
        tiles_cache[config_key] = tiles_objects

        # Calculate the geometric center of all tiles and determine central tiles
        all_vertices = np.concatenate([tile.vertices for tile in tiles_objects])
        geometric_center = np.mean(all_vertices, axis=0)
        distance_threshold = np.std(all_vertices) * 0.5  # Adjust this value based on observed clustering
        tiles_cache["central_tiles"] = [tile for tile in tiles_objects if np.linalg.norm(np.mean(tile.vertices, axis=0) - geometric_center) < distance_threshold]

    #tiles_objects = tiles_cache[config_key]
    central_tiles = tiles_cache["central_tiles"]
    shader_func = shaders.current_shader()

    for tile in central_tiles:
        modified_color = shader_func(tile, current_time, central_tiles, color1, color2)
        vertices = op.to_canvas(tile.vertices, scale_value, complex(width // 2, height // 2))
        glBegin(GL_POLYGON)
        # print("Color", modified_color)
        glColor4ub(*modified_color)
        for vertex in vertices:
            glVertex2f(vertex[0], vertex[1])
        glEnd()

def setup_window():
    if not glfw.init():
        raise Exception("GLFW can't be initialized")
    
    primary_monitor = glfw.get_primary_monitor()
    video_mode = glfw.get_video_mode(primary_monitor)

    if not video_mode:
        raise Exception("Failed to get video mode for the primary monitor")
        # Attempting to access width and height differently
    try:
        width, height = video_mode.size  # If video_mode.size is an attribute that returns a tuple
    except AttributeError:
        width = video_mode.width
        height = video_mode.height

    window = glfw.create_window(width, height, "Penrose Tiling", primary_monitor, None)
    if not window:
        glfw.terminate()
        raise Exception("GLFW window can't be created")
    
    glfw.make_context_current(window)
    setup_projection(config_data['width'], config_data['height'])

    # Hide the mouse cursor
    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_HIDDEN)

    # Set up basic OpenGL configuration
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glClearColor(0, 0, 0, 1)  # Set clear color to black

    return window

def main():
    try:
        logging.info("Starting the penrose generator script.")
        # Your existing code...
        window = setup_window()
        # More of your code...
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise
    window = setup_window()
    shaders = Shader()
    last_time = glfw.get_time()

    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

    while not glfw.window_should_close(window) and running:
        glfw.poll_events()
        glClear(GL_COLOR_BUFFER_BIT)

        if any(toggle_event.is_set() for toggle_event in [update_event, toggle_shader_event, toggle_regions_event, toggle_gui_event, randomize_colors_event]):
            update_toggles(shaders)

        render_tiles(shaders)
        glfw.swap_buffers(window)

        # Frame rate control
        while glfw.get_time() < last_time + 1.0 / 60.0:
            pass
        last_time = glfw.get_time()

    glfw.terminate()

if __name__ == '__main__':
    main()
