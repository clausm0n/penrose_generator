// region_blend.frag
#version 120

uniform vec3 color1;  // Base color
uniform vec3 color2;  // Pattern color

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_blend_factor;
varying float v_pattern_type;

void main() {
    vec3 finalColor = color1;  // Default to base color
    
    if (v_pattern_type > 0.5) {
        // Pattern tiles (star or starburst)
        finalColor = color2;
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}