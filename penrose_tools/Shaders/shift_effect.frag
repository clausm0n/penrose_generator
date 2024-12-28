// shift_effect.frag
#version 140

// Inputs from vertex shader
in float v_tile_type;
in vec2 v_tile_centroid;
in float v_is_edge;

// Output color
out vec4 fragColor;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    // If this is an edge, render solid black.
    if (v_is_edge > 0.5) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    // Otherwise, do your normal shift_effect logic
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;

    vec2 scaled_centroid = v_tile_centroid * 1000.0;
    float time_factor = sin(time + scaled_centroid.x * scaled_centroid.y) * 0.5 + 0.5;

    vec3 final_color = base_color * time_factor;
    fragColor = vec4(final_color, 1.0);
}