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

            # Calculate tile type
            tile_type = 1.0 if tile.is_kite else 0.0
            
            # Calculate centroid in screen space
            centroid = sum(tile.vertices) / len(tile.vertices)
            screen_centroid = op.to_canvas([centroid], scale_value, center, 3)[0]
            gl_centroid = self.transform_to_gl_space(screen_centroid[0], screen_centroid[1], width, height)

            # Add vertices and attributes
            for vert in transformed_verts:
                vertices.extend([
                    vert[0], vert[1],      # position
                    tile_type,             # tile_type
                    gl_centroid[0], gl_centroid[1]  # centroid
                ])

            # Create indices for this tile
            num_verts = len(transformed_verts)
            if num_verts < 3:
                continue

            # Triangulate the polygon
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
        self.attribute_locations['tile_centroid'] = glGetAttribLocation(shader_program, 'tile_centroid')

        # Get uniform locations
        self.uniform_locations['color1'] = glGetUniformLocation(shader_program, 'color1')
        self.uniform_locations['color2'] = glGetUniformLocation(shader_program, 'color2')
        self.uniform_locations['time'] = glGetUniformLocation(shader_program, 'time')
        
        # New uniform locations for region blend shader
        self.uniform_locations['star_centers'] = glGetUniformLocation(shader_program, 'star_centers')
        self.uniform_locations['starburst_centers'] = glGetUniformLocation(shader_program, 'starburst_centers')
        self.uniform_locations['neighbor_centers'] = glGetUniformLocation(shader_program, 'neighbor_centers')
        self.uniform_locations['neighbor_factors'] = glGetUniformLocation(shader_program, 'neighbor_factors')
        self.uniform_locations['num_stars'] = glGetUniformLocation(shader_program, 'num_stars')
        self.uniform_locations['num_starbursts'] = glGetUniformLocation(shader_program, 'num_starbursts')
        self.uniform_locations['num_neighbors'] = glGetUniformLocation(shader_program, 'num_neighbors')

    def process_patterns(self, tiles, width, height, scale_value):
        """Process and cache star/starburst patterns and neighbor information."""
        stars = []
        starbursts = []
        neighbor_counts = []
        center = complex(width / 2, height / 2)

        # Find all stars and starbursts
        for tile in tiles:
            # Transform centroid to screen space
            centroid = sum(tile.vertices) / len(tile.vertices)
            screen_centroid = op.to_canvas([centroid], scale_value, center, 3)[0]
            gl_centroid = self.transform_to_gl_space(screen_centroid[0], screen_centroid[1], width, height)
            
            if tile.is_kite and op.is_valid_star_kite(tile):
                extended_star = op.find_star(tile, tiles)
                if len(extended_star) == 5:
                    for t in extended_star:
                        t_centroid = sum(t.vertices) / len(t.vertices)
                        t_screen = op.to_canvas([t_centroid], scale_value, center, 3)[0]
                        t_gl = self.transform_to_gl_space(t_screen[0], t_screen[1], width, height)
                        stars.extend([t_gl[0], t_gl[1]])
                    
            elif not tile.is_kite and op.is_valid_starburst_dart(tile):
                extended_starburst = op.find_starburst(tile, tiles)
                if len(extended_starburst) == 10:
                    for t in extended_starburst:
                        t_centroid = sum(t.vertices) / len(t.vertices)
                        t_screen = op.to_canvas([t_centroid], scale_value, center, 3)[0]
                        t_gl = self.transform_to_gl_space(t_screen[0], t_screen[1], width, height)
                        starbursts.extend([t_gl[0], t_gl[1]])
                    
            # Calculate neighbor counts
            kite_count, dart_count = op.count_kite_and_dart_neighbors(tile)
            total_neighbors = kite_count + dart_count
            blend_factor = 0.5 if total_neighbors == 0 else kite_count / total_neighbors
            neighbor_counts.append((gl_centroid, blend_factor))

        # Convert to numpy arrays once
        pattern_data = {
            'stars': np.array(stars, dtype=np.float32) if stars else None,
            'starbursts': np.array(starbursts, dtype=np.float32) if starbursts else None
        }
        
        if neighbor_counts:
            centers, factors = zip(*neighbor_counts)
            pattern_data['neighbor_centers'] = np.array([(c[0], c[1]) for c in centers], dtype=np.float32).flatten()
            pattern_data['neighbor_factors'] = np.array(factors, dtype=np.float32)

        return pattern_data

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

        # Get cached pattern data
        pattern_data = self.pattern_cache[cache_key]
        
        # Set pattern uniforms
        if pattern_data.get('stars') is not None:
            stars_array = pattern_data['stars']
            loc = self.uniform_locations.get('star_centers')
            if loc != -1:
                glUniform2fv(loc, len(stars_array)//2, stars_array)
            loc = self.uniform_locations.get('num_stars')
            if loc != -1:
                glUniform1i(loc, len(stars_array)//2)

        if pattern_data.get('starbursts') is not None:
            starbursts_array = pattern_data['starbursts']
            loc = self.uniform_locations.get('starburst_centers')
            if loc != -1:
                glUniform2fv(loc, len(starbursts_array)//2, starbursts_array)
            loc = self.uniform_locations.get('num_starbursts')
            if loc != -1:
                glUniform1i(loc, len(starbursts_array)//2)

        if 'neighbor_centers' in pattern_data:
            centers_array = pattern_data['neighbor_centers']
            factors_array = pattern_data['neighbor_factors']
            loc = self.uniform_locations.get('neighbor_centers')
            if loc != -1:
                glUniform2fv(loc, len(centers_array)//2, centers_array)
            loc = self.uniform_locations.get('neighbor_factors')
            if loc != -1:
                glUniform1fv(loc, len(factors_array), factors_array)
            loc = self.uniform_locations.get('num_neighbors')
            if loc != -1:
                glUniform1i(loc, len(factors_array))

        # Set color and time uniforms
        color1 = np.array(config_data["color1"]) / 255.0
        color2 = np.array(config_data["color2"]) / 255.0
        current_time = glfw.get_time() * 1000.0  # Convert to milliseconds to match Python version
        
        glUniform3f(self.uniform_locations['color1'], *color1)
        glUniform3f(self.uniform_locations['color2'], *color2)
        if 'time' in self.uniform_locations and self.uniform_locations['time'] != -1:
            glUniform1f(self.uniform_locations['time'], current_time / 1000.0)

        # Enable blending
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Bind buffers and set attribute pointers
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        stride = 5 * ctypes.sizeof(GLfloat)  # position (2) + tile_type (1) + centroid (2)

        # Only enable and setup attributes that have valid locations
        for attr_name, loc in self.attribute_locations.items():
            if loc != -1:  # Only process valid locations
                glEnableVertexAttribArray(loc)
                if attr_name == 'position':
                    glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, stride, 
                                        ctypes.c_void_p(0))
                elif attr_name == 'tile_type':
                    glVertexAttribPointer(loc, 1, GL_FLOAT, GL_FALSE, stride, 
                                        ctypes.c_void_p(2 * ctypes.sizeof(GLfloat)))
                elif attr_name == 'tile_centroid':
                    glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, stride, 
                                        ctypes.c_void_p(3 * ctypes.sizeof(GLfloat)))

        # Draw elements
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glDrawElements(GL_TRIANGLES, len(self.indices_array), GL_UNSIGNED_INT, None)

        # Cleanup - only disable valid attributes
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