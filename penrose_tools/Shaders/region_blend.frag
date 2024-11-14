// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;  // Fixed: vec3 instead of vec2
uniform vec4 tile_patterns[1024];  // Increased size to handle larger tilings
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
    return abs(a.x - b.x) < EPSILON && abs(a.y - b.y) < EPSILON;
}

void main() {
    vec3 finalColor;
    float pattern_type = 0.0;
    float blend_factor = 0.5;
    
    // Binary search through pattern array for better performance
    int left = 0;
    int right = num_tiles - 1;
    bool found = false;
    
    while (left <= right) {
        int mid = (left + right) / 2;
        vec2 test_pos = tile_patterns[mid].xy;
        
        if (compareVec2(v_tile_centroid, test_pos)) {
            pattern_type = tile_patterns[mid].z;
            blend_factor = tile_patterns[mid].w;
            found = true;
            break;
        }
        
        // Compare based on x coordinate primarily, then y
        if (v_tile_centroid.x < test_pos.x || 
            (v_tile_centroid.x == test_pos.x && v_tile_centroid.y < test_pos.y)) {
            right = mid - 1;
        } else {
            left = mid + 1;
        }
    }
    
    // Apply pattern coloring
    if (pattern_type > 0.5 && pattern_type < 1.5) {
        // Star pattern
        finalColor = invertColor(blendColors(color1, color2, 0.3));
    }
    else if (pattern_type > 1.5) {
        // Starburst pattern
        finalColor = invertColor(blendColors(color1, color2, 0.7));
    }
    else {
        // Normal tile
        finalColor = blendColors(color1, color2, blend_factor);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}