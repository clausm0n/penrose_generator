#version 140

in vec2 v_position;
in float v_tile_type;
in vec2 v_tile_centroid;
in float v_is_edge;

out vec4 fragColor;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

const int MAX_RIPPLES = 4;
const float RIPPLE_SPACING = 3.5;
const float RIPPLE_LIFETIME = 25.0;
const float MAX_RADIUS = 1.8;
const float EDGE_THICKNESS = 0.15;

float getRippleRadius(float age) {
    return MAX_RADIUS * (1.0 - exp(-age / 5.0));
}

void main() {
    // If this is an edge, render solid black.
    if (v_is_edge > 0.5) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    // The original ripple effect logic
    float timeInSeconds = time;
    vec3 finalColor = color1;
    float baseIndex = floor(timeInSeconds / RIPPLE_SPACING);

    for(int i = 0; i < MAX_RIPPLES; i++) {
        float rippleStartTime = (baseIndex - float(i)) * RIPPLE_SPACING;
        float age = timeInSeconds - rippleStartTime;
        
        if(age >= 0.0 && age < RIPPLE_LIFETIME) {
            vec2 rippleCenter = vec2(
                sin(rippleStartTime * 1.23) * 0.6,
                cos(rippleStartTime * 0.97) * 0.6
            );
            
            float distance = length(v_tile_centroid - rippleCenter);
            float radius = getRippleRadius(age);
            
            if(distance <= radius + EDGE_THICKNESS) {
                float rippleIntensity = exp(-age / 3.0);
                
                if(abs(distance - radius) < EDGE_THICKNESS) {
                    float edgeIntensity = (1.0 - abs(distance - radius) / EDGE_THICKNESS);
                    finalColor = mix(finalColor, color2, edgeIntensity * rippleIntensity * 0.7);
                }
                else if(distance < EDGE_THICKNESS) {
                    finalColor = mix(finalColor, color2, rippleIntensity * 0.5);
                }
                else {
                    float colorIntensity = (1.0 - distance / radius) * rippleIntensity * 0.3;
                    finalColor = mix(finalColor, color2, colorIntensity);
                }
            }
        }
    }
    
    fragColor = vec4(finalColor, 1.0);
}