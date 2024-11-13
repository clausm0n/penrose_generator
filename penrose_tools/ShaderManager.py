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

            self.logger.debug(f"Vertex shader source:\n{vertex_src}")
            self.logger.debug(f"Fragment shader source:\n{fragment_src}")

            # Validate shader compatibility
            if not self.validate_shader_compatibility(vertex_src, fragment_src):
                raise RuntimeError("Shader validation failed: incompatible varying variables")

            # Compile shaders
            self.logger.debug("Compiling vertex shader...")
            vertex_shader = self.compile_shader(vertex_src, GL_VERTEX_SHADER, "Vertex")
            
            self.logger.debug("Compiling fragment shader...")
            fragment_shader = self.compile_shader(fragment_src, GL_FRAGMENT_SHADER, "Fragment")
            
            # Create program
            self.logger.debug("Creating shader program...")
            program = glCreateProgram()
            if not program:
                raise RuntimeError("Failed to create shader program")

            # Attach shaders
            glAttachShader(program, vertex_shader)
            glAttachShader(program, fragment_shader)

            # Bind attribute locations before linking
            self.logger.debug("Binding attribute locations...")
            attributes = {
                0: "position",
                1: "tile_type"
            }
            
            for location, name in attributes.items():
                glBindAttribLocation(program, location, name)
                self.logger.debug(f"Bound attribute {name} to location {location}")
            
            # Link program
            self.logger.debug("Linking shader program...")
            glLinkProgram(program)
            
            # Get linking status
            link_status = glGetProgramiv(program, GL_LINK_STATUS)
            link_log = glGetProgramInfoLog(program)
            
            if link_log:
                self.logger.debug(f"Link log: {link_log.decode() if isinstance(link_log, bytes) else link_log}")
            
            if not link_status:
                program_log = glGetProgramInfoLog(program)
                self.logger.error("Program linking failed:")
                self.logger.error(f"Vertex shader: {vertex_path}")
                self.logger.error(f"Fragment shader: {fragment_path}")
                self.logger.error(f"Program log: {program_log.decode() if isinstance(program_log, bytes) else program_log}")
                raise RuntimeError(f"Shader program linking failed: {program_log}")

            # Try binding the program to check if it's valid
            try:
                glUseProgram(program)
                glUseProgram(0)
            except Exception as e:
                self.logger.error(f"Error using shader program: {e}")
                raise

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

    def log_program_info(self, program):
        """Log information about the shader program's attributes and uniforms."""
        try:
            # Log active attributes
            num_attributes = glGetProgramiv(program, GL_ACTIVE_ATTRIBUTES)
            self.logger.debug(f"Active attributes ({num_attributes}):")
            for i in range(num_attributes):
                name, size, type = glGetActiveAttrib(program, i)
                name = name.decode() if isinstance(name, bytes) else name
                location = glGetAttribLocation(program, name)
                self.logger.debug(f"  {name}: location={location}, size={size}, type={type}")

            # Log active uniforms
            num_uniforms = glGetProgramiv(program, GL_ACTIVE_UNIFORMS)
            self.logger.debug(f"Active uniforms ({num_uniforms}):")
            for i in range(num_uniforms):
                name, size, type = glGetActiveUniform(program, i)
                name = name.decode() if isinstance(name, bytes) else name
                location = glGetUniformLocation(program, name)
                self.logger.debug(f"  {name}: location={location}, size={size}, type={type}")
        except Exception as e:
            self.logger.error(f"Error logging program info: {str(e)}")

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

        # Check if varyings match
        self.logger.debug("Vertex shader varyings: " + str(vertex_varyings))
        self.logger.debug("Fragment shader varyings: " + str(fragment_varyings))

        if vertex_varyings != fragment_varyings:
            self.logger.error("Mismatched varying variables between shaders:")
            self.logger.error(f"Vertex: {vertex_varyings}")
            self.logger.error(f"Fragment: {fragment_varyings}")
            return False

        return True

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