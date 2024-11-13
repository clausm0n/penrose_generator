# penrose_tools/ShaderManager.py
import os
import sys
from OpenGL.GL import *
from OpenGL.GL import shaders
import logging

class ShaderManager:
    def __init__(self, shaders_folder='Shaders'):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.shaders_folder = os.path.join(self.script_dir, shaders_folder)
        self.shader_programs = []
        self.shader_names = []
        self.current_shader_index = 0
        self.logger = logging.getLogger('ShaderManager')
        
        # Configure logging for more detailed output
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Load shaders
        self.load_shaders()
        
        if not self.shader_programs:
            self.logger.critical("No shaders were loaded successfully. Exiting application.")
            sys.exit(1)

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

            self.logger.debug("Compiling vertex shader...")
            vertex_shader = self.compile_shader(vertex_src, GL_VERTEX_SHADER, "Vertex")
            
            self.logger.debug("Compiling fragment shader...")
            fragment_shader = self.compile_shader(fragment_src, GL_FRAGMENT_SHADER, "Fragment")
            
            # Create program
            self.logger.debug("Creating shader program...")
            program = glCreateProgram()

            # Attach shaders
            glAttachShader(program, vertex_shader)
            glAttachShader(program, fragment_shader)

            # Bind attribute locations before linking
            self.logger.debug("Binding attribute locations...")
            attributes = {
                0: "position",
                1: "tile_type",
                2: "centroid",
                3: "tile_center"
            }
            
            for location, name in attributes.items():
                glBindAttribLocation(program, location, name)
                self.logger.debug(f"Bound attribute {name} to location {location}")
            
            # Link program
            self.logger.debug("Linking shader program...")
            glLinkProgram(program)
            
            # Check linking status
            link_status = glGetProgramiv(program, GL_LINK_STATUS)
            if not link_status:
                log = glGetProgramInfoLog(program)
                log_str = log.decode() if isinstance(log, bytes) else str(log)
                self.logger.error("Shader program linking failed:")
                self.logger.error(f"Link log: {log_str}")
                raise RuntimeError(f"Shader program linking failed: {log_str}")

            # Only validate after successful linking
            self.logger.debug("Validating shader program...")
            glValidateProgram(program)
            validate_status = glGetProgramiv(program, GL_VALIDATE_STATUS)
            if not validate_status:
                log = glGetProgramInfoLog(program)
                log_str = log.decode() if isinstance(log, bytes) else str(log)
                self.logger.error("Shader program validation failed:")
                self.logger.error(f"Validation log: {log_str}")
                raise RuntimeError(f"Shader program validation failed: {log_str}")

            # Log active attributes and uniforms
            num_attributes = glGetProgramiv(program, GL_ACTIVE_ATTRIBUTES)
            num_uniforms = glGetProgramiv(program, GL_ACTIVE_UNIFORMS)
            
            self.logger.debug(f"Active attributes ({num_attributes}):")
            for i in range(num_attributes):
                name, size, type = glGetActiveAttrib(program, i)
                location = glGetAttribLocation(program, name)
                self.logger.debug(f"  {name.decode() if isinstance(name, bytes) else name}: "
                                f"location={location}, size={size}, type={type}")

            self.logger.debug(f"Active uniforms ({num_uniforms}):")
            for i in range(num_uniforms):
                name, size, type = glGetActiveUniform(program, i)
                location = glGetUniformLocation(program, name)
                self.logger.debug(f"  {name.decode() if isinstance(name, bytes) else name}: "
                                f"location={location}, size={size}, type={type}")

            return program
            
        except Exception as e:
            self.logger.error(f"Error creating shader program: {str(e)}")
            # Clean up
            if vertex_shader:
                glDeleteShader(vertex_shader)
            if fragment_shader:
                glDeleteShader(fragment_shader)
            if program:
                glDeleteProgram(program)
            raise
        finally:
            # Clean up shaders (they're no longer needed after linking)
            if vertex_shader:
                glDeleteShader(vertex_shader)
            if fragment_shader:
                glDeleteShader(fragment_shader)

    def load_shaders(self):
        """Load all shader pairs from the shaders directory."""
        self.shader_programs.clear()
        self.shader_names.clear()
        
        shader_pairs = [
            ('no_effect.vert', 'no_effect.frag'),
        ]

        for vert_file, frag_file in shader_pairs:
            shader_name = vert_file.replace('.vert', '')
            vert_path = os.path.join(self.shaders_folder, vert_file)
            frag_path = os.path.join(self.shaders_folder, frag_file)
            
            self.logger.info(f"Loading shader pair: {vert_file} and {frag_file}")
            try:
                program = self.compile_shader_program(vert_path, frag_path)
                self.shader_programs.append(program)
                self.shader_names.append(shader_name)
                self.logger.info(f"Successfully loaded shader: {shader_name}")
            except Exception as e:
                self.logger.error(f"Error loading shader {shader_name}: {e}")

    def next_shader(self):
        if not self.shader_programs:
            return self.current_shader_index
        self.current_shader_index = (self.current_shader_index + 1) % len(self.shader_programs)
        return self.current_shader_index

    def current_shader_program(self):
        if not self.shader_programs:
            raise IndexError("No shader programs available")
        return self.shader_programs[self.current_shader_index]