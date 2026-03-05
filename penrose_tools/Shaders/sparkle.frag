// sparkle.frag - Procedural Penrose with color-shifting sparkle effect
// Each tile loops: color1 -> black -> color2 -> black -> color1 ...
// with random per-tile timing intervals
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

// Pseudo-random hash from a float seed (0-1 range output)
float hash(float n) {
    return fract(sin(n * 127.1 + 311.7) * 43758.5453);
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

    // Per-tile random values derived from tile ID
    float id = tile.tileId;
    float randSpeed = hash(id) * 0.1 + 0.2;         // cycle speed: 0.3 - 1.1
    float randOffset = hash(id + 73.0) * 6.28318;    // random phase offset

    // Time-based phase for this tile (0 to 1 repeating)
    // Full cycle: color1(0.0) -> black(0.25) -> color2(0.5) -> black(0.75) -> color1(1.0)
    float phase = fract(u_time * randSpeed * 0.3 + randOffset);

    // Determine which segment we're in and compute blend
    vec3 tileColor;
    if (phase < 0.25) {
        // color1 -> black
        float t = phase / 0.25;
        t = smoothstep(0.0, 1.0, t);
        tileColor = mix(u_color1, vec3(0.0), t);
    } else if (phase < 0.5) {
        // black -> color2
        float t = (phase - 0.25) / 0.25;
        t = smoothstep(0.0, 1.0, t);
        tileColor = mix(vec3(0.0), u_color2, t);
    } else if (phase < 0.75) {
        // color2 -> black
        float t = (phase - 0.5) / 0.25;
        t = smoothstep(0.0, 1.0, t);
        tileColor = mix(u_color2, vec3(0.0), t);
    } else {
        // black -> color1
        float t = (phase - 0.75) / 0.25;
        t = smoothstep(0.0, 1.0, t);
        tileColor = mix(vec3(0.0), u_color1, t);
    }

    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);

    fragColor = vec4(finalColor, 1.0);
}
