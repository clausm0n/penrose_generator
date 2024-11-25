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
const float RIPPLE_LIFETIME = 4.0; // Reduced lifetime for more frequent updates

float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
}

float smoothNoise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    
    // Smoother interpolation
    f = f * f * (3.0 - 2.0 * f);
    
    float a = random(i);
    float b = random(i + vec2(1.0, 0.0));
    float c = random(i + vec2(0.0, 1.0));
    float d = random(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec2 getRipplePosition(int index, float timeInSeconds) {
    float rippleTime = timeInSeconds + float(index) * PI;
    float slowTime = rippleTime * 0.2;
    
    float x = cos(slowTime * 0.5) * 0.6;
    float y = sin(slowTime * 0.3) * 0.6;
    
    // Smoother noise variation
    x += smoothNoise(vec2(slowTime * 0.1, 0.0)) * 0.2;
    y += smoothNoise(vec2(0.0, slowTime * 0.1)) * 0.2;
    
    return vec2(x, y);
}

float calculateRippleIntensity(vec2 center, vec2 position, float age, float size) {
    float distance = length(position - center);
    float normalizedAge = age / RIPPLE_LIFETIME;
    
    // Smoother radius progression
    float radius = size * (1.0 - pow(1.0 - normalizedAge, 2.0));
    
    // Wider edge for smoother transition
    float edgeWidth = 0.15 * size;
    float edgeStart = radius - edgeWidth;
    float edgeEnd = radius + edgeWidth;
    
    // Smooth falloff at start and end of lifetime
    float fadeIn = smoothstep(0.0, 0.1, normalizedAge);
    float fadeOut = 1.0 - smoothstep(0.7, 1.0, normalizedAge);
    float timeFactor = fadeIn * fadeOut;
    
    if (distance < edgeEnd) {
        float edgeIntensity = 1.0 - abs(distance - radius) / edgeWidth;
        edgeIntensity = smoothstep(0.0, 1.0, edgeIntensity);
        
        return edgeIntensity * timeFactor * 0.5;
    }
    
    return 0.0;
}

void main() {
    vec3 finalColor = color1;
    float timeInSeconds = time;
    
    // Slower surface movement
    float surfaceNoise = smoothNoise(v_tile_centroid + vec2(timeInSeconds * 0.03)) * 0.03;
    finalColor = mix(finalColor, color2, surfaceNoise);
    
    float totalRippleEffect = 0.0;
    
    for(int i = 0; i < MAX_RAINDROPS; i++) {
        float cycleTime = mod(timeInSeconds + float(i) * (RIPPLE_LIFETIME / float(MAX_RAINDROPS)), RIPPLE_LIFETIME);
        
        if(cycleTime < RIPPLE_LIFETIME) {
            vec2 rippleCenter = getRipplePosition(i, timeInSeconds);
            float rippleSize = 0.4 + smoothNoise(vec2(float(i), timeInSeconds * 0.05)) * 0.2;
            
            float rippleEffect = calculateRippleIntensity(
                rippleCenter,
                v_tile_centroid,
                cycleTime,
                rippleSize
            );
            
            totalRippleEffect += rippleEffect;
        }
    }
    
    // Softer ripple effect
    totalRippleEffect = smoothstep(0.0, 0.8, totalRippleEffect);
    vec3 rippleColor = mix(color2, vec3(1.0), 0.15);
    finalColor = mix(finalColor, rippleColor, totalRippleEffect);
    
    fragColor = vec4(finalColor, 1.0);
}