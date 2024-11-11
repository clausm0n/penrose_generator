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
        
    def setup_shader(self):
        # Simpler vertex shader that just transforms coordinates
        vertex_shader = """
        #version 120
        
        attribute vec2 position;
        attribute vec4 color;
        varying vec4 frag_color;
        
        void main() {
            gl_Position = gl_ModelViewProjectionMatrix * vec4(position, 0.0, 1.0);
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
        indices = []
        
        center = complex(width / 2, height / 2)
        vertex_count = 0
        
        # Clear the vertex counts dictionary
        self.tile_vertex_counts.clear()
        self.tile_start_indices = {}  # Track where each tile's vertices start
        
        for tile in tiles:
            # Transform vertices to screen space
            screen_verts = op.to_canvas(tile.vertices, scale_value, center, 3)
            
            # Store the starting index for this tile
            self.tile_start_indices[tile] = len(vertices) // 2
            
            # Add vertices
            for x, y in screen_verts:
                vertices.extend([x, y])
            
            # Create triangle fan indices for polygon
            num_verts = len(screen_verts)
            for i in range(1, num_verts - 1):
                indices.extend([vertex_count, vertex_count + i, vertex_count + i + 1])
            
            # Store number of vertices for this tile
            self.tile_vertex_counts[tile] = num_verts
            
            # Add initial colors (will be updated by shader effects)
            base_color = tile.color + (255,)  # Add alpha
            colors.extend(base_color * num_verts)
            
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
        self.total_vertices = len(vertices) // 2
    
    def update_colors(self, tiles, shader_func, current_time, width, height, color1, color2, scale_value):
        """Update color buffer with shader effects"""
        colors = np.zeros(self.total_vertices * 4, dtype=np.uint8)  # 4 components (RGBA) per vertex
        
        for tile in tiles:
            # Get shader color for this tile
            modified_color = shader_func(tile, current_time, tiles, color1, color2, width, height, scale_value)
            
            # Calculate the start and end positions in the color array
            start_idx = self.tile_start_indices[tile] * 4  # 4 components per vertex
            num_vertices = self.tile_vertex_counts[tile]
            end_idx = start_idx + (num_vertices * 4)
            
            # Create the color data for all vertices of this tile
            tile_colors = np.tile(modified_color, num_vertices)
            
            # Update the color array
            colors[start_idx:end_idx] = np.repeat(modified_color, num_vertices)
        
        # Update the GPU buffer
        glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
        glBufferData(GL_ARRAY_BUFFER, colors.nbytes, colors, GL_DYNAMIC_DRAW)
    
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
            # Use our shader program
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
            
            # Enable alpha blending
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Bind vertex buffer
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glVertexAttribPointer(self.position_loc, 2, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(self.position_loc)
            
            # Bind color buffer
            glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
            glVertexAttribPointer(self.color_loc, 4, GL_UNSIGNED_BYTE, GL_TRUE, 0, None)
            glEnableVertexAttribArray(self.color_loc)
            
            # Bind element buffer and draw
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
            glDrawElements(GL_TRIANGLES, self.num_indices, GL_UNSIGNED_INT, None)
            
            # Clean up
            glDisableVertexAttribArray(self.position_loc)
            glDisableVertexAttribArray(self.color_loc)
            glUseProgram(0)
            
        except GLError as e:
            print(f"OpenGL error during rendering: {e}")
            raise