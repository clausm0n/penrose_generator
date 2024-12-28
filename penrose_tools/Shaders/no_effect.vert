// no_effect.vert
#version 140

in vec2 position;
in float tile_type;
in vec2 tile_centroid;

out float v_tile_type;
out float v_is_edge;

uniform float vertex_offset;

void main() {
    vec2 direction = position - tile_centroid;
    vec2 snapped_pos = round(position * 1000.0) / 1000.0;
    vec2 offset = normalize(direction) * vertex_offset;
    gl_Position = vec4(snapped_pos + offset, 0.0, 1.0);

    v_tile_type = tile_type;

    // Mark edges by (tile_type=0, centroid=0).
    // This is how you identified "dummy" edges in your setup_buffers.
    v_is_edge = (tile_type == 0.0 && tile_centroid == vec2(0.0, 0.0)) ? 1.0 : 0.0;
}