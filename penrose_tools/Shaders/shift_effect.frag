// shift_effect.frag
precision mediump float;
uniform vec3 color1;
uniform vec3 color2;
uniform float time;
varying float v_tile_type;
varying vec2 v_position;

void main() {
    vec3 baseColor = v_tile_type > 0.5 ? color1 : color2;
    float timeFactor = sin(time + v_position.x * v_position.y) * 0.5 + 0.5;
    vec3 finalColor = baseColor * timeFactor;
    gl_FragColor = vec4(finalColor, 1.0);
}