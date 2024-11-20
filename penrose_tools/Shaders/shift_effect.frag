// shift_effect.frag
#version 140

// Inputs from vertex shader
in float v_tile_type;
in vec2 v_tile_centroid;

// Output color
out vec4 fragColor;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    // Get base color based on tile type
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Calculate time factor using original coordinate space values
    vec2 scaled_centroid = v_tile_centroid * 1000.0;  // Scale up to get more pronounced effect
    float time_factor = sin(time + scaled_centroid.x * scaled_centroid.y) * 0.5 + 0.5;
    
    // Apply color shift
    vec3 final_color = base_color * time_factor;
    
    fragColor = vec4(final_color, 1.0);
}