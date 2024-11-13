#version 120  // Using GLSL 120 for compatibility with OpenGL 2.1

// Input attributes
attribute vec2 position;
attribute float tile_type;
attribute vec2 centroid;
attribute vec2 tile_center;

// Varying variables to pass to fragment shader
varying float v_tile_type;
varying vec2 v_centroid;
varying vec2 v_position;

void main() {
    // Pass values to fragment shader
    v_tile_type = tile_type;
    v_centroid = centroid;
    v_position = position;
    
    // Set the position
    gl_Position = vec4(position, 0.0, 1.0);
}