// region_blend.frag
#version 140

in float v_tile_type;
in vec2 v_centroid;
in float v_blend_factor;
in float v_pattern_type;
in float v_is_edge;

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
    // If this is an edge, render solid black.
    if (v_is_edge > 0.5) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    // Normal region_blend logic
    vec3 final_color;
    float alpha = 1.0;
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

        float dist_from_center = length(v_centroid);
        float edge_fade = smoothstep(0.0, 0.1, dist_from_center);
        alpha = edge_fade;
    }
    else {
        // Normal tile
        final_color = blend_colors(color1, color2, blend);
    }
    
    fragColor = vec4(final_color, alpha);
}
