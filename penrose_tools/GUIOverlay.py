# penrose_tools/GUIOverlay.py
import numpy as np
from OpenGL.GL import *
import logging
import glfw
import ctypes
from PIL import Image, ImageDraw, ImageFont
import io

class GUIOverlay:
    """Simple GUI overlay system for displaying text and controls over the Penrose visualization."""
    
    def __init__(self):
        self.logger = logging.getLogger('GUIOverlay')
        self.visible = False  # Back to normal - toggle with F1
        self.font_size = 16
        self.line_height = 20
        self.padding = 20
        self.background_alpha = 0.7
        self.initialized = False

        # Control information to display
        self.controls = [
            "=== PENROSE TILING CONTROLS ===",
            "",
            "KEYBOARD SHORTCUTS:",
            "  F1          - Toggle this help overlay",
            "  F11         - Toggle fullscreen mode",
            "  ESC         - Exit application",
            "  SPACE       - Toggle shader effects",
            "  R           - Randomize colors",
            "  G           - Randomize gamma values",
            "  UP/DOWN     - Increase/decrease scale",
            "  [ / ]       - Decrease/increase vertex offset",
            "  1/2/3       - Toggle effect/gamma/color cycling",
            "",
            "CURRENT SETTINGS:",
            "  Shader: {shader_name}",
            "  Scale: {scale}",
            "  Vertex Offset: {vertex_offset}",
            "",
            "Press F1 to hide this overlay"
        ]

        # Text rendering resources
        self.text_texture = None
        self.text_texture_width = 0
        self.text_texture_height = 0

        # OpenGL resources (will be initialized when context is available)
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.shader_program = None
        self.textured_shader_program = None

    def initialize_gl_resources(self):
        """Initialize OpenGL resources when context is available."""
        if self.initialized:
            return

        try:
            self.logger.info("Starting GUI overlay OpenGL initialization...")
            self.setup_gl_resources()
            self.initialized = True
            self.logger.info("✓ GUI overlay OpenGL resources initialized successfully")
        except Exception as e:
            self.logger.error(f"✗ Failed to initialize GUI overlay OpenGL resources: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.initialized = False

    def setup_gl_resources(self):
        """Set up OpenGL resources for rendering simple quads and text backgrounds."""
        # Simple unit quad vertices (0 to 1) - will be scaled and positioned by shader
        self.quad_vertices = np.array([
            # Position (x, y)
            0.0, 0.0,  # Bottom-left
            1.0, 0.0,  # Bottom-right
            1.0, 1.0,  # Top-right
            0.0, 1.0   # Top-left
        ], dtype=np.float32)

        self.quad_indices = np.array([
            0, 1, 2,
            2, 3, 0
        ], dtype=np.uint32)
        
        # Create VAO and VBO for quad rendering
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)
        
        glBindVertexArray(self.vao)
        
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.quad_vertices.nbytes, self.quad_vertices, GL_STATIC_DRAW)
        
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.quad_indices.nbytes, self.quad_indices, GL_STATIC_DRAW)
        
        # Position attribute
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        
        glBindVertexArray(0)
        
        # Simple shader for rendering colored quads
        self.create_simple_shader()

        # Textured shader for rendering text
        self.create_textured_shader()
    
    def create_simple_shader(self):
        """Create a simple shader for rendering colored rectangles."""
        vertex_shader_source = """
        #version 330 core
        layout (location = 0) in vec2 aPos;

        uniform vec2 screenSize;
        uniform vec2 position;
        uniform vec2 size;

        void main()
        {
            // aPos is in [0,1] range
            // Scale by size to get pixel dimensions
            vec2 pixelPos = aPos * size;
            // Add position offset
            vec2 screenPos = pixelPos + position;
            // Convert to NDC: [0, screenSize] -> [-1, 1]
            vec2 ndc = (screenPos / screenSize) * 2.0 - 1.0;
            // Flip Y axis for screen coordinates (0,0 = top-left)
            ndc.y = -ndc.y;
            gl_Position = vec4(ndc, 0.0, 1.0);
        }
        """
        
        fragment_shader_source = """
        #version 330 core
        out vec4 FragColor;
        
        uniform vec4 color;
        
        void main()
        {
            FragColor = color;
        }
        """
        
        # Compile vertex shader
        vertex_shader = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vertex_shader, vertex_shader_source)
        glCompileShader(vertex_shader)
        
        # Check vertex shader compilation
        if not glGetShaderiv(vertex_shader, GL_COMPILE_STATUS):
            error = glGetShaderInfoLog(vertex_shader)
            self.logger.error(f"✗ Vertex shader compilation failed: {error}")
            self.logger.error(f"Vertex shader source:\n{vertex_shader_source}")
            raise RuntimeError("Vertex shader compilation failed")
        else:
            self.logger.info("✓ Vertex shader compiled successfully")
        
        # Compile fragment shader
        fragment_shader = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fragment_shader, fragment_shader_source)
        glCompileShader(fragment_shader)
        
        # Check fragment shader compilation
        if not glGetShaderiv(fragment_shader, GL_COMPILE_STATUS):
            error = glGetShaderInfoLog(fragment_shader)
            self.logger.error(f"✗ Fragment shader compilation failed: {error}")
            self.logger.error(f"Fragment shader source:\n{fragment_shader_source}")
            raise RuntimeError("Fragment shader compilation failed")
        else:
            self.logger.info("✓ Fragment shader compiled successfully")
        
        # Create shader program
        self.shader_program = glCreateProgram()
        glAttachShader(self.shader_program, vertex_shader)
        glAttachShader(self.shader_program, fragment_shader)
        glLinkProgram(self.shader_program)
        
        # Check program linking
        if not glGetProgramiv(self.shader_program, GL_LINK_STATUS):
            error = glGetProgramInfoLog(self.shader_program)
            self.logger.error(f"✗ Shader program linking failed: {error}")
            raise RuntimeError("Shader program linking failed")
        else:
            self.logger.info("✓ Shader program linked successfully")
        
        # Clean up shaders
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)
        
        # Get uniform locations
        self.screen_size_loc = glGetUniformLocation(self.shader_program, "screenSize")
        self.position_loc = glGetUniformLocation(self.shader_program, "position")
        self.size_loc = glGetUniformLocation(self.shader_program, "size")
        self.color_loc = glGetUniformLocation(self.shader_program, "color")

        self.logger.info(f"Simple shader uniform locations: screen={self.screen_size_loc}, pos={self.position_loc}, size={self.size_loc}, color={self.color_loc}")

    def create_textured_shader(self):
        """Create a shader for rendering textured quads (for text)."""
        vertex_shader_source = """
        #version 330 core
        layout (location = 0) in vec2 aPos;

        uniform vec2 screenSize;
        uniform vec2 position;
        uniform vec2 size;

        out vec2 TexCoord;

        void main()
        {
            // Convert to screen coordinates then to NDC
            vec2 screenPos = aPos * size + position;
            vec2 ndc = (screenPos / screenSize) * 2.0 - 1.0;
            ndc.y = -ndc.y;  // Flip Y axis
            gl_Position = vec4(ndc, 0.0, 1.0);
            TexCoord = aPos;  // Use vertex position directly for texture coordinates
        }
        """

        fragment_shader_source = """
        #version 330 core
        in vec2 TexCoord;
        out vec4 FragColor;

        uniform sampler2D textTexture;
        uniform vec4 color;

        void main()
        {
            vec4 texColor = texture(textTexture, TexCoord);
            FragColor = texColor * color;
        }
        """

        # Compile vertex shader
        vertex_shader = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vertex_shader, vertex_shader_source)
        glCompileShader(vertex_shader)

        # Check vertex shader compilation
        if not glGetShaderiv(vertex_shader, GL_COMPILE_STATUS):
            error = glGetShaderInfoLog(vertex_shader)
            self.logger.error(f"Textured vertex shader compilation failed: {error}")
            raise RuntimeError("Textured vertex shader compilation failed")

        # Compile fragment shader
        fragment_shader = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fragment_shader, fragment_shader_source)
        glCompileShader(fragment_shader)

        # Check fragment shader compilation
        if not glGetShaderiv(fragment_shader, GL_COMPILE_STATUS):
            error = glGetShaderInfoLog(fragment_shader)
            self.logger.error(f"Textured fragment shader compilation failed: {error}")
            raise RuntimeError("Textured fragment shader compilation failed")

        # Create shader program
        self.textured_shader_program = glCreateProgram()
        glAttachShader(self.textured_shader_program, vertex_shader)
        glAttachShader(self.textured_shader_program, fragment_shader)
        glLinkProgram(self.textured_shader_program)

        # Check program linking
        if not glGetProgramiv(self.textured_shader_program, GL_LINK_STATUS):
            error = glGetProgramInfoLog(self.textured_shader_program)
            self.logger.error(f"Textured shader program linking failed: {error}")
            raise RuntimeError("Textured shader program linking failed")

        # Clean up shaders
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)

        # Get uniform locations
        self.tex_screen_size_loc = glGetUniformLocation(self.textured_shader_program, "screenSize")
        self.tex_position_loc = glGetUniformLocation(self.textured_shader_program, "position")
        self.tex_size_loc = glGetUniformLocation(self.textured_shader_program, "size")
        self.tex_color_loc = glGetUniformLocation(self.textured_shader_program, "color")
        self.tex_texture_loc = glGetUniformLocation(self.textured_shader_program, "textTexture")
    
    def toggle_visibility(self):
        """Toggle the visibility of the GUI overlay."""
        self.visible = not self.visible
        self.logger.info(f"GUI overlay {'shown' if self.visible else 'hidden'}")
    
    def set_visible(self, visible):
        """Set the visibility of the GUI overlay."""
        self.visible = visible
    
    def is_visible(self):
        """Check if the GUI overlay is currently visible."""
        return self.visible
    
    def create_orthographic_projection(self, width, height):
        """Create an orthographic projection matrix for 2D rendering."""
        # Create orthographic projection: left=0, right=width, bottom=height, top=0
        # This maps screen coordinates directly (0,0 = top-left, width,height = bottom-right)
        left, right = 0.0, float(width)
        bottom, top = float(height), 0.0  # Flip Y so 0 is at top
        near, far = -1.0, 1.0

        projection = np.array([
            [2.0/(right-left), 0.0, 0.0, -(right+left)/(right-left)],
            [0.0, 2.0/(top-bottom), 0.0, -(top+bottom)/(top-bottom)],
            [0.0, 0.0, -2.0/(far-near), -(far+near)/(far-near)],
            [0.0, 0.0, 0.0, 1.0]
        ], dtype=np.float32)
        return projection
    
    def render_background_panel_simple(self, width, height):
        """Render background panel using modern OpenGL - fallback disabled for OpenGL 3.1+."""
        # This method is disabled because the application uses OpenGL 3.1 forward compatible
        # which doesn't support legacy matrix functions
        self.logger.debug("Simple rendering not available in OpenGL 3.1+ forward compatible mode")
        return False

    def render_background_panel(self, width, height):
        """Render a semi-transparent background panel for the overlay."""
        if not self.visible:
            return

        # Initialize OpenGL resources if not already done
        if not self.initialized:
            self.initialize_gl_resources()
            if not self.initialized:
                self.logger.error("Failed to initialize OpenGL resources for GUI overlay")
                return

        # Calculate panel dimensions and position
        panel_width = 450
        panel_height = len(self.controls) * self.line_height + 2 * self.padding
        panel_x = self.padding
        panel_y = self.padding  # Position from top-left

        # Rendering background panel

        # Set up OpenGL state for transparent rendering
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)  # Ensure overlay renders on top

        # Use our simple shader
        glUseProgram(self.shader_program)

        # Set screen size
        if self.screen_size_loc >= 0:
            glUniform2f(self.screen_size_loc, float(width), float(height))

        # Set panel position and size (in screen coordinates)
        if self.position_loc >= 0:
            glUniform2f(self.position_loc, float(panel_x), float(panel_y))
        if self.size_loc >= 0:
            glUniform2f(self.size_loc, float(panel_width), float(panel_height))

        # Set background color (dark semi-transparent)
        if self.color_loc >= 0:
            glUniform4f(self.color_loc, 0.0, 0.0, 0.0, 0.8)

        # Uniforms set successfully

        # Render the background quad
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

        glUseProgram(0)
        glEnable(GL_DEPTH_TEST)  # Restore depth testing
        glDisable(GL_BLEND)
    
    def get_formatted_controls(self, config_data, shader_manager):
        """Get formatted control text with current values."""
        # Prepare control text with current values
        current_shader = "Unknown"
        if hasattr(shader_manager, 'shader_names') and hasattr(shader_manager, 'current_shader_index'):
            if 0 <= shader_manager.current_shader_index < len(shader_manager.shader_names):
                current_shader = shader_manager.shader_names[shader_manager.current_shader_index]

        # Format control text with current values
        formatted_controls = []
        for line in self.controls:
            if "{shader_name}" in line:
                formatted_controls.append(line.format(shader_name=current_shader))
            elif "{scale}" in line:
                formatted_controls.append(line.format(scale=config_data.get('scale', 'Unknown')))
            elif "{vertex_offset}" in line:
                formatted_controls.append(line.format(vertex_offset=config_data.get('vertex_offset', 'Unknown')))
            else:
                formatted_controls.append(line)

        return formatted_controls

    def create_text_texture(self, text_lines, font_size=14):
        """Create a texture from text lines using PIL."""
        try:
            # Try to use a system font, fall back to default if not available
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("DejaVuSans.ttf", font_size)
                except:
                    try:
                        # Try Windows system fonts
                        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()

            # Calculate text dimensions with more generous spacing
            max_width = 0
            total_height = 0
            line_heights = []

            for line in text_lines:
                if line.strip():  # Non-empty line
                    bbox = font.getbbox(line)
                    line_width = bbox[2] - bbox[0]
                    line_height = max(bbox[3] - bbox[1], font_size)  # Ensure minimum height
                else:
                    line_width = 0
                    line_height = font_size // 2  # Half height for empty lines

                max_width = max(max_width, line_width)
                line_heights.append(line_height)
                total_height += line_height + 2  # Add line spacing

            # Add generous padding
            texture_width = max(max_width + 40, 400)  # Minimum width
            texture_height = total_height + 40

            # Create image with transparent background
            image = Image.new('RGBA', (texture_width, texture_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)

            # Draw text lines with better positioning
            y_offset = 20
            for i, line in enumerate(text_lines):
                if line.strip():  # Only draw non-empty lines
                    # Draw text with white color and full opacity
                    draw.text((20, y_offset), line, font=font, fill=(255, 255, 255, 255))
                y_offset += line_heights[i] + 2

            # Convert to OpenGL texture
            image_data = np.array(image)

            # Create or update texture
            if self.text_texture is None:
                self.text_texture = glGenTextures(1)

            glBindTexture(GL_TEXTURE_2D, self.text_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, texture_width, texture_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, image_data)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glBindTexture(GL_TEXTURE_2D, 0)

            self.text_texture_width = texture_width
            self.text_texture_height = texture_height

            self.logger.info(f"Created text texture: {texture_width}x{texture_height} pixels")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create text texture: {e}")
            return False

    def render_text_overlay(self, width, height, config_data, shader_manager):
        """Render text overlay using texture-based rendering."""
        if not self.visible:
            return

        # Initialize OpenGL resources if not already done
        if not self.initialized:
            self.initialize_gl_resources()
            if not self.initialized:
                return

        # Check if textured shader is available
        if not hasattr(self, 'textured_shader_program') or self.textured_shader_program is None:
            return

        # Get formatted text
        formatted_controls = self.get_formatted_controls(config_data, shader_manager)

        # Create text texture if needed
        if self.text_texture is None:
            if not self.create_text_texture(formatted_controls):
                return

        # Calculate text position (same as background panel but with small offset)
        text_x = self.padding + 10
        text_y = self.padding + 10

        # Set up OpenGL state for transparent rendering
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)  # Ensure text renders on top

        # Use textured shader
        glUseProgram(self.textured_shader_program)

        # Set screen size
        if self.tex_screen_size_loc >= 0:
            glUniform2f(self.tex_screen_size_loc, float(width), float(height))

        # Set text position and size (in screen coordinates)
        if self.tex_position_loc >= 0:
            glUniform2f(self.tex_position_loc, float(text_x), float(text_y))
        if self.tex_size_loc >= 0:
            glUniform2f(self.tex_size_loc, float(self.text_texture_width), float(self.text_texture_height))

        # Set text color (white)
        glUniform4f(self.tex_color_loc, 1.0, 1.0, 1.0, 1.0)

        # Bind texture
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.text_texture)
        glUniform1i(self.tex_texture_loc, 0)

        # Render the text quad
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)
        glEnable(GL_DEPTH_TEST)  # Restore depth testing
        glDisable(GL_BLEND)

    def render_text_simple(self, width, height, config_data, shader_manager):
        """Render text using simple OpenGL calls - disabled for OpenGL 3.1+."""
        # This method is disabled because the application uses OpenGL 3.1 forward compatible
        self.logger.debug("Simple text rendering not available in OpenGL 3.1+ forward compatible mode")
        return False

    def render(self, width, height, config_data, shader_manager):
        """Render the complete GUI overlay."""
        if not self.visible:
            # Ensure we don't interfere with main rendering when hidden
            return

        # Render GUI overlay

        # Save current OpenGL state
        current_program = glGetIntegerv(GL_CURRENT_PROGRAM)
        blend_enabled = glIsEnabled(GL_BLEND)
        depth_test_enabled = glIsEnabled(GL_DEPTH_TEST)

        try:
            # Render background panel
            self.render_background_panel(width, height)

            # Render text overlay (texture-based for OpenGL 3.1+)
            self.render_text_overlay(width, height, config_data, shader_manager)
        finally:
            # Restore OpenGL state
            glUseProgram(current_program)
            if blend_enabled:
                glEnable(GL_BLEND)
            else:
                glDisable(GL_BLEND)
            if depth_test_enabled:
                glEnable(GL_DEPTH_TEST)
            else:
                glDisable(GL_DEPTH_TEST)
    
    def cleanup(self):
        """Clean up OpenGL resources."""
        if not self.initialized:
            return

        try:
            if hasattr(self, 'vao') and self.vao is not None:
                glDeleteVertexArrays(1, [self.vao])
            if hasattr(self, 'vbo') and self.vbo is not None:
                glDeleteBuffers(1, [self.vbo])
            if hasattr(self, 'ebo') and self.ebo is not None:
                glDeleteBuffers(1, [self.ebo])
            if hasattr(self, 'shader_program') and self.shader_program is not None:
                glDeleteProgram(self.shader_program)
            if hasattr(self, 'textured_shader_program') and self.textured_shader_program is not None:
                glDeleteProgram(self.textured_shader_program)
            if hasattr(self, 'text_texture') and self.text_texture is not None:
                glDeleteTextures(1, [self.text_texture])

            self.logger.info("GUI overlay resources cleaned up")
        except Exception as e:
            self.logger.error(f"Error during GUI overlay cleanup: {e}")
