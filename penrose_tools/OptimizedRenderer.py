# penrose_tools/OptimizedRenderer.py
import numpy as np
from OpenGL.GL import *
import ctypes
import glfw
from .Operations import Operations
from .ShaderManager import ShaderManager
import logging
import time

op = Operations()

class OptimizedRenderer:
    def __init__(self):
        """Initialize the renderer after OpenGL context is created."""
        self.vao = None
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
        
        # Initialize VAO and buffers
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        # Enable line smoothing and proper blending
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Enable polygon smoothing
        # glEnable(GL_POLYGON_SMOOTH)
        # glHint(GL_POLYGON_SMOOTH_HINT, GL_NICEST)

        # Enable polygon offset
        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(-1.0, -1.0)  # Adjust these values if needed

        # Configure multi-sampling
        glEnable(GL_MULTISAMPLE)
        # Request 8x MSAA
        glfw.window_hint(glfw.SAMPLES, 8)

    def force_refresh(self):
        """Force a refresh of the buffers by clearing the tile cache and textures."""
        self.tile_cache.clear()
        self.pattern_cache.clear()
        
        # Clean up pattern texture if it exists
        if hasattr(self, 'pattern_texture'):
            glDeleteTextures([self.pattern_texture])
            delattr(self, 'pattern_texture')
        
        if hasattr(self, 'texture_dimensions'):
            delattr(self, 'texture_dimensions')


    def transform_to_gl_space(self, x, y, width, height):
        """Transform screen coordinates to OpenGL coordinate space."""
        # Snap to pixel boundaries
        x = round(x)
        y = round(y)
        return (2.0 * x / width - 1.0, 1.0 - 2.0 * y / height)
    
    def create_texture(self, image_data):
        """Create OpenGL texture with proper parameters."""
        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        
        # Set proper filtering modes
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        
        # Ensure proper alignment
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        
        # Use RGB format consistently
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB8, 
                    image_data.shape[1], image_data.shape[0],
                    0, GL_RGB, GL_UNSIGNED_BYTE, image_data)
        
        return texture

    def update_image_textures(self, current_image, next_image):
        """Update the current and next image textures with proper cleanup."""
        # Delete existing textures if they exist
        if hasattr(self, 'current_texture'):
            glDeleteTextures([self.current_texture])
            glDeleteTextures([self.next_texture])
        
        # Create fresh textures
        self.current_texture = self.create_texture(current_image)
        self.next_texture = self.create_texture(next_image)
        
        # Reset texture bindings
        glBindTexture(GL_TEXTURE_2D, 0)
            
    def set_image_transform_uniforms(self, shader_program, width, height, current_index):
        """Calculate and set image transformation uniforms."""
        if not hasattr(self, 'image_processor') or not self.image_processor.image_data:
            return
            
        # Get dimensions
        img = self.image_processor.image_data[current_index]
        img_width = float(img.shape[1])
        img_height = float(img.shape[0])
        screen_width = float(width)
        screen_height = float(height)
        
        # Calculate aspect ratios
        img_ratio = img_width / img_height
        screen_ratio = screen_width / screen_height
        
        # Calculate scales
        if img_ratio > screen_ratio:
            # Fit to width
            scale_x = 1.0
            scale_y = screen_ratio / img_ratio
            offset_x = 0.0
            offset_y = (1.0 - scale_y) / 2.0
        else:
            # Fit to height
            scale_x = img_ratio / screen_ratio
            scale_y = 1.0
            offset_x = (1.0 - scale_x) / 2.0
            offset_y = 0.0
        
        # Debug output
        self.logger.debug(f"Transform calc:")
        self.logger.debug(f"Image: {img_width}x{img_height} ratio={img_ratio}")
        self.logger.debug(f"Screen: {screen_width}x{screen_height} ratio={screen_ratio}")
        self.logger.debug(f"Scale: ({scale_x}, {scale_y})")
        self.logger.debug(f"Offset: ({offset_x}, {offset_y})")
        
        # Set uniform
        loc = glGetUniformLocation(shader_program, 'image_transform')
        if loc != -1:
            glUniform4f(loc, scale_x, scale_y, offset_x, offset_y)

    def set_texture_uniforms(self, shader_program, transition_progress):
        """Set texture uniforms with proper state management."""
        # Reset texture units
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, 0)
        
        # Bind current image
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.current_texture)
        loc = glGetUniformLocation(shader_program, 'current_image')
        if loc != -1:
            glUniform1i(loc, 0)
        
        # Bind next image
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.next_texture)
        loc = glGetUniformLocation(shader_program, 'next_image')
        if loc != -1:
            glUniform1i(loc, 1)
        
        # Set transition progress
        loc = glGetUniformLocation(shader_program, 'transition_progress')
        if loc != -1:
            glUniform1f(loc, transition_progress)
        
        # Reset to texture unit 0
        glActiveTexture(GL_TEXTURE0)

    def setup_buffers(self, tiles, edge_map, width, height, scale_value):
        """
        Set up separate buffers for fills (triangles) and edges (lines).
        Modified to shrink edges slightly to avoid black overdraw at star-vertices.
        """
        # ------------ 1) Build Fill Buffers (unchanged) ------------
        fill_vertices = []
        fill_indices = []
        vertex_offset = 0
        center = complex(width / 2, height / 2)

        for tile in tiles:
            # Transform tile vertices to screen->GL space
            screen_verts = op.to_canvas(tile.vertices, scale_value, center, shrink_factor=1.0)
            transformed_verts = [
                self.transform_to_gl_space(x, y, width, height)
                for (x, y) in screen_verts
            ]

            centroid = sum(tile.vertices) / len(tile.vertices)
            screen_centroid = op.to_canvas([centroid], scale_value, center, 1.0)[0]
            gl_centroid = self.transform_to_gl_space(screen_centroid[0], screen_centroid[1], width, height)

            for vert in transformed_verts:
                fill_vertices.extend([
                    vert[0], vert[1],               # position
                    1.0 if tile.is_kite else 0.0,   # tile_type
                    gl_centroid[0], gl_centroid[1]  # centroid
                ])

            # Triangulate
            n = len(transformed_verts)
            for i in range(1, n - 1):
                fill_indices.extend([vertex_offset, vertex_offset + i, vertex_offset + i + 1])
            vertex_offset += n

        self.vertices_array = np.array(fill_vertices, dtype=np.float32)
        self.fill_indices_array = np.array(fill_indices, dtype=np.uint32)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.vertices_array.nbytes, self.vertices_array, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.fill_indices_array.nbytes, self.fill_indices_array, GL_STATIC_DRAW)

        stride = 5 * ctypes.sizeof(GLfloat)
        offset = ctypes.c_void_p(0)

        # position -> location 0
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, offset)

        # tile_type -> location 1
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(
            1, 1, GL_FLOAT, GL_FALSE, stride,
            ctypes.c_void_p(2 * ctypes.sizeof(GLfloat))
        )

        # centroid -> location 2
        glEnableVertexAttribArray(2)
        glVertexAttribPointer(
            2, 2, GL_FLOAT, GL_FALSE, stride,
            ctypes.c_void_p(3 * ctypes.sizeof(GLfloat))
        )

        glBindVertexArray(0)

        # ------------ 2) Build Edges, but apply a slight 'shrink_factor' ------------
        edge_vertices = []
        edge_indices = []
        edge_offset = 0

        self.edges_vao = glGenVertexArrays(1)
        self.edges_vbo = glGenBuffers(1)
        self.edges_ebo = glGenBuffers(1)

        glBindVertexArray(self.edges_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.edges_vbo)

        # Shrink edges a tiny bit to avoid black overdraw
        edge_shrink_factor = 0.99

        for (v1, v2), shared_tiles in edge_map.items():
            # Notice the edge_shrink_factor below:
            s1 = op.to_canvas([v1], scale_value, center, edge_shrink_factor)[0]
            gl_v1 = self.transform_to_gl_space(s1[0], s1[1], width, height)

            s2 = op.to_canvas([v2], scale_value, center, edge_shrink_factor)[0]
            gl_v2 = self.transform_to_gl_space(s2[0], s2[1], width, height)

            # We'll store a dummy tile_type=0, dummy centroid=0
            edge_vertices.extend([
                gl_v1[0], gl_v1[1], 0.0, 0.0, 0.0,
                gl_v2[0], gl_v2[1], 0.0, 0.0, 0.0
            ])

            # Indices for the line
            edge_indices.extend([edge_offset, edge_offset + 1])
            edge_offset += 2

        self.edge_vertices_array = np.array(edge_vertices, dtype=np.float32)
        self.edge_indices_array = np.array(edge_indices, dtype=np.uint32)

        glBufferData(GL_ARRAY_BUFFER, self.edge_vertices_array.nbytes,
                     self.edge_vertices_array, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.edges_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.edge_indices_array.nbytes,
                     self.edge_indices_array, GL_STATIC_DRAW)

        stride = 5 * ctypes.sizeof(GLfloat)
        offset = ctypes.c_void_p(0)

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, offset)

        glBindVertexArray(0)


    def get_shader_locations(self):
        """Get locations of shader attributes and uniforms."""
        shader_program = self.shader_manager.current_shader_program()
        self.attribute_locations.clear()
        self.uniform_locations.clear()

        # Get attribute locations
        self.attribute_locations['position'] = glGetAttribLocation(shader_program, 'position')
        self.attribute_locations['tile_type'] = glGetAttribLocation(shader_program, 'tile_type')
        self.attribute_locations['tile_centroid'] = glGetAttribLocation(shader_program, 'tile_centroid')

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
            # Standard uniforms for all shaders
            self.uniform_locations.update({
                'color1': glGetUniformLocation(shader_program, 'color1'),
                'color2': glGetUniformLocation(shader_program, 'color2'),
                'time': glGetUniformLocation(shader_program, 'time')
            })
            
            # Region blend specific uniforms
            if shader_name == 'region_blend':
                self.uniform_locations.update({
                    'pattern_texture': glGetUniformLocation(shader_program, 'pattern_texture'),
                    'texture_width': glGetUniformLocation(shader_program, 'texture_width'),
                    'texture_height': glGetUniformLocation(shader_program, 'texture_height')
                })

        # Debug log uniform locations
        self.logger.debug(f"Shader uniforms for {shader_name}:")
        for name, loc in self.uniform_locations.items():
            self.logger.debug(f"  {name}: {loc}")

    def create_pattern_texture(self, pattern_data):
        """Create texture from pattern data."""
        # Calculate texture dimensions to fit all pattern data
        # Make it as square as possible
        total_patterns = len(pattern_data)
        texture_width = int(np.ceil(np.sqrt(total_patterns)))
        texture_height = int(np.ceil(total_patterns / texture_width))
        
        # Create texture data array (width × height × RGBA)
        texture_data = np.zeros((texture_height, texture_width, 4), dtype=np.float32)
        
        # Fill texture with pattern data
        for i, pattern in enumerate(pattern_data):
            y = i // texture_width
            x = i % texture_width
            texture_data[y, x] = pattern
        
        # Create and configure texture
        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        
        # Upload texture data
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, texture_width, texture_height, 
                    0, GL_RGBA, GL_FLOAT, texture_data)
        
        return texture, texture_width, texture_height

    def process_patterns(self, tiles, width, height, scale_value):
        """Process and cache pattern data with complete region detection."""
        center = complex(width / 2, height / 2)
        patterns = []
        pattern_tiles = set()

        # First pass - identify complete regions
        stars = []
        starbursts = []
        
        for tile in tiles:
            if tile not in pattern_tiles:
                if tile.is_kite and op.is_valid_star_kite(tile):
                    star_tiles = op.find_star(tile, tiles)
                    if len(star_tiles) == 5:
                        stars.append(star_tiles)
                        pattern_tiles.update(star_tiles)
                elif not tile.is_kite and op.is_valid_starburst_dart(tile):
                    starburst_tiles = op.find_starburst(tile, tiles)
                    if len(starburst_tiles) == 10:
                        starbursts.append(starburst_tiles)
                        pattern_tiles.update(starburst_tiles)

        # Second pass - process all tiles
        for tile in tiles:
            centroid = sum(tile.vertices) / len(tile.vertices)
            screen_centroid = op.to_canvas([centroid], scale_value, center, 3)[0]
            gl_centroid = self.transform_to_gl_space(screen_centroid[0], screen_centroid[1], width, height)
            
            # Initialize with default values
            pattern_type = 0.0
            blend_factor = 0.5  # Default blend factor
            
            # Check patterns first
            in_pattern = False
            for star in stars:
                if tile in star:
                    pattern_type = 1.0
                    blend_factor = 0.3
                    in_pattern = True
                    break
            
            if not in_pattern:
                for burst in starbursts:
                    if tile in burst:
                        pattern_type = 2.0
                        blend_factor = 0.7
                        in_pattern = True
                        break
            
            if not in_pattern:
                # Calculate neighbor-based blend for non-pattern tiles
                kite_count, dart_count = op.count_kite_and_dart_neighbors(tile)
                total_neighbors = kite_count + dart_count
                blend_factor = 0.5 if total_neighbors == 0 else kite_count / total_neighbors
            
            # Store centroid position and pattern data
            patterns.append([
                gl_centroid[0],     # x position
                gl_centroid[1],     # y position
                pattern_type,       # 0=normal, 1=star, 2=starburst
                blend_factor        # blending factor
            ])

        pattern_array = np.array(patterns, dtype=np.float32)
        return {'tile_patterns': pattern_array}

    def set_standard_uniforms(self, shader_program, config_data):
        """Set standard uniforms for all shaders."""
        # Set color uniforms
        loc = glGetUniformLocation(shader_program, 'color1')
        if loc != -1:
            glUniform3f(loc, 
                        config_data['color1'][0] / 255.0,
                        config_data['color1'][1] / 255.0, 
                        config_data['color1'][2] / 255.0)
        
        loc = glGetUniformLocation(shader_program, 'color2')
        if loc != -1:
            glUniform3f(loc, 
                        config_data['color2'][0] / 255.0,
                        config_data['color2'][1] / 255.0, 
                        config_data['color2'][2] / 255.0)
        
        # Set time uniform
        loc = glGetUniformLocation(shader_program, 'time')
        if loc != -1:
            glUniform1f(loc, glfw.get_time())
        
        # Set vertex_offset uniform
        loc = glGetUniformLocation(shader_program, 'vertex_offset')
        if loc != -1:
            glUniform1f(loc, float(config_data['vertex_offset']))

    def handle_pixelation_slideshow(self, shader_program, width, height, cache_key):
        """Handle the pixelation slideshow shader setup and image processing."""
        tiles, _ = self.tile_cache[cache_key]  # Unpack only the tiles from the cache
        
        if not hasattr(self, 'image_processor'):
            self.image_processor = Operations()
        
        if not hasattr(self, 'last_image_update') or time.time() - self.last_image_update > 0.1:
            self.image_processor.load_and_process_images(tiles)  # Pass only the tiles
            self.image_processor.create_tile_to_pixel_map(tiles)
            self.last_image_update = time.time()
        
        current_time = glfw.get_time() * 1000.0
        transition_duration = 8000.0
        cycle_duration = 15000.0
        
        # Initialize image processor if needed
        if not hasattr(self, 'image_processor') or not self.image_processor.image_data:
            self.logger.warning("No images available for slideshow")
            return
        
        # Calculate transition timings
        total_images = len(self.image_processor.image_data)
        cycle_position = (current_time % (cycle_duration * total_images)) / cycle_duration
        current_index = int(cycle_position)
        next_index = (current_index + 1) % total_images
        transition_progress = cycle_position - current_index
        
        self.logger.debug(f"Slideshow status: {current_index}->{next_index} ({transition_progress:.2f})")
        
        try:
            # Update textures
            self.update_image_textures(
                self.image_processor.image_data[current_index],
                self.image_processor.image_data[next_index]
            )
            
            # Set transformation uniforms
            self.set_image_transform_uniforms(shader_program, width, height, current_index)
            
            # Set texture uniforms
            self.set_texture_uniforms(shader_program, transition_progress)
            
        except Exception as e:
            self.logger.error(f"Error in pixelation slideshow: {str(e)}")
            raise

    def handle_region_blend(self, shader_program, cache_key, config_data):
        """Handle region blend shader setup."""
        # First set standard color uniforms
        self.set_standard_uniforms(shader_program, config_data)
        
        # Then handle pattern-specific setup
        pattern_data = self.pattern_cache[cache_key]['tile_patterns']
        
        # Calculate required texture dimensions
        total_patterns = len(pattern_data)
        new_texture_width = int(np.ceil(np.sqrt(total_patterns)))
        new_texture_height = int(np.ceil(total_patterns / new_texture_width))
        
        # Check if we need to recreate the texture due to size change
        needs_new_texture = (
            not hasattr(self, 'pattern_texture') or 
            not hasattr(self, 'texture_dimensions') or
            new_texture_width > self.texture_dimensions[0] or
            new_texture_height > self.texture_dimensions[1]
        )

        if needs_new_texture:
            # Delete old texture if it exists
            if hasattr(self, 'pattern_texture'):
                glDeleteTextures([self.pattern_texture])
            
            # Create new texture with new dimensions
            self.pattern_texture, width, height = self.create_pattern_texture(pattern_data)
            self.texture_dimensions = (width, height)
            self.logger.debug(f"Created new pattern texture with dimensions: {width}x{height}")
        else:
            # Update existing texture
            glBindTexture(GL_TEXTURE_2D, self.pattern_texture)
            texture_data = np.zeros((self.texture_dimensions[1], self.texture_dimensions[0], 4), dtype=np.float32)
            
            # Safely copy pattern data
            for i, pattern in enumerate(pattern_data):
                y = i // self.texture_dimensions[0]
                x = i % self.texture_dimensions[0]
                
                # Double-check bounds to prevent any possible index errors
                if y < texture_data.shape[0] and x < texture_data.shape[1]:
                    texture_data[y, x] = pattern
            
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, 
                        self.texture_dimensions[0], self.texture_dimensions[1],
                        0, GL_RGBA, GL_FLOAT, texture_data)

        # Bind texture and set uniforms
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.pattern_texture)
        
        # Debug output
        self.logger.debug(f"Current texture dimensions: {self.texture_dimensions}")
        self.logger.debug(f"Total patterns: {total_patterns}")
        
        # Set texture uniforms
        loc = glGetUniformLocation(shader_program, 'pattern_texture')
        if loc != -1:
            glUniform1i(loc, 0)
        
        loc = glGetUniformLocation(shader_program, 'texture_width')
        if loc != -1:
            glUniform1i(loc, self.texture_dimensions[0])
            
        loc = glGetUniformLocation(shader_program, 'texture_height')
        if loc != -1:
            glUniform1i(loc, self.texture_dimensions[1])

    def render_tiles(self, width, height, config_data):
        if self.current_shader_index != self.shader_manager.current_shader_index:
            self.current_shader_index = self.shader_manager.current_shader_index
            self.force_refresh()
            self.logger.info("Shader changed, forcing buffer refresh")

        # Use a cache key to avoid regenerating every frame...
        cache_key = (
            tuple(config_data['gamma']),
            width,
            height,
            config_data['scale'],
        )

        if cache_key not in self.tile_cache:
            self.tile_cache.clear()
            self.pattern_cache.clear()

            # 1) Generate tiles
            tiles = op.tiling(config_data['gamma'], width, height, config_data['scale'])

            # 2) Get the edge map
            edge_map = op.calculate_neighbors(tiles)  # <-- returns edge_map now!

            # 3) Store in cache
            self.tile_cache[cache_key] = (tiles, edge_map)

            # 4) Build patterns if you want
            self.pattern_cache[cache_key] = self.process_patterns(tiles, width, height, config_data['scale'])

            # 5) Create buffers
            self.setup_buffers(tiles, edge_map, width, height, config_data['scale'])
            self.get_shader_locations()

        else:
            tiles, edge_map = self.tile_cache[cache_key]

        # Select + use the current shader
        shader_program = self.shader_manager.current_shader_program()
        glUseProgram(shader_program)

        # Set standard uniforms, etc.
        shader_name = self.shader_manager.shader_names[self.current_shader_index]
        if shader_name == 'pixelation_slideshow':
            self.handle_pixelation_slideshow(shader_program, width, height, cache_key)
        elif shader_name == 'region_blend':
            self.handle_region_blend(shader_program, cache_key, config_data)
        else:
            self.set_standard_uniforms(shader_program, config_data)

        # ---------- PASS 1: Fill Polygons ----------
        glBindVertexArray(self.vao)   # our fill VAO
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)

        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glBlendEquation(GL_FUNC_ADD)

        glDrawElements(GL_TRIANGLES, len(self.fill_indices_array), GL_UNSIGNED_INT, None)

        glBindVertexArray(0)

        # ---------- PASS 2: Draw Unique Edges ----------
        glBindVertexArray(self.edges_vao)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.edges_ebo)

        # Set edge color to black
        loc = glGetUniformLocation(shader_program, 'edge_color')
        if loc != -1:
            glUniform3f(loc, 0.0, 0.0, 0.0)  # RGB black

        glLineWidth(1.0)
        glDrawElements(GL_LINES, len(self.edge_indices_array), GL_UNSIGNED_INT, None)


        # Cleanup
        glBindVertexArray(0)
        glUseProgram(0)

    def resize(self, width, height):
        glViewport(0, 1, width, height)  # Offset viewport by 1 pixel vertically

    def __del__(self):
        """Clean up OpenGL resources."""
        if glfw.get_current_context():
            if hasattr(self, 'pattern_texture'):
                glDeleteTextures([self.pattern_texture])
            if hasattr(self, 'current_texture'):
                glDeleteTextures([self.current_texture])
            if hasattr(self, 'next_texture'):
                glDeleteTextures([self.next_texture])
            if hasattr(self, 'vao'):
                glDeleteVertexArrays(1, [self.vao])
            if hasattr(self, 'vbo'):
                glDeleteBuffers(1, [self.vbo])
            if hasattr(self, 'ebo'):
                glDeleteBuffers(1, [self.ebo])
            if hasattr(self, 'edge_ebo'):
                glDeleteBuffers(1, [self.edge_ebo])

