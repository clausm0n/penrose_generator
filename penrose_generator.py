import os
import time
import numpy as np
import pygame  # type: ignore
from threading import Thread
from collections import OrderedDict
from penrose_tools import Operations,Tile, Shader, run_server, update_event, toggle_shader_event, toggle_regions_event, toggle_gui_event, randomize_colors_event

# Configuration and initialization
CONFIG_PATH = 'config.ini'
DEFAULT_CONFIG = {
    'width': 1040,
    'height': 1860,
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

def handle_events(shaders, screen, config_data):
    global running  # This ensures we modify the global running variable
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            return False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                toggle_shader_event.set()
            elif event.key == pygame.K_g:
                global gui_visible
                gui_visible = not gui_visible
            elif event.key == pygame.K_r:
                toggle_regions_event.set()
            elif event.key == pygame.K_c:
                randomize_colors_event.set()
                print("Randomizing colors...")
            elif event.key == pygame.K_ESCAPE:  # Ensure this is directly under KEYDOWN
                running = False
                print("Exiting...")
                return False
    return True

def update_toggles(config_data, shaders):
    print("Updating toggles...", update_event.is_set(), toggle_shader_event.is_set(), toggle_regions_event.is_set(), toggle_gui_event.is_set(), randomize_colors_event.is_set())
    if update_event.is_set():
        config_data.update(op.read_config_file(CONFIG_PATH))
        print(config_data)
        update_event.clear()
    if toggle_shader_event.is_set():
        shaders.next_shader()
        toggle_shader_event.clear()
    if toggle_regions_event.is_set():
        toggle_regions_event.clear()
    if toggle_gui_event.is_set():
        toggle_gui_event.clear()
    if randomize_colors_event.is_set():
        for i in range(3):
            config_data['color1'][i] = np.random.randint(0, 256)
            config_data['color2'][i] = np.random.randint(0, 256)
        op.update_config_file(CONFIG_PATH,**config_data)
        print(config_data)
        update_event.set()
        print("Randomizing colors...")
        randomize_colors_event.clear()

def render_tiles(screen, tiles_cache, shaders, config_data):
    width, height = config_data['width'], config_data['height']
    current_time = pygame.time.get_ticks()
    
    gamma_values = config_data['gamma']
    size_value = config_data['size']
    scale_value = config_data['scale']
    color1 = tuple(config_data["color1"])
    color2 = tuple(config_data["color2"])
    config_key = (tuple(gamma_values), size_value, color1, color2)

    if config_key not in tiles_cache:
        tiles_cache.clear()
        print("cache cleared")
        tiles_data = op.tiling(gamma_values, size_value)
        tiles_objects = [Tile(vertices, color) for vertices, color in tiles_data]
        op.calculate_neighbors(tiles_objects)
        tiles_cache[config_key] = tiles_objects

    tiles_objects = tiles_cache[config_key]
    
    center = complex(width // 2, height // 2)

    # Calculate the geometric center of all tiles
    all_vertices = np.concatenate([tile.vertices for tile in tiles_objects])
    geometric_center = np.mean(all_vertices, axis=0)

    # Define a threshold based on typical distances within the central body
    distance_threshold = np.std(all_vertices) * 0.5  # Adjust this value based on observed clustering

    central_tiles = [tile for tile in tiles_objects if np.linalg.norm(np.mean(tile.vertices, axis=0) - geometric_center) < distance_threshold]
    

    shader_func = shaders.current_shader()
    for tile in central_tiles:
        modified_color = shader_func(tile, current_time, central_tiles, color1, color2)
        vertices = op.to_canvas(tile.vertices, scale_value, center)
        pygame.draw.polygon(screen, modified_color, vertices)
    pygame.display.flip()  # Update the entire screen

def main():
    config_data = initialize_config(CONFIG_PATH)
    pygame.init()
    screen = pygame.display.set_mode((config_data['width'], config_data['height']), pygame.FULLSCREEN)
    pygame.display.set_caption("Penrose Tiling")

    shaders = Shader()
    tiles_cache = OrderedDict()
    clock = pygame.time.Clock()

    # Start server thread with stop event
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

    global running
    while running:
        if not handle_events(shaders, screen, config_data):
            running = False  # Set running to False to exit loop

        if any(toggle_event.is_set() for toggle_event in [update_event, toggle_shader_event, toggle_regions_event, toggle_gui_event, randomize_colors_event]):
            update_toggles(config_data, shaders)
        render_tiles(screen, tiles_cache, shaders, config_data)

        pygame.display.flip()
        screen.fill((0, 0, 0))
        clock.tick(60)
    pygame.quit()

if __name__ == '__main__':
    main()