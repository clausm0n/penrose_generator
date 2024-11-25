// fade.vert
attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
}