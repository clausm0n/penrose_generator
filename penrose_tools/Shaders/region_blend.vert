// region_blend.vert
#version 120

attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying float v_pattern_type;
varying float v_blend_factor;

uniform sampler2D pattern_texture;
uniform vec4 viewport_bounds;  // minX, minY, maxX, maxY in GL space

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_tile_centroid = tile_centroid;
    
    // Convert centroid to texture coordinates using viewport bounds
    vec2 tex_coord = (v_tile_centroid - viewport_bounds.xy) / (viewport_bounds.zw - viewport_bounds.xy);
    
    // Sample pattern data from texture
    vec4 pattern_data = texture2D(pattern_texture, tex_coord);
    
    v_pattern_type = pattern_data.r;  // Pattern type stored in red channel
    v_blend_factor = pattern_data.g;  // Blend factor stored in green channel
}