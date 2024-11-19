// region_blend.vert
#version 120

attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_pattern_type;
varying float v_neighbor_ratio;

uniform vec4 pattern_data[3000];  // x,y = centroid, z = pattern type, w = neighbor ratio
uniform int num_patterns;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_tile_centroid = tile_centroid;
    
    // Default to no pattern
    v_pattern_type = 0.0;
    v_neighbor_ratio = 0.5;  // Default neighbor ratio
    
    // Check for pattern or get neighbor ratio
    for (int i = 0; i < num_patterns; i++) {
        if (distance(pattern_data[i].xy, tile_centroid) < 0.001) {
            v_pattern_type = pattern_data[i].z;   // 1.0 = star, 2.0 = starburst
            v_neighbor_ratio = pattern_data[i].w; // neighbor ratio for non-pattern tiles
            break;
        }
    }
}