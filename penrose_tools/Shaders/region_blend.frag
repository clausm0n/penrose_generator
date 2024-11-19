// region_blend.frag
#version 120

uniform vec3 color1;  // Base color
uniform vec3 color2;  // Pattern color

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_blend_factor;
varying float v_pattern_type;

vec3 blendColors(vec3 c1, vec3 c2, float factor) {
    return mix(c1, c2, clamp(factor, 0.0, 1.0));
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

void main() {
    vec3 finalColor;
    
    // Get base blended color
    vec3 baseBlend = blendColors(color1, color2, v_blend_factor);
    
    if (v_pattern_type > 0.5) {
        if (v_pattern_type < 1.5) {
            // Star pattern
            finalColor = invertColor(blendColors(color1, color2, 0.3));
        } else {
            // Starburst pattern
            finalColor = invertColor(blendColors(color1, color2, 0.7));
        }
    } else {
        // Regular tile - use neighbor-based blending
        finalColor = baseBlend;
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}
