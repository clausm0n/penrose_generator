#version 140

in vec2 v_position;
in float v_tile_type;
in vec2 v_tile_centroid;

out vec4 fragColor;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

const int MAX_RIPPLES = 4;
const float RIPPLE_SPACING = 3.5;  // Seconds between ripples
const float RIPPLE_LIFETIME = 15.0; // Maximum ripple lifetime in seconds
const float MAX_RADIUS = 0.8;      // Maximum ripple radius in normalized space

float getRippleRadius(float age) {
    return MAX_RADIUS * (1.0 - exp(-age / 5.0));
}

void main() {
    float timeInSeconds = time;
    vec3 finalColor = color1;
    
    // Calculate active ripple indices based on time
    float baseIndex = floor(timeInSeconds / RIPPLE_SPACING);
    
    for(int i = 0; i < MAX_RIPPLES; i++) {
        float rippleStartTime = (baseIndex - float(i)) * RIPPLE_SPACING;
        float age = timeInSeconds - rippleStartTime;
        
        // Only process if ripple is within its lifetime
        if(age >= 0.0 && age < RIPPLE_LIFETIME) {
            // Calculate ripple center (fixed position for each ripple)
            vec2 rippleCenter = vec2(
                sin(rippleStartTime * 1.23) * 0.6,
                cos(rippleStartTime * 0.97) * 0.6
            );
            
            float distance = length(v_tile_centroid - rippleCenter);
            float radius = getRippleRadius(age);
            
            if(distance <= radius) {
                float rippleIntensity = exp(-age / 3.0); // Fade over time
                
                if(abs(distance - radius) < 0.05) {
                    // Ripple edge
                    float edgeIntensity = (1.0 - abs(distance - radius) / 0.05);
                    finalColor = mix(finalColor, color2, edgeIntensity * rippleIntensity * 0.7);
                }
                else if(distance < 0.05) {
                    // Ripple center
                    finalColor = mix(finalColor, color2, rippleIntensity * 0.5);
                }
                else {
                    // Inside ripple
                    float colorIntensity = (1.0 - distance / radius) * rippleIntensity * 0.3;
                    finalColor = mix(finalColor, color2, colorIntensity);
                }
            }
        }
    }
    
    fragColor = vec4(finalColor, 1.0);
}