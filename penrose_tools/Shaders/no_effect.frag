// no_effect.frag
#version 120

// Varying variables
varying float v_tile_type;

// Uniform variables
uniform vec3 color1;
uniform vec3 color2;

void main() {
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    gl_FragColor = vec4(base_color, 1.0);
}