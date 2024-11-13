#version 120  // Using GLSL 120 for compatibility with OpenGL 2.1

// Varying variables received from vertex shader
varying float v_tile_type;
varying vec2 v_centroid;
varying vec2 v_position;

// Uniform variables
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    // Choose color based on tile type
    vec3 tile_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Set the final color with full opacity
    gl_FragColor = vec4(tile_color, 1.0);
}