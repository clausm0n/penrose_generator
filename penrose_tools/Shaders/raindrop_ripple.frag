// raindrop_ripple.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_tile_centroid;

const int MAX_RIPPLES = 3;

// Pseudo-random function
float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
}

void main() {
    vec3 finalColor = color1;
    float timeInSeconds = time;
    
    // Create multiple ripple centers based on time
    for(int i = 0; i < MAX_RIPPLES; i++) {
        float rippleOffset = float(i) * 3.5; // 3.5 seconds between ripples
        float rippleTime = mod(timeInSeconds - rippleOffset, 15.0); // 15 second cycle
        
        if(rippleTime > 0.0) {
            // Create a ripple center based on time and index
            vec2 rippleCenter = vec2(
                sin(timeInSeconds * 0.5 + float(i)),
                cos(timeInSeconds * 0.3 + float(i))
            );
            
            float distance = length(v_tile_centroid - rippleCenter);
            float radius = 25.0 * (1.0 - exp(-rippleTime / 5.0));
            float rippleIntensity = exp(-rippleTime / 3.0);
            
            if(distance <= radius) {
                if(abs(distance - radius) < 0.05) {
                    // Ripple edge
                    float edgeIntensity = 1.0 - abs(distance - radius) / 0.05;
                    finalColor = mix(finalColor, color2, edgeIntensity * rippleIntensity);
                } else if(distance < 0.05) {
                    // Ripple center
                    finalColor = mix(finalColor, color2, rippleIntensity);
                } else {
                    // Inside ripple
                    float colorIntensity = (1.0 - distance / radius) * rippleIntensity * 0.5;
                    finalColor = mix(finalColor, color2, colorIntensity);
                }
            }
        }
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}