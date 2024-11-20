// pixelation_slideshow.vert
#version 140

// Inputs
in vec2 position;
in float tile_type;
in vec2 tile_centroid;

// Outputs to fragment shader
out vec2 v_position;
out float v_tile_type;
out vec2 v_tile_centroid;

void main() {
    // Pass through vertex position unchanged
    gl_Position = vec4(position, 0.0, 1.0);
    
    // Pass through data to fragment shader
    v_position = position;
    v_tile_type = tile_type;
    // Flip Y coordinate to fix upside-down issue
    v_tile_centroid = vec2(tile_centroid.x, -tile_centroid.y);
}