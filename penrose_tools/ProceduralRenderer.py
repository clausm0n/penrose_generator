# penrose_tools/ProceduralRenderer.py
"""
GPU-based procedural Penrose tiling renderer.
Generates infinite tiling in fragment shader using de Bruijn's pentagrid method.
Each effect has its own shader program for maintainability.
"""
import numpy as np
from OpenGL.GL import *
import glfw
import logging
import os
import re
from penrose_tools.Operations import Operations
from penrose_tools.TileDataManager import TileDataManager
from penrose_tools.OverlayRenderer import OverlayRenderer
from penrose_tools.InteractionManager import InteractionManager


class ProceduralRenderer:
    """
    Renders Penrose tiling entirely on the GPU using procedural generation.
    Manages multiple shader programs, one per effect.
    """

    EFFECT_NAMES = [
        'no_effect',
        'region_blend',
        'rainbow',
        'pulse',
        'sparkle',
        'eye_spy',
        'plasmaball',
    ]

    # Effects that use depth camera uniforms
    DEPTH_EFFECTS = {'eye_spy', 'plasmaball'}

    def __init__(self):
        self.logger = logging.getLogger('ProceduralRenderer')

        # Camera state - current (interpolated) values
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.zoom = 0.3
        # Camera state - target values for smooth interpolation
        self.target_camera_x = 0.0
        self.target_camera_y = 0.0
        self.target_zoom = 0.3

        # Smoothing factors (0.0 = no smoothing, 1.0 = instant)
        # Lower values = smoother/slower interpolation
        self.camera_smoothing = 0.08  # For panning
        self.zoom_smoothing = 0.10    # For zooming

        # Velocity for momentum-based movement
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.velocity_decay = 0.92  # How quickly velocity decays

        # Time tracking for frame-independent smoothing
        self.last_update_time = glfw.get_time()
        self._last_render_time = glfw.get_time()

        # Shader programs - one per effect
        self.shader_programs = []
        self.uniform_locations = []  # List of dicts, one per shader

        # Effect mode - start with region_blend (index 2) to show pattern highlighting
        self.effect_mode = 2  # region_blend
        self.num_effects = len(self.EFFECT_NAMES)
        self.logger.info(f"Starting with effect: {self.EFFECT_NAMES[self.effect_mode]}")

        # Edge thickness
        self.edge_thickness = 1.5

        # Gamma values for grid offsets
        self.gamma = [0.2, 0.2, 0.2, 0.2, 0.2]

        # Operations instance for tile generation and pattern detection
        self.operations = Operations()

        # Pattern cache for region_blend effect
        self.pattern_cache = {}
        self.pattern_texture = None
        self.last_pattern_params = None  # (camera_x, camera_y, zoom, width, height, gamma)

        # Overlay system — always-on for interaction support across all effects
        self.tile_manager = None
        self.overlay_renderer = None
        self.interaction_manager = None
        self.overlay_needs_upload = False
        self._last_gamma_for_overlay = None

        # Generation tracking for two-pass pipeline
        self._chunk_gen_id = 0           # generation ID to match geometry with patterns

        # Effects that use the overlay for their primary rendering (opaque overlay).
        # All simple effects render via overlay (zero findTile cost).
        # Complex effects (eye_spy, plasmaball) still use procedural shader.
        self.OVERLAY_EFFECTS = {'region_blend', 'no_effect', 'rainbow', 'pulse', 'sparkle'}

        # Map effect name → overlay shader effect_mode uniform value
        self.OVERLAY_EFFECT_MODE = {
            'region_blend': 0,
            'no_effect': 1,
            'rainbow': 2,
            'pulse': 3,
            'sparkle': 4,
        }

        # Depth mask layer (independent of effect mode — works with any effect)
        self.depth_mask_enabled = False
        self._mask_resolution = 128  # Mask texture resolution
        self._mask_update_interval = 2.0  # Seconds between random mask updates
        self._last_mask_update = 0.0
        self._mask_color = (1.0, 0.3, 0.1)  # Warm highlight color

        # Depth camera state for procedural shaders (eye_spy, plasmaball)
        self._depth_texture_procedural = None  # GL texture for procedural pipeline
        self._depth_coverage = 0.0   # Fraction of depth pixels active (0-1)
        self._depth_centroid = (0.5, 0.5)  # UV centroid of depth data
        self._depth_data_available = False
        self._depth_motion = 0.0  # Smoothed centroid motion magnitude (0-1)
        self._prev_depth_centroid = (0.5, 0.5)  # Previous frame centroid for motion detection

        # Interaction overlay enabled — draws interaction visuals on top of any effect
        self.interaction_overlay_enabled = True

        # Tween engine reference for smooth visual transitions
        self.tween_engine = None

        # Resolution scaling: render at fraction of screen res, upscale to display
        # 0.5 = half res each axis = 4x fewer pixels through fragment shader
        self.render_scale = 1.0
        self._fbo = None
        self._fbo_texture = None
        self._fbo_depth = None
        self._fbo_width = 0
        self._fbo_height = 0
        self._upscale_program = None
        self._upscale_uniforms = {}

        # Adaptive render scale: dynamically adjusts render_scale to maintain target FPS
        self.adaptive_scale_enabled = False
        self.adaptive_scale_min = 0.25
        self.adaptive_scale_max = 0.75
        self.adaptive_target_fps = 30
        self._frame_times = []          # rolling window of frame times
        self._frame_time_window = 20    # number of frames to average
        self._adaptive_last_adjust = 0.0
        self._adaptive_adjust_interval = 0.5  # seconds between scale adjustments
        self._adaptive_current_scale = 0.5    # smoothed working scale

        if not glfw.get_current_context():
            raise RuntimeError("ProceduralRenderer requires an active OpenGL context")

        self._load_all_shaders()
        self._create_quad()
        self._create_upscale_shader()

        # Initialize overlay + interaction system (always-on)
        try:
            self.tile_manager = TileDataManager()
            self.overlay_renderer = OverlayRenderer()
            self.interaction_manager = InteractionManager(self.tile_manager)
            self.interaction_manager.set_mask_stamp_callback(self._handle_mask_stamp)
            self.logger.info("Overlay + interaction system initialized")
        except Exception as e:
            self.logger.error(f"Overlay system init failed (falling back to texture): {e}")
            self.tile_manager = None
            self.overlay_renderer = None
            self.interaction_manager = None

        self.logger.info(f"ProceduralRenderer initialized with {len(self.shader_programs)} effect shaders")

    def _preprocess_shader(self, source, shader_dir):
        """Process #include directives in shader source."""
        include_pattern = re.compile(r'#include\s+"([^"]+)"')

        def replace_include(match):
            include_file = match.group(1)
            include_path = os.path.join(shader_dir, include_file)
            if os.path.exists(include_path):
                with open(include_path, 'r') as f:
                    return f.read()
            else:
                self.logger.warning(f"Include file not found: {include_path}")
                return f"// Include not found: {include_file}"

        # Process includes (single level - no recursive includes)
        processed = include_pattern.sub(replace_include, source)
        return processed

    def _compile_shader_program(self, vert_src, frag_src, name):
        """Compile and link a shader program."""
        from penrose_tools.gl_config import patch_shader
        vert_src = patch_shader(vert_src, is_fragment=False)
        frag_src = patch_shader(frag_src, is_fragment=True)

        # Compile vertex shader
        vert_shader = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vert_shader, vert_src)
        glCompileShader(vert_shader)
        if not glGetShaderiv(vert_shader, GL_COMPILE_STATUS):
            log = glGetShaderInfoLog(vert_shader)
            raise RuntimeError(f"Vertex shader error ({name}): {log}")

        # Compile fragment shader
        frag_shader = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(frag_shader, frag_src)
        glCompileShader(frag_shader)
        if not glGetShaderiv(frag_shader, GL_COMPILE_STATUS):
            log = glGetShaderInfoLog(frag_shader)
            raise RuntimeError(f"Fragment shader error ({name}): {log}")

        # Link program
        program = glCreateProgram()
        glAttachShader(program, vert_shader)
        glAttachShader(program, frag_shader)
        glBindAttribLocation(program, 0, "position")
        glLinkProgram(program)

        if not glGetProgramiv(program, GL_LINK_STATUS):
            log = glGetProgramInfoLog(program)
            raise RuntimeError(f"Shader link error ({name}): {log}")

        glDeleteShader(vert_shader)
        glDeleteShader(frag_shader)

        return program

    def _cache_uniforms_for_program(self, program):
        """Cache uniform locations for a shader program."""
        glUseProgram(program)
        uniforms = {
            'u_resolution': glGetUniformLocation(program, 'u_resolution'),
            'u_camera': glGetUniformLocation(program, 'u_camera'),
            'u_zoom': glGetUniformLocation(program, 'u_zoom'),
            'u_time': glGetUniformLocation(program, 'u_time'),
            'u_color1': glGetUniformLocation(program, 'u_color1'),
            'u_color2': glGetUniformLocation(program, 'u_color2'),
            'u_edge_thickness': glGetUniformLocation(program, 'u_edge_thickness'),
            'u_gamma': glGetUniformLocation(program, 'u_gamma'),
            'u_pattern_texture': glGetUniformLocation(program, 'u_pattern_texture'),
            # Depth camera uniforms (used by eye_spy effect)
            'u_depth_texture': glGetUniformLocation(program, 'u_depth_texture'),
            'u_depth_enabled': glGetUniformLocation(program, 'u_depth_enabled'),
            'u_depth_coverage': glGetUniformLocation(program, 'u_depth_coverage'),
            'u_depth_centroid': glGetUniformLocation(program, 'u_depth_centroid'),
            'u_depth_motion': glGetUniformLocation(program, 'u_depth_motion'),
        }
        glUseProgram(0)
        return uniforms

    def _load_all_shaders(self):
        """Load all effect shaders from the Shaders directory."""
        shader_dir = os.path.join(os.path.dirname(__file__), 'Shaders')
        vert_path = os.path.join(shader_dir, 'procedural.vert')

        self.logger.info(f"Loading procedural shaders from: {shader_dir}")

        # Load shared vertex shader
        if not os.path.exists(vert_path):
            raise FileNotFoundError(f"Shared vertex shader not found: {vert_path}")

        with open(vert_path, 'r') as f:
            vert_src = f.read()

        # Load each effect shader
        for effect_name in self.EFFECT_NAMES:
            frag_path = os.path.join(shader_dir, f'{effect_name}.frag')

            if not os.path.exists(frag_path):
                self.logger.warning(f"Effect shader not found: {frag_path}, adding placeholder")
                self.shader_programs.append(None)
                self.uniform_locations.append({})
                continue

            with open(frag_path, 'r') as f:
                frag_src = f.read()

            # Preprocess includes
            frag_src = self._preprocess_shader(frag_src, shader_dir)

            try:
                program = self._compile_shader_program(vert_src, frag_src, effect_name)
                uniforms = self._cache_uniforms_for_program(program)
                self.shader_programs.append(program)
                self.uniform_locations.append(uniforms)
                self.logger.info(f"Loaded effect shader: {effect_name}")
            except RuntimeError as e:
                self.logger.error(f"Failed to load {effect_name}: {e}")
                # Add placeholder to maintain index alignment
                self.shader_programs.append(None)
                self.uniform_locations.append({})

        self.logger.info(f"Loaded {len([p for p in self.shader_programs if p])} shaders successfully")

    def _create_quad(self):
        verts = np.array([-1, -1, 1, -1, 1, 1, -1, 1], dtype=np.float32)
        inds = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)
        
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        
        self.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, inds.nbytes, inds, GL_STATIC_DRAW)
        
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
        glBindVertexArray(0)
    
    def _create_upscale_shader(self):
        """Create a simple shader that samples an FBO texture to the screen."""
        from penrose_tools.gl_config import patch_shader
        vert_src = patch_shader("""
#version 140
in vec2 position;
out vec2 v_uv;
void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_uv = position * 0.5 + 0.5;
}
""", is_fragment=False)
        frag_src = patch_shader("""
#version 140
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D u_texture;
void main() {
    fragColor = texture(u_texture, v_uv);
}
""", is_fragment=True)
        vert = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vert, vert_src)
        glCompileShader(vert)
        if not glGetShaderiv(vert, GL_COMPILE_STATUS):
            self.logger.error(f"Upscale vert error: {glGetShaderInfoLog(vert)}")
            return
        frag = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(frag, frag_src)
        glCompileShader(frag)
        if not glGetShaderiv(frag, GL_COMPILE_STATUS):
            self.logger.error(f"Upscale frag error: {glGetShaderInfoLog(frag)}")
            return
        self._upscale_program = glCreateProgram()
        glAttachShader(self._upscale_program, vert)
        glAttachShader(self._upscale_program, frag)
        glBindAttribLocation(self._upscale_program, 0, "position")
        glLinkProgram(self._upscale_program)
        if not glGetProgramiv(self._upscale_program, GL_LINK_STATUS):
            self.logger.error(f"Upscale link error: {glGetProgramInfoLog(self._upscale_program)}")
            self._upscale_program = None
            return
        glDeleteShader(vert)
        glDeleteShader(frag)
        self._upscale_uniforms['u_texture'] = glGetUniformLocation(self._upscale_program, 'u_texture')
        self.logger.info("Upscale shader compiled")

    def _ensure_fbo(self, width, height):
        """Create or resize the offscreen FBO for reduced-resolution rendering."""
        rw = max(1, int(width * self.render_scale))
        rh = max(1, int(height * self.render_scale))
        if self._fbo is not None and self._fbo_width == rw and self._fbo_height == rh:
            return
        # Clean up old
        if self._fbo is not None:
            try:
                glDeleteFramebuffers(1, [self._fbo])
                glDeleteTextures([self._fbo_texture])
                if self._fbo_depth is not None:
                    glDeleteRenderbuffers(1, [self._fbo_depth])
            except Exception:
                pass
        self._fbo = None
        self._fbo_texture = None
        self._fbo_depth = None
        try:
            # Create color texture
            self._fbo_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self._fbo_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, rw, rh, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glBindTexture(GL_TEXTURE_2D, 0)
            # Create depth renderbuffer for depth pre-pass
            self._fbo_depth = glGenRenderbuffers(1)
            glBindRenderbuffer(GL_RENDERBUFFER, self._fbo_depth)
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT16, rw, rh)
            glBindRenderbuffer(GL_RENDERBUFFER, 0)
            # Create FBO with color + depth
            self._fbo = glGenFramebuffers(1)
            glBindFramebuffer(GL_FRAMEBUFFER, self._fbo)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self._fbo_texture, 0)
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self._fbo_depth)
            status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
            if status != GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"FBO incomplete: status={status}")
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            self._fbo_width = rw
            self._fbo_height = rh
            self.logger.info(f"FBO created: {rw}x{rh} (scale={self.render_scale})")
        except Exception as e:
            self.logger.error(f"FBO creation failed, falling back to direct render: {e}")
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            if self._fbo is not None:
                try:
                    glDeleteFramebuffers(1, [self._fbo])
                except Exception:
                    pass
            if self._fbo_texture is not None:
                try:
                    glDeleteTextures([self._fbo_texture])
                except Exception:
                    pass
            self._fbo = None
            self._fbo_texture = None
            # Disable scaling so we don't keep retrying
            self.render_scale = 1.0

    def _use_overlay(self):
        """Check if current effect should use the overlay as its primary rendering path."""
        return (self.EFFECT_NAMES[self.effect_mode] in self.OVERLAY_EFFECTS
                and self.tile_manager is not None
                and self.overlay_renderer is not None)

    def _has_interaction_overlay(self):
        """Check if the interaction overlay system is available and enabled."""
        return (self.interaction_overlay_enabled
                and self.tile_manager is not None
                and self.overlay_renderer is not None
                and self.interaction_manager is not None)

    def render(self, width, height, config_data):
        """Render the Penrose tiling with flattened render passes.

        Rendering strategy:
        - region_blend: overlay only (skip expensive procedural shader entirely)
        - other effects: depth pre-pass with overlay tiles → procedural with
          early-Z rejection (95%+ pixels skip findTile) → interaction overlay

        On VideoCore VII's TBDR, the depth pre-pass enables hardware hidden
        surface removal, so the expensive procedural fragment shader only runs
        for the ~5% of pixels in gaps between overlay tiles.
        """
        # Update camera smoothing before rendering
        self.update()

        # If render_scale < 1.0, render into FBO at reduced resolution then upscale
        use_fbo = self.render_scale < 1.0 and self._upscale_program is not None
        if use_fbo:
            self._ensure_fbo(width, height)
            if self._fbo is not None:
                glBindFramebuffer(GL_FRAMEBUFFER, self._fbo)
                glViewport(0, 0, self._fbo_width, self._fbo_height)
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                render_w, render_h = self._fbo_width, self._fbo_height
            else:
                use_fbo = False
                render_w, render_h = width, height
        else:
            render_w, render_h = width, height

        gamma = config_data.get('gamma', self.gamma)
        current_effect = self.EFFECT_NAMES[self.effect_mode]
        use_overlay = self._use_overlay()
        has_interaction = self._has_interaction_overlay()

        # --- Tick animations (always, regardless of effect) ---
        if has_interaction:
            dt = glfw.get_time() - self._last_render_time
            self._last_render_time = glfw.get_time()
            dt = max(0.0, min(dt, 0.1))
            self.interaction_manager.update_animations(dt)
            self._flush_interaction_dirty()

        # --- Prepare colors (shared by all passes) ---
        c1 = config_data.get('color1', [255, 255, 255])
        c2 = config_data.get('color2', [0, 0, 255])

        if self.tween_engine:
            color_tween = self.tween_engine.get('color')
            if color_tween is not None:
                c1 = [color_tween[0], color_tween[1], color_tween[2]]
                c2 = [color_tween[3], color_tween[4], color_tween[5]]

        brightness = self.tween_engine.brightness_multiplier if self.tween_engine else 1.0
        c1_r, c1_g, c1_b = c1[0] / 255.0 * brightness, c1[1] / 255.0 * brightness, c1[2] / 255.0 * brightness
        c2_r, c2_g, c2_b = c2[0] / 255.0 * brightness, c2[1] / 255.0 * brightness, c2[2] / 255.0 * brightness

        overlay_config = dict(config_data)
        overlay_config['color1'] = [c1_r * 255.0, c1_g * 255.0, c1_b * 255.0]
        overlay_config['color2'] = [c2_r * 255.0, c2_g * 255.0, c2_b * 255.0]

        # --- Process overlay tile updates once (shared by all paths) ---
        has_tile_data = (self.tile_manager is not None
                         and self.overlay_renderer is not None)
        if has_tile_data:
            aspect = float(render_w) / float(render_h)
            self._process_overlay_updates(gamma, aspect)
            has_tile_data = self.overlay_renderer.tile_count > 0

        if use_overlay:
            # === OVERLAY PATH: renders tile effect directly — zero findTile cost ===
            # All simple effects (no_effect, region_blend, rainbow, pulse, sparkle)
            # render via instanced overlay tiles instead of expensive procedural shader.
            effect_mode = self.OVERLAY_EFFECT_MODE.get(current_effect, 0)
            self.overlay_renderer.render(
                self.camera_x, self.camera_y, self.zoom,
                render_w, render_h, overlay_config,
                self.edge_thickness, glfw.get_time(),
                overlay_mode=0, effect_mode=effect_mode)
        else:
            # === NON-OVERLAY EFFECTS: depth pre-pass + procedural + interaction ===

            # STEP 1: Depth pre-pass — overlay tiles write depth only (no color)
            # This blocks the expensive procedural findTile for covered pixels.
            if has_tile_data:
                glEnable(GL_DEPTH_TEST)
                glDepthFunc(GL_LESS)
                glDepthMask(GL_TRUE)
                glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE)

                self.overlay_renderer.render_depth_prepass(
                    self.camera_x, self.camera_y, self.zoom,
                    render_w, render_h)

                glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)
                glDepthMask(GL_FALSE)  # procedural doesn't write depth

            # STEP 2: Procedural shader — depth tested, covered pixels rejected
            base_index = self.effect_mode
            program = self.shader_programs[base_index]
            if program is None:
                for i, p in enumerate(self.shader_programs):
                    if p is not None:
                        program = p
                        base_index = i
                        break
                if program is None:
                    self.logger.error("No valid shader programs available")
                    if has_tile_data:
                        glDisable(GL_DEPTH_TEST)
                        glDepthMask(GL_TRUE)
                    return

            uniforms = self.uniform_locations[base_index]
            glUseProgram(program)

            if uniforms.get('u_resolution', -1) != -1:
                glUniform2f(uniforms['u_resolution'], float(render_w), float(render_h))
            if uniforms.get('u_camera', -1) != -1:
                glUniform2f(uniforms['u_camera'], self.camera_x, self.camera_y)
            if uniforms.get('u_zoom', -1) != -1:
                glUniform1f(uniforms['u_zoom'], self.zoom)
            if uniforms.get('u_time', -1) != -1:
                glUniform1f(uniforms['u_time'], glfw.get_time())
            if uniforms.get('u_color1', -1) != -1:
                glUniform3f(uniforms['u_color1'], c1_r, c1_g, c1_b)
            if uniforms.get('u_color2', -1) != -1:
                glUniform3f(uniforms['u_color2'], c2_r, c2_g, c2_b)
            if uniforms.get('u_edge_thickness', -1) != -1:
                glUniform1f(uniforms['u_edge_thickness'], self.edge_thickness)
            if uniforms.get('u_gamma', -1) != -1:
                gamma_array = (GLfloat * 5)(*gamma)
                glUniform1fv(uniforms['u_gamma'], 5, gamma_array)

            # Depth camera uniforms
            if current_effect in self.DEPTH_EFFECTS and uniforms.get('u_depth_enabled', -1) != -1:
                if self._depth_data_available and self._depth_texture_procedural is not None:
                    glUniform1f(uniforms['u_depth_enabled'], 1.0)
                    glUniform1f(uniforms['u_depth_coverage'], self._depth_coverage)
                    glUniform2f(uniforms['u_depth_centroid'],
                                self._depth_centroid[0], self._depth_centroid[1])
                    if uniforms.get('u_depth_motion', -1) != -1:
                        glUniform1f(uniforms['u_depth_motion'], self._depth_motion)
                    if uniforms.get('u_depth_texture', -1) != -1:
                        glActiveTexture(GL_TEXTURE1)
                        glBindTexture(GL_TEXTURE_2D, self._depth_texture_procedural)
                        glUniform1i(uniforms['u_depth_texture'], 1)
                else:
                    glUniform1f(uniforms['u_depth_enabled'], 0.0)
                    glUniform1f(uniforms['u_depth_coverage'], 0.3)
                    glUniform2f(uniforms['u_depth_centroid'], 0.5, 0.5)
                    if uniforms.get('u_depth_motion', -1) != -1:
                        glUniform1f(uniforms['u_depth_motion'], 0.0)

            # Old texture-based region_blend fallback
            if current_effect == 'region_blend' and not use_overlay:
                self._update_pattern_data_if_needed(width, height, gamma)
                if self.pattern_texture is not None and uniforms.get('u_pattern_texture', -1) != -1:
                    glActiveTexture(GL_TEXTURE0)
                    glBindTexture(GL_TEXTURE_2D, self.pattern_texture)
                    glUniform1i(uniforms['u_pattern_texture'], 0)

            glBindVertexArray(self.vao)
            glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)

            if current_effect in self.DEPTH_EFFECTS and self._depth_texture_procedural is not None:
                glActiveTexture(GL_TEXTURE1)
                glBindTexture(GL_TEXTURE_2D, 0)
                glActiveTexture(GL_TEXTURE0)

            glUseProgram(0)

            # STEP 3: Disable depth, render interaction overlay if needed
            if has_tile_data:
                glDisable(GL_DEPTH_TEST)
                glDepthMask(GL_TRUE)

            if has_interaction and self._has_active_interactions():
                self.overlay_renderer.render(
                    self.camera_x, self.camera_y, self.zoom,
                    render_w, render_h, overlay_config,
                    self.edge_thickness, glfw.get_time(), overlay_mode=1)

        # --- Upscale FBO to screen ---
        if use_fbo and self._fbo is not None:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            glViewport(0, 0, width, height)
            glDisable(GL_DEPTH_TEST)
            glUseProgram(self._upscale_program)
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self._fbo_texture)
            glUniform1i(self._upscale_uniforms['u_texture'], 0)
            glBindVertexArray(self.vao)
            glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
            glBindTexture(GL_TEXTURE_2D, 0)
            glUseProgram(0)

    def _process_overlay_updates(self, gamma, aspect):
        """Poll for background generation results and upload to GPU.

        Two-pass pipeline: geometry arrives first (tiles render with default
        pattern values), pattern data arrives shortly after and is patched in.
        The heavy NumPy packing runs on the background thread — the render
        thread only does the fast GL upload (~1-2ms).
        """
        # --- Poll for new geometry (Pass 1 result) ---
        geo_result = self.tile_manager.poll_geometry()
        if geo_result is not None:
            gpu_verts, gpu_data, tile_count, gen_id = geo_result
            self._chunk_gen_id = gen_id

            if self.interaction_manager:
                self.interaction_manager.on_tiles_regenerated()

            # Use glBufferSubData to avoid GPU pipeline stall from buffer orphaning
            self.overlay_renderer.ensure_capacity(tile_count)
            self.overlay_renderer.upload_tile_chunk(gpu_verts, gpu_data, 0, tile_count)
            self.overlay_renderer.set_renderable_count(tile_count)
            self.overlay_needs_upload = False
            self.tile_manager.gpu_data_dirty = False

        # --- Poll for pattern data (Pass 2 result) ---
        pat_result = self.tile_manager.poll_patterns()
        if pat_result is not None:
            (pattern_type_col, blend_factor_col, stars, bursts,
             symmetry_tile_ids, gen_id) = pat_result

            if gen_id == self._chunk_gen_id and self.tile_manager.gpu_tile_data is not None:
                self.tile_manager.star_count = stars
                self.tile_manager.starburst_count = bursts

                # Patch pattern columns into the live gpu_tile_data array
                n = len(pattern_type_col)
                self.tile_manager.gpu_tile_data[:n, 1] = pattern_type_col
                self.tile_manager.gpu_tile_data[:n, 2] = blend_factor_col

                # Patch only the data VBO with updated patterns (avoids full re-upload)
                self.overlay_renderer.upload_pattern_patch_chunk(
                    self.tile_manager.gpu_tile_data, 0, n)

                # Pass 5-fold symmetry tile indices to interaction manager
                if self.interaction_manager and symmetry_tile_ids:
                    sym_indices = set()
                    for i, tile in enumerate(self.tile_manager.tile_list):
                        if id(tile) in symmetry_tile_ids:
                            sym_indices.add(i)
                    self.interaction_manager.set_symmetry_tiles(sym_indices)

        # --- Request new generation if camera left comfort zone ---
        gamma_tuple = tuple(round(g, 4) for g in gamma)
        gamma_changed = (gamma_tuple != self._last_gamma_for_overlay)

        if gamma_changed or self.tile_manager.needs_regeneration(
                self.camera_x, self.camera_y, self.zoom, aspect):
            self._last_gamma_for_overlay = gamma_tuple
            self.tile_manager.request_generation(
                self.camera_x, self.camera_y, self.zoom, aspect, gamma,
                self.velocity_x, self.velocity_y)

        # --- Depth mask management (unchanged) ---
        mask_stamp_active = (self.interaction_manager
                             and self.interaction_manager._mask_stamp_active)
        if self.depth_mask_enabled and not mask_stamp_active:
            self._update_depth_mask()
        elif not mask_stamp_active:
            if self.overlay_renderer:
                self.overlay_renderer.set_mask_enabled(False)

    def _update_overlay(self, width, height, gamma, config_data):
        """Manage overlay tile lifecycle and render overlay on top of base."""
        aspect = float(width) / float(height)
        self._process_overlay_updates(gamma, aspect)

        # Render overlay tiles on top of procedural base (primary mode = opaque)
        self.overlay_renderer.render(
            self.camera_x, self.camera_y, self.zoom,
            width, height, config_data,
            self.edge_thickness, glfw.get_time(), overlay_mode=0)

    def _update_interaction_overlay(self, width, height, gamma, config_data):
        """Manage tile lifecycle for interaction overlay (non-region_blend effects)."""
        aspect = float(width) / float(height)
        self._process_overlay_updates(gamma, aspect)

        # Render overlay if there are active interactions or depth mask to show
        if self._has_active_interactions():
            self.overlay_renderer.render(
                self.camera_x, self.camera_y, self.zoom,
                width, height, config_data,
                self.edge_thickness, glfw.get_time(), overlay_mode=1)

    def _has_active_interactions(self):
        """Check if there are any active interactions worth rendering."""
        if self.interaction_manager is None:
            return False
        return (self.interaction_manager._hovered_index >= 0
                or len(self.interaction_manager._selected_indices) > 0
                or len(self.interaction_manager._animations) > 0
                or self.interaction_manager._mask_stamp_active
                or self.depth_mask_enabled)

    def _flush_interaction_dirty(self):
        """Upload only the dirty tile range to GPU (partial buffer update)."""
        if not self.interaction_manager or not self.overlay_renderer:
            return
        offset, count = self.interaction_manager.get_dirty_range()
        if count > 0 and self.tile_manager.gpu_tile_data is not None:
            self.overlay_renderer.upload_tile_data_partial(
                self.tile_manager.gpu_tile_data, offset, count)
            self.tile_manager.gpu_data_dirty = False

    def screen_to_pentagrid(self, screen_x, screen_y, window_width, window_height):
        """Convert screen pixel coordinates to pentagrid/camera space.

        The procedural vertex shader maps:
            p = clip * 0.5 * vec2(aspect, 1) * (3/zoom) + camera
        where clip = (screen / resolution) * 2 - 1

        Returns (pentagrid_x, pentagrid_y).
        """
        aspect = float(window_width) / float(window_height)

        # Screen pixels → NDC clip space [-1, 1]
        clip_x = (screen_x / window_width) * 2.0 - 1.0
        clip_y = 1.0 - (screen_y / window_height) * 2.0  # flip Y

        # NDC → pentagrid/camera space (invert the procedural shader transform)
        pentagrid_x = clip_x * 0.5 * aspect * (3.0 / self.zoom) + self.camera_x
        pentagrid_y = clip_y * 0.5 * (3.0 / self.zoom) + self.camera_y

        return pentagrid_x, pentagrid_y
    
    # Camera controls
    def move(self, dx, dy):
        """Move camera target by delta (smooth interpolation applied in update)."""
        self.target_camera_x += dx
        self.target_camera_y += dy

    def move_direction(self, dx, dy, speed=0.05):
        """Move camera in a direction with velocity for momentum-based smoothing."""
        # Add to velocity for momentum-based movement
        accel = speed / self.target_zoom * 2.0
        self.velocity_x += dx * accel
        self.velocity_y += dy * accel

    def set_zoom(self, z):
        """Set target zoom level (smooth interpolation applied in update).

        Clamped to [0.3, 100.0]. Below 0.3 the tile count explodes and
        performance degrades; above 100 there's nothing useful to see.
        """
        self.target_zoom = max(0.1, min(100.0, z))

    def zoom_by(self, factor):
        """Zoom by a factor (smooth interpolation applied in update)."""
        self.set_zoom(self.target_zoom * factor)

    def reset(self):
        """Reset camera to origin with smooth transition."""
        self.target_camera_x = 0.0
        self.target_camera_y = 0.0
        self.target_zoom = 1.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
    
    def next_effect(self):
        self.effect_mode = (self.effect_mode + 1) % self.num_effects
        name = self.EFFECT_NAMES[self.effect_mode]
        self.logger.info(f"Effect: {self.effect_mode} - {name}")
        return self.effect_mode
    
    def set_effect(self, index):
        self.effect_mode = index % self.num_effects
        return self.effect_mode
    
    def get_effect_name(self):
        return self.EFFECT_NAMES[self.effect_mode]
    
    def set_edge_thickness(self, t):
        self.edge_thickness = max(0.0, min(5.0, t))
    
    def set_gamma(self, gamma):
        if len(gamma) == 5:
            self.gamma = list(gamma)
    
    def randomize_gamma(self):
        import random
        self.gamma = [random.uniform(0.0, 1.0) for _ in range(5)]
        return self.gamma

    # -------------------------------------------------------------------------
    # Depth mask effect
    # -------------------------------------------------------------------------

    def _update_depth_mask(self):
        """Ensure the depth mask texture exists (generated once, then static).
        User can stamp new masks via mask_stamp interaction mode."""
        if self._last_mask_update == 0.0:
            mask = self._generate_random_mask(self._mask_resolution)
            if self.overlay_renderer:
                self.overlay_renderer.upload_mask_texture(
                    mask, self._mask_resolution, self._mask_resolution)
                self.overlay_renderer.set_mask_color(*self._mask_color)
                self.overlay_renderer.set_mask_enabled(True)
            self._last_mask_update = glfw.get_time()

    def _generate_random_mask(self, resolution):
        """Generate a random blob mask simulating a depth camera silhouette.
        Returns a (resolution, resolution) float32 array with values in [0, 1].
        """
        # Create smooth blobs using summed Gaussians to simulate person silhouettes
        mask = np.zeros((resolution, resolution), dtype=np.float32)

        # Coordinate grid
        y, x = np.mgrid[0:resolution, 0:resolution].astype(np.float32) / resolution

        # Generate 2-5 random blobs (simulating people / objects)
        num_blobs = np.random.randint(2, 6)
        for _ in range(num_blobs):
            cx = np.random.uniform(0.15, 0.85)
            cy = np.random.uniform(0.15, 0.85)
            # Elliptical blob with random size
            sx = np.random.uniform(0.05, 0.20)
            sy = np.random.uniform(0.08, 0.30)
            intensity = np.random.uniform(0.5, 1.0)

            dx = (x - cx) / sx
            dy = (y - cy) / sy
            blob = np.exp(-0.5 * (dx * dx + dy * dy))
            mask += blob * intensity

        # Normalize to [0, 1]
        mask_max = mask.max()
        if mask_max > 0:
            mask /= mask_max

        # Apply a soft threshold to create more defined silhouettes
        mask = np.clip(mask * 1.5 - 0.2, 0.0, 1.0)

        return mask

    def set_mask_update_interval(self, interval):
        """Set how often the random mask regenerates (in seconds)."""
        self._mask_update_interval = max(0.1, interval)

    def set_mask_color(self, r, g, b):
        """Set the depth mask highlight color (0-1 float values)."""
        self._mask_color = (r, g, b)
        if self.overlay_renderer:
            self.overlay_renderer.set_mask_color(r, g, b)

    def upload_external_mask(self, mask_data, width, height):
        """Upload an external mask (e.g. from a depth camera).
        mask_data: numpy array of shape (height, width) with float32 values in [0, 1].
        Updates the texture but respects the current depth_mask_enabled toggle.
        """
        if self.overlay_renderer:
            self.overlay_renderer.upload_mask_texture(mask_data, width, height)
            # Only set mask_enabled on the renderer if the layer is toggled on
            if self.depth_mask_enabled:
                self.overlay_renderer.set_mask_enabled(True)
            self._last_mask_update = glfw.get_time()

        # Also compute depth metrics and upload texture for procedural shaders
        self._update_depth_metrics(mask_data, width, height)

    def _update_depth_metrics(self, mask_data, width, height):
        """Compute depth coverage and centroid from mask data, and upload
        the depth frame as a procedural-pipeline texture for depth-interactive effects."""
        # Coverage: fraction of pixels above a small threshold
        active = mask_data > 0.05
        total_pixels = mask_data.size
        active_count = np.count_nonzero(active)
        self._depth_coverage = active_count / total_pixels if total_pixels > 0 else 0.0

        # Centroid: weighted average of active pixel positions in UV space
        if active_count > 0:
            ys, xs = np.where(active)
            weights = mask_data[active]
            total_w = weights.sum()
            if total_w > 0:
                cx = (xs * weights).sum() / total_w / width
                cy = (ys * weights).sum() / total_w / height
                # Flip Y: numpy row 0 = top, but pentagrid Y+ = up
                self._depth_centroid = (float(cx), 1.0 - float(cy))
                if not hasattr(self, '_centroid_log_count'):
                    self._centroid_log_count = 0
                self._centroid_log_count += 1
                if self._centroid_log_count % 60 == 1:
                    self.logger.info(f"Depth centroid: ({cx:.3f}, {1.0-cy:.3f}) coverage={self._depth_coverage:.2f}")
            else:
                self._depth_centroid = (0.5, 0.5)
        else:
            self._depth_centroid = (0.5, 0.5)

        # Motion detection: distance the centroid moved since last frame
        dx = self._depth_centroid[0] - self._prev_depth_centroid[0]
        dy = self._depth_centroid[1] - self._prev_depth_centroid[1]
        raw_motion = (dx * dx + dy * dy) ** 0.5
        # Smooth: ramp up fast, decay very slowly
        # UV-space movements are tiny (0.001-0.05), so scale up aggressively
        if raw_motion > 0.002:
            self._depth_motion = min(1.0, self._depth_motion + raw_motion * 40.0)
        else:
            self._depth_motion = max(0.0, self._depth_motion * 0.995)
        self._prev_depth_centroid = self._depth_centroid

        self._depth_data_available = True

        # Upload depth data as a texture for the procedural pipeline
        if self._depth_texture_procedural is None:
            self._depth_texture_procedural = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self._depth_texture_procedural)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glBindTexture(GL_TEXTURE_2D, 0)

        glBindTexture(GL_TEXTURE_2D, self._depth_texture_procedural)
        contiguous = np.ascontiguousarray(mask_data, dtype=np.float32)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, width, height, 0,
                     GL_RED, GL_FLOAT, contiguous)
        glBindTexture(GL_TEXTURE_2D, 0)

    def _handle_mask_stamp(self, pentagrid_x, pentagrid_y):
        """Handle a mask stamp click — generate a Gaussian blob at the pentagrid position
        and upload it as the mask texture. Works across all effects."""
        res = self._mask_resolution
        mask = self._generate_stamp_mask(res, pentagrid_x, pentagrid_y)
        if self.overlay_renderer:
            self.overlay_renderer.upload_mask_texture(mask, res, res)
            self.overlay_renderer.set_mask_color(*self._mask_color)
            self.overlay_renderer.set_mask_center(pentagrid_x, pentagrid_y)
            self.overlay_renderer.set_mask_enabled(True)
            self.depth_mask_enabled = True

    def _generate_stamp_mask(self, resolution, center_x, center_y):
        """Generate a single Gaussian blob mask centered at (0.5, 0.5).
        The shader maps world positions to mask UV using the camera transform,
        so we always generate the blob at center and let the shader position it.
        Returns a (resolution, resolution) float32 array with values in [0, 1].
        """
        y, x = np.mgrid[0:resolution, 0:resolution].astype(np.float32) / resolution

        # Single centered blob — the fragment shader handles positioning via
        # u_mask_camera which is set to the current camera position.
        # The stamp appears where the camera is looking, so we create it at UV center.
        cx, cy = 0.5, 0.5
        sx, sy = 0.15, 0.15  # Stamp radius in UV space
        dx = (x - cx) / sx
        dy = (y - cy) / sy
        mask = np.exp(-0.5 * (dx * dx + dy * dy)).astype(np.float32)

        # Soft threshold for defined edges
        mask = np.clip(mask * 1.5 - 0.2, 0.0, 1.0)
        return mask

    def _generate_tiles_for_viewport(self, width, height, gamma):
        """Generate tile objects for the current viewport."""
        # Estimate the world-space bounds based on camera and zoom
        # The shader uses: vec2 p = uv * (3.0 / u_zoom) + u_camera
        aspect = width / height
        half_height = 3.0 / self.zoom
        half_width = half_height * aspect

        # World space bounds
        min_x = self.camera_x - half_width
        max_x = self.camera_x + half_width
        min_y = self.camera_y - half_height
        max_y = self.camera_y + half_height

        # Generate tiles using Operations
        # The tiling function uses scale to determine tile density
        # Lower scale = more tiles generated
        #
        # The key insight: the shader generates tiles in RIBBON SPACE, not screen space
        # Ribbon space has a fixed tile size regardless of zoom
        # We need to generate enough tiles to cover the visible ribbon space area
        #
        # Visible ribbon space area = (3.0 / zoom) * aspect for width, (3.0 / zoom) for height
        # At zoom=1.0, we see ~3 units of ribbon space vertically
        # At zoom=0.5, we see ~6 units of ribbon space vertically
        #
        # Tile size in ribbon space is roughly 1.0 unit
        # So we need size ≈ (3.0 / zoom) tiles in each direction
        #
        # But Operations.tiling() uses: size = max(width, height) // (scale * 3)
        # We want: size ≈ 3.0 / zoom
        # So: max(width, height) // (scale * 3) ≈ 3.0 / zoom
        # Therefore: scale ≈ max(width, height) / (9.0 / zoom) = max(width, height) * zoom / 9.0
        #
        # For width=800, zoom=1.0: scale = 800 * 1.0 / 9.0 ≈ 89
        # For width=800, zoom=0.5: scale = 800 * 0.5 / 9.0 ≈ 44

        virtual_scale = int(max(10, (max(width, height) * self.zoom) / 10.0))
        virtual_width = int(width)
        virtual_height = int(height)

        # Pass camera offset to align CPU tile generation with GPU world space
        camera_offset = complex(self.camera_x, self.camera_y)
        tiles = self.operations.tiling(gamma, virtual_width, virtual_height, virtual_scale, camera_offset)

        # Calculate neighbors for pattern detection
        self.operations.calculate_neighbors(tiles)

        # Debug: Check if neighbors were calculated (only log occasionally)
        # tiles_with_neighbors = sum(1 for t in tiles if len(t.neighbors) > 0)
        # self.logger.debug(f"Tiles with neighbors: {tiles_with_neighbors}/{len(tiles)}")

        return tiles

    def _detect_patterns(self, tiles):
        """Detect star and starburst patterns in tiles."""
        patterns = {}
        pattern_tiles = set()

        stars = []
        starbursts = []

        # Debug: Count valid candidates (disabled for performance)
        # valid_star_kites = sum(1 for t in tiles if t.is_kite and self.operations.is_valid_star_kite(t))
        # valid_starburst_darts = sum(1 for t in tiles if not t.is_kite and self.operations.is_valid_starburst_dart(t))
        # self.logger.debug(f"Valid star kites: {valid_star_kites}, Valid starburst darts: {valid_starburst_darts}")

        # First pass - identify complete regions
        for tile in tiles:
            if tile not in pattern_tiles:
                if tile.is_kite and self.operations.is_valid_star_kite(tile):
                    star_tiles = self.operations.find_star(tile, tiles)
                    if len(star_tiles) == 5:
                        stars.append(star_tiles)
                        pattern_tiles.update(star_tiles)
                elif not tile.is_kite and self.operations.is_valid_starburst_dart(tile):
                    starburst_tiles = self.operations.find_starburst(tile, tiles)
                    if len(starburst_tiles) == 10:
                        starbursts.append(starburst_tiles)
                        pattern_tiles.update(starburst_tiles)

        # Second pass - assign pattern data to each tile
        blend_factors_debug = []
        for tile in tiles:
            pattern_type = 0.0
            blend_factor = 0.5

            # Check if tile is in a pattern
            in_pattern = False
            for star in stars:
                if tile in star:
                    pattern_type = 1.0
                    blend_factor = 0.3
                    in_pattern = True
                    break

            if not in_pattern:
                for burst in starbursts:
                    if tile in burst:
                        pattern_type = 2.0
                        blend_factor = 0.7
                        in_pattern = True
                        break

            if not in_pattern:
                # Calculate neighbor-based blend for non-pattern tiles
                kite_count, dart_count = self.operations.count_kite_and_dart_neighbors(tile)
                total_neighbors = kite_count + dart_count
                blend_factor = 0.5 if total_neighbors == 0 else kite_count / total_neighbors
                blend_factors_debug.append((kite_count, dart_count, blend_factor))

            # Store pattern data indexed by tile centroid (in world/ribbon space)
            # The centroid from tile.vertices is already in the correct space
            # IMPORTANT: Scale by 0.1 to match shader's tileCentroid = center * 0.1
            centroid = sum(tile.vertices) / len(tile.vertices)
            scaled_centroid = centroid * 0.1  # Match shader scaling
            patterns[tile] = {
                'centroid': scaled_centroid,  # Complex number in world space, scaled to match shader
                'pattern_type': pattern_type,
                'blend_factor': blend_factor,
                'is_kite': tile.is_kite
            }

        self.logger.info(f"Pattern detection: {len(stars)} stars, {len(starbursts)} starbursts, {len(tiles)} total tiles")
        if len(stars) > 0:
            sample_tile = list(stars[0])[0]
            centroid = sum(sample_tile.vertices) / len(sample_tile.vertices)
            scaled = centroid * 0.1
            self.logger.info(f"  Sample star centroid: ribbon={centroid.real:.4f},{centroid.imag:.4f} scaled={scaled.real:.4f},{scaled.imag:.4f}")
        if len(starbursts) > 0:
            sample_tile = list(starbursts[0])[0]
            centroid = sum(sample_tile.vertices) / len(sample_tile.vertices)
            scaled = centroid * 0.1
            self.logger.info(f"  Sample starburst centroid: ribbon={centroid.real:.4f},{centroid.imag:.4f} scaled={scaled.real:.4f},{scaled.imag:.4f}")

        return patterns

    def _create_pattern_texture(self, patterns):
        """Create a texture containing pattern data for lookup in shader."""
        if not patterns:
            return None

        # Create a texture with pattern data indexed by centroid position
        # Each entry: (centroid.x, centroid.y, pattern_type, blend_factor)
        # Centroids are stored in ribbon space (same as tile.center in shader)
        pattern_list = []
        for tile, data in patterns.items():
            centroid = data['centroid']  # Complex number in ribbon space
            pattern_list.append([
                float(centroid.real),
                float(centroid.imag),
                data['pattern_type'],
                data['blend_factor']
            ])

        if not pattern_list:
            return None

        pattern_array = np.array(pattern_list, dtype=np.float32)

        # Create or update texture
        if self.pattern_texture is None:
            self.pattern_texture = glGenTextures(1)

        glBindTexture(GL_TEXTURE_2D, self.pattern_texture)

        # Upload as a 1D texture (width x 1) with RGBA = (centroid.x, centroid.y, pattern_type, blend_factor)
        width = len(pattern_list)
        height = 1

        # Create texture data
        texture_data = np.array(pattern_list, dtype=np.float32).reshape((height, width, 4))

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, width, height, 0,
                     GL_RGBA, GL_FLOAT, texture_data)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

        glBindTexture(GL_TEXTURE_2D, 0)

        self.logger.debug(f"Created pattern texture: {width} tiles, {height} rows")
        # Detailed logging disabled for performance
        # if len(pattern_list) > 0:
        #     self.logger.debug(f"  Sample pattern[0]: centroid=({pattern_list[0][0]:.3f}, {pattern_list[0][1]:.3f}), type={pattern_list[0][2]}, blend={pattern_list[0][3]}")

        return width

    def _update_pattern_data_if_needed(self, width, height, gamma):
        """Update pattern data when viewport changes."""
        # Cache based on viewport parameters
        # Use finer granularity for zoom (0.05 instead of 0.1) to catch more viewport changes
        # Especially important when zooming out, as the viewport expands rapidly
        current_params = (
            round(self.camera_x, 1),
            round(self.camera_y, 1),
            round(self.zoom, 2),  # Finer granularity: 0.01 instead of 0.1
            width,
            height,
            tuple(round(g, 3) for g in gamma)
        )

        if self.last_pattern_params == current_params:
            return

        self.logger.info("Regenerating pattern data for region_blend")

        # Generate tiles and detect patterns
        tiles = self._generate_tiles_for_viewport(width, height, gamma)
        self.logger.info(f"Generated {len(tiles)} tiles for viewport")

        patterns = self._detect_patterns(tiles)
        self.logger.info(f"Detected patterns for {len(patterns)} tiles")

        # Create texture
        texture_width = self._create_pattern_texture(patterns)

        # Cache the patterns and parameters
        self.pattern_cache = patterns
        self.last_pattern_params = current_params

        self.logger.info(f"Pattern data updated: {len(patterns)} tiles, texture width: {texture_width}")

    def update(self):
        """Update camera position and zoom with smooth interpolation."""
        current_time = glfw.get_time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time

        # Clamp dt to avoid jumps after pauses
        dt = min(dt, 0.1)

        # Frame-rate independent smoothing factor
        # At 60fps, dt ≈ 0.0167, so we scale our smoothing accordingly
        base_fps = 60.0
        time_factor = dt * base_fps

        # Apply velocity to targets (for momentum-based movement)
        self.target_camera_x += self.velocity_x * dt
        self.target_camera_y += self.velocity_y * dt

        # Decay velocity
        decay_factor = pow(self.velocity_decay, time_factor)
        self.velocity_x *= decay_factor
        self.velocity_y *= decay_factor

        # Stop velocity when very small
        if abs(self.velocity_x) < 0.0001:
            self.velocity_x = 0.0
        if abs(self.velocity_y) < 0.0001:
            self.velocity_y = 0.0

        # Smooth interpolation for camera position
        camera_lerp = 1.0 - pow(1.0 - self.camera_smoothing, time_factor)
        self.camera_x += (self.target_camera_x - self.camera_x) * camera_lerp
        self.camera_y += (self.target_camera_y - self.camera_y) * camera_lerp

        # Smooth interpolation for zoom (use exponential for natural feel)
        zoom_lerp = 1.0 - pow(1.0 - self.zoom_smoothing, time_factor)
        # Log-space interpolation for zoom feels more natural
        log_current = np.log(self.zoom)
        log_target = np.log(self.target_zoom)
        log_new = log_current + (log_target - log_current) * zoom_lerp
        self.zoom = np.exp(log_new)

    def update_adaptive_scale(self, frame_time):
        """Track frame times and adjust render_scale to maintain target FPS.

        Call this every frame with the measured frame_time (seconds).
        The render_scale is smoothly adjusted to keep frame rate near the target.
        """
        if not self.adaptive_scale_enabled:
            return

        # Track rolling frame times
        self._frame_times.append(frame_time)
        if len(self._frame_times) > self._frame_time_window:
            self._frame_times.pop(0)

        # Only adjust periodically to avoid oscillation
        now = glfw.get_time()
        if now - self._adaptive_last_adjust < self._adaptive_adjust_interval:
            return
        if len(self._frame_times) < 5:
            return

        self._adaptive_last_adjust = now

        # Use 90th percentile frame time (not average) to avoid stutter spikes
        sorted_times = sorted(self._frame_times)
        p90_time = sorted_times[int(len(sorted_times) * 0.9)]
        target_time = 1.0 / self.adaptive_target_fps

        # Compute ratio: >1 means we're too slow, <1 means we have headroom
        ratio = p90_time / target_time

        if ratio > 1.1:
            # Too slow — reduce scale. Scale pixel count proportionally.
            # Pixel count scales as scale^2, so scale adjustment is sqrt of ratio
            factor = 1.0 / (ratio ** 0.5)
            self._adaptive_current_scale *= factor
        elif ratio < 0.75:
            # Headroom available — increase scale gradually (slower than decrease)
            factor = 1.0 / (ratio ** 0.3)
            self._adaptive_current_scale *= min(factor, 1.05)  # cap increase at 5% per step

        # Clamp to configured bounds
        self._adaptive_current_scale = max(self.adaptive_scale_min,
                                           min(self.adaptive_scale_max,
                                               self._adaptive_current_scale))

        # Apply with snapping to avoid FBO churn on tiny changes
        new_scale = round(self._adaptive_current_scale * 20.0) / 20.0  # snap to 0.05 increments
        if abs(new_scale - self.render_scale) >= 0.05:
            old = self.render_scale
            self.render_scale = new_scale
            self.logger.info(f"Adaptive scale: {old:.2f} -> {new_scale:.2f} "
                           f"(p90={p90_time*1000:.1f}ms, target={target_time*1000:.1f}ms)")

    @property
    def camera(self):
        return self
    
    @property
    def x(self):
        return self.camera_x
    
    @property
    def y(self):
        return self.camera_y
    
    def __del__(self):
        if self.tile_manager:
            self.tile_manager.shutdown()
        if glfw.get_current_context():
            if hasattr(self, 'overlay_renderer') and self.overlay_renderer:
                self.overlay_renderer.cleanup()
            if hasattr(self, '_depth_texture_procedural') and self._depth_texture_procedural:
                glDeleteTextures(1, [self._depth_texture_procedural])
            if hasattr(self, 'vao'):
                glDeleteVertexArrays(1, [self.vao])
            if hasattr(self, 'vbo'):
                glDeleteBuffers(1, [self.vbo])
            if hasattr(self, 'ebo'):
                glDeleteBuffers(1, [self.ebo])
            if hasattr(self, 'shader_programs'):
                for program in self.shader_programs:
                    if program is not None:
                        glDeleteProgram(program)
