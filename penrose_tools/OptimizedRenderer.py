import numpy as np
from OpenGL.GL import *
from OpenGL.GL import shaders
import ctypes
import glfw
from penrose_tools import Operations

op = Operations()

class OptimizedRenderer:
    def __init__(self):
        self.vbo = None
        self.color_vbo = None
        self.ebo = None
        self.shader_program = None
        self.tile_cache = {}
        self.tile_to_vertices = {}
        
    def setup_shader(self):
        vertex_shader = """
        #version 120
        attribute vec2 position;
        void main() {
            gl_Position = vec4(position, 0.0, 1.0);
        }
        """

        fragment_shader = """
        #version 120
        uniform vec3 color1;
        uniform vec3 color2;
        uniform float time;
        void main() {
            // Example color computation (you can adjust this to match your shader logic)
            float factor = sin(time * 0.001 + gl_FragCoord.x * 0.01) * 0.5 + 0.5;
            vec3 color = mix(color1, color2, factor);
            gl_FragColor = vec4(color, 1.0);
        }
        """

        try:
            vertex = shaders.compileShader(vertex_shader, GL_VERTEX_SHADER)
            fragment = shaders.compileShader(fragment_shader, GL_FRAGMENT_SHADER)
            self.shader_program = shaders.compileProgram(vertex, fragment)

            self.position_loc = glGetAttribLocation(self.shader_program, 'position')
            self.color1_loc = glGetUniformLocation(self.shader_program, 'color1')
            self.color2_loc = glGetUniformLocation(self.shader_program, 'color2')
            self.time_loc = glGetUniformLocation(self.shader_program, 'time')

        except Exception as e:
            print(f"Shader compilation error: {e}")
            raise


    def setup_buffers(self, tiles, width, height, scale_value):
        vertices = []
        indices = []
        offset = 0  # To keep track of the index offset
        center = complex(width / 2, height / 2)

        # Transform coordinates to OpenGL space (-1 to 1)
        def transform_to_gl_space(x, y):
            return (2.0 * x / width - 1.0, 1.0 - 2.0 * y / height)

        for tile in tiles:
            # Get screen space vertices
            screen_verts = op.to_canvas(tile.vertices, scale_value, center, 3)
            transformed_verts = [transform_to_gl_space(x, y) for x, y in screen_verts]

            # Add vertices to the list
            for vert in transformed_verts:
                vertices.extend(vert)

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

    
    def update_colors(self, tiles, shader_func, current_time, width, height, color1, color2, scale_value):
        """Update color buffer with shader effects"""
        colors = []
        
        for tile in tiles:
            # Get shader color
            modified_color = shader_func(tile, current_time, tiles, color1, color2, width, height, scale_value)
            
            # Convert color from 0-255 to 0-1 range
            normalized_color = [c / 255.0 for c in modified_color]
            
            # Get number of vertices for this tile
            start_idx, end_idx = self.tile_to_vertices[tile]
            num_verts = end_idx - start_idx
            
            # Add color for each vertex of the tile
            colors.extend(normalized_color * num_verts)
        
        # Update color buffer
        colors_array = np.array(colors, dtype=np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
        glBufferData(GL_ARRAY_BUFFER, colors_array.nbytes, colors_array, GL_DYNAMIC_DRAW)
    
    def render_tiles(self, shaders, width, height, config_data):
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

            if self.shader_program is None:
                self.setup_shader()

            self.setup_buffers(tiles, width, height, config_data['scale'])

        try:
            # Use shader program
            glUseProgram(self.shader_program)

            # Pass uniforms to shader
            glUniform3f(self.color1_loc, *(np.array(config_data["color1"]) / 255.0))
            glUniform3f(self.color2_loc, *(np.array(config_data["color2"]) / 255.0))
            glUniform1f(self.time_loc, current_time)

            # Enable blending
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            # Bind vertex array and buffers
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glEnableVertexAttribArray(self.position_loc)
            glVertexAttribPointer(self.position_loc, 2, GL_FLOAT, GL_FALSE, 0, None)

            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)

            # Draw all tiles with one call
            glDrawElements(GL_TRIANGLES, len(self.indices_array), GL_UNSIGNED_INT, None)

            # Cleanup
            glDisableVertexAttribArray(self.position_loc)
            glUseProgram(0)

        except GLError as e:
            print(f"OpenGL error during rendering: {e}")
            raise
