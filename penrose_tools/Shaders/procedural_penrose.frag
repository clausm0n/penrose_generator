// procedural_penrose.frag
// Infinite Penrose tiling using de Bruijn's pentagrid method
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
uniform int u_effect_mode;
uniform float u_gamma[5];

#define PI 3.14159265359
#define PN 5

vec2 grid[PN];
float shift[PN];

float random(vec2 st) {
    return fract(sin(dot(st, vec2(12.9898, 78.233))) * 43758.5453123);
}

float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    float a = random(i);
    float b = random(i + vec2(1.0, 0.0));
    float c = random(i + vec2(0.0, 1.0));
    float d = random(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

vec3 hsvToRgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z * mix(vec3(1.0), rgb, c.y);
}

void getRhombusVerts(int r, int s, float kr, float ks, out vec2 verts[4]) {
    vec2 pI = grid[r] * (ks - shift[s]) - grid[s] * (kr - shift[r]);
    float denom = grid[s - r].y;
    if (abs(denom) < 0.0001) denom = 0.0001;
    pI = vec2(-pI.y, pI.x) / denom;
    
    vec2 sum = grid[r] * kr + grid[s] * ks;
    for (int k = 0; k < PN; k++) {
        if (k != r && k != s) {
            sum += grid[k] * ceil(dot(pI, grid[k]) + shift[k]);
        }
    }
    
    verts[0] = sum;
    verts[1] = sum + grid[r];
    verts[2] = sum + grid[r] + grid[s];
    verts[3] = sum + grid[s];
}

bool pointInQuad(vec2 p, vec2 v0, vec2 v1, vec2 v2, vec2 v3) {
    vec2 e0 = v1 - v0, e1 = v2 - v1, e2 = v3 - v2, e3 = v0 - v3;
    vec2 w0 = p - v0, w1 = p - v1, w2 = p - v2, w3 = p - v3;
    float c0 = e0.x * w0.y - e0.y * w0.x;
    float c1 = e1.x * w1.y - e1.y * w1.x;
    float c2 = e2.x * w2.y - e2.y * w2.x;
    float c3 = e3.x * w3.y - e3.y * w3.x;
    return (c0 >= 0.0 && c1 >= 0.0 && c2 >= 0.0 && c3 >= 0.0) ||
           (c0 <= 0.0 && c1 <= 0.0 && c2 <= 0.0 && c3 <= 0.0);
}

float distToQuadEdge(vec2 p, vec2 v0, vec2 v1, vec2 v2, vec2 v3) {
    vec2 edges[4]; edges[0] = v1 - v0; edges[1] = v2 - v1; edges[2] = v3 - v2; edges[3] = v0 - v3;
    vec2 starts[4]; starts[0] = v0; starts[1] = v1; starts[2] = v2; starts[3] = v3;
    float minDist = 1e10;
    for (int i = 0; i < 4; i++) {
        vec2 e = edges[i]; vec2 w = p - starts[i];
        float len2 = dot(e, e);
        float t = clamp(dot(w, e) / len2, 0.0, 1.0);
        minDist = min(minDist, length(p - (starts[i] + t * e)));
    }
    return minDist;
}

// Region blend effect based on camera position and zoom
// Creates dynamic highlighting that responds to navigation
vec3 getRegionBlendColor(vec2 tileCenter, bool isFat, vec3 col1, vec3 col2) {
    // Distance from camera center (in world space)
    float distFromCamera = length(tileCenter - u_camera);

    // Zoom-adjusted radius - larger zoom = smaller visible area = tighter effect
    float zoomFactor = log(u_zoom + 1.0) + 1.0;
    float effectRadius = 3.0 / zoomFactor;

    // Create multiple concentric regions with logarithmic falloff
    float normalizedDist = distFromCamera / effectRadius;

    // Inner region: inverted blend (like stars/starbursts in original)
    float innerRegion = 1.0 - smoothstep(0.0, 0.3, normalizedDist);

    // Middle region: transition zone
    float middleRegion = smoothstep(0.2, 0.5, normalizedDist) * (1.0 - smoothstep(0.5, 0.8, normalizedDist));

    // Outer region: normal tile coloring
    float outerRegion = smoothstep(0.6, 1.0, normalizedDist);

    // Base blend factor - fat tiles lean toward color1, thin toward color2
    float baseBlend = isFat ? 0.7 : 0.3;

    // Add some variation based on tile position for visual interest
    float posVariation = sin(tileCenter.x * 5.0) * cos(tileCenter.y * 5.0) * 0.15;
    baseBlend = clamp(baseBlend + posVariation, 0.0, 1.0);

    // Calculate colors for each region
    vec3 innerColor = vec3(1.0) - mix(col1, col2, isFat ? 0.3 : 0.7); // Inverted
    vec3 middleColor = mix(col1, col2, 0.5); // Even blend
    vec3 outerColor = mix(col1, col2, baseBlend); // Neighbor-influenced blend

    // Combine regions
    vec3 finalColor = innerColor * innerRegion +
                      middleColor * middleRegion +
                      outerColor * outerRegion;

    // Ensure we have valid color when regions don't sum to 1
    float totalWeight = innerRegion + middleRegion + outerRegion;
    if (totalWeight < 0.01) {
        finalColor = outerColor;
    } else {
        finalColor /= max(totalWeight, 1.0);
    }

    return finalColor;
}

