# penrose_tools/OptimizedRenderer.py
import numpy as np
from OpenGL.GL import *
from OpenGL.GL import shaders
import ctypes
import glfw
from .Operations import Operations
from .ShaderManager import ShaderManager
import logging

op = Operations()

class OptimizedRenderer:
    def __init__(self):
        self.vbo = None
        self.ebo = None
        self.tile_cache = {}
        self.shader_manager = ShaderManager()  # Initialize ShaderManager
        self.attribute_locations = {}
        self.uniform_locations = {}
        self.logger = logging.getLogger('OptimizedRenderer')
        self.ripples = []  # For ripple effects
        self.last_raindrop_time = 0

    def transform_to_gl_space(self, x, y, width, height):
        return (2.0 * x / width - 1.0, 1.0 - 2.0 * y / height)

    def setup_buffers(self, tiles, width, height, scale_value):
        vertices = []
        indices = []
        offset = 0  # To keep track of the index offset
        center = complex(width / 2, height / 2)

        for tile in tiles:
            # Get screen space vertices
            screen_verts = op.to_canvas(tile.vertices, scale_value, center, 3)
            transformed_verts = [self.transform_to_gl_space(x, y, width, height) for x, y in screen_verts]

            # Calculate attributes needed by shaders
            tile_type = 1.0 if tile.is_kite else 0.0
            centroid_x = sum([v[0] for v in transformed_verts]) / len(transformed_verts)
            centroid_y = sum([v[1] for v in transformed_verts]) / len(transformed_verts)

            # For raindrop ripple effect, store tile center positions
            tile_center_x = centroid_x
            tile_center_y = centroid_y

            # Add vertices and attributes
            for vert in transformed_verts:
                vertices.extend([
                    vert[0], vert[1],       # position
                    tile_type,              # tile_type
                    centroid_x, centroid_y,  # centroid
                    tile_center_x, tile_center_y  # tile_center
                    # Add other attributes as needed
                ])

            # Create indices for this tile
            num_verts = len(transformed_verts)
            if num_verts < 3:
                continue  # Skip invalid tiles

            # Triangulate the polygon (assuming convex polygons)
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
        glBufferData(GL_ARRAY_BUFFER, self.vertices_array.nbytes, self.vertices_array, GL_STATIC_DRAW)

        # Create and bind element buffer (index buffer)
        if self.ebo is None:
            self.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.indices_array.nbytes, self.indices_array, GL_STATIC_DRAW)

    def get_shader_locations(self):
        shader_program = self.shader_manager.current_shader_program()
        self.attribute_locations.clear()
        self.uniform_locations.clear()

        # Get attribute and uniform locations based on the current shader
        # Common attributes
        self.attribute_locations['position'] = glGetAttribLocation(shader_program, 'position')
        self.attribute_locations['tile_type'] = glGetAttribLocation(shader_program, 'tile_type')
        self.attribute_locations['centroid'] = glGetAttribLocation(shader_program, 'centroid')
        self.attribute_locations['tile_center'] = glGetAttribLocation(shader_program, 'tile_center')

        # Uniform locations
        self.uniform_locations['color1'] = glGetUniformLocation(shader_program, 'color1')
        self.uniform_locations['color2'] = glGetUniformLocation(shader_program, 'color2')
        self.uniform_locations['time'] = glGetUniformLocation(shader_program, 'time')

        # Uniforms for ripple effect
        possible_uniforms = ['ripple_centers', 'ripple_start_times']
        for uniform in possible_uniforms:
            loc = glGetUniformLocation(shader_program, uniform)
            if loc != -1:
                self.uniform_locations[uniform] = loc

    def render_tiles(self, width, height, config_data):
        current_time = glfw.get_time() * 1000
        cache_key = (
            tuple(config_data['gamma']),
            width,
            height,
            config_data['scale'],
        )

        # Regenerate tiles if needed
        if cache_key not in self.tile_cache:
            self.tile_cache.clear()
            tiles = op.tiling(config_data['gamma'], width, height, config_data['scale'])
            op.calculate_neighbors(tiles)
            self.tile_cache[cache_key] = tiles

            self.setup_buffers(tiles, width, height, config_data['scale'])
            self.get_shader_locations()

        # Use current shader program
        shader_program = self.shader_manager.current_shader_program()
        glUseProgram(shader_program)

        # Set uniforms
        color1 = np.array(config_data["color1"]) / 255.0
        color2 = np.array(config_data["color2"]) / 255.0
        glUniform3f(self.uniform_locations['color1'], *color1)
        glUniform3f(self.uniform_locations['color2'], *color2)
        glUniform1f(self.uniform_locations['time'], current_time)

        # Handle ripple effect uniforms if present
        if 'ripple_centers' in self.uniform_locations:
            MAX_RIPPLES = 5
            # Update ripple data
            if not hasattr(self, 'ripples'):
                self.ripples = []
                self.last_raindrop_time = 0

            # Create new raindrop every 3.5 seconds, if we're below the max ripples limit
            if current_time - self.last_raindrop_time > 3500 and len(self.ripples) < MAX_RIPPLES:
                self.last_raindrop_time = current_time
                # Choose a random tile center
                tiles = self.tile_cache[cache_key]
                random_tile = np.random.choice(list(tiles))
                centroid = op.calculate_centroid(random_tile.vertices)
                # Transform to GL space
                center_x, center_y = self.transform_to_gl_space(centroid.real, centroid.imag, width, height)
                self.ripples.append({'center': (center_x, center_y), 'start_time': current_time})

            # Remove old ripples
            self.ripples = [r for r in self.ripples if (current_time - r['start_time']) < 15000]

            # Prepare data arrays
            ripple_centers = np.zeros((MAX_RIPPLES, 2), dtype=np.float32)
            ripple_start_times = np.zeros(MAX_RIPPLES, dtype=np.float32)

            for i, ripple in enumerate(self.ripples):
                if i >= MAX_RIPPLES:
                    break
                ripple_centers[i] = ripple['center']
                ripple_start_times[i] = ripple['start_time']

            # Pass to shader
            loc_centers = self.uniform_locations['ripple_centers']
            loc_times = self.uniform_locations['ripple_start_times']
            glUniform2fv(loc_centers, MAX_RIPPLES, ripple_centers.flatten())
            glUniform1fv(loc_times, MAX_RIPPLES, ripple_start_times)

        # Enable blending
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Bind buffers and set attribute pointers
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        stride = 7 * ctypes.sizeof(GLfloat)  # Adjust stride based on number of attributes

        offset = 0

        # Position
        if 'position' in self.attribute_locations:
            loc = self.attribute_locations['position']
            glEnableVertexAttribArray(loc)
            glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(offset))
            offset += 2 * ctypes.sizeof(GLfloat)

        # Tile Type
        if 'tile_type' in self.attribute_locations:
            loc = self.attribute_locations['tile_type']
            glEnableVertexAttribArray(loc)
            glVertexAttribPointer(loc, 1, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(offset))
            offset += 1 * ctypes.sizeof(GLfloat)

        # Centroid
        if 'centroid' in self.attribute_locations:
            loc = self.attribute_locations['centroid']
            glEnableVertexAttribArray(loc)
            glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(offset))
            offset += 2 * ctypes.sizeof(GLfloat)

        # Tile Center
        if 'tile_center' in self.attribute_locations:
            loc = self.attribute_locations['tile_center']
            glEnableVertexAttribArray(loc)
            glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(offset))
            offset += 2 * ctypes.sizeof(GLfloat)

        # Draw elements
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glDrawElements(GL_TRIANGLES, len(self.indices_array), GL_UNSIGNED_INT, None)

        # Cleanup
        for loc in self.attribute_locations.values():
            glDisableVertexAttribArray(loc)
        glUseProgram(0)
