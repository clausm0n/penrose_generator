#version 120
uniform vec3 color1;
uniform vec3 color2;
uniform float time;
varying vec2 v_centroid;
varying float v_tile_type;

void main() {
    float time_factor = sin(time * 0.001 + v_centroid.x * v_centroid.y) * 0.5 + 0.5;
    vec3 base_color = mix(color2, color1, v_tile_type);
    vec3 color = base_color * time_factor;
    gl_FragColor = vec4(color, 1.0);
}
