// region_blend.vert
#version 120

attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_pattern_type;
varying float v_blend_factor;

uniform vec4 pattern_data[3000];
uniform int num_patterns;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_tile_centroid = tile_centroid;
    
    // Initialize with normal tile values
    v_pattern_type = 0.0;
    v_blend_factor = tile_type > 0.5 ? 1.0 : 0.0;  // Default kite/dart blending
    
    // Look for pattern matches
    for(int i = 0; i < num_patterns; i++) {
        if(distance(pattern_data[i].xy, tile_centroid) < 0.001) {
            v_pattern_type = pattern_data[i].z;
            v_blend_factor = pattern_data[i].w;
            break;
        }
    }
}