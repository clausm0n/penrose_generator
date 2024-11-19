// region_blend.frag
#version 120

uniform vec3 color1;  // Background/base color (blue in the image)
uniform vec3 color2;  // Pattern color (white in the image)

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_blend_factor;
varying float v_pattern_type;

void main() {
    vec3 finalColor;
    
    if (v_pattern_type > 0.5) {
        // Special patterns (stars and starbursts) - use color2 (white)
        finalColor = color2;
    } else {
        // Regular tiles - use color1 (blue)
        finalColor = color1;
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}