// shift_effect.frag
#version 120

// Varying variables
varying float v_tile_type;
varying vec2 v_position;

// Uniform variables
uniform vec3 color1;
uniform vec3 color2;
uniform float time;  // Add time uniform for animation

void main() {
    // Get base color based on tile type
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Calculate time factor similar to the Python version
    float time_factor = sin(time + v_position.x * v_position.y) * 0.5 + 0.5;
    
    // Apply the time-based color shift
    vec3 final_color = base_color * time_factor;
    
    gl_FragColor = vec4(final_color, 1.0);
}