import pygame
import cmath  # For complex number operations
import random
import numpy as np
import time
import functools
from collections import OrderedDict, deque
from itertools import combinations
import os

width, height = 1760, 1060

class Tile:
    def __init__(self, vertices, color=(255, 255, 255)):
        self.vertices = self.clamp_vertices(vertices)
        self.neighbors = []
        self.color = self.clamp_color(color)
        self.original_color = self.color
        self.current_temperature = random.uniform(20, 30)
        self.target_temperature = self.current_temperature
        self.highlighted = False
        self.angles = self.calculate_angles()
        self.is_kite = self.is_kite()
        #invert color for highlinghted tiles
        self.highlighted_color = self.clamp_color(tuple(255 - c for c in self.color))

    def clamp_color(self, color):
        """Ensure all color values are within the legal RGB range."""
        return tuple(max(0, min(255, int(c))) for c in color)
    
    def clamp_vertices(self, vertices, precision=3):
        """Clamp vertices to a specified precision."""
        return [complex(round(v.real, precision), round(v.imag, precision)) for v in vertices]
    
    def calculate_angles(self):
        """Calculate angles at each vertex of the tile using the correct phase calculation."""
        angles = []
        num_vertices = len(self.vertices)
        for i in range(num_vertices):
            a, b, c = self.vertices[i - 1], self.vertices[i], self.vertices[(i + 1) % num_vertices]
            # Calculate vectors from the current vertex to the previous and the next vertices
            ba = a - b
            bc = c - b
            # Calculate angle between vectors ba and bc using the dot product method
            angle_cos = (ba.real * bc.real + ba.imag * bc.imag) / (cmath.sqrt(ba.real**2 + ba.imag**2) * cmath.sqrt(bc.real**2 + bc.imag**2))
            angle = cmath.acos(angle_cos).real  # Get the real part of the angle in radians
            angles.append(angle)
        return angles

    def is_kite(self):
        """Determine if the tile is a kite based on its angles."""
        # Assuming specific angle criteria to differentiate kites and darts
        return all(angle < (2 * cmath.pi / 3) for angle in self.angles)  # Placeholder condition

    
    def edges(self):
        """ Generate normalized edges for better comparison efficiency. """
        return [normalized_edge(self.vertices[i], self.vertices[(i + 1) % len(self.vertices)]) for i in range(len(self.vertices))]

    def add_neighbor(self, neighbor_tile):
        """ Add a neighboring tile to the neighbors list if it's not already included. """
        if neighbor_tile not in self.neighbors:
            self.neighbors.append(neighbor_tile)
    
    def update_temperature(self, diffusion_rate=0.001):
        if self.neighbors:
            avg_neighbor_temp = sum(neighbor.current_temperature for neighbor in self.neighbors) / len(self.neighbors)
            self.target_temperature = (1 - diffusion_rate) * self.current_temperature + diffusion_rate * avg_neighbor_temp
            self.current_temperature -= 0.5

    def apply_temperature_update(self):
        self.current_temperature = self.target_temperature
    
    def set_color_based_on_temperature(self):
        """Update color based on temperature, for example."""
        low_temp, high_temp = 50, 255
        intensity = (self.current_temperature - low_temp) / (high_temp - low_temp)
        red = 255 * intensity
        blue = 0 * (1 - intensity)
        self.color = self.clamp_color((red, 0, blue))

    def update_color(self, new_color):
        """Update the color of the tile, clamping values to ensure validity."""
        self.color = self.clamp_color(new_color)

class Slider:
    def __init__(self, x, y, w, h, min_val, max_val, initial_val, label):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.val = initial_val
        self.active = False
        self.label = label
        self.handle_rect = pygame.Rect(x + (initial_val - min_val) / (max_val - min_val) * w - 5, y - 2, 10, h + 4)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos):
                self.active = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False
        elif event.type == pygame.MOUSEMOTION and self.active:
            self.handle_rect.x = max(self.rect.x, min(event.pos[0], self.rect.x + self.rect.width - self.handle_rect.width))
            self.val = (self.handle_rect.x - self.rect.x) / self.rect.width * (self.max_val - self.min_val) + self.min_val

    def draw(self, surface):
        pygame.draw.rect(surface, (100, 100, 100), self.rect)
        pygame.draw.rect(surface, (200, 200, 200), self.handle_rect)
        # Display the label
        font = pygame.font.Font(None, 24)
        label_surface = font.render(f'{self.label}: {self.val:.2f}', True, (255, 255, 255))
        surface.blit(label_surface, (self.rect.x + self.rect.width + 10, self.rect.y))

    def get_value(self):
        return self.val
    
