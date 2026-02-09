// koi_pond.frag - Procedural Penrose with swimming koi fish effect
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

const int MAX_KOI = 5;

vec2 calculateKoiPosition(float timeOffset, float pattern) {
    float t = u_time + timeOffset;
    
    if (pattern < 0.33) {
        // Figure-8 pattern
        return vec2(sin(t * 0.5), sin(t) * cos(t));
    } else if (pattern < 0.66) {
        // Circular pattern with varying radius
        float radius = 0.5 + 0.2 * sin(t * 0.3);
        return vec2(cos(t) * radius, sin(t * 0.7) * radius);
    } else {
        // Meandering pattern using noise
        return vec2(
            sin(t * 0.3) + noise(vec2(t * 0.1, 0.0)) * 0.4,
            cos(t * 0.2) + noise(vec2(0.0, t * 0.1)) * 0.4
        );
    }
}

float calculateRipple(vec2 center, vec2 position, float time, float intensity) {
    float dist = length(position - center);
    float radius = 0.3 * (1.0 - exp(-time * 2.0));
    float rippleStrength = exp(-time * 1.5) * intensity;
    
    if (dist <= radius) {
        if (abs(dist - radius) < 0.05) {
            return (1.0 - abs(dist - radius) / 0.05) * rippleStrength;
        } else {
            return (1.0 - dist / radius) * rippleStrength * 0.5;
        }
    }
    return 0.0;
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
    
    vec3 tileColor = u_color1;
    
    // Process each koi
    for (int i = 0; i < MAX_KOI; i++) {
        float timeOffset = float(i) * 2.0;
        float pattern = random(vec2(float(i), 0.0));
        float koiSize = 0.05 + random(vec2(float(i), 2.0)) * 0.03;
        
        vec2 koiPos = calculateKoiPosition(timeOffset, pattern);
        float distToKoi = length(tile.tileCentroid - koiPos);
        
        // Koi body
        if (distToKoi < koiSize) {
            float bodyIntensity = 1.0 - distToKoi / koiSize;
            tileColor = mix(tileColor, u_color2, bodyIntensity);
        }
        
        // Ripple effect
        float rippleTimer = mod(u_time + timeOffset, 10.0);
        if (rippleTimer < 2.0) {
            float rippleEffect = calculateRipple(koiPos, tile.tileCentroid, rippleTimer, 0.7);
            tileColor = mix(tileColor, u_color2, rippleEffect);
        }
    }
    
    // Subtle water movement
    float waterMovement = noise(tile.tileCentroid + u_time * 0.1) * 0.1;
    tileColor = mix(tileColor, u_color2, waterMovement);
    
    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);
    
    fragColor = vec4(finalColor, 1.0);
}

