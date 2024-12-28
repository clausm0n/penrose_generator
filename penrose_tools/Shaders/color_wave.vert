// color_wave.vert
#version 140

// Inputs
in vec2 position;
in float tile_type;
in vec2 tile_centroid;

// Outputs to fragment shader
out float v_tile_type;
out vec2 v_position;
out float v_is_edge;

// Uniforms
uniform float time;
uniform float vertex_offset;

void main() {
    vec2 direction = position - tile_centroid;
    vec2 offset = normalize(direction) * vertex_offset;
    gl_Position = vec4(position + offset, 0.0, 1.0);

    v_tile_type = tile_type;
    v_position = tile_centroid * 1000.0;

    // Mark edges
    v_is_edge = (tile_type == 0.0 && tile_centroid == vec2(0.0, 0.0)) ? 1.0 : 0.0;
}