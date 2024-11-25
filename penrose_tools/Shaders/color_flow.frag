// color_wave.frag 
#version 140

in float v_tile_type;
in vec2 v_centroid;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

out vec4 fragColor;

void main() {
    float baseAngle = 0.523599;
    float angleRange = 0.823599;
    float angleSpeed = 0.1;
    float currentAngle = baseAngle + angleRange * sin(time * angleSpeed);
    
    float rotatedX = v_centroid.x * cos(currentAngle) - v_centroid.y * sin(currentAngle);
    
    float speedRange = 1.0;
    float baseSpeed = 0.1;  // Fixed the double equals
    float currentSpeed = baseSpeed + speedRange * cos(time * angleSpeed);
    float wave = sin(rotatedX * 2.0 + time * currentSpeed);
    
    wave = (wave + 1.0) * 0.1;
    wave = smoothstep(0.2, 0.4, wave);
    
    wave = mix(wave, wave + v_tile_type * 0.1, 0.5);
    
    vec3 finalColor = mix(color1, color2, wave);
    fragColor = vec4(finalColor, 1.0);
}