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
        # Modified vertex shader with proper scaling
        vertex_shader = """
        #version 120
        
        attribute vec2 position;
        attribute vec4 color;
        uniform float time;
        uniform vec2 center;
        uniform float scale;
        uniform vec2 screen_size;
        varying vec4 frag_color;
        
        void main() {
            // Convert to normalized device coordinates
            vec2 pos = position;
            vec2 normalized_pos = 2.0 * (pos / screen_size) - 1.0;
            normalized_pos.y = -normalized_pos.y;  // Flip Y coordinate
            gl_Position = vec4(normalized_pos, 0.0, 1.0);
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
            
            # Get locations
            self.position_loc = glGetAttribLocation(self.shader_program, 'position')
            self.color_loc = glGetAttribLocation(self.shader_program, 'color')
            self.time_loc = glGetUniformLocation(self.shader_program, 'time')
            self.center_loc = glGetUniformLocation(self.shader_program, 'center')
            self.scale_loc = glGetUniformLocation(self.shader_program, 'scale')
            self.screen_size_loc = glGetUniformLocation(self.shader_program, 'screen_size')
            
        except Exception as e:
            print(f"Shader compilation error: {e}")
            raise
        
    def setup_buffers(self, tiles, width, height, scale_value):
        vertices = []
        colors = []
        
        # Calculate center for transformations
        center = complex(width / 2, height / 2)
        
        for tile in tiles:
            # Transform vertices to screen space
            screen_verts = op.to_canvas(tile.vertices, scale_value, center, 3)
            vertices.extend(screen_verts)
            
            # Add colors for each vertex
            tile_color = tile.color + (255,)
            colors.extend([tile_color] * len(screen_verts))
        
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
    
    def update_spatial_grid(self, tiles, width, height):
        """Updates the spatial partitioning grid with the current tiles."""
        self.spatial_grid.clear()
        grid_size = self.grid_size
        
        # Calculate grid dimensions
        num_cols = (width + grid_size - 1) // grid_size
        num_rows = (height + grid_size - 1) // grid_size
        
        for tile in tiles:
            # Get tile bounds
            vertices = [op.to_canvas([v], 1, complex(0, 0))[0] for v in tile.vertices]
            x_coords = [v[0] for v in vertices]
            y_coords = [v[1] for v in vertices]
            
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # Calculate grid cells this tile intersects with
            start_cell_x = max(0, int(min_x / grid_size))
            end_cell_x = min(num_cols - 1, int(max_x / grid_size))
            start_cell_y = max(0, int(min_y / grid_size))
            end_cell_y = min(num_rows - 1, int(max_y / grid_size))
            
            # Add tile to all intersecting grid cells
            for cell_x in range(start_cell_x, end_cell_x + 1):
                for cell_y in range(start_cell_y, end_cell_y + 1):
                    cell_key = (cell_x, cell_y)
                    if cell_key not in self.spatial_grid:
                        self.spatial_grid[cell_key] = set()
                    self.spatial_grid[cell_key].add(tile)
    
    def get_visible_tiles(self, width, height):
        """Returns set of tiles that are potentially visible in the viewport."""
        visible_tiles = set()
        grid_size = self.grid_size
        
        # Calculate visible grid range
        start_cell_x = 0
        end_cell_x = (width + grid_size - 1) // grid_size
        start_cell_y = 0
        end_cell_y = (height + grid_size - 1) // grid_size
        
        # Collect tiles from visible cells
        for cell_x in range(start_cell_x, end_cell_x):
            for cell_y in range(start_cell_y, end_cell_y):
                cell_key = (cell_x, cell_y)
                if cell_key in self.spatial_grid:
                    visible_tiles.update(self.spatial_grid[cell_key])
        
        return visible_tiles
    
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
            
            # Initialize shader program if not already done
            if self.shader_program is None:
                self.setup_shader()
            
            self.update_spatial_grid(tiles, width, height)
            self.setup_buffers(tiles, width, height, config_data['scale'])
        
        try:
            # Use shader program
            glUseProgram(self.shader_program)
            
            # Set uniforms
            glUniform1f(self.time_loc, current_time)
            glUniform2f(self.center_loc, width/2, height/2)
            glUniform1f(self.scale_loc, config_data['scale'])
            glUniform2f(self.screen_size_loc, width, height)
            
            # Bind vertex buffer
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glVertexAttribPointer(self.position_loc, 2, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(self.position_loc)
            
            # Bind color buffer
            glBindBuffer(GL_ARRAY_BUFFER, self.color_vbo)
            glVertexAttribPointer(self.color_loc, 4, GL_UNSIGNED_BYTE, GL_TRUE, 0, None)
            glEnableVertexAttribArray(self.color_loc)
            
            # Draw using triangles
            glDrawArrays(GL_TRIANGLES, 0, self.num_vertices)
            
            # Clean up
            glDisableVertexAttribArray(self.position_loc)
            glDisableVertexAttribArray(self.color_loc)
            glUseProgram(0)
            
        except GLError as e:
            print(f"OpenGL error during rendering: {e}")
            raise