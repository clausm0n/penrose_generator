// fade.frag
uniform vec3 color1;
uniform vec3 color2;
uniform float fade_amount;

void main() {
    vec3 base_color = mix(color1, color2, float(gl_FragCoord.x < gl_FragCoord.y));
    gl_FragColor = vec4(base_color * (1.0 - fade_amount), 1.0);
}