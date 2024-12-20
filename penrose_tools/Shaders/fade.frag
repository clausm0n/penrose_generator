// fade.frag
uniform sampler2D screen_texture;
uniform float fade_amount;

varying vec2 v_texcoord;

void main() {
    vec4 color = texture2D(screen_texture, v_texcoord);
    gl_FragColor = vec4(color.rgb, fade_amount > 0.0 ? 1.0 - fade_amount : 1.0);
}