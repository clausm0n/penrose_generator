# penrose_tools/ShaderManager.py
import os
import sys
from OpenGL.GL import *
from OpenGL.GL import shaders
import logging
import glfw
import configparser

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
        self.intro_played = False
        self.intro_start_time = None
        self.intro_duration = 1.5  # Duration in seconds, matching shader
        self.intro_shader = None

        # Intro state tracking
        self.reveal_triggered = False
        self.reveal_start_time = None
        self.reveal_duration = 1.5  # Duration in seconds
        self.black_shader = None
        self.curtain_shader = None
        
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
        self.transition_shader = None
        self.load_shaders()
        self.load_transition_shader()

        # Load intro shader
        self.load_intro_shaders()
        
        if not self.shader_programs:
            self.logger.critical("No shaders were loaded successfully.")
            raise RuntimeError("Failed to load any shader programs")
    
    def load_intro_shaders(self):
        """Load the black and curtain reveal shaders."""
        try:
            # Load black shader
            black_vert = os.path.join(self.shaders_folder, 'black.vert')
            black_frag = os.path.join(self.shaders_folder, 'black.frag')
            
            if not os.path.exists(black_vert) or not os.path.exists(black_frag):
                self.logger.error("Black shader files not found")
                self.black_shader = None
                return
                
            self.black_shader = self.compile_shader_program(black_vert, black_frag)
            
            # Load curtain shader
            curtain_vert = os.path.join(self.shaders_folder, 'curtain.vert')
            curtain_frag = os.path.join(self.shaders_folder, 'curtain.frag')
            
            if not os.path.exists(curtain_vert) or not os.path.exists(curtain_frag):
                self.logger.error("Curtain shader files not found")
                self.curtain_shader = None
                return
                
            self.curtain_shader = self.compile_shader_program(curtain_vert, curtain_frag)
            
            if self.black_shader and self.curtain_shader:
                self.logger.info("Successfully loaded intro shaders")
            else:
                self.logger.error("Failed to compile intro shaders")
                
        except Exception as e:
            self.logger.error(f"Error loading intro shaders: {e}")
            self.black_shader = None
            self.curtain_shader = None
    
    def load_transition_shader(self):
        """Load the transition shader separate from cycling shaders."""
        try:
            vert_path = os.path.join(self.shaders_folder, 'fade.vert')
            frag_path = os.path.join(self.shaders_folder, 'fade.frag')
            
            if not os.path.exists(vert_path) or not os.path.exists(frag_path):
                self.logger.error("Transition shader files not found")
                self.transition_shader = None
                return
                
            self.transition_shader = self.compile_shader_program(vert_path, frag_path)
            if self.transition_shader:
                self.logger.info("Successfully loaded transition shader")
            else:
                self.logger.error("Failed to compile transition shader")
                
        except Exception as e:
            self.logger.error(f"Error loading transition shader: {e}")
            self.transition_shader = None

    def get_transition_shader(self):
        """Get the transition shader program."""
        if not self.transition_shader:
            self.logger.warning("No transition shader available")
        return self.transition_shader

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

            # Attach and link
            glAttachShader(program, vertex_shader)
            glAttachShader(program, fragment_shader)

            # Bind attribute locations
            attributes = {
                0: "position",
                1: "tile_type",
                2: "tile_centroid"
            }
            for location, name in attributes.items():
                glBindAttribLocation(program, location, name)
            
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
            # Clean up shaders (they're no longer needed after linking)
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
            ('color_flow.vert', 'color_flow.frag'),
            ('region_blend.vert', 'region_blend.frag'),
            ('raindrop_ripple.vert', 'raindrop_ripple.frag'),
            ('koi_pond.vert', 'koi_pond.frag'),
            ('pixelation_slideshow.vert', 'pixelation_slideshow.frag')
        ]

        self.logger.info(f"Attempting to load {len(shader_pairs)} shader pairs")
        
        for vert_file, frag_file in shader_pairs:
            shader_name = vert_file.replace('.vert', '')
            vert_path = os.path.join(self.shaders_folder, vert_file)
            frag_path = os.path.join(self.shaders_folder, frag_file)
            
            try:
                if not os.path.exists(vert_path) or not os.path.exists(frag_path):
                    self.logger.error(f"Shader files not found: {vert_file} or {frag_file}")
                    self.logger.error(f"Looked in: {self.shaders_folder}")
                    self.logger.error(f"Full paths: {vert_path}, {frag_path}")
                    continue
                    
                program = self.compile_shader_program(vert_path, frag_path)
                self.shader_programs.append(program)
                self.shader_names.append(shader_name)
                self.logger.info(f"Successfully loaded shader: {shader_name}")
            except Exception as e:
                self.logger.error(f"Error loading shader {shader_name}: {e}")
        
        self.logger.info(f"Successfully loaded {len(self.shader_programs)} shader programs: {', '.join(self.shader_names)}")

    def next_shader(self):
        """Switch to the next available shader program."""
        current_time = glfw.get_time()
        
        # First toggle triggers the reveal
        if not self.reveal_triggered:
            self.reveal_triggered = True
            self.reveal_start_time = current_time
            return -2  # Special index for curtain reveal
            
        # Check if we're still in reveal animation
        if self.reveal_start_time and (current_time - self.reveal_start_time) < self.reveal_duration:
            return -2  # Still in reveal
            
        # Clear reveal state after animation completes and proceed to first regular shader
        if self.reveal_start_time and (current_time - self.reveal_start_time) >= self.reveal_duration:
            self.reveal_start_time = None
            # Reset to start of regular shaders
            self.current_shader_index = 0
            return self.current_shader_index

        # Continue with normal shader cycling logic...
        if not self.shader_programs:
            self.logger.warning("No shader programs available to switch to")
            return self.current_shader_index

        # Read config to get shader settings
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        try:
            shader_settings = eval(config['Settings'].get('shader_settings', '{}'))
        except:
            shader_settings = {}  # Default to empty dict if setting doesn't exist
            
        # Get list of enabled shaders
        enabled_indices = [
            i for i, name in enumerate(self.shader_names)
            if shader_settings.get(name.replace('.vert', ''), True)  # Default to True if not specified
        ]
        
        if not enabled_indices:
            self.logger.warning("No shaders are enabled in settings")
            return self.current_shader_index
            
        # Find the next enabled shader
        current_enabled_index = enabled_indices.index(self.current_shader_index) if self.current_shader_index in enabled_indices else -1
        next_enabled_index = (current_enabled_index + 1) % len(enabled_indices)
        self.current_shader_index = enabled_indices[next_enabled_index]
        
        return self.current_shader_index

    def current_shader_program(self):
        """Get the currently active shader program."""
        # Initial black state
        if not self.reveal_triggered:
            return self.black_shader
            
        # During reveal animation
        if self.reveal_start_time and (glfw.get_time() - self.reveal_start_time) < self.reveal_duration:
            return self.curtain_shader
            
        # Regular shader cycling
        if not self.shader_programs:
            self.logger.error("No shader programs available")
            return None
        return self.shader_programs[self.current_shader_index]

    def __del__(self):
        """Clean up shader programs when the manager is destroyed."""
        if glfw.get_current_context():
            if self.black_shader:
                glDeleteProgram(self.black_shader)
            if self.curtain_shader:
                glDeleteProgram(self.curtain_shader)
            if self.transition_shader:
                glDeleteProgram(self.transition_shader)
            for program in self.shader_programs:
                if program:
                    glDeleteProgram(program)