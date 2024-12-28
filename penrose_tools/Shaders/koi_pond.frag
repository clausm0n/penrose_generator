// koi_pond.frag
#version 140

// Inputs from vertex shader
in vec2 v_position;
in float v_tile_type;
in vec2 v_tile_centroid;
in float v_is_edge;

// Output
out vec4 fragColor;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

// Constants
const int MAX_KOI = 5;
const int MAX_RIPPLES = 10;
const float PI = 3.14159265359;

// Koi parameters
struct Koi {
    vec2 position;
    float speed;
    float size;
    float rippleTimer;
    float pattern;
};

// Pseudo-random functions
float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
}

float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    
    float a = random(i);
    float b = random(i + vec2(1.0, 0.0));
    float c = random(i + vec2(0.0, 1.0));
    float d = random(i + vec2(1.0, 1.0));

    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a)* u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

// Calculate koi position based on different patterns
vec2 calculateKoiPosition(float timeOffset, float pattern) {
    float t = time + timeOffset;
    
    if (pattern < 0.33) {
        // Figure-8 pattern
        return vec2(sin(t * 0.5), sin(t) * cos(t));
    } else if (pattern < 0.66) {
        // Circular pattern with varying radius
        float radius = 0.5 + 0.2 * sin(t * 0.3);
        return vec2(cos(t) * radius, sin(t * 0.7) * radius);
    } else {
        // Meandering pattern using noise
        float noiseScale = 0.4;
        return vec2(
            sin(t * 0.3) + noise(vec2(t * 0.1, 0.0)) * noiseScale,
            cos(t * 0.2) + noise(vec2(0.0, t * 0.1)) * noiseScale
        );
    }
}

// Calculate ripple effect
float calculateRipple(vec2 center, vec2 position, float time, float intensity) {
    float distance = length(position - center);
    float radius = 0.3 * (1.0 - exp(-time * 2.0));
    float rippleStrength = exp(-time * 1.5) * intensity;
    
    if (distance <= radius) {
        if (abs(distance - radius) < 0.05) {
            // Ripple edge
            return (1.0 - abs(distance - radius) / 0.05) * rippleStrength;
        } else {
            // Inside ripple
            return (1.0 - distance / radius) * rippleStrength * 0.5;
        }
    }
    return 0.0;
}

void main() {
    // If this is an edge, render solid black.
    if (v_is_edge > 0.5) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    vec3 finalColor = color1;
    Koi koi[MAX_KOI];
    
    // Initialize koi with different patterns and timings
    for (int i = 0; i < MAX_KOI; i++) {
        float timeOffset = float(i) * 2.0;
        float pattern = random(vec2(float(i), 0.0));
        float speed = 0.8 + random(vec2(float(i), 1.0)) * 0.4;
        float size = 0.05 + random(vec2(float(i), 2.0)) * 0.03;
        
        koi[i].position = calculateKoiPosition(timeOffset, pattern);
        koi[i].speed = speed;
        koi[i].size = size;
        koi[i].pattern = pattern;
        koi[i].rippleTimer = mod(time + timeOffset, 10.0);
    }
    
    // Process each koi
    for (int i = 0; i < MAX_KOI; i++) {
        // Calculate koi influence
        float distToKoi = length(v_tile_centroid - koi[i].position);
        
        // Koi body
        if (distToKoi < koi[i].size) {
            float bodyIntensity = 1.0 - distToKoi / koi[i].size;
            finalColor = mix(finalColor, color2, bodyIntensity);
        }
        
        // Ripple effect
        if (koi[i].rippleTimer < 2.0) {
            float rippleEffect = calculateRipple(
                koi[i].position,
                v_tile_centroid,
                koi[i].rippleTimer,
                0.7
            );
            finalColor = mix(finalColor, color2, rippleEffect);
        }
    }
    
    // Add subtle water movement
    float waterMovement = noise(v_tile_centroid + time * 0.1) * 0.1;
    finalColor = mix(finalColor, color2, waterMovement);
    
    fragColor = vec4(finalColor, 1.0);
}