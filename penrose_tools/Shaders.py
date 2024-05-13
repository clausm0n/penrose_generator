import pygame # type: ignore
import random
import numpy as np
from penrose_tools.Tile import Tile
from penrose_tools.Operations import Operations

op = Operations()

class Shader:

    def __init__(self):
        self.shader_index = 0
        # Read configuration data
        self.config_data = op.read_config_file("config.ini")
        # Initialize state variables for various shaders
        self.initialize_shader_states()
        self.shaders = [
        self.shader_no_effect,
        self.shader_shift_effect,
        self.shader_temperature_to_color,
        self.shader_decay_trail,
        self.shader_game_of_life,
        self.shader_color_wave
        ]
    
    def next_shader(self):
        """
        Increments the shader index and wraps it around if it exceeds the number of shaders.

        Returns:
            int: The new shader index.
        """
        self.shader_index = (self.shader_index + 1) % len(self.shaders)
        return self.shader_index
    
    def current_shader(self):
        return self.shaders[self.shader_index]

    def initialize_shader_states(self):
        self.trail_memory = {}
        self.visited_count = {}
        self.current_tile = None
        self.last_update_time = pygame.time.get_ticks()
        self.initialized = False
        self.life_map = {}
        self.colors = {}
        self.game_of_life_initialized = False
        self.last_temperature_update_time = 0

    def shader_no_effect(self, tile, time_ms, tiles, color1, color2):
        return color1 if tile.is_kite else color2

    def shader_shift_effect(self, tile, time_ms, tiles, color1, color2):
        base_color = color1 if tile.is_kite else color2
        centroid = sum(tile.vertices) / len(tile.vertices)
        time_factor = np.sin(time_ms / 1000.0 + centroid.real * centroid.imag) * 0.5 + 0.5
        new_color = [min(255, max(0, int(base_color[i] * time_factor))) for i in range(3)]
        return tuple(new_color)

    def shader_decay_trail(self, tile, time_ms, tiles, color1, color2):
        current_time = pygame.time.get_ticks()
        if not self.trail_memory or not self.current_tile or set(tiles) != set(self.visited_count.keys()):
            self.trail_memory = {}
            self.visited_count = {t: 0 for t in tiles}
            self.current_tile = random.choice(tiles)
            self.trail_memory[self.current_tile] = color2
            self.last_update_time = current_time

        if current_time - self.last_update_time > 100:
            self.last_update_time = current_time
            neighbors = self.current_tile.neighbors
            if neighbors:
                min_visits = min(self.visited_count.get(n, 0) for n in neighbors)
                least_visited_neighbors = [n for n in neighbors if self.visited_count.get(n, float('inf')) == min_visits]

                # Check if there are any eligible neighbors
                if least_visited_neighbors:
                    next_tile = random.choice(least_visited_neighbors)
                    self.current_tile = next_tile
                    self.trail_memory[next_tile] = color2
                    self.visited_count[next_tile] += 1
                else:
                    # Fallback strategy if no neighbors have the min visit count
                    self.current_tile = random.choice(neighbors)  # Default to a random neighbor

            new_trail_memory = {}
            for t, color in self.trail_memory.items():
                new_color = tuple(max(0, c - 25) for c in color)
                new_trail_memory[t] = new_color if sum(new_color) > 0 else color2
            self.trail_memory = new_trail_memory

        target_color = self.trail_memory.get(tile, color2)
        if tile in self.trail_memory:
            current_color = color1
            interpolated_color = [int(current + (target - current) * 0.1) for current, target in zip(current_color, target_color)]
            return tuple(interpolated_color)
        return color2



    def shader_color_wave(self, tile, time_ms, tiles, color1, color2):
        center = complex(self.config_data['width'] // 2, self.config_data['height'] // 2)

        centroid = op.calculate_centroid(tile.vertices)
        tile_position = centroid - center

        wave_speed = 0.0000002  # This speed should work for gradual changes
        wave_length = 1.0     # Adjusted for broader wave spans

        # Smooth direction transition using tweening
        base_direction = np.pi / 4
        direction_change = np.pi / 2
        tween_duration = 1000000  # Duration of the tween in milliseconds
        time_factor = (time_ms % tween_duration) / tween_duration
        wave_direction = base_direction + direction_change * np.sin(time_factor * np.pi)

        directional_influence = np.cos(np.angle(tile_position) - wave_direction) * abs(tile_position)
        phase = wave_speed * time_ms - directional_influence / wave_length

        wave_intensity = (np.sin(phase) + 1) / 2  # Normalized between 0 and 1

        # Linear interpolation for smooth color blending
        red = color1[0] * (1 - wave_intensity) + color2[0] * wave_intensity
        green = color1[1] * (1 - wave_intensity) + color2[1] * wave_intensity
        blue = color1[2] * (1 - wave_intensity) + color2[2] * wave_intensity

        return op.clamp_color((red, green, blue))


    def shader_game_of_life(self, tile, time_ms, tiles, color1, color2):
        if not self.game_of_life_initialized or self.initialized_tiles_set != set(tiles):
            self.life_map = {t: random.choice([True, False]) for t in tiles}
            self.colors = {t: color1 if self.life_map[t] else color2 for t in tiles}
            self.last_update_time = pygame.time.get_ticks()
            self.population_threshold = 0.3
            self.initialized_tiles_set = set(tiles)
            self.game_of_life_initialized = True

        current_time = pygame.time.get_ticks()
        if current_time - self.last_update_time > 600:
            self.last_update_time = current_time
            new_life_map = {}
            alive_count = 0

            for t in tiles:
                alive_neighbors = sum(1 for n in t.neighbors if self.life_map.get(n, False))
                new_life_map[t] = alive_neighbors in [2, 3] if self.life_map[t] else alive_neighbors == 3
                if new_life_map[t]:
                    alive_count += 1

            self.life_map = new_life_map

            if alive_count / len(tiles) < self.population_threshold:
                dead_tiles = [t for t in tiles if not self.life_map[t]]
                invigoration_count = max(1, int(len(tiles) * 0.01))
                for _ in range(invigoration_count):
                    if dead_tiles:
                        revival_tile = random.choice(dead_tiles)
                        self.life_map[revival_tile] = True
                        self.colors[revival_tile] = color1
                        for neighbor in revival_tile.neighbors:
                            if random.random() < 0.5:
                                self.life_map[neighbor] = True

        target_color = color1 if self.life_map.get(tile, False) else color2
        current_color = self.colors[tile]
        interpolated_color = [int(current + (target - current) * 0.02) for current, target in zip(current_color, target_color)]
        self.colors[tile] = tuple(interpolated_color)

        return self.colors[tile]

    def shader_temperature_to_color(self, tile, time_ms, tiles, color1, color2, update_interval=10):
        current_time = pygame.time.get_ticks()
        # Perform temperature updates at the specified interval
        if current_time - self.last_temperature_update_time > update_interval:
            self.last_temperature_update_time = current_time
            # Update the temperature of each tile
            for t in tiles:
                t.update_temperature(diffusion_rate=0.01)
            # Apply the temperature update to each tile
            for t in tiles:
                t.apply_temperature_update()
            # Increase the temperature of a random tile every 200 ms
            heat_interval = 10
            if current_time % heat_interval < 1:
                random_tile = random.choice(tiles)
                random_tile.current_temperature = 150  # Raise temperature significantly

        # Calculate color based on the tile's current temperature
        temperature = tile.current_temperature
        low_temp, high_temp = 0, 150
        intensity = (temperature - low_temp) / (high_temp - low_temp)
        intensity = min(max(intensity, 0), 1)  # Clamp intensity between 0 and 1

        # Blend between two colors based on the temperature intensity
        red = (color1[0] * intensity + color2[0] * (1 - intensity))
        green = (color1[1] * intensity + color2[1] * (1 - intensity))
        blue = (color1[2] * intensity + color2[2] * (1 - intensity))

        alpha = 255 * (1 - intensity)  # Transparency decreases as the tile cools

        # Return the clamped RGBA color tuple
        return op.clamp_color((int(red), int(green), int(blue), int(alpha)))

    def is_valid_star_kite(self,tile):
        """ Check if a kite has exactly two darts as neighbors. """
        dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite]
        return len(dart_neighbors) == 2

    def is_valid_starburst_dart(self,tile):
        """ Check if a dart has exactly two darts as neighbors. """
        dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite]
        return len(dart_neighbors) == 2

    def find_common_vertex(self,kites):
        """ Find a common vertex among a given set of kites. """
        vertex_sets = [set(kite.vertices) for kite in kites]
        common_vertices = set.intersection(*vertex_sets)
        return common_vertices

    def update_star_patterns(self,tiles):
        """ Check each tile to see if it's part of a star pattern. """
        stars_colored = 0
        for tile in tiles:
            if tile.is_kite and self.is_valid_star_kite(tile):
                # Check combinations of two neighbors to find a star
                kite_neighbors = [neighbor for neighbor in tile.neighbors if neighbor.is_kite and self.is_valid_star_kite(neighbor)]
                if len(kite_neighbors) >= 2:
                    for n1 in kite_neighbors:
                        for n2 in kite_neighbors:
                            if n1 is not n2:
                                # Check if these three kites share a common vertex
                                possible_star = [tile, n1, n2]
                                common_vertex = self.find_common_vertex(possible_star)
                                if common_vertex:
                                    # Check for two more kites sharing the same vertex
                                    extended_star = [t for t in tiles if set(t.vertices) & common_vertex and t.is_kite and self.is_valid_star_kite(t)]
                                    if len(extended_star) == 5:
                                        star_color = (255, 215, 0)  # Gold color for star pattern
                                        for star_tile in extended_star:
                                            star_tile.update_color(star_color)
                                        stars_colored += 1
                                        break  # Found a valid star, break out of loops
        return stars_colored


    def update_starburst_patterns(self,tiles):
        """ Check each dart to see if it's part of a starburst pattern. """
        starbursts_colored = 0
        for tile in tiles:
            if not tile.is_kite and self.is_valid_starburst_dart(tile):
                # Ensure the potential starburst darts all share a common vertex
                dart_neighbors = [neighbor for neighbor in tile.neighbors if not neighbor.is_kite and self.is_valid_starburst_dart(neighbor)]
                potential_starburst = [tile] + dart_neighbors
                if len(potential_starburst) >= 3:  # Start checking when there are at least 3 darts
                    common_vertex = self.find_common_vertex(potential_starburst)
                    if common_vertex:
                        # Extend to find all darts sharing this vertex
                        extended_starburst = [t for t in tiles if set(t.vertices) & common_vertex and not t.is_kite and self.is_valid_starburst_dart(t)]
                        if len(extended_starburst) == 10:
                            starburst_color = (255, 165, 0)  # Orange color for starburst pattern
                            for starburst_tile in extended_starburst:
                                starburst_tile.update_color(starburst_color)
                            starbursts_colored += 1
                            break  # Found a valid starburst, break out of loops
        return starbursts_colored