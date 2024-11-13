// no_effect.vert
#version 120
attribute vec2 position;
attribute float tile_type; // 1.0 for kite, 0.0 for dart
attribute vec2 centroid;
attribute vec2 tile_center;

varying float v_tile_type;
varying vec2 v_centroid;
varying vec2 v_tile_center;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_centroid = centroid;
    v_tile_center = tile_center;
}
