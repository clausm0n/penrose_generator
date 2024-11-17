// region_blend.vert
#version 120

attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_pattern_type;
varying float v_blend_factor;

uniform vec4 tile_patterns[3000];  // xy = centroid, z = pattern type, w = blend factor
uniform int num_tiles;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_tile_centroid = tile_centroid;
    
    // Find pattern data for this tile
    v_pattern_type = 0.0;
    v_blend_factor = v_tile_type > 0.5 ? 1.0 : 0.0;
    
    for(int i = 0; i < num_tiles; i++) {
        vec2 pattern_pos = tile_patterns[i].xy;
        if(abs(pattern_pos.x - tile_centroid.x) < 0.001 && 
           abs(pattern_pos.y - tile_centroid.y) < 0.001) {
            v_pattern_type = tile_patterns[i].z;
            v_blend_factor = tile_patterns[i].w;
            break;
        }
    }
}