void main() {
    vec2 uv = v_uv - 0.5;
    uv.x *= u_resolution.x / u_resolution.y;
    
    float gSc = 3.0 / u_zoom;
    vec2 p = uv * gSc + u_camera;
    
    float pindex[PN];
    vec2 rb_p = vec2(0.0);
    
    for (int k = 0; k < PN; k++) {
        shift[k] = u_gamma[k];
        float theta = PI * 2.0 / float(PN) * float(k);
        grid[k] = vec2(cos(theta), sin(theta));
        pindex[k] = dot(p, grid[k]) + shift[k];
        rb_p += grid[k] * pindex[k];
    }
    
    int found_r = 0, found_s = 1;
    float found_kr = 0.0, found_ks = 0.0;
    vec2 found_verts[4];
    vec2 found_center = vec2(0.0);
    bool found = false;
    
    for (int r = 0; r < PN - 1; r++) {
        if (found) break;
        for (int s = r + 1; s < PN; s++) {
            if (found) break;
            for (int dr = -2; dr <= 2; dr++) {
                if (found) break;
                for (int ds = -2; ds <= 2; ds++) {
                    if (found) break;
                    float kr = floor(pindex[r]) + float(dr);
                    float ks = floor(pindex[s]) + float(ds);
                    vec2 verts[4];
                    getRhombusVerts(r, s, kr, ks, verts);
                    if (pointInQuad(rb_p, verts[0], verts[1], verts[2], verts[3])) {
                        found_r = r; found_s = s; found_kr = kr; found_ks = ks;
                        found_verts = verts;
                        found_center = (verts[0] + verts[1] + verts[2] + verts[3]) * 0.25;
                        found = true;
                    }
                }
            }
        }
    }
    
    if (!found) { fragColor = vec4(0.1, 0.1, 0.1, 1.0); return; }
    
    int diff = found_s - found_r;
    bool isFat = (diff == 1 || diff == PN - 1);
    float tileType = isFat ? 1.0 : 0.0;
    float edgeDist = distToQuadEdge(rb_p, found_verts[0], found_verts[1], found_verts[2], found_verts[3]);
    vec2 tileCentroid = found_center * 0.1;
    float tileId = random(vec2(found_kr + float(found_r) * 100.0, found_ks + float(found_s) * 100.0));
    
    vec3 baseColor = isFat ? u_color1 : u_color2;
    vec3 tileColor = baseColor;
    
    // ===== EFFECT MODES =====
    if (u_effect_mode == 0) {
        tileColor = baseColor;
    }
    else if (u_effect_mode == 1) {
        vec2 sc = tileCentroid * 1000.0;
        float timeFactor = sin(u_time + sc.x * sc.y) * 0.5 + 0.5;
        tileColor = baseColor * timeFactor;
    }
    else if (u_effect_mode == 2) {
        float ms = u_time * 1000.0;
        float tf = mod(ms, 1000000.0) / 1000000.0;
        float waveDir = 0.785398 + 1.570796 * sin(tf * PI);
        vec2 pos = tileCentroid * 1000.0;
        float posAngle = atan(pos.y, pos.x);
        float posMag = length(pos);
        float dirInfl = cos(posAngle - waveDir) * posMag;
        float phase = 0.0000002 * ms - dirInfl;
        float waveInt = (sin(phase) + 1.0) * 0.5;
        tileColor = mix(u_color1, u_color2, waveInt);
    }
    else if (u_effect_mode == 3) {
        float ca = 0.123599 + 0.923599 * sin(u_time * 0.02);
        float rx = tileCentroid.x * cos(ca) - tileCentroid.y * sin(ca);
        float cs = 0.1 + 0.3 * cos(u_time * 0.02);
        float w = sin(rx * 3.0 + u_time * cs);
        w = (w + 1.0) * 0.3;
        w = smoothstep(0.2, 0.8, w);
        w = mix(w, w + tileType * 0.1, 0.3);
        tileColor = mix(u_color1, u_color2, w);
    }
    else if (u_effect_mode == 4) {
        // Region blend: dynamic highlighting based on camera position and zoom
        tileColor = getRegionBlendColor(found_center, isFat, u_color1, u_color2);
    }
    else if (u_effect_mode == 5) {
        tileColor = u_color1;
        float bi = floor(u_time / 3.5);
        for (int i = 0; i < 4; i++) {
            float rst = (bi - float(i)) * 3.5;
            float age = u_time - rst;
            if (age >= 0.0 && age < 25.0) {
                vec2 rc = vec2(sin(rst * 1.23) * 0.6, cos(rst * 0.97) * 0.6);
                float dist = length(tileCentroid - rc);
                float radius = 1.8 * (1.0 - exp(-age / 5.0));
                if (dist <= radius + 0.15) {
                    float ri = exp(-age / 3.0);
                    if (abs(dist - radius) < 0.15) {
                        float ei = (1.0 - abs(dist - radius) / 0.15);
                        tileColor = mix(tileColor, u_color2, ei * ri * 0.7);
                    } else if (dist < 0.15) {
                        tileColor = mix(tileColor, u_color2, ri * 0.5);
                    } else {
                        float ci = (1.0 - dist / radius) * ri * 0.3;
                        tileColor = mix(tileColor, u_color2, ci);
                    }
                }
            }
        }
    }
    else if (u_effect_mode == 6) {
        tileColor = u_color1;
        for (int i = 0; i < 5; i++) {
            float to = float(i) * 2.0;
            float t = u_time + to;
            float pt = random(vec2(float(i), 0.0));
            float ks = 0.05 + random(vec2(float(i), 2.0)) * 0.03;
            vec2 kp;
            if (pt < 0.33) { kp = vec2(sin(t * 0.5), sin(t) * cos(t)); }
            else if (pt < 0.66) { float rd = 0.5 + 0.2 * sin(t * 0.3); kp = vec2(cos(t) * rd, sin(t * 0.7) * rd); }
            else { kp = vec2(sin(t * 0.3) + noise(vec2(t * 0.1, 0.0)) * 0.4, cos(t * 0.2) + noise(vec2(0.0, t * 0.1)) * 0.4); }
            float dk = length(tileCentroid - kp);
            if (dk < ks) { tileColor = mix(tileColor, u_color2, 1.0 - dk / ks); }
            float rt = mod(t, 10.0);
            if (rt < 2.0) {
                float rr = 0.3 * (1.0 - exp(-rt * 2.0));
                float rs = exp(-rt * 1.5) * 0.7;
                if (dk <= rr && abs(dk - rr) < 0.05) { tileColor = mix(tileColor, u_color2, (1.0 - abs(dk - rr) / 0.05) * rs); }
            }
        }
        tileColor = mix(tileColor, u_color2, noise(tileCentroid + u_time * 0.1) * 0.1);
    }
    else if (u_effect_mode == 7) {
        float h = tileId + u_time * 0.1;
        tileColor = hsvToRgb(vec3(h, isFat ? 0.9 : 0.6, 1.0));
    }
    else if (u_effect_mode == 8) {
        float dist = length(tileCentroid);
        float pulse = sin(dist * 8.0 - u_time * 3.0) * 0.5 + 0.5;
        tileColor = mix(baseColor * 0.3, baseColor, pulse);
    }
    else if (u_effect_mode == 9) {
        float sp = tileId * 6.28318 + u_time * 2.0;
        float sk = pow(max(0.0, sin(sp)), 8.0);
        tileColor = mix(baseColor * 0.5, baseColor * 1.5, sk);
    }
    
    // Sharp edge with minimal anti-aliasing to avoid dark asterisk at vertices
    float edgeWidth = 0.012 * u_edge_thickness;
    float aaWidth = 0.003;  // Very thin anti-aliasing band
    float edgeFactor = smoothstep(edgeWidth - aaWidth, edgeWidth, edgeDist);

    // Edge color (dark) vs tile color
    vec3 edgeColor = tileColor * 0.15;
    vec3 finalColor = mix(edgeColor, tileColor, edgeFactor);

    fragColor = vec4(finalColor, 1.0);
}