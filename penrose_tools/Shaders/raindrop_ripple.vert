// raindrop_ripple.vert
#version 140

// Inputs
in vec2 position;
in float tile_type;
in vec2 tile_centroid;

// Outputs
out vec2 v_position;
out float v_tile_type;
out vec2 v_tile_centroid;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_position = position;
    v_tile_type = tile_type;
    v_tile_centroid = tile_centroid;
}