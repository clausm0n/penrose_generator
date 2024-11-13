#version 120

// Varying variables received from vertex shader
varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_centroid;
varying vec2 v_tile_center;  // Added to match vertex shader

// Uniform variables
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    // Choose color based on tile type
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Set the final color with full opacity
    gl_FragColor = vec4(base_color, 1.0);
}