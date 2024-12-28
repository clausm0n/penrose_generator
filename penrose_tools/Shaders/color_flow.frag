// color_wave.frag 
#version 140

in float v_tile_type;
in vec2 v_centroid;
in float v_is_edge;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

out vec4 fragColor;

void main() {
    // If this is an edge, render solid black.
    if (v_is_edge > 0.5) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    // Normal color_flow logic
    float baseAngle = 0.123599;
    float angleRange = 0.923599;
    float angleSpeed = 0.02;
    float currentAngle = baseAngle + angleRange * sin(time * angleSpeed);

    float rotatedX = v_centroid.x * cos(currentAngle) - v_centroid.y * sin(currentAngle);

    float speedRange = 0.3;
    float baseSpeed = 0.1;
    float currentSpeed = baseSpeed + speedRange * cos(time * angleSpeed);
    float wave = sin(rotatedX * 3.0 + time * currentSpeed);

    wave = (wave + 1.0) * 0.3;
    wave = smoothstep(0.2, 0.8, wave);
    wave = mix(wave, wave + v_tile_type * 0.1, 0.3);

    vec3 finalColor = mix(color1, color2, wave);
    fragColor = vec4(finalColor, 1.0);
}