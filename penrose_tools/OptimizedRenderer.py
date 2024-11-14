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
        
        # Pattern uniforms
        self.uniform_locations['tile_patterns'] = glGetUniformLocation(shader_program, 'tile_patterns')
        self.uniform_locations['num_tiles'] = glGetUniformLocation(shader_program, 'num_tiles')

    def process_patterns(self, tiles, width, height, scale_value):
        """Process and cache pattern data for every tile with complete pattern coverage."""
        center = complex(width / 2, height / 2)
        patterns = []
        pattern_tiles = set()  # Track all tiles that are part of a pattern

        # First pass - identify all pattern tiles
        for tile in tiles:
            if tile.is_kite and op.is_valid_star_kite(tile):
                extended_star = op.find_star(tile, tiles)
                if len(extended_star) == 5:
                    # Add all tiles in the star
                    for star_tile in extended_star:
                        pattern_tiles.add((star_tile, 1.0))  # 1.0 = star pattern
                    
            elif not tile.is_kite and op.is_valid_starburst_dart(tile):
                extended_starburst = op.find_starburst(tile, tiles)
                if len(extended_starburst) == 10:
                    # Add all tiles in the starburst
                    for burst_tile in extended_starburst:
                        pattern_tiles.add((burst_tile, 2.0))  # 2.0 = starburst pattern

        # For logging pattern counts
        star_tiles = len([t for t, p in pattern_tiles if p == 1.0])
        starburst_tiles = len([t for t, p in pattern_tiles if p == 2.0])
        self.logger.info(f"Found {star_tiles} tiles in stars and {starburst_tiles} tiles in starbursts")

        # Second pass - process all tiles with pattern information
        for tile in tiles:
            # Transform centroid to GL space
            centroid = sum(tile.vertices) / len(tile.vertices)
            screen_centroid = op.to_canvas([centroid], scale_value, center, 3)[0]
            gl_centroid = self.transform_to_gl_space(screen_centroid[0], screen_centroid[1], width, height)
            
            # Calculate neighbor blend factor
            kite_count, dart_count = op.count_kite_and_dart_neighbors(tile)
            total_neighbors = kite_count + dart_count
            blend_factor = 0.5 if total_neighbors == 0 else kite_count / total_neighbors

            # Check if this tile is part of a pattern
            pattern_type = 0.0  # Default to normal tile
            for pattern_tile, pattern_code in pattern_tiles:
                if pattern_tile == tile:
                    pattern_type = pattern_code
                    break

            patterns.append([gl_centroid[0], gl_centroid[1], pattern_type, blend_factor])

        # Convert to numpy array and return
        return {
            'tile_patterns': np.array(patterns, dtype=np.float32)
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

        # Get cached pattern data
        pattern_data = self.pattern_cache[cache_key]
        if 'tile_patterns' in pattern_data:
            patterns = pattern_data['tile_patterns']
            
            # Set pattern data - using single uniform array
            loc = self.uniform_locations.get('tile_patterns')
            if loc is not None and loc != -1:
                glUniform4fv(loc, len(patterns), patterns)
            
            # Set number of tiles
            loc = self.uniform_locations.get('num_tiles')
            if loc is not None and loc != -1:
                glUniform1i(loc, len(patterns))

        # Set color and time uniforms
        color1 = np.array(config_data["color1"]) / 255.0
        color2 = np.array(config_data["color2"]) / 255.0
        current_time = glfw.get_time() * 1000.0
        
        # Set color uniforms
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
                elif attr_name == 'tile_centroid':
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