// no_effect.vert
#version 140

// Input attributes
in vec2 position;
in float tile_type;
in vec2 tile_centroid;

// Output to fragment shader
out float v_tile_type;

void main() {
    v_tile_type = tile_type;
    gl_Position = vec4(position, 0.0, 1.0);
}