def calculate_centroid(vertices):
    """ Calculate the centroid from a list of vertices. """
    x_coords = [v.real for v in vertices]
    y_coords = [v.imag for v in vertices]
    centroid_x = sum(x_coords) / len(vertices)
    centroid_y = sum(y_coords) / len(vertices)
    return complex(centroid_x, centroid_y)  # Ensure returning a single complex number


def is_valid_star_kite(tile):
    """ Check if a kite has exactly two darts as neighbors. """
    dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite]
    return len(dart_neighbors) == 2

def is_valid_starburst_dart(tile):
    """ Check if a dart has exactly two darts as neighbors. """
    dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite]
    return len(dart_neighbors) == 2

def find_common_vertex(kites):
    """ Find a common vertex among a given set of kites. """
    vertex_sets = [set(kite.vertices) for kite in kites]
    common_vertices = set.intersection(*vertex_sets)
    return common_vertices

def update_star_patterns(tiles):
    """ Check each tile to see if it's part of a star pattern. """
    stars_colored = 0
    for tile in tiles:
        if tile.is_kite and is_valid_star_kite(tile):
            # Check combinations of two neighbors to find a star
            kite_neighbors = [neighbor for neighbor in tile.neighbors if neighbor.is_kite and is_valid_star_kite(neighbor)]
            if len(kite_neighbors) >= 2:
                for n1 in kite_neighbors:
                    for n2 in kite_neighbors:
                        if n1 is not n2:
                            # Check if these three kites share a common vertex
                            possible_star = [tile, n1, n2]
                            common_vertex = find_common_vertex(possible_star)
                            if common_vertex:
                                # Check for two more kites sharing the same vertex
                                extended_star = [t for t in tiles if set(t.vertices) & common_vertex and t.is_kite and is_valid_star_kite(t)]
                                if len(extended_star) == 5:
                                    star_color = (255, 215, 0)  # Gold color for star pattern
                                    for star_tile in extended_star:
                                        star_tile.update_color(star_color)
                                    stars_colored += 1
                                    break  # Found a valid star, break out of loops
    return stars_colored


def update_starburst_patterns(tiles):
    """ Check each dart to see if it's part of a starburst pattern. """
    starbursts_colored = 0
    for tile in tiles:
        if not tile.is_kite and is_valid_starburst_dart(tile):
            # Ensure the potential starburst darts all share a common vertex
            dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite and is_valid_starburst_dart(neighbor)]
            potential_starburst = [tile] + dart_neighbors
            if len(potential_starburst) >= 3:  # Start checking when there are at least 3 darts
                common_vertex = find_common_vertex(potential_starburst)
                if common_vertex:
                    # Extend to find all darts sharing this vertex
                    extended_starburst = [t for t in tiles if set(t.vertices) & common_vertex and not t.is_kite and is_valid_starburst_dart(t)]
                    if len(extended_starburst) == 10:
                        starburst_color = (255, 165, 0)  # Orange color for starburst pattern
                        for starburst_tile in extended_starburst:
                            starburst_tile.update_color(starburst_color)
                        starbursts_colored += 1
                        break  # Found a valid starburst, break out of loops
    return starbursts_colored

def normalized_edge(vertex1, vertex2):
    """Sort vertices based on their real parts first, and then imaginary parts if real parts are equal."""
    return (vertex1, vertex2) if (vertex1.real, vertex1.imag) < (vertex2.real, vertex2.imag) else (vertex2, vertex1)

def spatial_hash(tile, grid_size):
    """Hash a tile into one or more grid cells."""
    min_x = min(vertex.real for vertex in tile.vertices)
    max_x = max(vertex.real for vertex in tile.vertices)
    min_y = min(vertex.imag for vertex in tile.vertices)
    max_y = max(vertex.imag for vertex in tile.vertices)
    #print(f"Min_x: {min_x}, Max_x: {max_x}, Min_y: {min_y}, Max_y: {max_y}")  # Debug information
    return {(int((x - min_x) / grid_size), int((y - min_y) / grid_size)) for x in [min_x, max_x] for y in [min_y, max_y]}

