// raindrop_ripple.vert
attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_tile_centroid;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_position = position;
    v_tile_type = tile_type;
    v_tile_centroid = tile_centroid;
}