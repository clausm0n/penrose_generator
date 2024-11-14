// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;
uniform vec4 tile_patterns[500];  // x,y = center, z = pattern type, w = blend factor
uniform int num_tiles;

varying float v_tile_type;
varying vec2 v_tile_centroid;

const float EPSILON = 0.005;

vec3 blendColors(vec3 c1, vec3 c2, float factor) {
    return mix(c1, c2, factor);
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

bool compareVec2(vec2 a, vec2 b) {
    // More precise position matching
    return abs(a.x - b.x) < EPSILON && abs(a.y - b.y) < EPSILON;
}

void main() {
    vec3 finalColor;
    float pattern_type = 0.0;
    float blend_factor = 0.5;
    bool found = false;
    
    // Find this tile's exact pattern info
    for (int i = 0; i < num_tiles && i < 500; i++) {
        if (compareVec2(v_tile_centroid, tile_patterns[i].xy)) {
            pattern_type = tile_patterns[i].z;
            blend_factor = tile_patterns[i].w;
            found = true;
            break;
        }
    }
    
    // Exactly match the original Python effect's logic
    if (pattern_type > 0.5 && pattern_type < 1.5) {
        // Star pattern (5 kites) - invert with 0.3 blend
        finalColor = invertColor(blendColors(color1, color2, 0.3));
    }
    else if (pattern_type > 1.5) {
        // Starburst pattern (10 darts) - invert with 0.7 blend
        finalColor = invertColor(blendColors(color1, color2, 0.7));
    }
    else {
        // Normal tile - use neighbor-based blend
        finalColor = blendColors(color1, color2, blend_factor);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}