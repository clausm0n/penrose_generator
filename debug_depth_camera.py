"""
Debug viewer for the Orbbec depth camera via OpenNI2.
Uses GLFW + OpenGL (same stack as the main penrose_generator).
Shows live depth with background subtraction and threshold controls.

Usage:
    python debug_depth_camera.py [--no-invert] [--min 500] [--max 4000] [--smoothing 0.3]

Controls:
    Q / ESC     Quit
    I           Toggle invert
    S           Toggle smoothing on/off
    +/-         Adjust depth max range
    [/]         Adjust depth min range
    R           Reset to defaults
    P           Print frame stats to console

    B           Capture background reference (step away from camera first!)
    X           Clear background reference
    T           Toggle threshold mode (binary silhouette)
    UP/DOWN     Adjust background subtraction tolerance (mm)
    LEFT/RIGHT  Adjust binary threshold level
    G           Toggle Gaussian blur on output
    E           Toggle edge erosion (removes noisy edges)
"""

import argparse
import sys
import os
import time

import numpy as np
import glfw
from OpenGL.GL import *

sys.path.insert(0, os.path.dirname(__file__))
from penrose_tools.DepthCameraManager import DepthCameraManager, OPENNI2_AVAILABLE

# ── Shaders ──────────────────────────────────────────────────────────────

VERT_SRC = """
#version 140
in vec2 a_pos;
out vec2 v_uv;
void main() {
    v_uv = a_pos * 0.5 + 0.5;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

FRAG_SRC = """
#version 140
in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D u_depth;
uniform float u_mode;  // 0 = grayscale, 1 = colorized, 2 = silhouette (green on black)

vec3 inferno(float t) {
    t = clamp(t, 0.0, 1.0);
    vec3 c0 = vec3(0.0, 0.0, 0.04);
    vec3 c1 = vec3(0.34, 0.06, 0.42);
    vec3 c2 = vec3(0.72, 0.21, 0.33);
    vec3 c3 = vec3(0.99, 0.56, 0.15);
    vec3 c4 = vec3(0.99, 0.99, 0.64);

    if (t < 0.25) return mix(c0, c1, t / 0.25);
    if (t < 0.50) return mix(c1, c2, (t - 0.25) / 0.25);
    if (t < 0.75) return mix(c2, c3, (t - 0.50) / 0.25);
    return mix(c3, c4, (t - 0.75) / 0.25);
}

