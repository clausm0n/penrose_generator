// region_blend.frag
#version 120

// Varying variables from vertex shader
varying float v_tile_type;
varying vec2 v_centroid;    // Name now matches vertex shader
varying float v_blend_factor;
varying float v_pattern_type;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;

vec3 invert_color(vec3 color) {
    return vec3(1.0) - color;
}

void main() {
    vec3 blended_color;
    
    if (v_pattern_type == 1.0) {
        // Complete star region
        blended_color = invert_color(mix(color1, color2, 0.3));
    } else if (v_pattern_type == 2.0) {
        // Complete starburst region
        blended_color = invert_color(mix(color1, color2, 0.7));
    } else {
        // Normal tile blending based on neighbor ratio
        blended_color = mix(color1, color2, v_blend_factor);
    }
    
    gl_FragColor = vec4(blended_color, 1.0);
}