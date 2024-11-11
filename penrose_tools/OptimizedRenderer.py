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
        self.shader_program = None
        self.tile_cache = {}
        self.tile_to_vertices = {}
        
    def setup_shader(self):
        # Simpler vertex shader without matrix multiplication
        vertex_shader = """
        #version 120
        attribute vec2 position;
        attribute vec4 color;
        varying vec4 frag_color;
        
        void main() {
            gl_Position = vec4(position, 0.0, 1.0);
            frag_color = color;
        }
        """
        
        fragment_shader = """
        #version 120
        varying vec4 frag_color;
        
        void main() {
            gl_FragColor = frag_color;
        }
        """
        
        try:
            vertex = shaders.compileShader(vertex_shader, GL_VERTEX_SHADER)
            fragment = shaders.compileShader(fragment_shader, GL_FRAGMENT_SHADER)
            self.shader_program = shaders.compileProgram(vertex, fragment)
            
            self.position_loc = glGetAttribLocation(self.shader_program, 'position')
            self.color_loc = glGetAttribLocation(self.shader_program, 'color')
            
        except Exception as e:
            print(f"Shader compilation error: {e}")
            raise

    def setup_buffers(self, tiles, width, height, scale_value):
        vertices = []
        colors = []
        
        center = complex(width / 2, height / 2)
        self.tile_to_vertices.clear()
        
        # Transform coordinates to OpenGL space (-1 to 1)
        def transform_to_gl_space(x, y):
            return (2.0 * x / width - 1.0, 1.0 - 2.0 * y / height)
        
        for tile in tiles:
            # Store starting vertex index for this tile
            start_idx = len(vertices) // 2
            
            # Get screen space vertices
            screen_verts = op.to_canvas(tile.vertices, scale_value, center, 3)
            
            # Transform to GL space and store vertices
            for x, y in screen_verts:
                gl_x, gl_y = transform_to_gl_space(x, y)
                vertices.extend([gl_x, gl_y])
            
            # Store vertex range for this tile
            self.tile_to_vertices[tile] = (start_idx, len(vertices) // 2)
            
            # Add initial colors
            base_color = [0, 0, 0, 1.0]  # Initial black with full alpha
            colors.extend(base_color * len(screen_verts))
        
        # Convert to numpy arrays
        self.vertices_array = np.array(vertices, dtype=np.float32)
        self.colors_array = np.array(colors, dtype=np.float32)
        
        # Create and bind vertex buffer
        if self.vbo is None:
            self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.vertices_array.nbytes, self.vertices_array, GL_STATIC_DRAW)
        
        # Create and bind color buffer
        if self.color_vbo is None:
            self.color_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
        glBufferData(GL_ARRAY_BUFFER, self.colors_array.nbytes, self.colors_array, GL_DYNAMIC_DRAW)
    
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
            tuple(config_data["color1"]),
            tuple(config_data["color2"])
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
            
            # Update colors based on current shader effect
            self.update_colors(
                self.tile_cache[cache_key],
                shaders.current_shader(),
                current_time,
                width,
                height,
                config_data["color1"],
                config_data["color2"],
                config_data['scale']
            )
            
            # Enable blending
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Bind vertex buffer
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glVertexAttribPointer(self.position_loc, 2, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(self.position_loc)
            
            # Bind color buffer
            glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
            glVertexAttribPointer(self.color_loc, 4, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(self.color_loc)
            
            # Draw tiles
            for tile in self.tile_cache[cache_key]:
                start_idx, end_idx = self.tile_to_vertices[tile]
                num_vertices = end_idx - start_idx
                glDrawArrays(GL_TRIANGLE_FAN, start_idx, num_vertices)
            
            # Cleanup
            glDisableVertexAttribArray(self.position_loc)
            glDisableVertexAttribArray(self.color_loc)
            glUseProgram(0)
            
        except GLError as e:
            print(f"OpenGL error during rendering: {e}")
            raise