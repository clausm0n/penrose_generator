// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;

varying float v_tile_type;
varying vec2 v_tile_centroid;  // Added missing varying
varying float v_pattern_type;
varying float v_blend_factor;

void main() {
    vec3 baseBlend = mix(color1, color2, v_blend_factor);
    vec3 finalColor;
    
    if (v_pattern_type > 0.5 && v_pattern_type < 1.5) {
        // Star pattern
        finalColor = vec3(1.0) - mix(color1, color2, 0.3);
    } else if (v_pattern_type > 1.5) {
        // Starburst pattern
        finalColor = vec3(1.0) - mix(color1, color2, 0.7);
    } else {
        finalColor = baseBlend;
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}