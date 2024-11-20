// no_effect.frag
#version 140

// Input from vertex shader
in float v_tile_type;

// Output color
out vec4 fragColor;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    fragColor = vec4(base_color, 1.0);
}