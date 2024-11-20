// raindrop_ripple.frag
#version 140

// Input from vertex shader
in vec2 v_position;
in float v_tile_type;
in vec2 v_tile_centroid;

// Output
out vec4 fragColor;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

// Constants
const int MAX_RAINDROPS = 15;  // Increased number of simultaneous drops
const float PI = 3.14159265359;

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

// Get raindrop properties based on index and time
vec4 getRaindropProperties(int index, float timeInSeconds) {
    // Use noise to create natural-feeling raindrop timing
    float dropSeed = random(vec2(float(index), floor(timeInSeconds / 10.0)));
    float dropOffset = dropSeed * 5.0;  // Spread out drop timing
    
    // Calculate drop position using noise for natural distribution
    float posX = -1.0 + 2.0 * random(vec2(float(index), dropSeed));
    float posY = -1.0 + 2.0 * random(vec2(dropSeed, float(index)));
    
    // Vary drop sizes
    float size = 0.15 + 0.1 * random(vec2(dropSeed, posY));
    
    return vec4(posX, posY, size, dropOffset);
}

// Calculate raindrop ripple effect
float calculateRipple(vec2 center, vec2 position, float rippleTime, float dropSize) {
    float distance = length(position - center);
    
    // Expand ripple radius over time with natural easing
    float baseRadius = 0.2 * dropSize;
    float maxRadius = baseRadius * 8.0;
    float radius = maxRadius * (1.0 - exp(-rippleTime * 2.0));
    
    // Calculate ripple intensity with natural falloff
    float baseIntensity = exp(-rippleTime * 1.5);
    float rippleIntensity = baseIntensity * dropSize;
    
    // Edge width varies with drop size
    float edgeWidth = 0.03 * dropSize;
    
    if (distance <= radius) {
        if (abs(distance - radius) < edgeWidth) {
            // Ripple edge - sharper for bigger drops
            float edgeIntensity = 1.0 - abs(distance - radius) / edgeWidth;
            return edgeIntensity * rippleIntensity * 1.5;  // Emphasize edges
        } else if (distance < dropSize * 0.1) {
            // Impact point - stronger for bigger drops
            return rippleIntensity * (1.0 + dropSize);
        } else {
            // Ripple body - more pronounced for bigger drops
            float bodyIntensity = (1.0 - distance / radius) * rippleIntensity;
            return bodyIntensity * (0.3 + dropSize * 0.7);
        }
    }
    return 0.0;
}

void main() {
    vec3 finalColor = color1;
    float timeInSeconds = time;
    float surfaceNoise = noise(v_tile_centroid + vec2(timeInSeconds * 0.1)) * 0.05;
    
    // Add subtle water surface movement
    finalColor = mix(finalColor, color2, surfaceNoise);
    
    // Process each raindrop
    for(int i = 0; i < MAX_RAINDROPS; i++) {
        vec4 dropProps = getRaindropProperties(i, timeInSeconds);
        vec2 dropCenter = vec2(dropProps.x, dropProps.y);
        float dropSize = dropProps.z;
        float dropOffset = dropProps.w;
        
        // Calculate drop timing with natural randomization
        float cycleLength = 4.0 + random(vec2(dropProps.x, dropProps.y)) * 2.0;
        float rippleTime = mod(timeInSeconds - dropOffset, cycleLength);
        
        if(rippleTime > 0.0) {
            float rippleEffect = calculateRipple(dropCenter, v_tile_centroid, rippleTime, dropSize);
            
            // Add secondary ripples for larger drops
            if(dropSize > 0.2 && rippleTime > 0.2) {
                float secondaryTime = rippleTime - 0.2;
                rippleEffect += calculateRipple(dropCenter, v_tile_centroid, secondaryTime, dropSize * 0.6) * 0.3;
            }
            
            // Mix colors with intensity variation
            vec3 rippleColor = mix(color2, vec3(1.0), 0.2);  // Slight highlight for ripples
            finalColor = mix(finalColor, rippleColor, rippleEffect);
        }
    }
    
    fragColor = vec4(finalColor, 1.0);
}