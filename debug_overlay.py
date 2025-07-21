#!/usr/bin/env python3
"""
Debug script for GUI overlay rendering issues.
This script will help identify what's wrong with the overlay rendering.
"""

import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_overlay():
    """Debug the GUI overlay rendering."""
    print("=== GUI Overlay Debug ===")
    print()
    
    # Test basic imports
    try:
        from penrose_tools.GUIOverlay import GUIOverlay
        print("✓ GUIOverlay import successful")
    except Exception as e:
        print(f"✗ GUIOverlay import failed: {e}")
        return False
    
    # Test overlay creation
    try:
        overlay = GUIOverlay()
        print("✓ GUIOverlay creation successful")
        print(f"  - Initialized: {overlay.initialized}")
        print(f"  - Visible: {overlay.visible}")
        print(f"  - Controls count: {len(overlay.controls)}")
    except Exception as e:
        print(f"✗ GUIOverlay creation failed: {e}")
        return False
    
    # Test visibility toggle
    try:
        overlay.toggle_visibility()
        print(f"✓ Visibility toggle successful - now visible: {overlay.visible}")
        overlay.toggle_visibility()
        print(f"✓ Visibility toggle successful - now visible: {overlay.visible}")
    except Exception as e:
        print(f"✗ Visibility toggle failed: {e}")
        return False
    
    # Test formatted controls
    try:
        # Mock config data and shader manager
        mock_config = {
            'scale': 25,
            'vertex_offset': 0.0001
        }
        
        class MockShaderManager:
            def __init__(self):
                self.shader_names = ['test_shader']
                self.current_shader_index = 0
        
        mock_shader_manager = MockShaderManager()
        
        formatted_controls = overlay.get_formatted_controls(mock_config, mock_shader_manager)
        print(f"✓ Formatted controls successful - {len(formatted_controls)} lines")
        print("  Sample lines:")
        for i, line in enumerate(formatted_controls[:5]):
            print(f"    {i+1}: {line}")
    except Exception as e:
        print(f"✗ Formatted controls failed: {e}")
        return False
    
    print()
    print("=== Debug Summary ===")
    print("✓ Basic overlay functionality works")
    print("✓ The issue is likely in OpenGL rendering, not Python logic")
    print()
    print("Possible rendering issues:")
    print("1. Shader compilation problems")
    print("2. Vertex data setup issues")
    print("3. Coordinate system problems")
    print("4. OpenGL state management")
    print()
    print("To test rendering:")
    print("1. Run the main application")
    print("2. Press F1 to toggle overlay")
    print("3. Check console output for shader compilation errors")
    print("4. Look for uniform location warnings")
    
    return True

if __name__ == "__main__":
    success = debug_overlay()
    if success:
        print("\n✓ Debug completed - basic functionality works")
    else:
        print("\n✗ Debug failed - basic functionality broken")
        sys.exit(1)
