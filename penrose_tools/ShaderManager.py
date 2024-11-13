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
        
        # Load shaders
        self.load_shaders()
        
        if not self.shader_programs:
            self.logger.critical("No shaders were loaded successfully. Exiting application.")
            sys.exit(1)

    def compile_shader(self, source, shader_type):
        """Compile a shader with detailed error checking."""
        try:
            shader = shaders.compileShader(source, shader_type)
            status = glGetShaderiv(shader, GL_COMPILE_STATUS)
            if not status:
                log = glGetShaderInfoLog(shader)
                self.logger.error(f"Shader compilation error: {log}")
                raise RuntimeError(f"Shader compilation failed: {log}")
            return shader
        except Exception as e:
            self.logger.error(f"Error compiling shader: {str(e)}")
            raise

    def compile_shader_program(self, vertex_path, fragment_path):
        """Compile shader program with detailed error checking."""
        try:
            # Read shader sources
            with open(vertex_path, 'r') as f:
                vertex_src = f.read()
            with open(fragment_path, 'r') as f:
                fragment_src = f.read()

            self.logger.debug(f"Vertex shader source:\n{vertex_src}")
            self.logger.debug(f"Fragment shader source:\n{fragment_src}")
            
            # Compile shaders
            vertex_shader = self.compile_shader(vertex_src, GL_VERTEX_SHADER)
            fragment_shader = self.compile_shader(fragment_src, GL_FRAGMENT_SHADER)
            
            # Create program
            program = glCreateProgram()
            glAttachShader(program, vertex_shader)
            glAttachShader(program, fragment_shader)
            
            # Link program
            glLinkProgram(program)
            if not glGetProgramiv(program, GL_LINK_STATUS):
                log = glGetProgramInfoLog(program)
                self.logger.error(f"Program linking error: {log}")
                raise RuntimeError(f"Program linking failed: {log}")
            
            # Validate program
            glValidateProgram(program)
            if not glGetProgramiv(program, GL_VALIDATE_STATUS):
                log = glGetProgramInfoLog(program)
                self.logger.error(f"Program validation error: {log}")
                raise RuntimeError(f"Program validation failed: {log}")
            
            # Clean up
            glDeleteShader(vertex_shader)
            glDeleteShader(fragment_shader)
            
            return program
            
        except Exception as e:
            self.logger.error(f"Error compiling shader program: {str(e)}")
            raise

    def load_shaders(self):
        """Load all shader pairs from the shaders directory."""
        self.shader_programs.clear()
        self.shader_names.clear()
        
        shader_pairs = [
            ('no_effect.vert', 'no_effect.frag'),
            # Add other shader pairs here as needed
        ]

        for vert_file, frag_file in shader_pairs:
            shader_name = vert_file.replace('.vert', '')
            vert_path = os.path.join(self.shaders_folder, vert_file)
            frag_path = os.path.join(self.shaders_folder, frag_file)
            
            self.logger.info(f"Loading shader: {shader_name}")
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