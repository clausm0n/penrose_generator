// black.vert
#version 140

// Input attributes
in vec2 position;
in float tile_type;
in vec2 tile_centroid;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
}
