
// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_pattern_type;
varying float v_blend_factor;

vec3 blendColors(vec3 c1, vec3 c2, float factor) {
    return mix(c1, c2, factor);
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

void main() {
    vec3 finalColor;
    
    // Pattern type: 1.0 = star, 2.0 = starburst
    if (v_pattern_type > 0.5) {
        if (v_pattern_type < 1.5) {
            // Star pattern
            finalColor = invertColor(blendColors(color1, color2, 0.3));
        } else {
            // Starburst pattern
            finalColor = invertColor(blendColors(color1, color2, 0.7));
        }
    } else {
        // Normal tile - use neighbor-based blending
        finalColor = blendColors(color1, color2, v_blend_factor);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}