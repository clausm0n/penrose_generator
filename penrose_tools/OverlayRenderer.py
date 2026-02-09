# penrose_tools/OverlayRenderer.py
"""
GPU-side instanced quad renderer for the tile overlay system.
Draws pre-generated tiles as instanced quads on top of the procedural base layer.
Per-tile data (pattern, interaction, animation) comes as instance attributes.
"""
import numpy as np
from OpenGL.GL import *
import glfw
import logging
import os
from ctypes import c_void_p


class OverlayRenderer:
    """
    Renders tile quads using instanced drawing.
    Each tile is a rhombus drawn as a quad with per-instance vertex positions
    and tile data attributes.
    """

    def __init__(self):
        self.logger = logging.getLogger('OverlayRenderer')
        self.shader_program = None
        self.uniforms = {}
        self.vao = None
        self.quad_vbo = None
        self.quad_ebo = None
        self.instance_vert_vbo = None
        self.instance_data_vbo = None
        self.tile_count = 0

        self._compile_shader()
        self._create_vao()
        self.logger.info("OverlayRenderer initialized")

    def _compile_shader(self):
        """Compile the overlay shader program."""
        shader_dir = os.path.join(os.path.dirname(__file__), 'Shaders')

        with open(os.path.join(shader_dir, 'tile_overlay.vert'), 'r') as f:
            vert_src = f.read()
        with open(os.path.join(shader_dir, 'region_blend_overlay.frag'), 'r') as f:
            frag_src = f.read()

        # Compile vertex shader
        vert = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vert, vert_src)
        glCompileShader(vert)
        if not glGetShaderiv(vert, GL_COMPILE_STATUS):
            log = glGetShaderInfoLog(vert).decode('utf-8')
            raise RuntimeError(f"Overlay vertex shader error: {log}")

        # Compile fragment shader
        frag = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(frag, frag_src)
        glCompileShader(frag)
        if not glGetShaderiv(frag, GL_COMPILE_STATUS):
            log = glGetShaderInfoLog(frag).decode('utf-8')
            raise RuntimeError(f"Overlay fragment shader error: {log}")

        # Link program
        self.shader_program = glCreateProgram()
        glAttachShader(self.shader_program, vert)
        glAttachShader(self.shader_program, frag)

        # Bind attribute locations before linking
        glBindAttribLocation(self.shader_program, 0, "a_corner")
        glBindAttribLocation(self.shader_program, 1, "a_v0")
        glBindAttribLocation(self.shader_program, 2, "a_v1")
        glBindAttribLocation(self.shader_program, 3, "a_v2")
        glBindAttribLocation(self.shader_program, 4, "a_v3")
        glBindAttribLocation(self.shader_program, 5, "a_tile_data1")
        glBindAttribLocation(self.shader_program, 6, "a_tile_data2")

        glLinkProgram(self.shader_program)
        if not glGetProgramiv(self.shader_program, GL_LINK_STATUS):
            log = glGetProgramInfoLog(self.shader_program).decode('utf-8')
            raise RuntimeError(f"Overlay shader link error: {log}")

        glDeleteShader(vert)
        glDeleteShader(frag)

        # Cache uniform locations
        glUseProgram(self.shader_program)
        self.uniforms = {
            'u_camera': glGetUniformLocation(self.shader_program, 'u_camera'),
            'u_zoom': glGetUniformLocation(self.shader_program, 'u_zoom'),
            'u_aspect': glGetUniformLocation(self.shader_program, 'u_aspect'),
            'u_color1': glGetUniformLocation(self.shader_program, 'u_color1'),
            'u_color2': glGetUniformLocation(self.shader_program, 'u_color2'),
            'u_edge_thickness': glGetUniformLocation(self.shader_program, 'u_edge_thickness'),
            'u_time': glGetUniformLocation(self.shader_program, 'u_time'),
        }
        glUseProgram(0)
        self.logger.info("Overlay shader compiled and linked")

    def _create_vao(self):
        """Create VAO with unit quad + instance buffer slots."""
        # Unit quad corners: [0,0] [1,0] [1,1] [0,1]
        quad_verts = np.array([
            0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0
        ], dtype=np.float32)
        quad_indices = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)

        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)

        # Quad VBO — attribute 0 (a_corner), divisor 0
        self.quad_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_verts.nbytes, quad_verts, GL_STATIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)

        # Quad EBO
        self.quad_ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.quad_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, quad_indices.nbytes, quad_indices, GL_STATIC_DRAW)

        # Instance vertex VBO — attributes 1-4 (a_v0..a_v3), divisor 1
        # Layout per instance: [v0x, v0y, v1x, v1y, v2x, v2y, v3x, v3y] = 8 floats
        self.instance_vert_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.instance_vert_vbo)
        glBufferData(GL_ARRAY_BUFFER, 0, None, GL_DYNAMIC_DRAW)
        stride = 8 * 4  # 8 floats × 4 bytes = 32 bytes per instance
        for i in range(4):
            loc = 1 + i
            glEnableVertexAttribArray(loc)
            glVertexAttribPointer(loc, 2, GL_FLOAT, GL_FALSE, stride, c_void_p(i * 8))
            glVertexAttribDivisor(loc, 1)

        # Instance tile data VBO — attributes 5-6 (a_tile_data1, a_tile_data2), divisor 1
        # Layout per instance: [is_kite, pattern, blend, selected, hovered, anim_phase, anim_type, tile_id]
        self.instance_data_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.instance_data_vbo)
        glBufferData(GL_ARRAY_BUFFER, 0, None, GL_DYNAMIC_DRAW)
        data_stride = 8 * 4
        glEnableVertexAttribArray(5)
        glVertexAttribPointer(5, 4, GL_FLOAT, GL_FALSE, data_stride, c_void_p(0))
        glVertexAttribDivisor(5, 1)
        glEnableVertexAttribArray(6)
        glVertexAttribPointer(6, 4, GL_FLOAT, GL_FALSE, data_stride, c_void_p(16))
        glVertexAttribDivisor(6, 1)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    # -------------------------------------------------------------------------
    # Data upload
    # -------------------------------------------------------------------------

    def upload_tile_data(self, gpu_vertices, gpu_tile_data, tile_count):
        """Upload complete tile data from TileDataManager to GPU."""
        self.tile_count = tile_count
        if tile_count == 0:
            return

        # Vertices: (N, 4, 2) → contiguous (N*8,) float32
        vert_flat = gpu_vertices.reshape(-1).astype(np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self.instance_vert_vbo)
        glBufferData(GL_ARRAY_BUFFER, vert_flat.nbytes, vert_flat, GL_DYNAMIC_DRAW)

        # Tile data: (N, 8) → contiguous (N*8,) float32
        data_flat = gpu_tile_data.reshape(-1).astype(np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self.instance_data_vbo)
        glBufferData(GL_ARRAY_BUFFER, data_flat.nbytes, data_flat, GL_DYNAMIC_DRAW)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.logger.debug(f"Uploaded {tile_count} tiles to GPU")

    def upload_tile_data_partial(self, gpu_tile_data, offset, count):
        """Partial update of tile data (interaction changes only)."""
        if count == 0:
            return
        data_slice = gpu_tile_data[offset:offset + count].reshape(-1).astype(np.float32)
        byte_offset = offset * 8 * 4  # 8 floats × 4 bytes per tile
        glBindBuffer(GL_ARRAY_BUFFER, self.instance_data_vbo)
        glBufferSubData(GL_ARRAY_BUFFER, byte_offset, data_slice.nbytes, data_slice)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def render(self, camera_x, camera_y, zoom, width, height,
               config_data, edge_thickness, time_val):
        """Draw all tile instances."""
        if self.tile_count == 0 or self.shader_program is None:
            return

        aspect = float(width) / float(height)

        glUseProgram(self.shader_program)

        # Set uniforms
        glUniform2f(self.uniforms['u_camera'], camera_x, camera_y)
        glUniform1f(self.uniforms['u_zoom'], zoom)
        glUniform1f(self.uniforms['u_aspect'], aspect)
        glUniform1f(self.uniforms['u_time'], time_val)
        glUniform1f(self.uniforms['u_edge_thickness'], edge_thickness)

        c1 = config_data.get('color1', [255, 255, 255])
        c2 = config_data.get('color2', [0, 0, 255])
        glUniform3f(self.uniforms['u_color1'], c1[0] / 255.0, c1[1] / 255.0, c1[2] / 255.0)
        glUniform3f(self.uniforms['u_color2'], c2[0] / 255.0, c2[1] / 255.0, c2[2] / 255.0)

        # Instanced draw
        glBindVertexArray(self.vao)
        glDrawElementsInstanced(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None, self.tile_count)
        glBindVertexArray(0)
        glUseProgram(0)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def cleanup(self):
        """Release all GPU resources."""
        if glfw.get_current_context():
            if self.vao:
                glDeleteVertexArrays(1, [self.vao])
            for buf in [self.quad_vbo, self.quad_ebo,
                        self.instance_vert_vbo, self.instance_data_vbo]:
                if buf:
                    glDeleteBuffers(1, [buf])
            if self.shader_program:
                glDeleteProgram(self.shader_program)

    def __del__(self):
        self.cleanup()


