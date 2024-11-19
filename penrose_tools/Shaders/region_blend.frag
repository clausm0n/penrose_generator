// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;

varying float v_tile_type;
varying float v_pattern_type;
varying float v_blend_factor;

void main() {
    vec3 blendedColor = mix(color1, color2, v_blend_factor);
    vec3 finalColor;

    if (v_pattern_type >= 1.0) {
        finalColor = vec3(1.0) - blendedColor;  // Inverted color
    } else {
        finalColor = blendedColor;
    }

    gl_FragColor = vec4(finalColor, 1.0);
}
