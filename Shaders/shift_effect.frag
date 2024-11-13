// shift_effect.frag
#version 330 core

in float v_tile_type;
in vec2 v_centroid;
in vec2 v_tile_center;

uniform vec3 color1;
uniform vec3 color2;
uniform float time; // Time in milliseconds

out vec4 frag_color;

void main()
{
    vec3 base_color = mix(color2, color1, v_tile_type);
    float time_factor = sin(time / 1000.0 + v_centroid.x * v_centroid.y) * 0.5 + 0.5;
    vec3 new_color = base_color * time_factor;
    frag_color = vec4(new_color, 1.0);
}
