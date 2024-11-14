// no_effect.vert
#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;  // Add this even though we don't use it

// Varying variables
varying float v_tile_type;

void main() {
    v_tile_type = tile_type;
    gl_Position = vec4(position, 0.0, 1.0);
}
