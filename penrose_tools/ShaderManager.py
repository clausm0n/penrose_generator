# penrose_tools/ShaderManager.py
import os
import sys
from OpenGL.GL import *
from OpenGL.GL import shaders
import logging

class ShaderManager:
    def __init__(self, shaders_folder='Shaders'):
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.shaders_folder = os.path.join(script_dir, shaders_folder)
        self.shader_programs = []
        self.shader_names = []
        self.current_shader_index = 0
        self.logger = logging.getLogger('ShaderManager')
        self.load_shaders()
        if not self.shader_programs:
            self.logger.critical("No shaders were loaded successfully. Exiting application.")
            sys.exit(1)

    def load_shaders(self):
        # List of shader file pairs
        shader_files = [
            ('no_effect.vert', 'no_effect.frag'),
            ('shift_effect.vert', 'shift_effect.frag'),
            ('raindrop_ripple.vert', 'raindrop_ripple.frag'),
            ('color_wave.vert', 'color_wave.frag'),
            ('region_blend.vert', 'region_blend.frag'),
            ('pixelation_slideshow.vert', 'pixelation_slideshow.frag'),
            # Add other shader file pairs here
        ]

        for vert_file, frag_file in shader_files:
            shader_name = vert_file.replace('.vert', '')
            vert_path = os.path.join(self.shaders_folder, vert_file)
            frag_path = os.path.join(self.shaders_folder, frag_file)
            self.logger.debug(f"Attempting to load shader: {shader_name}")
            self.logger.debug(f"Vertex shader path: {vert_path}")
            self.logger.debug(f"Fragment shader path: {frag_path}")
            try:
                program = self.compile_shader_program(vert_path, frag_path)
                self.shader_programs.append(program)
                self.shader_names.append(shader_name)
                self.logger.info(f"Successfully loaded shader: {shader_name}")
            except Exception as e:
                self.logger.error(f"Error loading shader {shader_name}: {e}")

    def compile_shader_program(self, vertex_path, fragment_path):
        if not os.path.isfile(vertex_path):
            raise FileNotFoundError(f"Vertex shader file not found: {vertex_path}")
        if not os.path.isfile(fragment_path):
            raise FileNotFoundError(f"Fragment shader file not found: {fragment_path}")

        with open(vertex_path, 'r') as f:
            vertex_src = f.read()
        with open(fragment_path, 'r') as f:
            fragment_src = f.read()

        try:
            vertex_shader = shaders.compileShader(vertex_src, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(fragment_src, GL_FRAGMENT_SHADER)
            program = shaders.compileProgram(vertex_shader, fragment_shader)
            return program
        except shaders.ShaderCompilationError as e:
            self.logger.error(f"Shader compilation error in {vertex_path} or {fragment_path}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during shader compilation: {e}")
            raise

    def next_shader(self):
        if not self.shader_programs:
            self.logger.error("No shaders loaded to switch to.")
            return self.current_shader_index
        self.current_shader_index = (self.current_shader_index + 1) % len(self.shader_programs)
        self.logger.info(f"Switched to shader index: {self.current_shader_index} ({self.shader_names[self.current_shader_index]})")
        return self.current_shader_index

    def current_shader_program(self):
        if not self.shader_programs:
            self.logger.error("No shaders loaded. Cannot retrieve current shader program.")
            raise IndexError("No shader programs available.")
        return self.shader_programs[self.current_shader_index]

    def reset_state(self):
        # Implement if needed
        pass
