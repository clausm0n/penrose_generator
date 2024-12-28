// color_flow.vert
#version 140

in vec2 position;
in float tile_type;
in vec2 tile_centroid;

out float v_tile_type;
out vec2 v_centroid;
out float v_is_edge;

uniform float vertex_offset;

void main() {
    vec2 direction = position - tile_centroid;
    vec2 offset = normalize(direction) * vertex_offset;
    gl_Position = vec4(position + offset, 0.0, 1.0);

    v_tile_type = tile_type;
    v_centroid = tile_centroid;
    
    // Mark edges
    v_is_edge = (tile_type == 0.0 && tile_centroid == vec2(0.0, 0.0)) ? 1.0 : 0.0;
}