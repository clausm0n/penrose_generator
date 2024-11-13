// color_wave.vert
attribute vec2 position;
attribute float tile_type;
varying float v_tile_type;
varying vec2 v_position;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_position = position;
}