#version 120
uniform vec3 color1;
uniform vec3 color2;
varying float v_tile_type;

void main() {
    vec3 color = mix(color2, color1, v_tile_type);
    gl_FragColor = vec4(color, 1.0);
}
