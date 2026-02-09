// pulse.frag - Procedural Penrose with radial pulsing effect
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
    
    vec3 baseColor = tile.isFat ? u_color1 : u_color2;
    
    // Pulse effect: radial waves emanating from center
    float dist = length(tile.tileCentroid);
    float pulse = sin(dist * 8.0 - u_time * 3.0) * 0.5 + 0.5;
    vec3 tileColor = mix(baseColor * 0.3, baseColor, pulse);
    
    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);
    
    fragColor = vec4(finalColor, 1.0);
}

