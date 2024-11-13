// shift_effect.vert
#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;
attribute vec2 centroid;  // Add centroid as a new attribute

// Varying variables
varying float v_tile_type;
varying vec2 v_centroid;  // Pass centroid to fragment shader

void main() {
    // Pass values to fragment shader
    v_tile_type = tile_type;
    v_centroid = centroid;
    
    // Set the position
    gl_Position = vec4(position, 0.0, 1.0);
}