def point_in_polygon(point, polygon):
    """Check if the point is inside the polygon using the ray-casting algorithm."""
    x, y = point
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def calculate_neighbors(tiles, grid_size=100):
    grid = {}
    edge_map = {}  # Use a dictionary to map edges to tiles

    # Hash tiles into grid cells and record edges
    for tile in tiles:
        cells = spatial_hash(tile, grid_size)
        for cell in cells:
            if cell not in grid:
                grid[cell] = []
            grid[cell].append(tile)
        for edge in tile.edges():
            if edge not in edge_map:
                edge_map[edge] = []
            edge_map[edge].append(tile)

    # Find neighbors via shared edges
    for edge, tiles_sharing_edge in edge_map.items():
        for i, tile_a in enumerate(tiles_sharing_edge):
            for tile_b in tiles_sharing_edge[i+1:]:
                tile_a.add_neighbor(tile_b)
                tile_b.add_neighbor(tile_a)

    print(f"Tiles processed: {len(tiles)}, Edge pairs registered: {len(edge_map)}")

def find_connected_components(tiles):
    # Using a dictionary to map tiles to component IDs
    visited = {}
    component_id = 0
    components = {}

    def dfs(tile, comp_id):
        stack = [tile]
        while stack:
            current = stack.pop()
            if current not in visited:
                visited[current] = comp_id
                if comp_id not in components:
                    components[comp_id] = []
                components[comp_id].append(current)
                for neighbor in current.neighbors:
                    if neighbor not in visited:
                        stack.append(neighbor)

    # Run DFS from each unvisited tile to find all components
    for tile in tiles:
        if tile not in visited:
            dfs(tile, component_id)
            component_id += 1

    return components

def remove_small_components(tiles, min_size=5):
    components = find_connected_components(tiles)
    # Keep only components that have a size >= min_size
    valid_tiles = [tile for comp in components.values() if len(comp) >= min_size for tile in comp]
    return valid_tiles

