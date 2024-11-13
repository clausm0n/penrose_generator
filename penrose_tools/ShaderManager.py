# penrose_tools/ShaderManager.py
import os
import sys
from OpenGL.GL import *
from OpenGL.GL import shaders
import logging
import glfw

class ShaderManager:
    def __init__(self, shaders_folder='Shaders'):
        """Initialize the shader manager after OpenGL context is created."""
        # Verify we have a valid OpenGL context
        if not glfw.get_current_context():
            raise RuntimeError("ShaderManager requires an active OpenGL context")
            
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.shaders_folder = os.path.join(self.script_dir, shaders_folder)
        self.shader_programs = []
        self.shader_names = []
        self.current_shader_index = 0
        self.logger = logging.getLogger('ShaderManager')
        
        # Configure logging
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Check OpenGL context capabilities
        self.check_opengl_context()
        
        # Load shaders
        self.load_shaders()
        
        if not self.shader_programs:
            self.logger.critical("No shaders were loaded successfully.")
            raise RuntimeError("Failed to load any shader programs")

    def compile_shader(self, source, shader_type, name):
        """Compile a shader with detailed error checking."""
        try:
            shader = glCreateShader(shader_type)
            glShaderSource(shader, source)
            glCompileShader(shader)
            
            # Check compilation status
            result = glGetShaderiv(shader, GL_COMPILE_STATUS)
            if not result:
                log = glGetShaderInfoLog(shader)
                self.logger.error(f"{name} shader compilation failed:")
                self.logger.error(f"Shader source:\n{source}")
                self.logger.error(f"Error log: {log.decode() if isinstance(log, bytes) else log}")
                glDeleteShader(shader)
                raise RuntimeError(f"{name} shader compilation failed: {log}")
            
            self.logger.debug(f"{name} shader compiled successfully")
            return shader
            
        except Exception as e:
            self.logger.error(f"Error compiling {name} shader: {str(e)}")
            raise

    def compile_shader_program(self, vertex_path, fragment_path):
        """Compile shader program with detailed error checking."""
        vertex_shader = None
        fragment_shader = None
        program = None
        
        try:
            # Read shader sources
            with open(vertex_path, 'r') as f:
                vertex_src = f.read()
            with open(fragment_path, 'r') as f:
                fragment_src = f.read()

            # Create program
            program = glCreateProgram()
            if not program:
                gl_error = glGetError()
                raise RuntimeError(f"Failed to create shader program. GL Error: {gl_error}")

            # Validate shader compatibility
            if not self.validate_shader_compatibility(vertex_src, fragment_src):
                raise RuntimeError("Shader validation failed: incompatible varying variables")

            # Compile shaders
            vertex_shader = self.compile_shader(vertex_src, GL_VERTEX_SHADER, "Vertex")
            fragment_shader = self.compile_shader(fragment_src, GL_FRAGMENT_SHADER, "Fragment")

            # Attach shaders
            glAttachShader(program, vertex_shader)
            glAttachShader(program, fragment_shader)

            # Bind attribute locations before linking
            glBindAttribLocation(program, 0, "position")
            glBindAttribLocation(program, 1, "tile_type")
            
            # Link program
            glLinkProgram(program)
            
            # Check linking status
            link_status = glGetProgramiv(program, GL_LINK_STATUS)
            if not link_status:
                log = glGetProgramInfoLog(program)
                raise RuntimeError(f"Shader program linking failed: {log}")

            # Validate program
            glValidateProgram(program)
            validate_status = glGetProgramiv(program, GL_VALIDATE_STATUS)
            if not validate_status:
                log = glGetProgramInfoLog(program)
                raise RuntimeError(f"Shader program validation failed: {log}")

            return program
            
        except Exception as e:
            self.logger.error(f"Error creating shader program: {str(e)}")
            if vertex_shader:
                glDeleteShader(vertex_shader)
            if fragment_shader:
                glDeleteShader(fragment_shader)
            if program:
                glDeleteProgram(program)
            raise
        finally:
            if vertex_shader:
                glDeleteShader(vertex_shader)
            if fragment_shader:
                glDeleteShader(fragment_shader)

    def validate_shader_compatibility(self, vertex_src, fragment_src):
        """Validate that vertex and fragment shaders have matching varying variables."""
        def extract_varyings(src):
            varyings = {}
            for line in src.split('\n'):
                if 'varying' in line and not line.strip().startswith('//'):
                    parts = line.split()
                    if len(parts) >= 3:
                        var_type = parts[1]
                        var_name = parts[2].rstrip(';')
                        varyings[var_name] = var_type
            return varyings

        vertex_varyings = extract_varyings(vertex_src)
        fragment_varyings = extract_varyings(fragment_src)

        if vertex_varyings != fragment_varyings:
            self.logger.error("Mismatched varying variables between shaders:")
            self.logger.error(f"Vertex: {vertex_varyings}")
            self.logger.error(f"Fragment: {fragment_varyings}")
            return False

        return True

    def check_opengl_context(self):
        """Check OpenGL context and capabilities."""
        try:
            vendor = glGetString(GL_VENDOR)
            renderer = glGetString(GL_RENDERER)
            version = glGetString(GL_VERSION)
            glsl_version = glGetString(GL_SHADING_LANGUAGE_VERSION)
            
            if not all([vendor, renderer, version, glsl_version]):
                raise RuntimeError("Unable to get OpenGL context information")
            
            self.logger.info("OpenGL Context Information:")
            self.logger.info(f"Vendor: {vendor.decode()}")
            self.logger.info(f"Renderer: {renderer.decode()}")
            self.logger.info(f"OpenGL Version: {version.decode()}")
            self.logger.info(f"GLSL Version: {glsl_version.decode()}")
            
            if not glCreateShader:
                raise RuntimeError("This OpenGL context does not support shaders!")
                
        except Exception as e:
            self.logger.error(f"Error checking OpenGL context: {e}")
            raise

    def load_shaders(self):
        """Load all shader pairs from the shaders directory."""
        self.shader_programs.clear()
        self.shader_names.clear()
        
        shader_pairs = [
            ('no_effect.vert', 'no_effect.frag'),
            ('shift_effect.vert', 'shift_effect.frag'),
            ('color_wave.vert', 'color_wave.frag'),
            ('raindrop_ripple.vert', 'raindrop_ripple.frag'),
        ]

        for vert_file, frag_file in shader_pairs:
            shader_name = vert_file.replace('.vert', '')
            vert_path = os.path.join(self.shaders_folder, vert_file)
            frag_path = os.path.join(self.shaders_folder, frag_file)
            
            try:
                if not os.path.exists(vert_path) or not os.path.exists(frag_path):
                    self.logger.error(f"Shader files not found: {vert_file} or {frag_file}")
                    continue
                    
                program = self.compile_shader_program(vert_path, frag_path)
                self.shader_programs.append(program)
                self.shader_names.append(shader_name)
                
                # Set up uniforms for specific shaders
                glUseProgram(program)
                
                # Common uniforms
                glUniform1i(glGetUniformLocation(program, "time"), 0)
                
                # Special uniforms for ripple shader
                if shader_name == 'raindrop_ripple':
                    glUniform1i(glGetUniformLocation(program, "activeRipples"), 0)
                    ripple_centers_loc = glGetUniformLocation(program, "rippleCenters")
                    ripple_states_loc = glGetUniformLocation(program, "rippleStates")
                    if ripple_centers_loc != -1:
                        glUniform2fv(ripple_centers_loc, 3, np.zeros(6))
                    if ripple_states_loc != -1:
                        glUniform1fv(ripple_states_loc, 6, np.zeros(6))
                
                glUseProgram(0)
                self.logger.info(f"Successfully loaded shader: {shader_name}")
                
            except Exception as e:
                self.logger.error(f"Error loading shader {shader_name}: {e}")


    def next_shader(self):
        """Switch to the next available shader program."""
        if not self.shader_programs:
            return self.current_shader_index
        self.current_shader_index = (self.current_shader_index + 1) % len(self.shader_programs)
        return self.current_shader_index

    def current_shader_program(self):
        """Get the currently active shader program."""
        if not self.shader_programs:
            raise IndexError("No shader programs available")
        return self.shader_programs[self.current_shader_index]

    def __del__(self):
        """Clean up shader programs when the manager is destroyed."""
        if glfw.get_current_context():
            for program in self.shader_programs:
                if program:
                    glDeleteProgram(program)
    
    def update_shader_uniforms(self, current_time, ripple_data=None):
        """Update time-dependent uniforms for the current shader."""
        program = self.current_shader_program()
        glUseProgram(program)
        
        # Update common time uniform
        time_loc = glGetUniformLocation(program, "time")
        if time_loc != -1:
            glUniform1f(time_loc, current_time)
        
        # Update ripple shader specific uniforms
        shader_name = self.shader_names[self.current_shader_index]
        if shader_name == 'raindrop_ripple' and ripple_data:
            active_ripples, centers, states = ripple_data
            
            glUniform1i(glGetUniformLocation(program, "activeRipples"), active_ripples)
            
            centers_loc = glGetUniformLocation(program, "rippleCenters")
            if centers_loc != -1:
                glUniform2fv(centers_loc, len(centers), np.array(centers).flatten())
                
            states_loc = glGetUniformLocation(program, "rippleStates")
            if states_loc != -1:
                glUniform1fv(states_loc, len(states), np.array(states).flatten())
        
        glUseProgram(0)