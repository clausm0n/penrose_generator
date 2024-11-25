// color_wave.frag 
#version 140

in float v_tile_type;
in vec2 v_centroid;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

out vec4 fragColor;

void main() {
    // Calculate angle for diagonal waves
    float angle = 0.785398; // 45 degrees in radians
    float rotatedX = v_centroid.x * cos(angle) - v_centroid.y * sin(angle);
    
    // Create diagonal bands with sharp transitions
    float wave = sin(rotatedX * 6.0 + time * 1.5);
    wave = smoothstep(-0.2, 0.2, wave);
    
    // Add subtle variation based on tile type
    wave += v_tile_type * 0.1;
    
    // Mix colors
    vec3 finalColor = mix(color1, color2, wave);
    fragColor = vec4(finalColor, 1.0);
}
