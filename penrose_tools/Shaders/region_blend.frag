// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;
uniform vec4 tile_patterns[500];  // x,y = center, z = pattern type, w = blend factor
uniform int num_tiles;

varying float v_tile_type;
varying vec2 v_tile_centroid;

const float EPSILON = 0.01;

vec3 blendColors(vec3 c1, vec3 c2, float factor) {
    return mix(c1, c2, factor);
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

void main() {
    vec3 finalColor;
    bool found = false;
    float pattern_type = 0.0;
    float blend_factor = 0.5;
    
    // Find this tile's pattern info
    for (int i = 0; i < num_tiles && i < 500; i++) {
        vec4 pattern = tile_patterns[i];
        if (distance(v_tile_centroid, pattern.xy) < EPSILON) {
            pattern_type = pattern.z;
            blend_factor = pattern.w;
            found = true;
            break;
        }
    }
    
    // Apply pattern-specific coloring
    if (pattern_type > 0.5 && pattern_type < 1.5) {  // Star pattern
        // Use inverted colors for complete star tiles
        finalColor = invertColor(blendColors(color1, color2, 0.3));
    }
    else if (pattern_type > 1.5) {  // Starburst pattern
        // Use inverted colors for complete starburst tiles
        finalColor = invertColor(blendColors(color1, color2, 0.7));
    }
    else {  // Normal tile or fallback
        // Use neighbor-based blending
        finalColor = blendColors(color1, color2, blend_factor);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}