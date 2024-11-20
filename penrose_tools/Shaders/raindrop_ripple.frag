// raindrop_ripple.frag
#version 140

in vec2 v_position;
in float v_tile_type;
in vec2 v_tile_centroid;

out vec4 fragColor;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

const int MAX_RAINDROPS = 8;  // Reduced for clearer visuals
const float PI = 3.14159265359;

// Improved random function for smoother variation
float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
}

// Smoother noise function
float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = smoothstep(0.0, 1.0, fract(st));
    
    float a = random(i);
    float b = random(i + vec2(1.0, 0.0));
    float c = random(i + vec2(0.0, 1.0));
    float d = random(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec4 getRaindropProperties(int index, float timeInSeconds) {
    // Slower variation in drop patterns
    float slowTime = timeInSeconds * 0.2;
    float dropSeed = random(vec2(float(index), floor(slowTime)));
    
    // More spread out timing
    float dropOffset = dropSeed * 10.0;  // Increased spread
    
    // More controlled position distribution
    float posX = -0.8 + 1.6 * random(vec2(float(index), dropSeed));
    float posY = -0.8 + 1.6 * random(vec2(dropSeed, float(index)));
    
    // More consistent drop sizes
    float size = 0.2 + 0.15 * random(vec2(dropSeed, posY));
    
    return vec4(posX, posY, size, dropOffset);
}

float calculateRipple(vec2 center, vec2 position, float rippleTime, float dropSize) {
    float distance = length(position - center);
    
    // Slower ripple expansion
    float baseRadius = 0.3 * dropSize;
    float maxRadius = baseRadius * 6.0;
    float expansionRate = 1.0;
    float radius = maxRadius * (1.0 - exp(-rippleTime * expansionRate));
    
    // Longer-lasting ripples with smoother falloff
    float fadeStart = 2.0;
    float fadeLength = 3.0;
    float timeFactor = clamp(1.0 - (rippleTime - fadeStart) / fadeLength, 0.0, 1.0);
    float baseIntensity = smoothstep(0.0, 0.2, rippleTime) * timeFactor;
    
    // Wider, smoother ripple edges
    float edgeWidth = 0.08 * dropSize;
    
    if (distance <= radius) {
        float rippleShape;
        if (abs(distance - radius) < edgeWidth) {
            // Smoother edge transition
            float edgeProgress = abs(distance - radius) / edgeWidth;
            rippleShape = smoothstep(1.0, 0.0, edgeProgress);
        } else {
            // Smoother internal ripple
            rippleShape = smoothstep(radius, radius * 0.7, distance);
        }
        
        // Combine all factors for final intensity
        return rippleShape * baseIntensity * dropSize;
    }
    
    return 0.0;
}

void main() {
    vec3 finalColor = color1;
    float timeInSeconds = time;
    
    // Very subtle background water movement
    float surfaceNoise = noise(v_tile_centroid * 2.0 + vec2(timeInSeconds * 0.05)) * 0.02;
    finalColor = mix(finalColor, color2, surfaceNoise);
    
    // Accumulate ripple effects
    float totalRippleEffect = 0.0;
    
    for(int i = 0; i < MAX_RAINDROPS; i++) {
        vec4 dropProps = getRaindropProperties(i, timeInSeconds);
        vec2 dropCenter = vec2(dropProps.x, dropProps.y);
        float dropSize = dropProps.z;
        float dropOffset = dropProps.w;
        
        // Longer cycle length for each ripple
        float cycleLength = 8.0 + random(vec2(dropProps.x, dropProps.y)) * 4.0;
        float rippleTime = mod(timeInSeconds - dropOffset, cycleLength);
        
        if(rippleTime > 0.0) {
            // Calculate main ripple
            float mainRipple = calculateRipple(dropCenter, v_tile_centroid, rippleTime, dropSize);
            
            // Add subtle secondary ripple with delay
            float secondaryRipple = 0.0;
            if(rippleTime > 0.5) {
                secondaryRipple = calculateRipple(dropCenter, v_tile_centroid, rippleTime - 0.5, dropSize * 0.7) * 0.3;
            }
            
            totalRippleEffect += mainRipple + secondaryRipple;
        }
    }
    
    // Clamp and smooth the total effect
    totalRippleEffect = smoothstep(0.0, 1.0, totalRippleEffect);
    
    // Apply ripple effect to final color
    vec3 rippleColor = mix(color2, vec3(1.0), 0.1);  // Subtle highlight
    finalColor = mix(finalColor, rippleColor, totalRippleEffect);
    
    fragColor = vec4(finalColor, 1.0);
}