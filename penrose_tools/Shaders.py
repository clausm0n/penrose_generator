import glfw
import random
import numpy as np
from penrose_tools.Tile import Tile
from penrose_tools.Operations import Operations
from PIL import Image
import os
import logging
op = Operations()
import scipy.spatial

class Shader:

    def __init__(self):
        self.shader_index = 0
        self.config_data = op.read_config_file("config.ini")
        self.initialize_shader_states()
        self.shaders = [
            self.shader_no_effect,
            self.shader_shift_effect,
            self.shader_pixelation_slideshow,
            self.shader_raindrop_ripple,
            self.shader_color_wave,
            self.shader_region_blend
            # self.shader_relay
        ]

    def next_shader(self):
        self.shader_index = (self.shader_index + 1) % len(self.shaders)
        logging.info(f"Switched to shader index: {self.shader_index}")
        return self.shader_index
    
    def current_shader(self):
        return self.shaders[self.shader_index]

    def initialize_shader_states(self):
        self.trail_memory = {}
        self.visited_count = {}
        self.current_tile = None
        self.last_update_time = glfw.get_time() * 1000
        self.initialized = False
        self.life_map = {}
        self.colors = {}
        self.game_of_life_initialized = False
        self.last_temperature_update_time = 0
        self.cached_neighbors = {}
        self.cached_star_patterns = {}
        self.cached_starburst_patterns = {}
        self.ripples = []
        self.last_raindrop_time = 0
        self.max_ripples = 3
        self.current_image_data = None
        self.next_image_data = None
        self.tile_to_pixel_map = None
        self.image_files = []
        self.image_data = []
        self.current_image_index = 0
        self.next_image_index = 1
        self.transition_start_time = 0
        self.transition_duration = 5000  # 5 seconds for transition
        self.time_between_transitions = 10000  # 10 seconds between transitions
        self.is_transitioning = False
        self.relay_waves = []
        self.last_relay_time = 0
        self.relay_duration = 5000  # Duration of a single relay wave
        self.tile_interpolation = {}  # To track interpolation state of tiles
        self.spatial_index = None
        self.centroid_array = None
        self.tile_lookup = None

    def build_spatial_index(self, tiles):
        """Build spatial index for efficient neighbor lookups"""
        centroids = []
        tile_lookup = {}
        
        for i, tile in enumerate(tiles):
            centroid = op.calculate_centroid(tile.vertices)
            centroids.append([centroid.real, centroid.imag])
            tile_lookup[i] = tile
            
        self.centroid_array = np.array(centroids)
        self.spatial_index = scipy.spatial.cKDTree(self.centroid_array)
        self.tile_lookup = tile_lookup

    def get_nearby_tiles(self, center_pos, radius):
        """Get tiles within radius using spatial index"""
        if self.spatial_index is None:
            return []
            
        indices = self.spatial_index.query_ball_point(
            [center_pos.real, center_pos.imag], 
            radius
        )
        return [self.tile_lookup[i] for i in indices]

    def reset_state(self):
        """Reset the shader state when tile map changes."""
        self.initialize_shader_states()
        self.image_files = []  # Clear image files
        # self.load_images_from_folder()  # Reload images
        print("Shader state reset")

    def shader_no_effect(self, tile, time_ms, tiles, color1, color2, width, height, scale_value):
        base_color = color1 if tile.is_kite else color2
        return (*base_color, 255)

    def shader_shift_effect(self, tile, time_ms, tiles, color1, color2, width, height, scale_value):
        base_color = color1 if tile.is_kite else color2
        centroid = sum(tile.vertices) / len(tile.vertices)
        time_factor = np.sin(time_ms / 1000.0 + centroid.real * centroid.imag) * 0.5 + 0.5
        new_color = [min(255, max(0, int(base_color[i] * time_factor))) for i in range(3)]
        return (*new_color, 255)

    def shader_raindrop_ripple(self, tile, time_ms, tiles, color1, color2, width, height, scale_value):
        current_time = glfw.get_time() * 1000
        
        # Initialize or reinitialize if needed
        if not hasattr(self, 'tile_positions') or not self.tile_positions:
            self.tile_positions = {t: op.calculate_centroid(t.vertices) for t in tiles}
            self.ripples = []
            self.last_raindrop_time = 0
        
        # Create new raindrop every 3.5 seconds, if we're below the max ripples limit
        if current_time - self.last_raindrop_time > 3500 and len(self.ripples) < self.max_ripples:
            self.last_raindrop_time = current_time
            new_raindrop = random.choice(tiles)
            self.ripples.append((new_raindrop, 0, current_time))  # (center_tile, radius, start_time)
        
        # Update and render ripples
        new_ripples = []
        for center_tile, radius, start_time in self.ripples:
            time_elapsed = (current_time - start_time) / 1000  # Time elapsed in seconds
            new_radius = 25 * (1 - np.exp(-time_elapsed / 5))  # Slower expansion
            if new_radius < 100 and time_elapsed < 15:  # Keep ripples for 15 seconds max
                new_ripples.append((center_tile, new_radius, start_time))
        
        self.ripples = new_ripples
        
        # If all ripples have faded, reset the last_raindrop_time to create a new one immediately
        if not self.ripples:
            self.last_raindrop_time = 0
        
        # Determine tile color based on ripples
        if tile not in self.tile_positions:
            # If the tile is not in tile_positions, add it
            self.tile_positions[tile] = op.calculate_centroid(tile.vertices)
        
        tile_pos = self.tile_positions[tile]
        tile_color = color1
        
        for center_tile, radius, start_time in self.ripples:
            if center_tile not in self.tile_positions:
                # If the center tile is not in tile_positions, skip this ripple
                continue
            center_pos = self.tile_positions[center_tile]
            distance = abs(tile_pos - center_pos)
            
            if distance <= radius:
                ripple_age = (current_time - start_time) / 1000  # Ripple age in seconds
                ripple_intensity = np.exp(-ripple_age / 3)  # Intensity decreases over time
                
                if abs(distance - radius) < 5:  # Ripple edge
                    edge_intensity = 1 - abs(distance - radius) / 5
                    tile_color = self.blend_colors(tile_color, color2, edge_intensity * ripple_intensity)
                elif distance < 5:  # Raindrop center
                    tile_color = self.blend_colors(tile_color, color2, ripple_intensity)
                else:
                    # Gradual color change within the ripple
                    color_intensity = (1 - distance / radius) * ripple_intensity
                    tile_color = self.blend_colors(tile_color, color2, color_intensity * 0.5)
        
        return (*tile_color, 255)

    def shader_color_wave(self, tile, time_ms, tiles, color1, color2, width, height, scale_value):
        center = complex(width // 2, height // 2)
        centroid = op.calculate_centroid(tile.vertices)
        tile_position = centroid - center

        wave_speed = 0.0000002
        wave_length = 1.0

        base_direction = np.pi / 4
        direction_change = np.pi / 2
        tween_duration = 1000000
        time_factor = (time_ms % tween_duration) / tween_duration
        wave_direction = base_direction + direction_change * np.sin(time_factor * np.pi)

        directional_influence = np.cos(np.angle(tile_position) - wave_direction) * abs(tile_position)
        phase = wave_speed * time_ms - directional_influence / wave_length

        wave_intensity = (np.sin(phase) + 1) / 2

        red = color1[0] * (1 - wave_intensity) + color2[0] * wave_intensity
        green = color1[1] * (1 - wave_intensity) + color2[1] * wave_intensity
        blue = color1[2] * (1 - wave_intensity) + color2[2] * wave_intensity

        return (int(red), int(green), int(blue), 255)

    def shader_relay(self, tile, time_ms, tiles, color1, color2, width, height, scale_value):
        current_time = time_ms

        # Initialize or reinitialize if needed
        if not hasattr(self, 'tile_positions') or not self.tile_positions:
            self.tile_positions = {t: op.calculate_centroid(t.vertices) for t in tiles}
            self.relay_waves = []
            self.last_relay_time = 0
            self.tile_interpolation = {}

        # Create new relay wave every 5 seconds
        if current_time - self.last_relay_time > 5000:
            self.last_relay_time = current_time
            star_tiles = [t for t in tiles if op.is_valid_star_kite(t) or op.is_valid_starburst_dart(t)]
            if star_tiles:
                new_center = random.choice(star_tiles)
                self.relay_waves.append((new_center, 0, current_time, 1))  # (center_tile, radius, start_time, direction)

        # Update and render waves
        new_waves = []
        for center_tile, radius, start_time, direction in self.relay_waves:
            time_elapsed = (current_time - start_time) / 1000  # Time elapsed in seconds
            new_radius = 50 * (1 - np.exp(-time_elapsed / 2))  # Expansion rate
            if new_radius < 200 and time_elapsed < self.relay_duration / 1000:
                new_waves.append((center_tile, new_radius, start_time, direction))
            
            # Check for collisions with other stars/starbursts
            for other_tile in tiles:
                if (op.is_valid_star_kite(other_tile) or op.is_valid_starburst_dart(other_tile)) and other_tile != center_tile:
                    other_pos = self.tile_positions[other_tile]
                    center_pos = self.tile_positions[center_tile]
                    distance = abs(other_pos - center_pos)
                    if abs(distance - new_radius) < 5 and new_radius > 0:  # If wave hits another star/starburst and radius is positive
                        new_waves.append((other_tile, 0, current_time, -direction))  # Start a new wave in opposite direction

        self.relay_waves = new_waves

        # Determine tile color based on waves
        base_color = color1 if tile.is_kite else color2
        tile_pos = self.tile_positions[tile]
        interpolation_factor = 0

        for center_tile, radius, start_time, direction in self.relay_waves:
            center_pos = self.tile_positions[center_tile]
            distance = abs(tile_pos - center_pos)
            
            if distance <= radius and radius > 0:  # Ensure radius is positive
                wave_progress = distance / radius
                wave_intensity = 1 - wave_progress
                interpolation_factor += direction * wave_intensity

        # Clamp interpolation factor between -1 and 1
        interpolation_factor = max(-1, min(1, interpolation_factor))

        # Interpolate color
        if interpolation_factor > 0:
            inverted_color = self.invert_color(base_color)
            final_color = self.blend_colors(base_color, inverted_color, interpolation_factor)
        else:
            final_color = self.blend_colors(base_color, base_color, -interpolation_factor)

        return (*final_color, 255)

    def shader_region_blend(self, tile, time_ms, tiles, color1, color2, width, height, scale_value):
        # Convert color lists to immutable tuples for hashing
        color1_tuple = tuple(color1)
        color2_tuple = tuple(color2)
        
        # Create a cache key using immutable types
        cache_key = (tile, color1_tuple, color2_tuple)
        
        if cache_key not in self.cached_neighbors:
            kite_count, dart_count = op.count_kite_and_dart_neighbors(tile)
            total_neighbors = kite_count + dart_count
            blend_factor = 0.5 if total_neighbors == 0 else kite_count / total_neighbors

            if tile.is_kite and op.is_valid_star_kite(tile):
                extended_star = op.find_star(tile, tiles)
                if len(extended_star) == 5:
                    color = self.invert_color(self.blend_colors(color1_tuple, color2_tuple, 0.3))
                else:
                    color = self.blend_colors(color1_tuple, color2_tuple, blend_factor)
            elif not tile.is_kite and op.is_valid_starburst_dart(tile):
                extended_starburst = op.find_starburst(tile, tiles)
                if len(extended_starburst) == 10:
                    color = self.invert_color(self.blend_colors(color1_tuple, color2_tuple, 0.7))
                else:
                    color = self.blend_colors(color1_tuple, color2_tuple, blend_factor)
            else:
                color = self.blend_colors(color1_tuple, color2_tuple, blend_factor)

            self.cached_neighbors[cache_key] = color
        else:
            color = self.cached_neighbors[cache_key]

        return (*color, 255)

    def invert_color(self, color):
        return tuple(255 - component for component in color)

    def blend_colors(self, color1, color2, blend_factor):
        return tuple(
            int(color1[i] * (1 - blend_factor) + color2[i] * blend_factor)
            for i in range(3)
        )

    def load_images_from_folder(self, folder_path='uploaded_images'):
        self.image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not self.image_files:
            print(f"Error: No image files found in {folder_path}")
        else:
            print(f"Loaded {len(self.image_files)} images from {folder_path}")

    def load_and_process_images(self, tiles):
        if not self.image_files:
            self.load_images_from_folder()
        
        # Calculate the bounding box of the tile array
        all_vertices = np.array([(v.real, v.imag) for tile in tiles for v in tile.vertices])
        min_x, min_y = np.min(all_vertices, axis=0)
        max_x, max_y = np.max(all_vertices, axis=0)
        tile_width = max_x - min_x
        tile_height = max_y - min_y
        tile_ratio = tile_width / tile_height

        self.image_data = []
        self.image_scales = []  # Store scaling info for each image
        for image_file in self.image_files:
            image_path = os.path.join('uploaded_images', image_file)
            with Image.open(image_path) as img:
                img = img.convert('RGB')  # Ensure consistent color format
                
                # Calculate aspect ratios
                img_ratio = img.width / img.height
                
                if img_ratio > tile_ratio:  # Image is wider
                    scale = tile_width / img.width
                    new_width = int(tile_width)
                    new_height = int(img.height * scale)
                    offset_x = 0
                    offset_y = (tile_height - new_height) / 2
                else:  # Image is taller
                    scale = tile_height / img.height
                    new_height = int(tile_height)
                    new_width = int(img.width * scale)
                    offset_x = (tile_width - new_width) / 2
                    offset_y = 0
                
                # Resize image
                img_resized = img.resize((new_width, new_height), Image.LANCZOS)
                
                # Create a black background of tile array size
                background = Image.new('RGB', (int(tile_width), int(tile_height)), (0, 0, 0))
                
                # Paste the resized image onto the background
                background.paste(img_resized, (int(offset_x), int(offset_y)))
                
                self.image_data.append(np.array(background))
                self.image_scales.append((scale, offset_x, offset_y, new_width, new_height))
        
        if not self.image_data:
            self.image_data = [np.full((int(tile_height), int(tile_width), 3), 128, dtype=np.uint8)]  # Gray image as fallback
            self.image_scales = [(1, 0, 0, int(tile_width), int(tile_height))]

        # Store tile array dimensions for mapping
        self.tile_dimensions = (min_x, min_y, max_x, max_y)

    def create_tile_to_pixel_map(self, tiles):
        min_x, min_y, max_x, max_y = self.tile_dimensions
        tile_width = max_x - min_x
        tile_height = max_y - min_y

        self.tile_to_pixel_map = {}
        for tile in tiles:
            centroid = op.calculate_centroid(tile.vertices)
            x = (centroid.real - min_x) / tile_width
            y = (centroid.imag - min_y) / tile_height
            self.tile_to_pixel_map[tile] = (x, y)  # Store normalized coordinates

    def shader_pixelation_slideshow(self, tile, time_ms, tiles, color1, color2, width, height, scale_value):
        if not hasattr(self, 'last_scale') or self.last_scale != scale_value:
            self.last_scale = scale_value
            self.load_and_process_images(tiles)
            self.create_tile_to_pixel_map(tiles)
            self.transition_start_time = time_ms

        if self.tile_to_pixel_map is None:
            return (128, 128, 128, 255)  # Gray color as fallback

        current_time = time_ms
        elapsed_time = current_time - self.transition_start_time
        total_duration = self.transition_duration * len(self.image_data)
        
        cycle_position = (elapsed_time % total_duration) / self.transition_duration
        current_index = int(cycle_position)
        next_index = (current_index + 1) % len(self.image_data)
        
        transition_progress = cycle_position - current_index

        x, y = self.tile_to_pixel_map[tile]
        
        current_color = self.get_color_from_image(current_index, x, y)
        next_color = self.get_color_from_image(next_index, x, y)

        progress = transition_progress * transition_progress * (3 - 2 * transition_progress)
        color = tuple(int(c1 * (1 - progress) + c2 * progress) for c1, c2 in zip(current_color, next_color))

        return (*color, 255)


    def get_color_from_image(self, image_index, x, y):
        image = self.image_data[image_index]
        scale, offset_x, offset_y, new_width, new_height = self.image_scales[image_index]
        
        # Convert normalized coordinates to image pixel coordinates
        px = int(x * image.shape[1])
        py = int(y * image.shape[0])
        
        # Ensure px and py are within image bounds
        px = max(0, min(px, image.shape[1] - 1))
        py = max(0, min(py, image.shape[0] - 1))
        
        return image[py, px]