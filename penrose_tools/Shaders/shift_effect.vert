#version 120
attribute vec2 position;
attribute vec2 centroid;
attribute float tile_type;
varying vec2 v_centroid;
varying float v_tile_type;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_centroid = centroid;
    v_tile_type = tile_type;
}
