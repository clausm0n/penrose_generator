// region_blend.frag
#version 120

uniform vec3 color1;  // Kite color
uniform vec3 color2;  // Dart color

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
    
    if (v_pattern_type > 0.5) {
        // Handle special patterns
        vec3 baseBlend = blendColors(color1, color2, v_blend_factor);
        
        if (v_pattern_type < 1.5) {
            // Star pattern (type 1.0)
            finalColor = invertColor(baseBlend);
        } else {
            // Starburst pattern (type 2.0)
            finalColor = invertColor(baseBlend);
        }
    } else {
        // Regular tile blending based on neighbors
        finalColor = blendColors(color1, color2, v_blend_factor);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}