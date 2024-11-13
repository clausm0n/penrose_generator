// shift_effect.vert
#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;

// Varying variables
varying float v_tile_type;
varying vec2 v_position;

void main() {
    // Pass values to fragment shader
    v_tile_type = tile_type;
    v_position = position;
    
    // Set the position
    gl_Position = vec4(position, 0.0, 1.0);
}