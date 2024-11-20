// color_wave.vert
#version 140

// Inputs
in vec2 position;
in float tile_type;
in vec2 tile_centroid;

// Outputs to fragment shader
out float v_tile_type;
out vec2 v_position;

// Uniforms
uniform float time;

void main() {
    // Pass values to fragment shader
    v_tile_type = tile_type;
    
    // Scale the centroid position to match Python's coordinate space
    v_position = tile_centroid * 1000.0;  // Scale up normalized coordinates
    
    gl_Position = vec4(position, 0.0, 1.0);
}