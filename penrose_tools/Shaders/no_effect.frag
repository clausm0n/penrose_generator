// no_effect.frag
#version 140

uniform vec3 color1;
uniform vec3 color2;
in float v_tile_type;
out vec4 fragColor;

void main() {
    vec3 color = v_tile_type > 0.5 ? color1 : color2;
    fragColor = vec4(color, 1.0);
}