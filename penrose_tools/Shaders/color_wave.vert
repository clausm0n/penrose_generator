// color_wave.vert
#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

// Varying variables
varying float v_tile_type;
varying vec2 v_position;

uniform float time;  // Add time uniform to vertex shader

void main() {
    // Pass values to fragment shader
    v_tile_type = tile_type;
    
    // Scale the centroid position to match Python's coordinate space
    v_position = tile_centroid * 1000.0;  // Scale up normalized coordinates
    
    gl_Position = vec4(position, 0.0, 1.0);
}