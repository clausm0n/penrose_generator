// pixelation_slideshow.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_tile_centroid;

// Generate a pseudo-random pattern based on position
vec3 pattern1(vec2 pos, float t) {
    float s = sin(t * 0.5);
    float c = cos(t * 0.3);
    return vec3(
        sin(pos.x * 10.0 * s + t) * 0.5 + 0.5,
        sin(pos.y * 10.0 * c + t) * 0.5 + 0.5,
        sin((pos.x + pos.y) * 5.0 + t) * 0.5 + 0.5
    );
}

// Generate a different pattern
vec3 pattern2(vec2 pos, float t) {
    float s = sin(t * 0.4);
    float c = cos(t * 0.6);
    return vec3(
        sin(pos.y * 8.0 * s) * 0.5 + 0.5,
        sin((pos.x + pos.y) * 8.0 * c) * 0.5 + 0.5,
        sin(pos.x * 8.0 + t) * 0.5 + 0.5
    );
}

void main() {
    float cycleTime = 5.0; // Duration of each pattern in seconds
    float totalTime = time;
    float cycle = mod(totalTime, cycleTime * 2.0);
    float transition = mod(cycle, cycleTime) / cycleTime;
    
    // Create two different patterns
    vec3 currentPattern = pattern1(v_tile_centroid, totalTime);
    vec3 nextPattern = pattern2(v_tile_centroid, totalTime);
    
    // Smooth transition between patterns
    float progress = smoothstep(0.0, 1.0, transition);
    vec3 finalPattern = mix(currentPattern, nextPattern, progress);
    
    // Mix with base colors
    vec3 baseColor = mix(color1, color2, v_tile_type);
    vec3 finalColor = mix(baseColor, finalPattern, 0.7);
    
    gl_FragColor = vec4(finalColor, 1.0);
}