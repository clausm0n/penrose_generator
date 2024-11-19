// region_blend.vert
#version 120

attribute vec2 position;
attribute float tile_type;
attribute float pattern_type;
attribute float blend_factor;

varying float v_tile_type;
varying float v_pattern_type;
varying float v_blend_factor;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_pattern_type = pattern_type;
    v_blend_factor = blend_factor;
}
