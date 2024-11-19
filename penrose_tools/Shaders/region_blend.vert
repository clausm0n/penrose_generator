// region_blend.vert
#version 120

attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_blend_factor;
varying float v_pattern_type;

uniform vec4 pattern_data[3000];  // x,y = centroid, z = pattern type, w = blend factor
uniform int num_patterns;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_tile_centroid = tile_centroid;
    
    // Initialize with the tile type as the blend factor
    v_pattern_type = 0.0;
    v_blend_factor = v_tile_type;
    
    // Look for pattern matches
    for (int i = 0; i < num_patterns; i++) {
        if (distance(pattern_data[i].xy, tile_centroid) < 0.001) {
            v_pattern_type = pattern_data[i].z;   // 1.0 = star, 2.0 = starburst
            v_blend_factor = pattern_data[i].w;   // Use the pattern-specific blend factor
            break;
        }
    }
}
