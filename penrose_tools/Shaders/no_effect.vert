#version 120

// Input attributes
attribute vec2 position;      // location 0
attribute float tile_type;    // location 1
attribute vec2 centroid;      // location 2
attribute vec2 tile_center;   // location 3

// Varying variables to pass to fragment shader
varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_centroid;
varying vec2 v_tile_center;  // Added this to pass tile_center to fragment shader

void main() {
    // Pass values to fragment shader
    v_position = position;
    v_tile_type = tile_type;
    v_centroid = centroid;
    v_tile_center = tile_center;  // Pass the tile center
    
    // Set the position
    gl_Position = vec4(position, 0.0, 1.0);
}