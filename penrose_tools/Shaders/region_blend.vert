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
    
    // Default blend factor from tile type (will be used for neighbor-based blending)
    v_pattern_type = 0.0;
    v_blend_factor = pattern_data[0].w;  // Default blend factor from first non-pattern tile
    
    // Look for pattern matches
    for (int i = 0; i < num_patterns; i++) {
        vec2 pattern_pos = pattern_data[i].xy;
        float dist = distance(pattern_pos, tile_centroid);
        if (dist < 0.001) {
            v_pattern_type = pattern_data[i].z;  // 1.0 = star, 2.0 = starburst
            v_blend_factor = pattern_data[i].w;  // Pattern-specific blend factor
            break;
        }
    }
}