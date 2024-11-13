// raindrop_ripple.vert
#version 140

in vec2 position;
in float tile_type;
out float v_tile_type;
out vec2 v_position;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_position = position;
}