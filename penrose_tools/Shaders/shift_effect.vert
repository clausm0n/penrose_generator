// shift_effect.vert
#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

// Varying variables
varying float v_tile_type;
varying vec2 v_tile_centroid;

void main() {
    // Pass values to fragment shader without modification
    v_tile_type = tile_type;
    v_tile_centroid = tile_centroid;
    
    // Set the position
    gl_Position = vec4(position, 0.0, 1.0);
}
