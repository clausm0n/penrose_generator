// region_blend.frag
#version 120

varying vec2 v_centroid;
varying float v_tile_type;
varying float v_blend_factor;

uniform vec3 color1;
uniform vec3 color2;

vec3 invert_color(vec3 color) {
    return vec3(1.0) - color;
}

void main()
{
    vec3 blended_color;

    // Check if part of a complete pattern
    if (v_tile_type == 1.0) {
        // Invert color for complete star region
        blended_color = invert_color(mix(color1, color2, 0.3));
    } else if (v_tile_type == 2.0) {
        // Invert color for complete starburst region
        blended_color = invert_color(mix(color1, color2, 0.7));
    } else {
        // General blend based on neighboring counts
        blended_color = mix(color1, color2, v_blend_factor);
    }

    gl_FragColor = vec4(blended_color, 1.0);
}