// no_effect.frag
#version 330 core

in float v_tile_type;
in vec2 v_centroid;
in vec2 v_tile_center;

uniform vec3 color1;
uniform vec3 color2;

out vec4 frag_color;

void main()
{
    vec3 base_color = mix(color2, color1, v_tile_type);
    frag_color = vec4(base_color, 1.0);
}
