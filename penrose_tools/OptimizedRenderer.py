import numpy as np
from OpenGL.GL import *
from OpenGL.GL import shaders
import ctypes

class OptimizedRenderer:
    def __init__(self):
        self.vbo = None
        self.color_vbo = None
        self.shader_program = None
        self.spatial_grid = {}
        self.grid_size = 100  # Size of each grid cell
        self.setup_shader()
        self.tile_cache = {}
        self.visible_tiles_cache = set()
        
    def setup_shader(self):
        # Vertex shader that handles basic positioning
        vertex_shader = """
        #version 330
        layout(location = 0) in vec2 position;
        layout(location = 1) in vec4 color;
        uniform float time;
        uniform vec2 center;
        uniform float scale;
        out vec4 frag_color;
        
        void main() {
            vec2 pos = (position - center) * scale;
            gl_Position = vec4(pos, 0.0, 1.0);
            frag_color = color;
        }
        """
        
        # Fragment shader that handles color effects
        fragment_shader = """
        #version 330
        in vec4 frag_color;
        out vec4 out_color;
        
        void main() {
            out_color = frag_color;
        }
        """
        
        # Compile and link shaders
        vertex = shaders.compileShader(vertex_shader, GL_VERTEX_SHADER)
        fragment = shaders.compileShader(fragment_shader, GL_FRAGMENT_SHADER)
        self.shader_program = shaders.compileProgram(vertex, fragment)
        
    def setup_buffers(self, tiles):
        # Convert tiles to vertex array
        vertices = []
        colors = []
        
        for tile in tiles:
            # Add vertices for each tile
            tile_verts = [v for v in tile.vertices]
            vertices.extend([(v.real, v.imag) for v in tile_verts])
            
            # Add colors for each vertex
            tile_color = tile.color + (255,)  # Add alpha channel
            colors.extend([tile_color] * len(tile_verts))
        
        # Convert to numpy arrays
        vertices_array = np.array(vertices, dtype=np.float32)
        colors_array = np.array(colors, dtype=np.uint8)
        
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
        
    def update_spatial_grid(self, tiles, width, height):
        self.spatial_grid.clear()
        grid_size = self.grid_size
        
        for tile in tiles:
            # Get tile bounds
            x_coords = [v.real for v in tile.vertices]
            y_coords = [v.imag for v in tile.vertices]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # Calculate grid cells this tile occupies
            start_x = int(min_x / grid_size)
            end_x = int(max_x / grid_size) + 1
            start_y = int(min_y / grid_size)
            end_y = int(max_y / grid_size) + 1
            
            # Add tile to relevant grid cells
            for x in range(start_x, end_x):
                for y in range(start_y, end_y):
                    cell = (x, y)
                    if cell not in self.spatial_grid:
                        self.spatial_grid[cell] = set()
                    self.spatial_grid[cell].add(tile)
    
    def get_visible_tiles(self, width, height):
        visible_tiles = set()
        grid_size = self.grid_size
        
        # Calculate visible grid cells
        start_x = int(0 / grid_size)
        end_x = int(width / grid_size) + 1
        start_y = int(0 / grid_size)
        end_y = int(height / grid_size) + 1
        
        # Collect tiles from visible cells
        for x in range(start_x, end_x):
            for y in range(start_y, end_y):
                cell = (x, y)
                if cell in self.spatial_grid:
                    visible_tiles.update(self.spatial_grid[cell])
        
        return visible_tiles
    
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
        
        visible_tiles = self.get_visible_tiles(width, height)
        
        # Use shader program
        glUseProgram(self.shader_program)
        
        # Set uniforms
        glUniform1f(glGetUniformLocation(self.shader_program, "time"), current_time)
        glUniform2f(glGetUniformLocation(self.shader_program, "center"), width/2, height/2)
        glUniform1f(glGetUniformLocation(self.shader_program, "scale"), 2.0/width)
        
        # Enable vertex attributes
        glEnableVertexAttribArray(0)  # position
        glEnableVertexAttribArray(1)  # color
        
        # Bind vertex buffer
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
        
        # Bind color buffer
        glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
        glVertexAttribPointer(1, 4, GL_UNSIGNED_BYTE, GL_TRUE, 0, None)
        
        # Draw all visible tiles in one batch
        num_vertices = len(visible_tiles) * 4  # Assuming 4 vertices per tile
        glDrawArrays(GL_QUADS, 0, num_vertices)
        
        # Clean up
        glDisableVertexAttribArray(0)
        glDisableVertexAttribArray(1)
        glUseProgram(0)