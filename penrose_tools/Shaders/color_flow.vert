// color_wave.vert
#version 140

in vec2 position;
in float tile_type;
in vec2 tile_centroid;

out float v_tile_type;
out vec2 v_centroid;

void main() {
    v_tile_type = tile_type;
    v_centroid = tile_centroid;
    gl_Position = vec4(position, 0.0, 1.0);
}