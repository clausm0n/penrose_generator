import pygame # type: ignore
import time
from threading import Event, Thread
from collections import OrderedDict
from penrose_tools.Tile import Tile
from penrose_tools.Operations import Operations
from penrose_tools.Slider import Slider
from penrose_tools.Shaders import Shader
from penrose_tools.Server import run_server, update_event


op = Operations()
shaders = Shader()

def main():

    config_data = op.read_config_file("config.ini")
    pygame.init()
    clock = pygame.time.Clock()
    width = config_data['width']
    height = config_data['height']
    size = config_data['size']
    scale = config_data['scale']
    screen = pygame.display.set_mode((width,height))
    pygame.display.set_caption("Penrose Tiling")

    gamma = config_data['gamma']
    sliders = [Slider(100, 50 + 40 * i, 200, 20, -1.0, 1.0, gamma[i], f'Gamma {i}') for i in range(5)]
    print("Number of Gamma Sliders:", len(sliders))
    size_slider = Slider(100, 300, 200, 20, 1, 8, size, 'Size')
    scale_slider = Slider(100, 350, 200, 20, 25, 100, scale, 'Scale')
    color_sliders =[    
        Slider(100, 450, 200, 20, 0, 255, config_data["color1"][0], 'Red Color1'),
        Slider(100, 480, 200, 20, 0, 255, config_data['color1'][1], 'Green Color1'),
        Slider(100, 510, 200, 20, 0, 255, config_data['color1'][2], 'Blue Color1'),
        Slider(100, 540, 200, 20, 0, 255, config_data["color2"][0], 'Red Color2'),
        Slider(100, 570, 200, 20, 0, 255, config_data["color2"][1], 'Green Color2'),
        Slider(100, 600, 200, 20, 0, 255, config_data["color2"][2], 'Blue Color2')]
    sliders.extend([size_slider, scale_slider])
    sliders.extend(color_sliders)
    shader_functions = [shaders.shader_no_effect, shaders.shader_shift_effect,shaders.shader_temperature_to_color, shaders.shader_decay_trail, shaders.shader_game_of_life, shaders.shader_color_wave]

    shader_index = 0

    start_time = time.time() * 1000
    running = True
    show_regions = False
    gui_visible = False
    # Initialize caches
    tiles_cache = OrderedDict()
    tile_colors_cache = OrderedDict()

    # Initialize previous values for gamma, size, and scale
    previous_gamma = None
    previous_size = None
    previous_scale = None

    
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    while running:
        if update_event.is_set():
            update_event.clear()
            config_data = op.read_config_file("config.ini")
            
            gamma_values = config_data['gamma']


            for i, slider in enumerate(sliders[:5]):
                if i < len(gamma_values):  # Safeguard against index error
                    print("Updating Gamma slider", i, "with value", gamma_values[i])
                    slider.val = gamma_values[i]

            
            size_slider.val = config_data['size']
            scale_slider.val = config_data['scale']
            
            # Assuming color_sliders is a list of sliders for RGB values of two colors
            color_sliders[0].val = config_data['color1'][0]  # Red of color1
            color_sliders[1].val = config_data['color1'][1]  # Green of color1
            color_sliders[2].val = config_data['color1'][2]  # Blue of color1
            color_sliders[3].val = config_data['color2'][0]  # Red of color2
            color_sliders[4].val = config_data['color2'][1]  # Green of color2
            color_sliders[5].val = config_data['color2'][2]  # Blue of color2

        current_time = time.time() * 1000 - start_time
        screen.fill((0, 0, 0))
        center = complex(width // 2,height // 2)
        scale = scale_slider.get_value()
        color1 = tuple(slider.get_value() for slider in color_sliders[:3])
        color2 = tuple(slider.get_value() for slider in color_sliders[3:6])
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    tiles_cache.clear()
                    tile_colors_cache.clear()
                    shader_index = (shader_index + 1) % len(shader_functions)
                if event.key == pygame.K_r:
                    show_regions = not show_regions
                    # clear cache when toggling region display
                    tiles_cache.clear()
                    print("Region display toggled")
                if event.key == pygame.K_g:
                    gui_visible = not gui_visible
                    print("GUI visibility toggled")
            elif event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
                for slider in sliders:
                    slider.handle_event(event)
                if event.type == pygame.MOUSEBUTTONUP:
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    for tile in tiles_objects:
                        if op.point_in_polygon((mouse_x, mouse_y), op.to_canvas(tile.vertices, scale, center)):
                            print("Neighbors:", len(tile.neighbors))
                            #toggle highlight when click on a tile and reverse it when click again
                            tile.highlighted = not tile.highlighted
                            if tile.highlighted:
                                tile.update_color(tile.highlighted_color)
                            else:
                                tile.update_color(tile.original_color)
                            break

    # Get updated values from sliders
        gamma_updated = [slider.get_value() for slider in sliders[:-2]]
        size_updated = int(size_slider.get_value())
        scale_updated = scale_slider.get_value()

    # Clear cache if parameters have changed
        if gamma_updated != previous_gamma or size_updated != previous_size or scale_updated != previous_scale:
            tiles_cache.clear()
            tile_colors_cache.clear()
            print("Cache cleared due to parameter change")

    # Update previous values
        previous_gamma = gamma_updated
        previous_size = size_updated
        previous_scale = scale_updated

        current_config = (tuple(gamma_updated), size_updated, scale_updated)

        if current_config not in tiles_cache:
            tiles_data = list(op.tiling(gamma_updated, size_updated))
            tiles_objects = [Tile(vertices, color) for vertices, color in tiles_data]
            
            op.calculate_neighbors(tiles_objects, grid_size=10)
            print("Neighbors calculated")

            # Remove orphan tiles
            tiles_objects = [tile for tile in tiles_objects if tile.neighbors]
            op.remove_small_components(tiles_objects, min_size=0)
            tile_colors = {tuple(vertices): color for vertices, color in tiles_data}

            tiles_cache[current_config] = tiles_objects
            tile_colors_cache[current_config] = tile_colors
            # Detect and update star patterns
            if show_regions:
                op.update_star_patterns(tiles_objects)
                op.update_starburst_patterns(tiles_objects)
        else:
            tiles_objects = tiles_cache[current_config]
            tile_colors = tile_colors_cache[current_config]

        for tile in tiles_objects:
            shader_func = shader_functions[shader_index]
            modified_color = shader_func(tile, current_time, tiles_objects,color1,color2)
            #print("Drawing color:", modified_color)  # Debug print
            vertices = op.to_canvas(tile.vertices, scale_updated, complex(width // 2,height // 2))
            pygame.draw.polygon(screen, modified_color, vertices)
        if gui_visible:
            for slider in sliders:
                slider.draw(screen)

        pygame.display.flip()
        clock.tick(80)
        

    pygame.quit()


if __name__ == '__main__':
    main()


