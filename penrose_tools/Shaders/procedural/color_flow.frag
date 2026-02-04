// color_flow.frag - Procedural Penrose with flowing color bands
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
    
    // Color flow effect: rotating bands of color
    float ca = 0.123599 + 0.923599 * sin(u_time * 0.02);
    float rx = tile.tileCentroid.x * cos(ca) - tile.tileCentroid.y * sin(ca);
    float cs = 0.1 + 0.3 * cos(u_time * 0.02);
    float w = sin(rx * 3.0 + u_time * cs);
    w = (w + 1.0) * 0.3;
    w = smoothstep(0.2, 0.8, w);
    float tileType = tile.isFat ? 1.0 : 0.0;
    w = mix(w, w + tileType * 0.1, 0.3);
    
    vec3 tileColor = mix(u_color1, u_color2, w);
    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);
    
    fragColor = vec4(finalColor, 1.0);
}

