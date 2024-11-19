// region_blend.vert
#version 120

attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

varying float v_tile_type;
varying vec2 v_centroid;
varying float v_blend_factor;
varying float v_pattern_type;

uniform vec4 tile_patterns[1000]; // x, y, pattern_type, blend_factor
uniform int num_tiles;

// Binary search to find pattern data for current tile
float find_pattern_type(vec2 centroid) {
    int left = 0;
    int right = num_tiles - 1;
    
    while (left <= right) {
        int mid = (left + right) / 2;
        vec2 pattern_pos = vec2(tile_patterns[mid].x, tile_patterns[mid].y);
        
        // Compare positions with small epsilon for float comparison
        float epsilon = 0.0001;
        vec2 diff = abs(centroid - pattern_pos);
        
        if (diff.x < epsilon && diff.y < epsilon) {
            return tile_patterns[mid].z; // Return pattern type
        }
        
        // Compare x coordinates first, then y if x is equal
        if (abs(pattern_pos.x - centroid.x) < epsilon) {
            if (pattern_pos.y < centroid.y) {
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        } else if (pattern_pos.x < centroid.x) {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    
    return 0.0; // No pattern found
}

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_centroid = tile_centroid;
    v_tile_type = tile_type;
    
    // Find pattern type for this tile
    v_pattern_type = find_pattern_type(tile_centroid);
    
    // Find blend factor from pattern data
    float pattern_blend = 0.0;
    for (int i = 0; i < num_tiles; i++) {
        if (abs(tile_patterns[i].x - tile_centroid.x) < 0.0001 && 
            abs(tile_patterns[i].y - tile_centroid.y) < 0.0001) {
            pattern_blend = tile_patterns[i].w;
            break;
        }
    }
    
    v_blend_factor = pattern_blend;
}