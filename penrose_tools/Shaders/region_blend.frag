// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_pattern_type;
varying float v_neighbor_ratio;

vec3 getStarColor() {
    // Unique color for star pattern (white)
    return vec3(1.0, 1.0, 1.0);
}

vec3 getStarburstColor() {
    // Unique color for starburst pattern (bright yellow)
    return vec3(1.0, 1.0, 0.0);
}

void main() {
    vec3 finalColor;
    
    if (v_pattern_type > 1.9) {
        // Starburst pattern (type 2.0)
        finalColor = getStarburstColor();
    }
    else if (v_pattern_type > 0.9) {
        // Star pattern (type 1.0)
        finalColor = getStarColor();
    }
    else {
        // Regular tile - interpolate between colors based on neighbor ratio
        finalColor = mix(color1, color2, v_neighbor_ratio);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}