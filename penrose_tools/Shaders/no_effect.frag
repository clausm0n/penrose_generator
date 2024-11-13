// no_effect.frag
precision mediump float;
uniform vec3 color1;
uniform vec3 color2;
varying float v_tile_type;

void main() {
    vec3 color = v_tile_type > 0.5 ? color1 : color2;
    gl_FragColor = vec4(color, 1.0);
}