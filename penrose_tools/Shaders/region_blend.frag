// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;
uniform vec4 tile_patterns[500];  // x,y = center, z = pattern type, w = blend factor
uniform int num_tiles;

varying float v_tile_type;
varying vec2 v_tile_centroid;

const float EPSILON = 0.005;  // Reduced epsilon for more precise matching

vec3 blendColors(vec3 c1, vec3 c2, float factor) {
    return mix(c1, c2, factor);
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

bool compareVec2(vec2 a, vec2 b) {
    return abs(a.x - b.x) < EPSILON && abs(a.y - b.y) < EPSILON;
}

void main() {
    vec3 finalColor;
    bool found = false;
    float pattern_type = 0.0;
    float blend_factor = 0.5;
    
    // Find this tile's pattern info with precise matching
    for (int i = 0; i < num_tiles && i < 500; i++) {
        vec4 pattern = tile_patterns[i];
        if (compareVec2(v_tile_centroid, pattern.xy)) {
            pattern_type = pattern.z;
            blend_factor = pattern.w;
            found = true;
            break;
        }
    }
    
    // Apply pattern-specific coloring
    if (pattern_type > 0.5 && pattern_type < 1.5) {  // Star pattern
        // All tiles in a star pattern get inverted colors
        finalColor = invertColor(blendColors(color1, color2, 0.3));
    }
    else if (pattern_type > 1.5) {  // Starburst pattern
        // All tiles in a starburst pattern get inverted colors
        finalColor = invertColor(blendColors(color1, color2, 0.7));
    }
    else {  // Normal tile or fallback
        // Use neighbor-based blending
        finalColor = blendColors(color1, color2, blend_factor);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}