#version 120

// Input attributes (must match the bound locations)
attribute vec2 position;      // location 0
attribute float tile_type;    // location 1
attribute vec2 centroid;      // location 2
attribute vec2 tile_center;   // location 3

// Varying variables to pass to fragment shader (must match fragment shader)
varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_centroid;

void main() {
    // Pass values to fragment shader
    v_position = position;
    v_tile_type = tile_type;
    v_centroid = centroid;
    
    // Set the position
    gl_Position = vec4(position, 0.0, 1.0);
}