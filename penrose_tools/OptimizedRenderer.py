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
        self.spatial_grid = {}
        self.grid_size = 100  # Size of each grid cell
        self.tile_cache = {}
        self.visible_tiles_cache = set()
        
    def setup_shader(self):
        # Vertex shader using OpenGL ES 2.0 / OpenGL 2.1 compatibility
        vertex_shader = """
        #version 120  // OpenGL 2.1 compatible
        
        attribute vec2 position;
        attribute vec4 color;
        uniform float time;
        uniform vec2 center;
        uniform float scale;
        varying vec4 frag_color;
        
        void main() {
            vec2 pos = (position - center) * scale;
            gl_Position = vec4(pos, 0.0, 1.0);
            frag_color = color;
        }
        """
        
        # Fragment shader using OpenGL ES 2.0 / OpenGL 2.1 compatibility
        fragment_shader = """
        #version 120  // OpenGL 2.1 compatible
        
        varying vec4 frag_color;
        
        void main() {
            gl_FragColor = frag_color;
        }
        """
        
        try:
            # Compile shaders
            vertex = shaders.compileShader(vertex_shader, GL_VERTEX_SHADER)
            fragment = shaders.compileShader(fragment_shader, GL_FRAGMENT_SHADER)
            
            # Create program
            self.shader_program = shaders.compileProgram(vertex, fragment)
            
            # Get attribute locations
            self.position_loc = glGetAttribLocation(self.shader_program, 'position')
            self.color_loc = glGetAttribLocation(self.shader_program, 'color')
            
            # Get uniform locations
            self.time_loc = glGetUniformLocation(self.shader_program, 'time')
            self.center_loc = glGetUniformLocation(self.shader_program, 'center')
            self.scale_loc = glGetUniformLocation(self.shader_program, 'scale')
            
        except Exception as e:
            print(f"Shader compilation error: {e}")
            raise
        
    def setup_buffers(self, tiles):
        vertices = []
        colors = []
        
        for tile in tiles:
            # Convert complex vertices to pairs of floats
            tile_verts = [(v.real, v.imag) for v in tile.vertices]
            vertices.extend(tile_verts)
            
            # Add colors for each vertex
            tile_color = tile.color + (255,)  # Add alpha channel
            colors.extend([tile_color] * len(tile_verts))
        
        # Convert to numpy arrays
        vertices_array = np.array(vertices, dtype=np.float32).flatten()
        colors_array = np.array(colors, dtype=np.uint8).flatten()
        
        # Create and bind vertex buffer
        if self.vbo is None:
            self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices_array.nbytes, vertices_array, GL_STATIC_DRAW)
        
        # Create and bind color buffer
        if self.color_vbo is None:
            self.color_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
        glBufferData(GL_ARRAY_BUFFER, colors_array.nbytes, colors_array, GL_DYNAMIC_DRAW)
        
        self.num_vertices = len(vertices)
    
    def render_tiles(self, shaders, width, height, config_data):
        current_time = glfw.get_time() * 1000
        
        # Create cache key
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
            self.update_spatial_grid(tiles, width, height)
            self.setup_buffers(tiles)
            
            # Initialize shader program if not already done
            if self.shader_program is None:
                self.setup_shader()
        
        visible_tiles = self.get_visible_tiles(width, height)
        
        try:
            # Use shader program
            glUseProgram(self.shader_program)
            
            # Set uniforms
            glUniform1f(self.time_loc, current_time)
            glUniform2f(self.center_loc, width/2, height/2)
            glUniform1f(self.scale_loc, 2.0/width)
            
            # Bind vertex buffer
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glVertexAttribPointer(self.position_loc, 2, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(self.position_loc)
            
            # Bind color buffer
            glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
            glVertexAttribPointer(self.color_loc, 4, GL_UNSIGNED_BYTE, GL_TRUE, 0, None)
            glEnableVertexAttribArray(self.color_loc)
            
            # Draw all visible tiles
            glDrawArrays(GL_TRIANGLES, 0, self.num_vertices)
            
            # Clean up
            glDisableVertexAttribArray(self.position_loc)
            glDisableVertexAttribArray(self.color_loc)
            glUseProgram(0)
            
        except GLError as e:
            print(f"OpenGL error during rendering: {e}")
            raise