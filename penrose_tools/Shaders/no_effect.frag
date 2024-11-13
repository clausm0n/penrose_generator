// no_effect.frag
#version 120

varying float v_tile_type;
varying vec2 v_centroid;
varying vec2 v_tile_center;

uniform vec3 color1;
uniform vec3 color2;

void main()
{
    vec3 base_color = mix(color2, color1, v_tile_type);
    gl_FragColor = vec4(base_color, 1.0);
}
