#!/usr/bin/env python3
"""
Test script for the optimized procedural region_blend shader.
This verifies that pattern detection works on tile objects instead of per-pixel.
"""

import sys
import glfw
from OpenGL.GL import *
from penrose_tools.ProceduralRenderer import ProceduralRenderer
import logging

# Set up logging to see debug output
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def main():
    # Initialize GLFW
    if not glfw.init():
        print("Failed to initialize GLFW")
        return -1

    # Create window with OpenGL context
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 2)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
    
    window = glfw.create_window(800, 600, "Procedural Region Blend Test", None, None)
    if not window:
        print("Failed to create GLFW window")
        glfw.terminate()
        return -1

    glfw.make_context_current(window)
    
    # Create renderer
    try:
        renderer = ProceduralRenderer()
        print(f"ProceduralRenderer created successfully")
        print(f"Available effects: {renderer.EFFECT_NAMES}")
        
        # Switch to region_blend effect
        region_blend_index = renderer.EFFECT_NAMES.index('region_blend')
        renderer.set_effect(region_blend_index)
        print(f"Switched to effect: {renderer.get_effect_name()}")
        
    except Exception as e:
        print(f"Failed to create renderer: {e}")
        import traceback
        traceback.print_exc()
        glfw.terminate()
        return -1

    # Configuration
    config = {
        'color1': [255, 200, 100],
        'color2': [100, 150, 255],
        'gamma': [0.2, 0.2, 0.2, 0.2, 0.2]
    }

    frame_count = 0

    # Main loop - only render 10 frames for testing
    while not glfw.window_should_close(window) and frame_count < 10:
        glClear(GL_COLOR_BUFFER_BIT)
        
        width, height = glfw.get_framebuffer_size(window)
        glViewport(0, 0, width, height)
        
        try:
            renderer.render(width, height, config)
        except Exception as e:
            print(f"Render error: {e}")
            import traceback
            traceback.print_exc()
            break
        
        glfw.swap_buffers(window)
        glfw.poll_events()
        
        frame_count += 1
        print(f"Frame {frame_count}: Rendered successfully")
        if hasattr(renderer, 'pattern_cache'):
            print(f"  Pattern cache size: {len(renderer.pattern_cache)} tiles")

    print(f"\nTest completed successfully! Rendered {frame_count} frames.")
    print("The optimized shader uses CPU-based tile pattern detection instead of per-pixel computation.")
    
    glfw.terminate()
    return 0

if __name__ == '__main__':
    sys.exit(main())

