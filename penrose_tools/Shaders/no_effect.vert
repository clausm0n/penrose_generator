// no_effect.vert
#version 140

in vec2 position;
in float tile_type;
out float v_tile_type;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
}