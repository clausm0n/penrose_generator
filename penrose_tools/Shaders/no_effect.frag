// no_effect.frag
#version 140

in float v_tile_type;
in float v_is_edge;

out vec4 fragColor;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;
uniform vec3 edge_color;
uniform float time;

void main() {
    vec3 final_color;
    float alpha = 1.0;

    // For edges, pick a lower alpha (e.g. 0.2 or 0.3).
    if (v_is_edge > 0.5) {
        final_color = edge_color;
        alpha = 0.3;  // 30% opacity for edges
    }
    else {
        final_color = (v_tile_type > 0.5) ? color1 : color2;
    }

    fragColor = vec4(final_color, alpha);
}