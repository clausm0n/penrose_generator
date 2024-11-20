// color_flow.vert
#version 140

// Input attributes
in vec2 position;
in float tile_type;
in vec2 tile_centroid;

// Output to fragment shader
out float v_tile_type;
out vec2 v_centroid;

void main() {
    // Pass tile type and centroid to fragment shader
    v_tile_type = tile_type;
    v_centroid = tile_centroid;
    
    // Standard position transform
    gl_Position = vec4(position, 0.0, 1.0);
}