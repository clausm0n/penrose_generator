// region_blend.vert
#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

// Varying variables
varying float v_tile_type;
varying vec2 v_centroid;
varying float v_blend_factor;
varying float v_pattern_type;

// Uniforms
uniform vec4 tile_patterns[4500];
uniform int num_tiles;

// Helper function to find both pattern type and blend factor
vec2 find_pattern_data(vec2 center_pos) {
    int left = 0;
    int right = num_tiles - 1;
    
    // Increased precision for better pattern matching
    float epsilon = 0.00001;
    
    while (left <= right) {
        int mid = (left + right) / 2;
        vec2 pattern_pos = tile_patterns[mid].xy;
        vec2 diff = abs(center_pos - pattern_pos);
        
        // Check if we found a match
        if (diff.x < epsilon && diff.y < epsilon) {
            return vec2(tile_patterns[mid].z, tile_patterns[mid].w);
        }
        
        // Binary search comparison
        if (pattern_pos.x < center_pos.x || 
            (abs(pattern_pos.x - center_pos.x) < epsilon && pattern_pos.y < center_pos.y)) {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    
    // Return default values if no match found
    return vec2(0.0, 0.5);
}

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_centroid = tile_centroid;
    v_tile_type = tile_type;
    
    // Get both pattern type and blend factor in one search
    vec2 pattern_data = find_pattern_data(tile_centroid);
    v_pattern_type = pattern_data.x;
    v_blend_factor = pattern_data.y;
}
