// shift_effect.frag
#version 120

// Varying variables
varying float v_tile_type;
varying vec2 v_centroid;

// Uniform variables
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    // Get base color based on tile type
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Calculate time factor exactly like the Python version
    float time_factor = sin(time / 1000.0 + v_centroid.x * v_centroid.y) * 0.5 + 0.5;
    
    // Apply the time-based color shift
    vec3 final_color = base_color * time_factor;
    
    // Clamp the color values between 0 and 1
    final_color = clamp(final_color, 0.0, 1.0);
    
    gl_FragColor = vec4(final_color, 1.0);
}