// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_pattern_type;
varying float v_neighbor_ratio;

void main() {
    vec3 finalColor;
    
    if (v_pattern_type > 0.5) {
        // Pattern tiles are white
        finalColor = vec3(1.0);
    } else {
        // Non-pattern tiles - interpolate between colors based on neighbor ratio
        finalColor = mix(color1, color2, v_neighbor_ratio);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}