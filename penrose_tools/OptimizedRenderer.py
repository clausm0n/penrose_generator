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
        self.ebo = None  # Element buffer for indices
        self.shader_program = None
        self.spatial_grid = {}
        self.grid_size = 100
        self.tile_cache = {}
        self.visible_tiles_cache = set()
        self.indices = []
        self.vertices_per_tile = 0
        self.tile_vertex_counts = {}
        self.tile_to_vertices = {}
        
    def setup_shader(self):
        vertex_shader = """
        #version 120
        attribute vec2 position;
        attribute vec4 color;
        varying vec4 frag_color;
        
        void main() {
            gl_Position = gl_ModelViewProjectionMatrix * vec4(position, 0.0, 1.0);
            frag_color = color / 255.0;  // Normalize color values
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
        indices = []
        
        center = complex(width / 2, height / 2)
        vertex_count = 0
        
        self.tile_vertex_counts.clear()
        self.tile_to_vertices.clear()
        
        for tile in tiles:
            # Transform vertices to screen space
            screen_verts = op.to_canvas(tile.vertices, scale_value, center, 3)
            start_idx = len(vertices) // 2
            
            # Add vertices
            for x, y in screen_verts:
                vertices.extend([x, y])
            
            # Store the vertex range for this tile
            num_verts = len(screen_verts)
            self.tile_to_vertices[tile] = (start_idx, start_idx + num_verts)
            
            # Create triangle fan indices for polygon
            for i in range(1, num_verts - 1):
                indices.extend([vertex_count, vertex_count + i, vertex_count + i + 1])
            
            # Add base colors (will be updated later)
            colors.extend([0, 0, 0, 255] * num_verts)  # Initialize with transparent black
            
            self.tile_vertex_counts[tile] = num_verts
            vertex_count += num_verts
        
        # Convert to numpy arrays
        self.vertices_array = np.array(vertices, dtype=np.float32)
        self.colors_array = np.array(colors, dtype=np.uint8)
        self.indices_array = np.array(indices, dtype=np.uint32)
        
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
        
        # Create and bind element buffer
        if self.ebo is None:
            self.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.indices_array.nbytes, self.indices_array, GL_STATIC_DRAW)
        
        self.num_indices = len(indices)
    
    def update_colors(self, tiles, shader_func, current_time, width, height, color1, color2, scale_value):
        """Update color buffer with shader effects"""
        colors = np.zeros(len(self.colors_array), dtype=np.uint8)
        
        for tile in tiles:
            # Get shader color for this tile
            modified_color = shader_func(tile, current_time, tiles, color1, color2, width, height, scale_value)
            
            # Get vertex range for this tile
            start_idx, end_idx = self.tile_to_vertices[tile]
            vertex_count = end_idx - start_idx
            
            # Fill color array for all vertices of this tile
            for i in range(vertex_count):
                base_idx = (start_idx + i) * 4  # 4 components per vertex
                colors[base_idx:base_idx + 4] = modified_color
        
        # Update GPU buffer
        glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
        glBufferSubData(GL_ARRAY_BUFFER, 0, colors.nbytes, colors)
    
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
        
        # Check if we need to regenerate tiles
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
            
            # Update projection matrix
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            glOrtho(0, width, height, 0, -1, 1)
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            
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
            
            # Bind buffers and set attributes
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glVertexAttribPointer(self.position_loc, 2, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(self.position_loc)
            
            glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
            glVertexAttribPointer(self.color_loc, 4, GL_UNSIGNED_BYTE, GL_TRUE, 0, None)
            glEnableVertexAttribArray(self.color_loc)
            
            # Draw elements
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
            glDrawElements(GL_TRIANGLES, self.num_indices, GL_UNSIGNED_INT, None)
            
            # Cleanup
            glDisableVertexAttribArray(self.position_loc)
            glDisableVertexAttribArray(self.color_loc)
            glUseProgram(0)
            
        except GLError as e:
            print(f"OpenGL error during rendering: {e}")
            raise