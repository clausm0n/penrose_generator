// region_blend.vert
#version 120

attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_pattern_type;
varying float v_neighbor_ratio;

uniform sampler2D pattern_texture;
uniform int texture_width;
uniform int texture_height;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_tile_centroid = tile_centroid;
    
    // Default to using tile type for non-pattern tiles
    v_pattern_type = 0.0;
    v_neighbor_ratio = v_tile_type;
    
    // Convert centroid to texture coordinates
    vec2 tex_coord = (v_tile_centroid + 1.0) * 0.5;
    vec4 pattern_data = texture2D(pattern_texture, tex_coord);
    
    if (pattern_data.a > 0.0) {  // Valid pattern data
        v_pattern_type = pattern_data.r;    // Pattern type in red channel
        v_neighbor_ratio = pattern_data.g;  // Neighbor ratio in green channel
    }
}