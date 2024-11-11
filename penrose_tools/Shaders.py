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
from functools import lru_cache

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

    @lru_cache(maxsize=2048)

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
        self.tile_centroids = {}  # Cache for centroids
        self.wave_intensities = {}  # Cache for wave calculations
        self.last_wave_time = 0
        self.wave_cache_duration = 16  # ms (cache wave calculations for 16ms)

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
        current_time = time_ms
        
        # Initialize positions only once
        if not self.tile_centroids:
            for t in tiles:
                op.calculate_centroid(t.vertices)
        
        # Create ripples with numpy arrays for faster calculations
        if len(self.ripples) < self.max_ripples and current_time - self.last_raindrop_time > 3500:
            self.last_raindrop_time = current_time
            new_raindrop = random.choice(tiles)
            self.ripples.append((new_raindrop, 0, current_time))
        
        # Get tile position from cache
        tile_pos = op.calculate_centroid(tile.vertices)
        
        # Pre-calculate base colors as arrays
        base_color = np.array(color1, dtype=np.float32)
        target_color = np.array(color2, dtype=np.float32)
        
        # Process all ripples at once
        total_influence = 0.0
        new_ripples = []
        
        for center_tile, radius, start_time in self.ripples:
            time_elapsed = (current_time - start_time) / 1000
            
            if time_elapsed >= 15:  # Skip dead ripples early
                continue
                
            new_radius = 25 * (1 - np.exp(-time_elapsed / 5))
            if new_radius < 100:
                new_ripples.append((center_tile, new_radius, start_time))
                
                # Fast distance calculation
                center_pos = op.calculate_centroid(center_tile.vertices)
                distance = abs(tile_pos - center_pos)
                
                if distance <= new_radius:
                    # Consolidated intensity calculation
                    ripple_intensity = np.exp(-time_elapsed / 3)
                    if distance < 5:
                        total_influence += ripple_intensity
                    elif abs(distance - new_radius) < 5:
                        edge_factor = 1 - abs(distance - new_radius) / 5
                        total_influence += edge_factor * ripple_intensity
                    else:
                        total_influence += (1 - distance / new_radius) * ripple_intensity * 0.5
        
        self.ripples = new_ripples
        
        if not self.ripples:
            self.last_raindrop_time = 0
            return (*color1, 255)
        
        # Fast color interpolation
        total_influence = min(1.0, total_influence)
        final_color = np.rint(base_color + (target_color - base_color) * total_influence).astype(np.int32)
        
        return (*final_color, 255)

    def shader_color_wave(self, tile, time_ms, tiles, color1, color2, width, height, scale_value):
        # Bucket time to reduce unique calculations
        time_bucket = (time_ms // self.wave_cache_duration) * self.wave_cache_duration
        
        if time_bucket != self.last_wave_time:
            self.wave_intensities.clear()
            self.last_wave_time = time_bucket
        
        # Get or calculate tile position
        centroid = op.calculate_centroid(tile.vertices)
        center = complex(width // 2, height // 2)
        tile_position = centroid - center
        
        # Use cached wave calculation
        x, y = tile_position.real, tile_position.imag
        wave_intensity = self.calculate_wave_params(time_bucket, x, y)
        
        # Vectorized color calculation
        color_array = np.array([color1, color2])
        weights = np.array([1 - wave_intensity, wave_intensity])
        final_color = np.rint(np.dot(weights, color_array)).astype(np.int32)
        
        return (*final_color, 255)

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
    
    def calculate_wave_params(self, time_bucket, x, y):
        """Cached wave parameter calculation"""
        pos = complex(x, y)
        wave_speed = 0.0000002
        phase = wave_speed * time_bucket
        return np.sin(phase + abs(pos)) * 0.5 + 0.5

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