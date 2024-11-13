#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;

// Varying variables
varying float v_tile_type;

void main() {
    // Pass values to fragment shader
    v_tile_type = tile_type;
    
    // Set the position
    gl_Position = vec4(position, 0.0, 1.0);
}