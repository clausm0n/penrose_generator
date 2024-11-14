// color_wave.vert
#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

// Varying variables
varying float v_tile_type;
varying vec2 v_position;  // We'll pass the relative position to calculate wave effect

void main() {
    // Pass values to fragment shader
    v_tile_type = tile_type;
    v_position = tile_centroid;  // This is already in normalized coordinates
    
    // Set the position
    gl_Position = vec4(position, 0.0, 1.0);
}
