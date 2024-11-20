// region_blend.frag
#version 140

in float v_tile_type;
in vec2 v_centroid;
in float v_blend_factor;
in float v_pattern_type;

out vec4 fragColor;

uniform vec3 color1;
uniform vec3 color2;

vec3 blend_colors(vec3 col1, vec3 col2, float factor) {
    return mix(col1, col2, clamp(factor, 0.0, 1.0));
}

vec3 invert_color(vec3 color) {
    return vec3(1.0) - color;
}

void main() {
    vec3 final_color;
    float blend = clamp(v_blend_factor, 0.0, 1.0);
    
    if (v_pattern_type == 1.0) {
        // Star pattern
        vec3 blended = blend_colors(color1, color2, 0.3);
        final_color = invert_color(blended);
    }
    else if (v_pattern_type == 2.0) {
        // Starburst pattern
        vec3 blended = blend_colors(color1, color2, 0.7);
        final_color = invert_color(blended);
    }
    else {
        // Normal tile
        final_color = blend_colors(color1, color2, blend);
    }
    
    fragColor = vec4(final_color, 1.0);
}
