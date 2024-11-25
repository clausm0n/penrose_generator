// color_wave.frag 
#version 140

in float v_tile_type;
in vec2 v_centroid;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

out vec4 fragColor;

void main() {
    // Oscillate angle between 30 and 60 degrees
    float baseAngle = 0.123599; // 30 degrees
    float angleRange = 0.923599; // 30 degrees
    float angleSpeed = 0.04;
    float currentAngle = baseAngle + angleRange * sin(time * angleSpeed);
    
    // Rotate coordinates
    float rotatedX = v_centroid.x * cos(currentAngle) - v_centroid.y * sin(currentAngle);
    
    // Smoother wave pattern with dynamic speed
    float speedRange = 0.5;
    float baseSpeed = 0.1;
    float currentSpeed = baseSpeed + speedRange * cos(time * angleSpeed);
    float wave = sin(rotatedX * 4.0 + time * currentSpeed);
    
    // Softer transition between colors
    wave = (wave + 1.0) * 0.3;  // Normalize to 0-1
    wave = smoothstep(0.2, 0.8, wave);  // Wider blend range
    
    // Add subtle variation based on tile type
    wave = mix(wave, wave + v_tile_type * 0.1, 0.3);
    
    vec3 finalColor = mix(color1, color2, wave);
    fragColor = vec4(finalColor, 1.0);
}