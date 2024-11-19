// region_blend.vert
#version 120

attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

varying float v_tile_type;
varying vec2 v_centroid;
varying float v_blend_factor;

uniform mat4 projection;
uniform mat4 model;

void main()
{
    gl_Position = projection * model * vec4(position, 0.0, 1.0);
    v_tile_type = tile_type;
    v_centroid = tile_centroid;

    // Calculate blend factor based on tile type (default to 0.5 if no neighbors)
    if (tile_type == 0.0) {
        v_blend_factor = 0.5;  // No neighbors case
    } else {
        v_blend_factor = tile_type;  // Tile type carries blend factor in this case
    }
} 
