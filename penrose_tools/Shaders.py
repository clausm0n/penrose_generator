import pygame # type: ignore
import random
import numpy as np
from penrose_tools.Tile import Tile
from penrose_tools.Operations import Operations

op = Operations()

class Shader:

    def __init__(self):
        # Read configuration data
        self.config_data = op.read_config_file("config.ini")
        # Initialize state variables for various shaders
        self.initialize_shader_states()

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
                min_visits = min(self.visited_count[n] for n in neighbors)
                least_visited_neighbors = [n for n in neighbors if self.visited_count[n] == min_visits]
                next_tile = random.choice(least_visited_neighbors)
                self.current_tile = next_tile
                self.trail_memory[next_tile] = color2
                self.visited_count[next_tile] += 1

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

        wave_speed = 0.00008
        wave_length = 2
        wave_direction = np.pi / 2 / (time_ms * 10)

        directional_influence = np.cos(np.angle(tile_position) - wave_direction) * abs(tile_position) * time_ms
        phase = wave_speed * time_ms / 20.0 - directional_influence / wave_length * 2

        wave_intensity = (np.sin(phase) + 1) / 2
        color_cycle_phase = time_ms / 1000.0

        red = color1[0] * (((color_cycle_phase / 3) + 1) / 2 * wave_intensity)
        green = color1[1] * (((color_cycle_phase / 3 + 2 * np.pi / 3) + 1) / 2 * wave_intensity)
        blue = color1[2] * (((color_cycle_phase / 3 + 4 * np.pi / 3) + 1) / 2 * (1 - wave_intensity))

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

    def shader_temperature_to_color(self, tile, time_ms, tiles, color1, color2, update_interval=100):
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
            heat_interval = 200
            if current_time % heat_interval < 1:
                random_tile = random.choice(tiles)
                random_tile.current_temperature = 50 + 100  # Raise temperature significantly

        # Calculate color based on the tile's current temperature
        temperature = tile.current_temperature
        low_temp, high_temp = 0, 50
        intensity = (temperature - low_temp) / (high_temp - low_temp)
        red = color1[0] * intensity
        blue = color2[0] * (1 - intensity)
        alpha = 255 * (1 - intensity)  # Transparency decreases as the tile cools
        return op.clamp_color((red, 0, blue, alpha))  # RGBA tuple

