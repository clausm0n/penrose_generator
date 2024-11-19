# penrose_tools/OptimizedRenderer.py
import numpy as np
from OpenGL.GL import *
import ctypes
import glfw
from .Operations import Operations
from .ShaderManager import ShaderManager
import logging

op = Operations()

class OptimizedRenderer:
    def __init__(self):
        """Initialize the renderer after OpenGL context is created."""
        self.vbo = None
        self.ebo = None
        self.tile_cache = {}
        self.attribute_locations = {}
        self.uniform_locations = {}
        self.logger = logging.getLogger('OptimizedRenderer')
        self.current_shader_index = 0
        self.pattern_cache = {}
        
        # Verify we have a valid OpenGL context before creating shader manager
        if not glfw.get_current_context():
            raise RuntimeError("OptimizedRenderer requires an active OpenGL context")
            
        self.shader_manager = ShaderManager()

    def force_refresh(self):
        """Force a refresh of the buffers by clearing the tile cache."""
        self.tile_cache.clear()


    def transform_to_gl_space(self, x, y, width, height):
        """Transform screen coordinates to OpenGL coordinate space."""
        return (2.0 * x / width - 1.0, 1.0 - 2.0 * y / height)
    

    
    def create_texture(self, image_data):
        """Create OpenGL texture from numpy array."""
        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        
        # Convert image to RGB if necessary
        if len(image_data.shape) == 3 and image_data.shape[2] == 3:
            format = GL_RGB
        else:
            format = GL_RGBA
        
        glTexImage2D(GL_TEXTURE_2D, 0, format, image_data.shape[1], image_data.shape[0], 
                    0, format, GL_UNSIGNED_BYTE, image_data)
        return texture

    def update_image_textures(self, current_image, next_image):
        """Update the current and next image textures."""
        if not hasattr(self, 'current_texture'):
            self.current_texture = self.create_texture(current_image)
            self.next_texture = self.create_texture(next_image)
        else:
            glBindTexture(GL_TEXTURE_2D, self.current_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, current_image.shape[1], current_image.shape[0],
                        0, GL_RGB, GL_UNSIGNED_BYTE, current_image)
            glBindTexture(GL_TEXTURE_2D, self.next_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, next_image.shape[1], next_image.shape[0],
                        0, GL_RGB, GL_UNSIGNED_BYTE, next_image)

    def setup_buffers(self, tiles, width, height, scale_value):
        """Set up vertex and element buffers for rendering."""
        vertices = []
        indices = []
        offset = 0
        center = complex(width / 2, height / 2)

        # Process each tile
        for tile in tiles:
            # Get screen space vertices
            screen_verts = op.to_canvas(tile.vertices, scale_value, center, 3)
            transformed_verts = [self.transform_to_gl_space(x, y, width, height) 
                            for x, y in screen_verts]

            # Calculate centroid in screen space
            centroid = sum(tile.vertices) / len(tile.vertices)
            screen_centroid = op.to_canvas([centroid], scale_value, center, 3)[0]
            gl_centroid = self.transform_to_gl_space(screen_centroid[0], screen_centroid[1], width, height)

            # Add vertices with tile type and centroid
            for vert in transformed_verts:
                vertices.extend([
                    vert[0], vert[1],          # position
                    1.0 if tile.is_kite else 0.0,  # tile_type
                    gl_centroid[0], gl_centroid[1]  # centroid
                ])

            # Create indices for triangulation
            num_verts = len(transformed_verts)
            for i in range(1, num_verts - 1):
                indices.extend([offset, offset + i, offset + i + 1])

            offset += num_verts

        # Convert to numpy arrays
        self.vertices_array = np.array(vertices, dtype=np.float32)
        self.indices_array = np.array(indices, dtype=np.uint32)

        # Create and bind vertex buffer
        if self.vbo is None:
            self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.vertices_array.nbytes, 
                    self.vertices_array, GL_STATIC_DRAW)

        # Create and bind element buffer
        if self.ebo is None:
            self.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.indices_array.nbytes, 
                    self.indices_array, GL_STATIC_DRAW)

    def get_shader_locations(self):
        """Get locations of shader attributes and uniforms."""
        shader_program = self.shader_manager.current_shader_program()
        self.attribute_locations.clear()
        self.uniform_locations.clear()

        # Get attribute locations
        self.attribute_locations['position'] = glGetAttribLocation(shader_program, 'position')
        self.attribute_locations['tile_type'] = glGetAttribLocation(shader_program, 'tile_type')
        self.attribute_locations['tile_centroid'] = glGetAttribLocation(shader_program, 'tile_center')

        # Get uniform locations
        shader_name = self.shader_manager.shader_names[self.current_shader_index]
        if shader_name == 'pixelation_slideshow':
            self.uniform_locations.update({
                'current_image': glGetUniformLocation(shader_program, 'current_image'),
                'next_image': glGetUniformLocation(shader_program, 'next_image'),
                'transition_progress': glGetUniformLocation(shader_program, 'transition_progress'),
                'image_transform': glGetUniformLocation(shader_program, 'image_transform')
            })
        else:
            # Standard uniforms for other shaders
            self.uniform_locations['color1'] = glGetUniformLocation(shader_program, 'color1')
            self.uniform_locations['color2'] = glGetUniformLocation(shader_program, 'color2')
            self.uniform_locations['time'] = glGetUniformLocation(shader_program, 'time')
            
            if shader_name == 'region_blend':
                self.uniform_locations.update({
                    'color1': glGetUniformLocation(shader_program, 'color1'),
                    'color2': glGetUniformLocation(shader_program, 'color2'),
                    'tile_patterns': glGetUniformLocation(shader_program, 'tile_patterns'),
                    'num_tiles': glGetUniformLocation(shader_program, 'num_tiles')
                })

    def process_patterns(self, tiles, width, height, scale_value):
        """Process and cache pattern data with complete region detection."""
        center = complex(width / 2, height / 2)
        patterns = []
        pattern_tiles = set()  # Track tiles that are part of complete patterns
        stars = []  # Track complete star regions
        starbursts = []  # Track complete starburst regions

        # First pass - identify complete regions
        for tile in tiles:
            if tile not in pattern_tiles:  # Only process tiles not already in a pattern
                if tile.is_kite and op.is_valid_star_kite(tile):
                    star_tiles = op.find_star(tile, tiles)
                    if len(star_tiles) == 5:  # Complete star found
                        stars.append(star_tiles)
                        pattern_tiles.update(star_tiles)
                        self.logger.debug(f"Found complete star with {len(star_tiles)} kites")
                
                elif not tile.is_kite and op.is_valid_starburst_dart(tile):
                    starburst_tiles = op.find_starburst(tile, tiles)
                    if len(starburst_tiles) == 10:  # Complete starburst found
                        starbursts.append(starburst_tiles)
                        pattern_tiles.update(starburst_tiles)
                        self.logger.debug(f"Found complete starburst with {len(starburst_tiles)} darts")

        self.logger.info(f"Found {len(stars)} complete stars and {len(starbursts)} complete starbursts")

        # Second pass - process all tiles
        for tile in tiles:
            # Transform centroid to GL space
            centroid = sum(tile.vertices) / len(tile.vertices)
            screen_centroid = op.to_canvas([centroid], scale_value, center, 3)[0]
            gl_centroid = self.transform_to_gl_space(screen_centroid[0], screen_centroid[1], width, height)
            
            # Check if tile is in a complete pattern first
            pattern_type = 0.0
            for star in stars:
                if tile in star:
                    pattern_type = 1.0
                    break
                    
            if pattern_type == 0.0:  # Not in a star, check starbursts
                for starburst in starbursts:
                    if tile in starburst:
                        pattern_type = 2.0
                        break

            # If not in a pattern, calculate neighbor-based blend
            if pattern_type == 0.0:
                kite_count, dart_count = op.count_kite_and_dart_neighbors(tile)
                total_neighbors = kite_count + dart_count
                blend_factor = 0.5 if total_neighbors == 0 else kite_count / total_neighbors
            else:
                # Pattern tiles use fixed blend factors
                blend_factor = 0.3 if pattern_type == 1.0 else 0.7

            patterns.append([gl_centroid[0], gl_centroid[1], pattern_type, blend_factor])

        total_pattern_tiles = len(pattern_tiles)
        star_tiles = sum(len(star) for star in stars)
        starburst_tiles = sum(len(burst) for burst in starbursts)
        
        self.logger.info(f"Star regions contain {star_tiles} tiles")
        self.logger.info(f"Starburst regions contain {starburst_tiles} tiles")
        self.logger.info(f"Total tiles in patterns: {total_pattern_tiles}")

        # In the process_patterns method, before returning:
        pattern_array = np.array(patterns, dtype=np.float32)

        # Sort pattern data by x then y coordinates for binary search
        sorted_indices = np.lexsort((pattern_array[:,1], pattern_array[:,0]))
        pattern_array = pattern_array[sorted_indices]

        return {
            'tile_patterns': pattern_array,
            'pattern_counts': {
                'stars': len(stars),
                'starbursts': len(starbursts),
                'star_tiles': star_tiles,
                'starburst_tiles': starburst_tiles,
                'total_pattern_tiles': total_pattern_tiles
            }
        }

    def render_tiles(self, width, height, config_data):
        """Render the Penrose tiling."""
        # Check if shader has changed
        if self.current_shader_index != self.shader_manager.current_shader_index:
            self.current_shader_index = self.shader_manager.current_shader_index
            self.force_refresh()  # Force refresh when shader changes
            self.logger.info("Shader changed, forcing buffer refresh")

        cache_key = (
            tuple(config_data['gamma']),
            width,
            height,
            config_data['scale'],
        )

        # Regenerate tiles and patterns if needed
        if cache_key not in self.tile_cache:
            self.tile_cache.clear()
            self.pattern_cache.clear()
            tiles = op.tiling(config_data['gamma'], width, height, config_data['scale'])
            op.calculate_neighbors(tiles)
            self.tile_cache[cache_key] = tiles
            
            # Process and cache pattern data
            self.pattern_cache[cache_key] = self.process_patterns(tiles, width, height, config_data['scale'])
            
            self.setup_buffers(tiles, width, height, config_data['scale'])
            self.get_shader_locations()

        # Use shader program
        shader_program = self.shader_manager.current_shader_program()
        glUseProgram(shader_program)
        
        shader_name = self.shader_manager.shader_names[self.current_shader_index]

        # Handle different shader types
        if shader_name == 'pixelation_slideshow':
            current_time = glfw.get_time() * 1000.0
            transition_duration = 5000.0  # 5 seconds
            cycle_duration = 10000.0  # 10 seconds
            
            if not hasattr(self, 'image_processor'):
                from .Effects import Effects
                self.image_processor = Effects()
                self.image_processor.load_images_from_folder()
                if self.image_processor.image_files:
                    self.image_processor.load_and_process_images(self.tile_cache[cache_key])
            
            if hasattr(self, 'image_processor') and self.image_processor.image_data:
                cycle_position = (current_time % (cycle_duration * len(self.image_processor.image_data))) / cycle_duration
                current_index = int(cycle_position)
                next_index = (current_index + 1) % len(self.image_processor.image_data)
                
                transition_progress = cycle_position - current_index
                
                # Update image textures
                self.update_image_textures(
                    self.image_processor.image_data[current_index],
                    self.image_processor.image_data[next_index]
                )
                
                # Calculate proper scale to fill the array while maintaining aspect ratio
                img_width = self.image_processor.image_data[current_index].shape[1]
                img_height = self.image_processor.image_data[current_index].shape[0]
                
                # Calculate aspect ratios
                img_ratio = img_width / img_height
                array_ratio = width / height
                
                if img_ratio > array_ratio:
                    # Image is wider relative to array
                    scale_x = 1.0
                    scale_y = array_ratio / img_ratio
                    offset_x = 0.0
                    offset_y = (1.0 - scale_y) * 0.5
                else:
                    # Image is taller relative to array
                    scale_x = img_ratio / array_ratio
                    scale_y = 1.0
                    offset_x = (1.0 - scale_x) * 0.5
                    offset_y = 0.0

                # Set textures and uniforms
                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, self.current_texture)
                loc = self.uniform_locations.get('current_image')
                if loc is not None and loc != -1:
                    glUniform1i(loc, 0)

                glActiveTexture(GL_TEXTURE1)
                glBindTexture(GL_TEXTURE_2D, self.next_texture)
                loc = self.uniform_locations.get('next_image')
                if loc is not None and loc != -1:
                    glUniform1i(loc, 1)

                loc = self.uniform_locations.get('transition_progress')
                if loc is not None and loc != -1:
                    glUniform1f(loc, transition_progress)

                loc = self.uniform_locations.get('image_transform')
                if loc is not None and loc != -1:
                    glUniform4f(loc, scale_x, scale_y, offset_x, offset_y)

                self.logger.debug(f"Scale: ({scale_x}, {scale_y}), Offset: ({offset_x}, {offset_y})")
                self.logger.debug(f"Transition progress: {transition_progress}")
        
        elif shader_name == 'region_blend':
            # Get pattern data
            pattern_data = self.pattern_cache[cache_key]['tile_patterns']
            
            # Ensure we don't exceed the maximum number of patterns
            max_patterns = 1000  # Must match uniform array size in shader
            if len(pattern_data) > max_patterns:
                self.logger.warning(f"Pattern data exceeds maximum size ({len(pattern_data)} > {max_patterns})")
                pattern_data = pattern_data[:max_patterns]
            
            # Set pattern data uniform
            loc = self.uniform_locations.get('tile_patterns')
            if loc is not None and loc != -1:
                glUniform4fv(loc, len(pattern_data), pattern_data.flatten())
            
            # Set number of tiles uniform
            loc = self.uniform_locations.get('num_tiles')
            if loc is not None and loc != -1:
                glUniform1i(loc, len(pattern_data))
            
            # Set colors
            color1 = np.array(config_data["color1"]) / 255.0
            color2 = np.array(config_data["color2"]) / 255.0
            
            loc = self.uniform_locations.get('color1')
            if loc is not None and loc != -1:
                glUniform3f(loc, *color1)
            
            loc = self.uniform_locations.get('color2')
            if loc is not None and loc != -1:
                glUniform3f(loc, *color2)

        else:  # Handle other shaders
            # Set color and time uniforms for non-special shaders
            color1 = np.array(config_data["color1"]) / 255.0
            color2 = np.array(config_data["color2"]) / 255.0
            current_time = glfw.get_time() * 1000.0
            
            loc = self.uniform_locations.get('color1')
            if loc is not None and loc != -1:
                glUniform3f(loc, *color1)
            
            loc = self.uniform_locations.get('color2')
            if loc is not None and loc != -1:
                glUniform3f(loc, *color2)
            
            loc = self.uniform_locations.get('time')
            if loc is not None and loc != -1:
                glUniform1f(loc, current_time / 1000.0)

        # Enable blending
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Bind buffers and set attribute pointers
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        stride = 5 * ctypes.sizeof(GLfloat)

        # Only enable and setup attributes that have valid locations
        for attr_name, loc in self.attribute_locations.items():
            if loc != -1:
                glEnableVertexAttribArray(loc)
                if attr_name == 'position':
                    glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, stride, 
                                        ctypes.c_void_p(0))
                elif attr_name == 'tile_type':
                    glVertexAttribPointer(loc, 1, GL_FLOAT, GL_FALSE, stride, 
                                        ctypes.c_void_p(2 * ctypes.sizeof(GLfloat)))
                elif attr_name == 'tile_center':
                    glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, stride, 
                                        ctypes.c_void_p(3 * ctypes.sizeof(GLfloat)))

        # Draw elements
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glDrawElements(GL_TRIANGLES, len(self.indices_array), GL_UNSIGNED_INT, None)

        # Cleanup
        for loc in self.attribute_locations.values():
            if loc != -1:
                glDisableVertexAttribArray(loc)
        
        glUseProgram(0)

def __del__(self):
    """Clean up OpenGL resources."""
    if glfw.get_current_context():
        if self.vbo is not None:
            glDeleteBuffers(1, [self.vbo])
        if self.ebo is not None:
            glDeleteBuffers(1, [self.ebo])
