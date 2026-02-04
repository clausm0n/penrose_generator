// raindrop_ripple.frag - Procedural Penrose with expanding ripple effects
#version 140

in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;
uniform vec2 u_camera;
uniform float u_zoom;
uniform float u_time;
uniform vec3 u_color1;
uniform vec3 u_color2;
uniform float u_edge_thickness;
uniform float u_gamma[5];

#include "pentagrid_common.glsl"

const int MAX_RIPPLES = 4;
const float RIPPLE_SPACING = 3.5;
const float RIPPLE_LIFETIME = 25.0;
const float MAX_RADIUS = 1.8;
const float EDGE_THICKNESS = 0.15;

float getRippleRadius(float age) {
    return MAX_RADIUS * (1.0 - exp(-age / 5.0));
}

void main() {
    vec2 uv = v_uv - 0.5;
    uv.x *= u_resolution.x / u_resolution.y;
    
    float gSc = 3.0 / u_zoom;
    vec2 p = uv * gSc + u_camera;
    
    float gamma[5];
    for (int i = 0; i < 5; i++) gamma[i] = u_gamma[i];
    
    TileData tile = findTile(p, gamma);
    
    if (!tile.found) {
        fragColor = vec4(0.1, 0.1, 0.1, 1.0);
        return;
    }
    
    // Raindrop ripple effect
    vec3 tileColor = u_color1;
    float baseIndex = floor(u_time / RIPPLE_SPACING);
    
    for (int i = 0; i < MAX_RIPPLES; i++) {
        float rippleStartTime = (baseIndex - float(i)) * RIPPLE_SPACING;
        float age = u_time - rippleStartTime;
        
        if (age >= 0.0 && age < RIPPLE_LIFETIME) {
            vec2 rippleCenter = vec2(
                sin(rippleStartTime * 1.23) * 0.6,
                cos(rippleStartTime * 0.97) * 0.6
            );
            
            float dist = length(tile.tileCentroid - rippleCenter);
            float radius = getRippleRadius(age);
            
            if (dist <= radius + EDGE_THICKNESS) {
                float rippleIntensity = exp(-age / 3.0);
                
                if (abs(dist - radius) < EDGE_THICKNESS) {
                    float edgeIntensity = (1.0 - abs(dist - radius) / EDGE_THICKNESS);
                    tileColor = mix(tileColor, u_color2, edgeIntensity * rippleIntensity * 0.7);
                } else if (dist < EDGE_THICKNESS) {
                    tileColor = mix(tileColor, u_color2, rippleIntensity * 0.5);
                } else {
                    float colorIntensity = (1.0 - dist / radius) * rippleIntensity * 0.3;
                    tileColor = mix(tileColor, u_color2, colorIntensity);
                }
            }
        }
    }
    
    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);
    
    fragColor = vec4(finalColor, 1.0);
}

