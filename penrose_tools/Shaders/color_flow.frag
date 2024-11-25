// color_wave.frag 
#version 140

in float v_tile_type;
in vec2 v_centroid;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

out vec4 fragColor;

void main() {
    // Multiple overlapping waves
    float wave1 = sin(v_centroid.x * 4.0 + time * 2.0) * 0.5;
    float wave2 = sin(v_centroid.y * 4.0 + time * 1.5) * 0.5;
    float wave3 = sin((v_centroid.x + v_centroid.y) * 3.0 + time) * 0.5;
    
    // Combine waves with different weights
    float combinedWave = wave1 * 0.4 + wave2 * 0.4 + wave3 * 0.2;
    
    // Add tile-based variation
    float tileOffset = v_tile_type * 0.2;
    combinedWave += tileOffset;
    
    // Sharpen the transition between colors
    float sharpness = 4.0;
    float finalWave = pow(0.5 * (combinedWave + 1.0), sharpness);
    
    // Interpolate between colors
    vec3 finalColor = mix(color1, color2, finalWave);
    
    fragColor = vec4(finalColor, 1.0);
}