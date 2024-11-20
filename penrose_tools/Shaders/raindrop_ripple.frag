// raindrop_ripple.frag
#version 140

in vec2 v_position;
in float v_tile_type;
in vec2 v_tile_centroid;

out vec4 fragColor;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

const int MAX_RAINDROPS = 8;
const float PI = 3.14159265359;
const float RIPPLE_LIFETIME = 12.0; // Full lifetime of a ripple

float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
}

float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = smoothstep(0.0, 1.0, fract(st));
    
    float a = random(i);
    float b = random(i + vec2(1.0, 0.0));
    float c = random(i + vec2(0.0, 1.0));
    float d = random(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// Get a continuous position for a raindrop based on its lifecycle
vec2 getRipplePosition(int index, float timeInSeconds) {
    float rippleTime = timeInSeconds + float(index) * 1234.5678;
    float slowTime = rippleTime * 0.1; // Slow down the variation
    
    // Use different frequencies for x and y to avoid repetitive patterns
    float x = cos(slowTime * 0.7) * 0.8;
    float y = sin(slowTime * 0.5) * 0.8;
    
    // Add some noise for natural variation
    x += noise(vec2(slowTime * 0.3, 0.0)) * 0.2;
    y += noise(vec2(0.0, slowTime * 0.3)) * 0.2;
    
    return vec2(x, y);
}

float calculateRippleIntensity(vec2 center, vec2 position, float age, float size) {
    float distance = length(position - center);
    
    // Calculate ripple radius based on age
    float maxRadius = 0.8 * size;
    float radius = maxRadius * (1.0 - exp(-age * 1.5));
    
    // Calculate intensity with smooth falloff
    float fadeStart = RIPPLE_LIFETIME * 0.3;
    float fadeEnd = RIPPLE_LIFETIME * 0.9;
    float timeFactor = 1.0;
    
    if (age > fadeStart) {
        timeFactor = smoothstep(fadeEnd, fadeStart, age);
    }
    
    // Edge width varies with size and age
    float edgeWidth = 0.08 * size * (1.0 + age * 0.1);
    
    if (distance <= radius) {
        float rippleShape;
        if (abs(distance - radius) < edgeWidth) {
            // Smooth edge transition
            float edgeProgress = abs(distance - radius) / edgeWidth;
            rippleShape = smoothstep(1.0, 0.0, edgeProgress) * 0.7;
        } else {
            // Internal ripple pattern
            rippleShape = smoothstep(radius, radius * 0.7, distance) * 0.3;
        }
        
        // Combine for final intensity
        return rippleShape * timeFactor * smoothstep(0.0, 0.2, age);
    }
    
    return 0.0;
}