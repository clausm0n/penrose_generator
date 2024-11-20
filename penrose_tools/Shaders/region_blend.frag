// region_blend.frag
#version 140

// Input from vertex shader
in float v_tile_type;
in vec2 v_centroid;
in float v_blend_factor;
in float v_pattern_type;

// Output
out vec4 fragColor;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;

vec3 blend_colors(vec3 col1, vec3 col2, float factor) {
    return mix(col1, col2, factor);
}

vec3 invert_color(vec3 color) {
    return vec3(1.0) - color;
}

void main() {
    vec3 final_color;
    
    if (v_pattern_type == 1.0) {
        // Star pattern - invert blend with 0.3 factor
        final_color = invert_color(blend_colors(color1, color2, 0.3));
    }
    else if (v_pattern_type == 2.0) {
        // Starburst pattern - invert blend with 0.7 factor
        final_color = invert_color(blend_colors(color1, color2, 0.7));
    }
    else {
        // Normal tile - blend based on neighbor ratio
        final_color = blend_colors(color1, color2, v_blend_factor);
    }
    
    fragColor = vec4(final_color, 1.0);
}
