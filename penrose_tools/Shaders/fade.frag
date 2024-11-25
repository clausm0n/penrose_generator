// fade.frag
uniform vec3 color1;
uniform vec3 color2;
uniform float fade_amount;
uniform float time;

varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_centroid;

void main() {
    // Use the same color calculation as the normal shader
    vec3 base_color = mix(color1, color2, v_tile_type);
    
    // Add a slight movement effect during fade
    float wave = sin(time + v_position.x * 5.0 + v_position.y * 5.0) * 0.5 + 0.5;
    base_color = mix(base_color, base_color * 0.8, wave * fade_amount);
    
    // Fade to transparent instead of black
    gl_FragColor = vec4(base_color, 1.0 - fade_amount);
}
