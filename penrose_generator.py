import os
import pygame  # type: ignore
from threading import Thread
from collections import OrderedDict
from penrose_tools import Operations, Shader, Slider,Tile, run_server, update_event, toggle_shader_event, toggle_regions_event, toggle_gui_event

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

def initialize_config(path):
    if not os.path.isfile(path):
        print("Config file not found. Creating a new one...")
        op.write_config_file(*DEFAULT_CONFIG.values())
    return op.read_config_file(path)

def setup_sliders(config_data):
    sliders = [Slider(100, 50 + 40 * i, 200, 20, -1.0, 1.0, config_data['gamma'][i], f'Gamma {i}') for i in range(5)]
    # Ensure size and scale sliders use integer steps
    sliders.extend([
        Slider(100, 300, 200, 20, 1, 10, int(config_data['size']), 'Size', step=1),
        Slider(100, 350, 200, 5, 10, 100, int(config_data['scale']), 'Scale', step=1),
        # Color sliders
        Slider(100, 490, 200, 20, 0, 255, int(config_data["color1"][0]), 'Red Color1'),
        Slider(100, 520, 200, 20, 0, 255, int(config_data["color1"][1]), 'Green Color1'),
        Slider(100, 550, 200, 20, 0, 255, int(config_data["color1"][2]), 'Blue Color1'),
        Slider(100, 580, 200, 20, 0, 255, int(config_data["color2"][0]), 'Red Color2'),
        Slider(100, 610, 200, 20, 0, 255, int(config_data["color2"][1]), 'Green Color2'),
        Slider(100, 640, 200, 20, 0, 255, int(config_data["color2"][2]), 'Blue Color2')
    ])
    return sliders

def handle_events(sliders, shaders, screen, config_data):
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                toggle_shader_event.set()
            elif event.key == pygame.K_g:
                global gui_visible
                gui_visible = not gui_visible
        elif event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
            for slider in sliders:
                slider.handle_event(event)

    return True

def update_toggles(config_data, sliders,shaders):
    print("Updating toggles...", update_event.is_set(), toggle_shader_event.is_set(), toggle_regions_event.is_set(), toggle_gui_event.is_set())
    if update_event.is_set():
        config_data.update(op.read_config_file(CONFIG_PATH))
        print(config_data)
        update_sliders_from_config(config_data, sliders)
        update_event.clear()
    if toggle_shader_event.is_set():
        shaders.next_shader()
        toggle_shader_event.clear()
    if toggle_regions_event.is_set():
        toggle_regions_event.clear()
    if toggle_gui_event.is_set():
        toggle_gui_event.clear()

def update_sliders_from_config(config_data, sliders):
    for slider in sliders:
        label_lower = slider.label.lower()
        if 'gamma' in label_lower:
            # Gamma sliders are indexed numerically at the end
            index = int(label_lower.split()[-1])  # Using split to directly access the numeric index
            slider.val = config_data['gamma'][index]
        elif 'size' in label_lower:
            slider.val = config_data['size']
        elif 'scale' in label_lower:
            slider.val = config_data['scale']
        elif 'color' in label_lower:
            # Determine which color array to use ('color1' or 'color2')
            color_key = 'color1' if 'color1' in label_lower else 'color2'
            color_values = config_data[color_key]
            # Map 'red', 'green', 'blue' to the respective index 0, 1, 2
            if 'red' in label_lower:
                color_index = 0
            elif 'green' in label_lower:
                color_index = 1
            elif 'blue' in label_lower:
                color_index = 2
            slider.val = color_values[color_index]
            print("setting colors from sliders as:", slider.label, slider.val)



def render_tiles(screen, tiles_cache, sliders, shaders, config_data):
    width, height = config_data['width'], config_data['height']
    current_time = pygame.time.get_ticks()
    gamma_values = [slider.get_value() for slider in sliders if 'gamma' in slider.label.lower()]
    size_value = next(slider.get_value() for slider in sliders if 'size' in slider.label.lower())
    scale_value = next(slider.get_value() for slider in sliders if 'scale' in slider.label.lower())
    color1 = tuple(next(slider.get_value() for slider in sliders if f'{color} Color1' in slider.label) for color in ['Red', 'Green', 'Blue'])
    color2 = tuple(next(slider.get_value() for slider in sliders if f'{color} Color2' in slider.label) for color in ['Red', 'Green', 'Blue'])
    config_key = (tuple(gamma_values), size_value, color1, color2)
    if config_key not in tiles_cache:
        print("Generating new tile cache...")
        tiles_data = op.tiling(gamma_values, size_value)
        tiles_objects = [Tile(vertices, color) for vertices, color in tiles_data]
        op.calculate_neighbors(tiles_objects)
        tiles_cache[config_key] = tiles_objects
    tiles_objects = tiles_cache[config_key]
    screen.fill((0, 0, 0))
    center = complex(width // 2, height // 2)
    shader_func = shaders.current_shader()
    for tile in tiles_objects:
        modified_color = shader_func(tile, current_time, tiles_objects, color1, color2)
        vertices = Operations().to_canvas(tile.vertices, scale_value, center)
        pygame.draw.polygon(screen, modified_color, vertices)

def main():
    config_data = initialize_config(CONFIG_PATH)
    pygame.init()
    screen = pygame.display.set_mode((config_data['width'], config_data['height']))
    pygame.display.set_caption("Penrose Tiling")

    sliders = setup_sliders(config_data)
    shaders = Shader()  # Instance of the Shader class

    clock = pygame.time.Clock()
    running = True
    tiles_cache = OrderedDict()

    # Start server thread
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

    while running:
        handle_events(sliders, shaders, screen, config_data)  # Pass the Shader instance here

        if any(toggle_event.is_set() for toggle_event in [update_event, toggle_shader_event, toggle_regions_event, toggle_gui_event]):
            update_toggles(config_data, sliders,shaders)

        render_tiles(screen, tiles_cache, sliders, shaders, config_data)  # Pass the Shader instance here
        if gui_visible:
            for slider in sliders:
                slider.draw(screen)

        pygame.display.flip()
        clock.tick(80)
    pygame.quit()

if __name__ == '__main__':
    main()