void main() {
    float d = texture(u_depth, v_uv).r;
    vec3 color;
    if (u_mode < 0.5) {
        color = vec3(d);
    } else if (u_mode < 1.5) {
        color = inferno(d);
    } else {
        // Silhouette: green foreground on black
        color = vec3(0.0, d, 0.0);
    }
    fragColor = vec4(color, 1.0);
}
"""

# ── Text rendering (bitmap font via OpenGL immediate mode) ───────────────

_FONT = {}

def _define_font():
    glyphs = {
        '0': [0x0E,0x11,0x13,0x15,0x19,0x11,0x0E],
        '1': [0x04,0x0C,0x04,0x04,0x04,0x04,0x0E],
        '2': [0x0E,0x11,0x01,0x06,0x08,0x10,0x1F],
        '3': [0x0E,0x11,0x01,0x06,0x01,0x11,0x0E],
        '4': [0x02,0x06,0x0A,0x12,0x1F,0x02,0x02],
        '5': [0x1F,0x10,0x1E,0x01,0x01,0x11,0x0E],
        '6': [0x06,0x08,0x10,0x1E,0x11,0x11,0x0E],
        '7': [0x1F,0x01,0x02,0x04,0x08,0x08,0x08],
        '8': [0x0E,0x11,0x11,0x0E,0x11,0x11,0x0E],
        '9': [0x0E,0x11,0x11,0x0F,0x01,0x02,0x0C],
        ' ': [0x00,0x00,0x00,0x00,0x00,0x00,0x00],
        '.': [0x00,0x00,0x00,0x00,0x00,0x00,0x04],
        ':': [0x00,0x04,0x00,0x00,0x00,0x04,0x00],
        '/': [0x01,0x02,0x02,0x04,0x08,0x08,0x10],
        '-': [0x00,0x00,0x00,0x0E,0x00,0x00,0x00],
        '+': [0x00,0x04,0x04,0x1F,0x04,0x04,0x00],
        '=': [0x00,0x00,0x1F,0x00,0x1F,0x00,0x00],
        '(': [0x02,0x04,0x08,0x08,0x08,0x04,0x02],
        ')': [0x08,0x04,0x02,0x02,0x02,0x04,0x08],
        '%': [0x11,0x12,0x02,0x04,0x08,0x09,0x11],
        '#': [0x0A,0x0A,0x1F,0x0A,0x1F,0x0A,0x0A],
        'x': [0x00,0x00,0x11,0x0A,0x04,0x0A,0x11],
        '*': [0x00,0x04,0x15,0x0E,0x15,0x04,0x00],
        '<': [0x02,0x04,0x08,0x10,0x08,0x04,0x02],
        '>': [0x08,0x04,0x02,0x01,0x02,0x04,0x08],
    }
    az = {
        'A': [0x0E,0x11,0x11,0x1F,0x11,0x11,0x11],
        'B': [0x1E,0x11,0x11,0x1E,0x11,0x11,0x1E],
        'C': [0x0E,0x11,0x10,0x10,0x10,0x11,0x0E],
        'D': [0x1E,0x11,0x11,0x11,0x11,0x11,0x1E],
        'E': [0x1F,0x10,0x10,0x1E,0x10,0x10,0x1F],
        'F': [0x1F,0x10,0x10,0x1E,0x10,0x10,0x10],
        'G': [0x0E,0x11,0x10,0x17,0x11,0x11,0x0F],
        'H': [0x11,0x11,0x11,0x1F,0x11,0x11,0x11],
        'I': [0x0E,0x04,0x04,0x04,0x04,0x04,0x0E],
        'J': [0x01,0x01,0x01,0x01,0x01,0x11,0x0E],
        'K': [0x11,0x12,0x14,0x18,0x14,0x12,0x11],
        'L': [0x10,0x10,0x10,0x10,0x10,0x10,0x1F],
        'M': [0x11,0x1B,0x15,0x15,0x11,0x11,0x11],
        'N': [0x11,0x19,0x15,0x13,0x11,0x11,0x11],
        'O': [0x0E,0x11,0x11,0x11,0x11,0x11,0x0E],
        'P': [0x1E,0x11,0x11,0x1E,0x10,0x10,0x10],
        'Q': [0x0E,0x11,0x11,0x11,0x15,0x12,0x0D],
        'R': [0x1E,0x11,0x11,0x1E,0x14,0x12,0x11],
        'S': [0x0E,0x11,0x10,0x0E,0x01,0x11,0x0E],
        'T': [0x1F,0x04,0x04,0x04,0x04,0x04,0x04],
        'U': [0x11,0x11,0x11,0x11,0x11,0x11,0x0E],
        'V': [0x11,0x11,0x11,0x11,0x0A,0x0A,0x04],
        'W': [0x11,0x11,0x11,0x15,0x15,0x1B,0x11],
        'X': [0x11,0x11,0x0A,0x04,0x0A,0x11,0x11],
        'Y': [0x11,0x11,0x0A,0x04,0x04,0x04,0x04],
        'Z': [0x1F,0x01,0x02,0x04,0x08,0x10,0x1F],
    }
    glyphs.update(az)
    for ch in 'abcdefghijklmnopqrstuvwxyz':
        glyphs[ch] = az.get(ch.upper(), glyphs[' '])
    _FONT.update(glyphs)

_define_font()


def draw_text_gl(text, x, y, win_w, win_h, scale=2, color=(0.0, 1.0, 0.0)):
    """Draw text using GL_POINTS in orthographic projection. (x,y) from top-left."""
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, win_w, win_h, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glColor3f(*color)
    glPointSize(float(scale))
    glBegin(GL_POINTS)
    cx = x
    for ch in text:
        glyph = _FONT.get(ch)
        if glyph is None:
            cx += 6 * scale
            continue
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits & (0x10 >> col):
                    px = cx + col * scale
                    py = y + row * scale
                    for dx in range(scale):
                        for dy in range(scale):
                            glVertex2f(px + dx, py + dy)
        cx += 6 * scale
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def draw_text_shadow(text, x, y, w, h, scale=2, color=(0.0, 1.0, 0.0)):
    """Draw text with a dark shadow behind it for readability."""
    draw_text_gl(text, x + 1, y + 1, w, h, scale=scale, color=(0.0, 0.0, 0.0))
    draw_text_gl(text, x, y, w, h, scale=scale, color=color)


# ── Post-processing helpers (numpy, no opencv) ──────────────────────────

def box_blur_3x3(arr):
    """Simple 3x3 box blur on a 2D float32 array using numpy."""
    h, w = arr.shape
    out = np.zeros_like(arr)
    # Pad with zeros
    padded = np.pad(arr, 1, mode='constant', constant_values=0)
    for dy in range(3):
        for dx in range(3):
            out += padded[dy:dy + h, dx:dx + w]
    return out / 9.0


def erode_mask(arr, iterations=1):
    """Simple erosion: pixel is kept only if all 4 neighbors are also > 0."""
    result = arr.copy()
    for _ in range(iterations):
        h, w = result.shape
        padded = np.pad(result, 1, mode='constant', constant_values=0)
        # A pixel survives only if it AND all 4-connected neighbors are non-zero
        up    = padded[0:h, 1:w+1]
        down  = padded[2:h+2, 1:w+1]
        left  = padded[1:h+1, 0:w]
        right = padded[1:h+1, 2:w+2]
        center = padded[1:h+1, 1:w+1]
        survived = (center > 0) & (up > 0) & (down > 0) & (left > 0) & (right > 0)
        result = np.where(survived, result, 0.0)
    return result


# ── Main ─────────────────────────────────────────────────────────────────

def run_debug_viewer(args):
    if not OPENNI2_AVAILABLE:
        print("ERROR: OpenNI2 is not available.")
        print("Make sure the openni2 runtime is in penrose_tools/openni2_runtime/")
        sys.exit(1)

    cam = DepthCameraManager(
        depth_min_mm=args.min,
        depth_max_mm=args.max,
        invert=not args.no_invert,
    )
    cam.set_temporal_smoothing(args.smoothing)

    # ── GLFW + OpenGL init (before camera so window is visible during wait) ──
    print("Initializing GLFW...")
    if not glfw.init():
        print("ERROR: Failed to init GLFW.")
        sys.exit(1)

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
    glfw.window_hint(glfw.FOCUSED, glfw.TRUE)
    glfw.window_hint(glfw.FLOATING, glfw.TRUE)  # Stay on top initially
    window = glfw.create_window(960, 540, "Depth Camera Debug", None, None)
    if not window:
        glfw.terminate()
        print("ERROR: Failed to create window.")
        sys.exit(1)

    glfw.make_context_current(window)
    glfw.swap_interval(1)
    glfw.show_window(window)
    glfw.focus_window(window)

    # Show a "loading" frame so the window isn't blank
    fb_w, fb_h = glfw.get_framebuffer_size(window)
    glViewport(0, 0, fb_w, fb_h)
    glClearColor(0.1, 0.1, 0.1, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    glfw.swap_buffers(window)
    glfw.poll_events()

    print("Starting depth camera...")
    if not cam.start(timeout=10.0):
        print("ERROR: Failed to start depth camera.")
        glfw.terminate()
        sys.exit(1)
    print("Depth camera started.")
    # Disable always-on-top after startup
    glfw.set_window_attrib(window, glfw.FLOATING, glfw.FALSE)

    # Compile shader
    vert = glCreateShader(GL_VERTEX_SHADER)
    glShaderSource(vert, VERT_SRC)
    glCompileShader(vert)
    if not glGetShaderiv(vert, GL_COMPILE_STATUS):
        print("Vert error:", glGetShaderInfoLog(vert).decode())
        sys.exit(1)

    frag = glCreateShader(GL_FRAGMENT_SHADER)
    glShaderSource(frag, FRAG_SRC)
    glCompileShader(frag)
    if not glGetShaderiv(frag, GL_COMPILE_STATUS):
        print("Frag error:", glGetShaderInfoLog(frag).decode())
        sys.exit(1)

    prog = glCreateProgram()
    glAttachShader(prog, vert)
    glAttachShader(prog, frag)
    glBindAttribLocation(prog, 0, "a_pos")
    glLinkProgram(prog)
    if not glGetProgramiv(prog, GL_LINK_STATUS):
        print("Link error:", glGetProgramInfoLog(prog).decode())
        sys.exit(1)
    glDeleteShader(vert)
    glDeleteShader(frag)

    u_depth = glGetUniformLocation(prog, "u_depth")
    u_mode = glGetUniformLocation(prog, "u_mode")

    # Fullscreen quad
    quad = np.array([-1,-1, 1,-1, 1,1, -1,-1, 1,1, -1,1], dtype=np.float32)
    vao = glGenVertexArrays(1)
    vbo = glGenBuffers(1)
    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, quad.nbytes, quad, GL_STATIC_DRAW)
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
    glBindVertexArray(0)

    # Depth texture
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, 1, 1, 0, GL_RED, GL_FLOAT,
                 np.zeros((1,1), dtype=np.float32))
    glBindTexture(GL_TEXTURE_2D, 0)

    # ── Processing state ──
    bg_reference = None         # Background reference frame (raw depth from cam)
    bg_tolerance = 0.05         # Normalized tolerance for background subtraction
    threshold_mode = False       # Binary silhouette mode
    threshold_level = 0.15       # Cutoff for binary threshold
    blur_enabled = False         # Gaussian (box) blur
    erode_enabled = False        # Edge erosion
    bg_frames_to_avg = 30        # Number of frames to average for bg capture
    bg_capturing = False         # Currently capturing bg frames
    bg_capture_frames = []       # Accumulated frames during bg capture

    def on_key(win, key, scancode, action, mods):
        nonlocal bg_reference, bg_tolerance, threshold_mode, threshold_level
        nonlocal blur_enabled, erode_enabled, bg_capturing, bg_capture_frames

        if action != glfw.PRESS:
            return

        if key in (glfw.KEY_Q, glfw.KEY_ESCAPE):
            glfw.set_window_should_close(win, True)
        elif key == glfw.KEY_I:
            cam.set_invert(not cam.invert)
            print(f"Invert: {cam.invert}")
        elif key == glfw.KEY_S:
            if cam.temporal_smoothing > 0:
                cam.set_temporal_smoothing(0.0)
            else:
                cam.set_temporal_smoothing(0.3)
            print(f"Smoothing: {cam.temporal_smoothing}")
        elif key == glfw.KEY_EQUAL:
            cam.set_depth_range(cam.depth_min_mm, cam.depth_max_mm + 500)
            print(f"Range: {cam.depth_min_mm}-{cam.depth_max_mm}mm")
        elif key == glfw.KEY_MINUS:
            cam.set_depth_range(cam.depth_min_mm, max(1000, cam.depth_max_mm - 500))
            print(f"Range: {cam.depth_min_mm}-{cam.depth_max_mm}mm")
        elif key == glfw.KEY_RIGHT_BRACKET:
            cam.set_depth_range(min(cam.depth_min_mm + 100, cam.depth_max_mm - 100),
                                cam.depth_max_mm)
            print(f"Range: {cam.depth_min_mm}-{cam.depth_max_mm}mm")
        elif key == glfw.KEY_LEFT_BRACKET:
            cam.set_depth_range(max(0, cam.depth_min_mm - 100), cam.depth_max_mm)
            print(f"Range: {cam.depth_min_mm}-{cam.depth_max_mm}mm")
        elif key == glfw.KEY_R:
            cam.set_depth_range(500, 4000)
            cam.set_invert(True)
            cam.set_temporal_smoothing(0.3)
            bg_reference = None
            threshold_mode = False
            threshold_level = 0.15
            bg_tolerance = 0.05
            blur_enabled = False
            erode_enabled = False
            print("Reset all to defaults")
        elif key == glfw.KEY_P:
            depth, _ = cam.get_depth()
            if depth is not None:
                valid_mask = depth > 0
                valid_count = np.count_nonzero(valid_mask)
                print(f"\n--- Frame #{cam.frame_count} ---")
                print(f"  Shape: {depth.shape}")
                print(f"  Valid: {valid_count}/{depth.size} ({100*valid_count/depth.size:.1f}%)")
                if valid_count > 0:
                    v = depth[valid_mask]
                    print(f"  Min: {v.min():.4f}  Max: {v.max():.4f}  "
                          f"Mean: {v.mean():.4f}  Std: {v.std():.4f}")
                print(f"  Range: {cam.depth_min_mm}-{cam.depth_max_mm}mm  Invert: {cam.invert}")
                print(f"  BG ref: {'SET' if bg_reference is not None else 'NONE'}  "
                      f"Tolerance: {bg_tolerance:.3f}  Threshold: {threshold_mode} ({threshold_level:.2f})")

        # Background subtraction controls
        elif key == glfw.KEY_B:
            print(f"Capturing background ({bg_frames_to_avg} frames)... hold still!")
            bg_capturing = True
            bg_capture_frames = []
        elif key == glfw.KEY_X:
            bg_reference = None
            print("Background reference cleared")
        elif key == glfw.KEY_T:
            threshold_mode = not threshold_mode
            print(f"Threshold mode: {threshold_mode} (level: {threshold_level:.2f})")
        elif key == glfw.KEY_UP:
            bg_tolerance = min(0.5, bg_tolerance + 0.01)
            print(f"BG tolerance: {bg_tolerance:.3f}")
        elif key == glfw.KEY_DOWN:
            bg_tolerance = max(0.005, bg_tolerance - 0.01)
            print(f"BG tolerance: {bg_tolerance:.3f}")
        elif key == glfw.KEY_RIGHT:
            threshold_level = min(0.9, threshold_level + 0.02)
            print(f"Threshold level: {threshold_level:.2f}")
        elif key == glfw.KEY_LEFT:
            threshold_level = max(0.02, threshold_level - 0.02)
            print(f"Threshold level: {threshold_level:.2f}")
        elif key == glfw.KEY_G:
            blur_enabled = not blur_enabled
            print(f"Blur: {blur_enabled}")
        elif key == glfw.KEY_E:
            erode_enabled = not erode_enabled
            print(f"Erosion: {erode_enabled}")

    glfw.set_key_callback(window, on_key)

    fps = 0.0
    last_time = time.monotonic()
    print("Debug window open.")
    print("Step away from camera and press B to capture background.\n")

    try:
        while not glfw.window_should_close(window):
            glfw.poll_events()

            raw_depth, _ = cam.get_depth()
            if raw_depth is None:
                # Still draw something so the window isn't frozen
                fb_w, fb_h = glfw.get_framebuffer_size(window)
                glViewport(0, 0, fb_w, fb_h)
                glClearColor(0.1, 0.1, 0.1, 1.0)
                glClear(GL_COLOR_BUFFER_BIT)
                draw_text_shadow("Waiting for depth frames...", 10, 10,
                                 fb_w, fb_h, scale=2, color=(1.0, 1.0, 0.0))
                glfw.swap_buffers(window)
                time.sleep(0.01)
                continue

            now = time.monotonic()
            dt = now - last_time
            last_time = now
            if dt > 0:
                fps = fps * 0.9 + (1.0 / dt) * 0.1

            # ── Background capture accumulation ──
            if bg_capturing:
                bg_capture_frames.append(raw_depth.copy())
                if len(bg_capture_frames) >= bg_frames_to_avg:
                    bg_reference = np.mean(bg_capture_frames, axis=0).astype(np.float32)
                    bg_capturing = False
                    bg_capture_frames = []
                    valid_bg = np.count_nonzero(bg_reference > 0)
                    print(f"Background captured! ({valid_bg}/{bg_reference.size} valid pixels)")

            # ── Apply post-processing pipeline ──
            processed = raw_depth.copy()

            # Background subtraction
            if bg_reference is not None and bg_reference.shape == processed.shape:
                # Foreground = pixels significantly closer than background
                # (with invert=True, closer objects are brighter/higher value)
                if cam.invert:
                    # Inverted: foreground is HIGHER than bg reference
                    fg_mask = processed > (bg_reference + bg_tolerance)
                else:
                    # Normal: foreground is LOWER than bg reference
                    fg_mask = processed < (bg_reference - bg_tolerance)
                # Also require the pixel to have valid data
                fg_mask = fg_mask & (processed > 0)
                processed = np.where(fg_mask, processed, 0.0)

            # Erosion (remove noisy single-pixel edges)
            if erode_enabled:
                processed = erode_mask(processed, iterations=1)

            # Blur
            if blur_enabled:
                processed = box_blur_3x3(processed)

            # Binary threshold
            if threshold_mode:
                processed = np.where(processed > threshold_level, 1.0, 0.0).astype(np.float32)

            h, w = processed.shape
            fb_w, fb_h = glfw.get_framebuffer_size(window)

            # Upload processed depth to texture
            glBindTexture(GL_TEXTURE_2D, tex)
            contiguous = np.ascontiguousarray(processed, dtype=np.float32)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, w, h, 0,
                         GL_RED, GL_FLOAT, contiguous)
            glBindTexture(GL_TEXTURE_2D, 0)

            glViewport(0, 0, fb_w, fb_h)
            glClearColor(0.05, 0.05, 0.05, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)

            # Three panels: raw | processed | silhouette
            panel_w = fb_w // 3

            glUseProgram(prog)
            glActiveTexture(GL_TEXTURE0)
            glUniform1i(u_depth, 0)
            glBindVertexArray(vao)

            # Left: raw grayscale (upload raw depth temporarily)
            glBindTexture(GL_TEXTURE_2D, tex)
            raw_contiguous = np.ascontiguousarray(raw_depth, dtype=np.float32)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, w, h, 0,
                         GL_RED, GL_FLOAT, raw_contiguous)
            glViewport(0, 0, panel_w, fb_h)
            glUniform1f(u_mode, 0.0)
            glDrawArrays(GL_TRIANGLES, 0, 6)

            # Middle: processed colorized
            proc_contiguous = np.ascontiguousarray(processed, dtype=np.float32)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, w, h, 0,
                         GL_RED, GL_FLOAT, proc_contiguous)
            glViewport(panel_w, 0, panel_w, fb_h)
            glUniform1f(u_mode, 1.0)
            glDrawArrays(GL_TRIANGLES, 0, 6)

            # Right: silhouette view (what the main app would use)
            glViewport(panel_w * 2, 0, fb_w - panel_w * 2, fb_h)
            glUniform1f(u_mode, 2.0)
            glDrawArrays(GL_TRIANGLES, 0, 6)

            glBindVertexArray(0)
            glUseProgram(0)

            # ── Text overlay ──
            glViewport(0, 0, fb_w, fb_h)

            valid_raw = np.count_nonzero(raw_depth > 0)
            valid_proc = np.count_nonzero(processed > 0)
            total = raw_depth.size

            lines = [
                f"FPS: {fps:.1f}   Frame: {cam.frame_count}   Res: {w}x{h}",
                f"Range: {cam.depth_min_mm}-{cam.depth_max_mm}mm   Invert: {cam.invert}   Smooth: {cam.temporal_smoothing:.1f}",
                f"Raw valid: {valid_raw}/{total} ({100*valid_raw/total:.0f}%)   Processed: {valid_proc}/{total} ({100*valid_proc/total:.0f}%)",
                f"BG: {'SET' if bg_reference is not None else 'NONE'}   Tol: {bg_tolerance:.3f}   Thresh: {'ON' if threshold_mode else 'OFF'} ({threshold_level:.2f})",
                f"Blur: {'ON' if blur_enabled else 'OFF'}   Erode: {'ON' if erode_enabled else 'OFF'}",
            ]
            if bg_capturing:
                lines.append(f"*** CAPTURING BG: {len(bg_capture_frames)}/{bg_frames_to_avg} ***")

            y = 10
            for line in lines:
                draw_text_shadow(line, 10, y, fb_w, fb_h, scale=2, color=(0.0, 1.0, 0.0))
                y += 18

            # Panel labels
            draw_text_shadow("Raw", 10, fb_h - 20, fb_w, fb_h, scale=2, color=(1, 1, 1))
            draw_text_shadow("Processed", panel_w + 10, fb_h - 20, fb_w, fb_h, scale=2, color=(1, 1, 1))
            draw_text_shadow("Silhouette", panel_w * 2 + 10, fb_h - 20, fb_w, fb_h, scale=2, color=(1, 1, 1))

            # Help
            help_lines = [
                "B:BG capture  X:Clear BG  T:Threshold  G:Blur  E:Erode",
                "Up/Dn:Tolerance  L/R:ThreshLvl  +/-:MaxRange  [/]:MinRange",
                "I:Invert  S:Smooth  R:Reset  P:Stats  Q:Quit",
            ]
            y = fb_h - 8
            for line in reversed(help_lines):
                y -= 12
                draw_text_gl(line, 11, y + 1, fb_w, fb_h, scale=1, color=(0, 0, 0))
                draw_text_gl(line, 10, y, fb_w, fb_h, scale=1, color=(0.7, 0.7, 1.0))

            glfw.swap_buffers(window)

    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping depth camera...")
        cam.stop()
        glDeleteTextures(1, [tex])
        glDeleteBuffers(1, [vbo])
        glDeleteVertexArrays(1, [vao])
        glDeleteProgram(prog)
        glfw.terminate()
        print("Done.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Debug viewer for Orbbec depth camera")
    parser.add_argument('--no-invert', action='store_true',
                        help="Disable depth inversion (default: inverted so close=bright)")
    parser.add_argument('--min', type=int, default=500,
                        help="Minimum depth in mm (default: 500)")
    parser.add_argument('--max', type=int, default=4000,
                        help="Maximum depth in mm (default: 4000)")
    parser.add_argument('--smoothing', type=float, default=0.3,
                        help="Temporal smoothing factor 0-1 (default: 0.3)")
    args = parser.parse_args()
    run_debug_viewer(args)
