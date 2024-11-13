#version 120
attribute vec2 position;
attribute vec2 tile_center;
attribute float tile_type;
varying vec2 v_tile_center;
varying float v_tile_type;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_center = tile_center;
    v_tile_type = tile_type;
}
