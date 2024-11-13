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
        
        # Create shaders directory if it doesn't exist
        os.makedirs(self.shaders_folder, exist_ok=True)
        
        # Ensure shader files exist
        self.create_default_shaders()
        self.load_shaders()
        
        if not self.shader_programs:
            self.logger.critical("No shaders were loaded successfully. Exiting application.")
            sys.exit(1)

    def create_default_shaders(self):
        """Create default shader files if they don't exist."""
        shader_pairs = {
            'no_effect.vert': VERTEX_SHADER_SOURCE,
            'no_effect.frag': FRAGMENT_SHADER_SOURCE,
            # Add other shader pairs here
        }
        
        for filename, content in shader_pairs.items():
            filepath = os.path.join(self.shaders_folder, filename)
            if not os.path.exists(filepath):
                with open(filepath, 'w') as f:
                    f.write(content)
                self.logger.info(f"Created default shader file: {filename}")

    def compile_shader_program(self, vertex_path, fragment_path):
        """Compile shader program with detailed error checking."""
        try:
            with open(vertex_path, 'r') as f:
                vertex_src = f.read()
                
            with open(fragment_path, 'r') as f:
                fragment_src = f.read()
                
            # Compile vertex shader with error checking
            vertex_shader = shaders.compileShader(vertex_src, GL_VERTEX_SHADER)
            vertex_log = glGetShaderInfoLog(vertex_shader)
            if vertex_log:
                self.logger.warning(f"Vertex shader compile log: {vertex_log}")
                
            # Compile fragment shader with error checking
            fragment_shader = shaders.compileShader(fragment_src, GL_FRAGMENT_SHADER)
            fragment_log = glGetShaderInfoLog(fragment_shader)
            if fragment_log:
                self.logger.warning(f"Fragment shader compile log: {fragment_log}")
                
            # Link program with error checking
            program = shaders.compileProgram(vertex_shader, fragment_shader)
            program_log = glGetProgramInfoLog(program)
            if program_log:
                self.logger.warning(f"Shader program link log: {program_log}")
                
            return program
            
        except Exception as e:
            self.logger.error(f"Error compiling shader program: {e}")
            raise

    def load_shaders(self):
        """Load all shader pairs from the shaders directory."""
        self.shader_programs.clear()
        self.shader_names.clear()
        
        # List of shader file pairs
        shader_pairs = [
            ('no_effect.vert', 'no_effect.frag'),
            # Add other shader pairs here
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

# Define shader sources as constants
VERTEX_SHADER_SOURCE = """#version 120

attribute vec2 position;
attribute float tile_type;
attribute vec2 centroid;
attribute vec2 tile_center;

varying float v_tile_type;
varying vec2 v_centroid;
varying vec2 v_position;

void main() {
    v_tile_type = tile_type;
    v_centroid = centroid;
    v_position = position;
    gl_Position = vec4(position, 0.0, 1.0);
}
"""

FRAGMENT_SHADER_SOURCE = """#version 120

varying float v_tile_type;
varying vec2 v_centroid;
varying vec2 v_position;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    vec3 tile_color = v_tile_type > 0.5 ? color1 : color2;
    gl_FragColor = vec4(tile_color, 1.0);
}
"""