def rhombus_at_intersection(gamma, r, s, kr, ks):
    z0 = 1j*(zeta[r]*(ks-gamma[s]) - zeta[s]*(kr-gamma[r])) / (zeta[s-r].imag)
    k = [0--((z0/t).real+p)//1 for t, p in zip(zeta, gamma)]
    for k[r], k[s] in [(kr, ks), (kr+1, ks), (kr+1, ks+1), (kr, ks+1)]:
        yield sum(x*t for t, x in zip(zeta, k))

def tiling(gamma, size):
    for r in range(5):
        for s in range(r+1, 5):
            for kr in range(-size, size+1):
                for ks in range(-size, size+1):
                    color = (0, 255, 255) if (r-s)**2 % 5 == 1 else (0, 255, 0)
                    yield list(rhombus_at_intersection(gamma, r, s, kr, ks)), color

def to_canvas(vertices, scale, center, shrink_factor=5):
    centroid = sum(vertices) / len(vertices)
    result = []
    for z in vertices:
        w = center + scale * (z - shrink_factor * (z - centroid) / scale)
        result.append((w.real, w.imag))
    return result

# Fifth roots of unity.
zeta = [cmath.exp(2j * cmath.pi * i / 5) for i in range(5)]

def clamp_color(color):
    """Ensure all color values are within the legal RGB range."""
    return tuple(max(0, min(255, int(c))) for c in color)

def shader_no_effect(tile, time_ms, tiles, color1, color2):
    if tile.is_kite:
        return color1
    else:
        return color2


def shader_shift_effect(tile, time_ms, tiles, color1, color2):
    # Similar adjustment as above, ensure the color is accessed from the tile object
    base_color = color1 if tile.is_kite else color2
    centroid = sum(tile.vertices) / len(tile.vertices)
    time_factor = np.sin(time_ms / 1000.0 + centroid.real * centroid.imag) * 0.5 + 0.5
    new_color = [min(255, max(0, int(base_color[i] * time_factor))) for i in range(3)]
    return tuple(new_color)

def shader_decay_trail(tile, time_ms, tiles, color1, color2):
    current_time = pygame.time.get_ticks()

    # Initialize or reset the trail if necessary
    if not hasattr(shader_decay_trail, "trail_memory") or not hasattr(shader_decay_trail, "tiles_set") or shader_decay_trail.tiles_set != set(tiles):
        shader_decay_trail.trail_memory = {}
        shader_decay_trail.tiles_set = set(tiles)
        shader_decay_trail.visited_count = {t: 0 for t in tiles}
        shader_decay_trail.current_tile = random.choice(tiles)
        shader_decay_trail.trail_memory[shader_decay_trail.current_tile] = color2  # Start trail with full intensity using color2
        shader_decay_trail.last_update_time = current_time

    # Update the trail effect periodically
    if current_time - shader_decay_trail.last_update_time > 100:
        shader_decay_trail.last_update_time = current_time

        # Move to a new tile if possible
        neighbors = shader_decay_trail.current_tile.neighbors
        if neighbors:
            min_visits = min(shader_decay_trail.visited_count[n] for n in neighbors)
            least_visited_neighbors = [n for n in neighbors if shader_decay_trail.visited_count[n] == min_visits]
            next_tile = random.choice(least_visited_neighbors)
            shader_decay_trail.current_tile = next_tile
            shader_decay_trail.trail_memory[next_tile] = color2  # Ensure the new tile highlights with color2
            shader_decay_trail.visited_count[next_tile] += 1

        # Decay the trail colors over time
        new_trail_memory = {}
        for t, color in shader_decay_trail.trail_memory.items():
            if t in shader_decay_trail.tiles_set:  # Ensure the tile is still in the current tile set
                new_color = tuple(max(0, c - 25) for c in color)  # Gradually reduce the color intensity
                new_trail_memory[t] = new_color if sum(new_color) > 0 else color2  # Reset to color2 if decayed fully
        shader_decay_trail.trail_memory = new_trail_memory

    # Apply smoothed color transition for current tile
    target_color = shader_decay_trail.trail_memory.get(tile, color2)  # Use color2 when tile is not on the trail
    if tile in shader_decay_trail.trail_memory:
        current_color = color1
        interpolated_color = [int(current + (target - current) * 0.1) for current, target in zip(current_color, target_color)]
        return tuple(interpolated_color)
    else:
        return color2  # Default to color2 if not on the trail





def shader_color_wave(tile, time_ms, tiles,color1,color2, center=None):
    if center is None:
        # Assuming the center of the canvas; this center should be set to the visual or geometric center of your display
        center = complex(width // 2, height // 2)  # Adjust this to your actual window's center dimensions

    centroid = calculate_centroid(tile.vertices)
    # Convert to a vector relative to the center
    tile_position = centroid - center

    # Parameters for the translating wave
    wave_speed = 0.00008  # Speed of the wave, controls how fast the wave travels
    wave_length = 2  # Length of the wave, controls the spacing between peaks
    wave_direction = np.pi / 2 / time_ms  # Direction of the wave in radians

    # Calculate the directional influence on the phase
    # Ensure that the directional influence provides a dynamic component that varies across tiles
    directional_influence = np.cos(np.angle(tile_position) - wave_direction) * abs(tile_position) * time_ms
    # Ensure the phase calculation is linearly dependent on both time and space
    # Subtracting the directional influence times a scaling factor to create movement
    phase = wave_speed * time_ms / 100.0 - directional_influence / wave_length * 2

    # Normalize wave intensity
    wave_intensity = (np.sin(phase) + 1) / 2
    color_cycle_phase = time_ms / 1000.0  # Used for continuous color cycling

    # Create a dynamic color modulation based on the wave intensity and color cycle
    red = color1[0] * (((color_cycle_phase / 3) + 1) / 2 * wave_intensity)
    green = color1[1] * (((color_cycle_phase / 3 + 2 * np.pi / 3) + 1) / 2 * wave_intensity)
    blue = color1[2] * (((color_cycle_phase / 3 + 4 * np.pi / 3) + 1) / 2 * (1 - wave_intensity))
    
    return clamp_color((red, green, blue))


def shader_game_of_life(tile, time_ms, tiles, color1, color2):
    # Initialize or reset the shader state if it's the first time or if tiles have changed
    if not hasattr(shader_game_of_life, "initialized") or shader_game_of_life.initialized_tiles_set != set(tiles):
        shader_game_of_life.life_map = {t: random.choice([True, False]) for t in tiles}
        shader_game_of_life.colors = {t: color1 if shader_game_of_life.life_map[t] else color2 for t in tiles}
        shader_game_of_life.last_update_time = pygame.time.get_ticks()
        shader_game_of_life.population_threshold = 0.3  # Threshold of population below which to invigorate
        shader_game_of_life.initialized_tiles_set = set(tiles)
        shader_game_of_life.initialized = True

    current_time = pygame.time.get_ticks()
    if current_time - shader_game_of_life.last_update_time > 600:  # Update every 600 ms
        shader_game_of_life.last_update_time = current_time
        new_life_map = {}
        alive_count = 0

        # Apply the Game of Life rules
        for t in tiles:
            alive_neighbors = sum(1 for n in t.neighbors if shader_game_of_life.life_map.get(n, False))
            new_life_map[t] = alive_neighbors in [2, 3] if shader_game_of_life.life_map[t] else alive_neighbors == 3
            if new_life_map[t]:
                alive_count += 1

        shader_game_of_life.life_map = new_life_map

        # Check population health and possibly invigorate
        if alive_count / len(tiles) < shader_game_of_life.population_threshold:
            dead_tiles = [t for t in tiles if not shader_game_of_life.life_map[t]]
            invigoration_count = max(1, int(len(tiles) * 0.01))  # Invigorate at least 5 or 5% of the tiles
            for _ in range(invigoration_count):
                if dead_tiles:
                    revival_tile = random.choice(dead_tiles)
                    shader_game_of_life.life_map[revival_tile] = True
                    shader_game_of_life.colors[revival_tile] = color1
                    if revival_tile.neighbors:
                        for neighbor in revival_tile.neighbors:
                            if random.random() < 0.5:  # 50% chance to also invigorate each neighbor
                                shader_game_of_life.life_map[neighbor] = True
                                # shader_game_of_life.colors[neighbor] = (0, 255, 0)

    # Update colors smoothly towards the target color
    target_color = color1 if shader_game_of_life.life_map.get(tile, False) else color2
    current_color = shader_game_of_life.colors[tile]
    interpolated_color = [int(current + (target - current) * 0.02) for current, target in zip(current_color, target_color)]
    shader_game_of_life.colors[tile] = tuple(interpolated_color)

    return shader_game_of_life.colors[tile]


def shader_temperature_to_color(tile, time_ms, tiles,color1,color2, update_interval=100):
    current_time = pygame.time.get_ticks()
    if current_time % update_interval < 20:
        for t in tiles:
            t.update_temperature(diffusion_rate=0.01)
        for t in tiles:
            t.apply_temperature_update()
        heat_interval = 200
        high_temp = 50
        if current_time % heat_interval < 1:
            random_tile = random.choice(tiles)
            random_tile.current_temperature = high_temp + 100

    temperature = tile.current_temperature
    low_temp, high_temp = 0, 50
    intensity = (temperature - low_temp) / (high_temp - low_temp)
    red = color1[0] * intensity
    blue = color2[0] * (1 - intensity)
    alpha = 255 * (1 - intensity)  # Transparency decreases as the tile cools
    return clamp_color((red, 0, blue, alpha))  # RGBA tuple

def shader_lenia(tile, time_ms, tiles, color1, color2):
    update_interval = 100  # Update every 100 ms
    disturbance_interval = 3000  # Introduce new kernels every 3000 ms
    kernel_radius = 1.0
    growth_rate = 0.15  # Increased growth rate
    decay_rate = 0.02  # Lower decay rate
    activation_threshold = 0.4
    death_threshold = 0.01

    if not hasattr(shader_lenia, "last_update_time"):
        shader_lenia.last_update_time = time_ms
        shader_lenia.last_disturbance_time = time_ms
        for t in tiles:
            t.state = random.random()

    if time_ms - shader_lenia.last_update_time > update_interval:
        shader_lenia.last_update_time = time_ms
        new_states = {}
        for t in tiles:
            if t.state > death_threshold:
                total_influence = sum(kernel_function(calculate_distance(t, neighbor), kernel_radius) * neighbor.state for neighbor in t.neighbors if neighbor.state > death_threshold)
                if total_influence > activation_threshold:
                    new_state = t.state + growth_rate * (1 - t.state)
                else:
                    new_state = t.state - decay_rate * t.state
                new_states[t] = new_state
            else:
                new_states[t] = t.state  # Keep dead state unchanged

        for t in tiles:
            t.state = new_states[t]

    if time_ms - shader_lenia.last_disturbance_time > disturbance_interval:
        shader_lenia.last_disturbance_time = time_ms
        for _ in range(5):  # Introduce multiple disturbances
            random_tile = random.choice(tiles)
            random_tile.state = random.uniform(0.5, 1.0)  # Use a range of higher values for activation

    if tile.state < death_threshold:
        return (0, 0, 0)
    else:
        blended_color = [int(c1 + (c2 - c1) * tile.state) for c1, c2 in zip(color1, color2)]
        return tuple(blended_color)

def kernel_function(distance, radius):
    # Simple exponential decay kernel
    return np.exp(-distance**2 / (2 * radius**2))

def calculate_distance(tile1, tile2):
    # Calculate Euclidean distance between the centroids of two tiles
    centroid1 = calculate_centroid(tile1.vertices)
    centroid2 = calculate_centroid(tile2.vertices)
    return abs(centroid1 - centroid2)

def main():
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pygame.init()
    info = pygame.display.Info()
    screen_width,screen_height = info.current_w,info.current_h
    clock = pygame.time.Clock()
    
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Penrose Tiling")

    gamma = [0.3, 0.2, -0.1, -0.4, 0.0]
    sliders = [Slider(100, 50 + 40 * i, 200, 20, -1.0, 1.0, gamma[i], f'Gamma {i}') for i in range(5)]
    size_slider = Slider(100, 300, 200, 20, 1, 9, 5, 'Size')
    scale_slider = Slider(100, 350, 200, 20, 25, 100, 35, 'Scale')
    color_sliders =[    
        Slider(100, 450, 200, 20, 0, 255, 128, 'Red Color1'),
        Slider(100, 480, 200, 20, 0, 255, 128, 'Green Color1'),
        Slider(100, 510, 200, 20, 0, 255, 128, 'Blue Color1'),
        Slider(100, 540, 200, 20, 0, 255, 128, 'Red Color2'),
        Slider(100, 570, 200, 20, 0, 255, 128, 'Green Color2'),
        Slider(100, 600, 200, 20, 0, 255, 128, 'Blue Color2')]
    sliders.extend([size_slider, scale_slider])
    sliders.extend(color_sliders)
    scale = scale_slider.get_value()
    shader_functions = [shader_no_effect, shader_shift_effect,shader_lenia ,shader_temperature_to_color, shader_decay_trail, shader_game_of_life, shader_color_wave]

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

    while running:
        current_time = time.time() * 1000 - start_time
        screen.fill((0, 0, 0))
        center = complex(width // 2, height // 2)
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
                        if point_in_polygon((mouse_x, mouse_y), to_canvas(tile.vertices, scale, center)):
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
            tiles_data = list(tiling(gamma_updated, size_updated))
            tiles_objects = [Tile(vertices, color) for vertices, color in tiles_data]
            
            calculate_neighbors(tiles_objects, grid_size=10)
            print("Neighbors calculated")

            # Remove orphan tiles
            tiles_objects = [tile for tile in tiles_objects if tile.neighbors]
            remove_small_components(tiles_objects, min_size=0)
            tile_colors = {tuple(vertices): color for vertices, color in tiles_data}

            tiles_cache[current_config] = tiles_objects
            tile_colors_cache[current_config] = tile_colors
            # Detect and update star patterns
            if show_regions:
                update_star_patterns(tiles_objects)
                update_starburst_patterns(tiles_objects)
        else:
            tiles_objects = tiles_cache[current_config]
            tile_colors = tile_colors_cache[current_config]

        for tile in tiles_objects:
            shader_func = shader_functions[shader_index]
            modified_color = shader_func(tile, current_time, tiles_objects,color1,color2)
            #print("Drawing color:", modified_color)  # Debug print
            vertices = to_canvas(tile.vertices, scale_updated, complex(width // 2, height // 2))
            pygame.draw.polygon(screen, modified_color, vertices)
        if gui_visible:
            for slider in sliders:
                slider.draw(screen)

        pygame.display.flip()
        clock.tick(80)

    pygame.quit()

if __name__ == '__main__':
    main()


