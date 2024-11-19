// region_blend.vert
#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_center;  // renamed from tile_centroid

// Varying variables
varying float v_tile_type;
varying vec2 v_center;      // renamed from v_centroid
varying float v_blend_factor;
varying float v_pattern_type;

// Uniforms
uniform vec4 tile_patterns[1000];
uniform int num_tiles;

float find_pattern_type(vec2 center_pos) {    // renamed parameter from centroid
    int left = 0;
    int right = num_tiles - 1;
    
    while (left <= right) {
        int mid = (left + right) / 2;
        vec2 pattern_pos = tile_patterns[mid].xy;
        
        float epsilon = 0.0001;
        vec2 diff = abs(center_pos - pattern_pos);
        
        if (diff.x < epsilon && diff.y < epsilon) {
            return tile_patterns[mid].z;
        }
        
        if (pattern_pos.x < center_pos.x || 
            (abs(pattern_pos.x - center_pos.x) < epsilon && pattern_pos.y < center_pos.y)) {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    
    return 0.0;
}

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_center = tile_center;
    v_tile_type = tile_type;
    v_pattern_type = find_pattern_type(tile_center);
    
    float pattern_blend = 0.0;
    for (int i = 0; i < num_tiles; i++) {
        if (abs(tile_patterns[i].x - tile_center.x) < 0.0001 && 
            abs(tile_patterns[i].y - tile_center.y) < 0.0001) {
            pattern_blend = tile_patterns[i].w;
            break;
        }
    }
    
    v_blend_factor = pattern_blend;
}