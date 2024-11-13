// shift_effect.frag
#version 140

uniform vec3 color1;
uniform vec3 color2;
uniform float time;
in float v_tile_type;
in vec2 v_position;
out vec4 fragColor;

void main() {
    vec3 baseColor = v_tile_type > 0.5 ? color1 : color2;
    float timeFactor = sin(time + v_position.x * v_position.y) * 0.5 + 0.5;
    vec3 finalColor = baseColor * timeFactor;
    fragColor = vec4(finalColor, 1.0);
}