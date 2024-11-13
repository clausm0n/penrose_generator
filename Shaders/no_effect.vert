#version 120
attribute vec2 position;
attribute float tile_type; // 1.0 for kite, 0.0 for dart
varying float v_tile_type;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
}
