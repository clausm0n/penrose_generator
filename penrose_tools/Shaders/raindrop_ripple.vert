// raindrop_ripple.frag
precision mediump float;
uniform vec3 color1;
uniform vec3 color2;
uniform float time;
uniform vec2 rippleCenters[3];  // Support up to 3 active ripples
uniform float rippleStates[3];   // Time and radius info for each ripple
uniform int activeRipples;

varying float v_tile_type;
varying vec2 v_position;

vec3 blendColors(vec3 color1, vec3 color2, float factor) {
    return mix(color1, color2, factor);
}

void main() {
    vec3 tileColor = color1;
    
    for(int i = 0; i < 3; i++) {  // Max ripples
        if(i >= activeRipples) break;
        
        vec2 rippleCenter = rippleCenters[i];
        float rippleAge = rippleStates[i * 2];
        float rippleRadius = rippleStates[i * 2 + 1];
        
        float distance = length(v_position - rippleCenter);
        
        if(distance <= rippleRadius) {
            float rippleIntensity = exp(-rippleAge / 3.0);
            
            if(abs(distance - rippleRadius) < 0.05) {  // Ripple edge
                float edgeIntensity = 1.0 - abs(distance - rippleRadius) / 0.05;
                tileColor = blendColors(tileColor, color2, edgeIntensity * rippleIntensity);
            } else if(distance < 0.05) {  // Ripple center
                tileColor = blendColors(tileColor, color2, rippleIntensity);
            } else {
                float colorIntensity = (1.0 - distance / rippleRadius) * rippleIntensity;
                tileColor = blendColors(tileColor, color2, colorIntensity * 0.5);
            }
        }
    }
    
    gl_FragColor = vec4(tileColor, 1.0);
}