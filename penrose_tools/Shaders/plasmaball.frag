// plasmaball.frag - Plasma ball simulation on Penrose tiles
// Lightning arcs toward depth-detected shapes; idle mode arcs randomly.
// When depth is detected, arcs reach toward the depth centroid region.
// When no motion is detected, arcs cycle randomly across the sphere.
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

// Depth camera uniforms
uniform sampler2D u_depth_texture;
uniform float u_depth_enabled;
uniform float u_depth_coverage;
uniform vec2 u_depth_centroid;
uniform float u_depth_motion;

#include "pentagrid_common.glsl"

// ---------------------------------------------------------------
// Lightning / plasma helpers
// ---------------------------------------------------------------

// Fractal brownian motion for organic noise
float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    vec2 shift = vec2(100.0);
    mat2 rot = mat2(cos(0.5), sin(0.5), -sin(0.5), cos(0.5));
    for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p = rot * p * 2.0 + shift;
        a *= 0.5;
    }
    return v;
}

// Distance from point p to a lightning bolt between a and b
// Returns a glow intensity (higher = closer to bolt)
float lightningBolt(vec2 p, vec2 a, vec2 b, float time, float seed) {
    vec2 ab = b - a;
    float len = length(ab);
    if (len < 0.001) return 0.0;
    vec2 dir = ab / len;
    vec2 perp = vec2(-dir.y, dir.x);

    // Project p onto line a->b
    vec2 ap = p - a;
    float t = dot(ap, dir) / len;

    // Only glow along the bolt length
    if (t < -0.05 || t > 1.05) return 0.0;

    // Displacement: fractal noise makes the bolt jagged
    float noiseScale = 3.0 + seed * 2.0;
    float displacement = fbm(vec2(t * noiseScale + time * 4.0 + seed * 17.0,
                                   seed * 31.0 + time * 1.5)) - 0.5;
    // Scale displacement by bolt length and taper at endpoints
    float taper = smoothstep(0.0, 0.15, t) * smoothstep(1.0, 0.85, t);
    displacement *= len * 0.15 * taper;

    // Distance from the displaced bolt path
    float dist = abs(dot(ap, perp) - displacement);

    // Glow falloff
    float boltWidth = len * 0.008;
    float glow = exp(-dist * dist / (boltWidth * boltWidth));

    // Flickering intensity
    float flicker = 0.7 + 0.3 * sin(time * 20.0 + seed * 50.0);

    return glow * taper * flicker;
}

// Generate a random point on the sphere edge for idle arcs
vec2 randomSpherePoint(float seed, float time) {
    float angle = seed * 6.28318 + time * 0.3;
    return vec2(cos(angle), sin(angle));
}

void main() {
    // --- Standard pentagrid tile lookup ---
    vec2 uv = v_uv - 0.5;
    uv.x *= u_resolution.x / u_resolution.y;

    float gSc = 3.0 / u_zoom;
    vec2 p = uv * gSc + u_camera;

    float gamma[5];
    for (int i = 0; i < 5; i++) gamma[i] = u_gamma[i];

    TileData tile = findTile(p, gamma);

    if (!tile.found) {
        fragColor = vec4(0.02, 0.0, 0.05, 1.0);
        return;
    }

    // --- Coordinate setup ---
    float aspect = u_resolution.x / u_resolution.y;
    float viewW = gSc * aspect;
    float viewH = gSc;
    float rbScale = float(PN) / 2.0;

    // Sphere center in rb_p space (same transform as eye_spy)
    vec2 sphereCenter = vec2(0.0);
    for (int k = 0; k < PN; k++) {
        sphereCenter += grid[k] * (dot(u_camera, grid[k]) + shift[k]);
    }

    // Sphere radius: fills ~60% of the viewport
    float sphereRadius = min(viewW, viewH) * 0.3 * rbScale;

    vec2 tc = tile.center;
    vec2 localTC = tc - sphereCenter;
    float distFromCenter = length(localTC);

    // --- Depth target in rb_p space ---
    vec2 depthTargetPG = vec2(
        (u_depth_centroid.x - 0.5) * viewW + u_camera.x,
        (u_depth_centroid.y - 0.5) * viewH + u_camera.y
    );
    vec2 depthTargetRB = vec2(0.0);
    for (int k = 0; k < PN; k++) {
        depthTargetRB += grid[k] * (dot(depthTargetPG, grid[k]) + shift[k]);
    }

    // --- Determine arc targets ---
    float motion = 0.0;
    if (u_depth_enabled >= 0.5) {
        motion = clamp(u_depth_motion, 0.0, 1.0);
    }

    // Number of arcs
    int numArcs = 6;

    // Accumulate lightning intensity for this tile
    float totalGlow = 0.0;
    vec3 glowColor = vec3(0.0);

    for (int i = 0; i < 6; i++) {
        float seed = float(i);
        float arcPhase = fract(u_time * 0.15 + seed * 0.1618);

        // Arc lifetime: each arc lives ~0.5s then a new one spawns
        float arcTime = fract(u_time * 0.8 + seed * 0.37);
        float arcAlpha = smoothstep(0.0, 0.05, arcTime) * smoothstep(0.5, 0.35, arcTime);

        // Start point: always from the center of the ball
        vec2 arcStart = sphereCenter;

        // End point in idle mode: random point on/inside the sphere surface
        float endAngle = seed * 1.2566 + floor(u_time * 0.8 + seed * 0.37) * 2.39996;
        vec2 endDir = vec2(cos(endAngle), sin(endAngle));
        float endDist = sphereRadius * (0.6 + 0.3 * random(vec2(seed, floor(u_time * 0.8))));
        vec2 idleTarget = sphereCenter + endDir * endDist;

        // When depth detected, arcs reach from center toward the depth centroid
        vec2 depthDir = normalize(depthTargetRB - sphereCenter);
        vec2 depthTarget = sphereCenter + depthDir * sphereRadius * 1.3;
        // Spread arcs around the depth target
        float spreadAngle = (seed - 2.5) * 0.3;
        mat2 spreadRot = mat2(cos(spreadAngle), -sin(spreadAngle),
                              sin(spreadAngle), cos(spreadAngle));
        depthTarget = sphereCenter + spreadRot * (depthTarget - sphereCenter);

        vec2 arcEnd = mix(idleTarget, depthTarget, motion);

        // Compute lightning glow for this tile
        float g = lightningBolt(tc, arcStart, arcEnd,
                                u_time + seed * 7.0,
                                seed + floor(u_time * 0.8 + seed * 0.37) * 0.5);
        g *= arcAlpha;

        // Color: alternate between color1-tinted and color2-tinted arcs
        float colorMix = fract(seed * 0.618);
        vec3 arcColor = mix(u_color1, u_color2, colorMix);
        // Brighten arcs significantly
        arcColor = arcColor * 1.5 + vec3(0.3, 0.2, 0.5);

        totalGlow += g;
        glowColor += arcColor * g;
    }

    // Normalize glow color
    if (totalGlow > 0.001) {
        glowColor /= totalGlow;
    } else {
        glowColor = mix(u_color1, u_color2, 0.5);
    }

    // --- Base tile color: dark sphere interior, darker outside ---
    float insideSphere = smoothstep(sphereRadius * 1.05, sphereRadius * 0.95, distFromCenter);

    // Inner glow of the sphere (ambient plasma)
    float innerGlow = (1.0 - distFromCenter / sphereRadius) * insideSphere;
    innerGlow = max(innerGlow, 0.0);
    float ambientPlasma = fbm(localTC * 2.0 / sphereRadius + u_time * 0.3) * 0.3;

    // Sphere edge glow
    float edgeGlow = smoothstep(sphereRadius * 1.1, sphereRadius * 0.85, distFromCenter)
                   * smoothstep(sphereRadius * 0.7, sphereRadius * 0.95, distFromCenter);

    // Dark base for sphere interior
    vec3 sphereBase = mix(u_color1, u_color2, 0.5) * 0.06;
    // Ambient purple-ish plasma swirl inside
    vec3 ambientColor = mix(u_color1 * 0.15, u_color2 * 0.15, ambientPlasma + 0.5);

    // Outside color: very dark
    vec3 outsideColor = mix(u_color1, u_color2, 0.5) * 0.03;

    // Compose base
    vec3 tileColor = mix(outsideColor, sphereBase + ambientColor * innerGlow, insideSphere);

    // Add sphere edge highlight
    vec3 edgeHighlight = mix(u_color1, u_color2, 0.5) * 0.25;
    tileColor += edgeHighlight * edgeGlow;

    // Add lightning glow
    float glowIntensity = clamp(totalGlow, 0.0, 1.0);
    tileColor = mix(tileColor, glowColor, glowIntensity * 0.9);
    // Bloom: extra bright core
    tileColor += glowColor * pow(glowIntensity, 2.0) * 0.5;

    // Sphere glass reflection highlight (subtle)
    float reflectAngle = atan(localTC.y, localTC.x);
    float reflect = smoothstep(0.7, 1.0, cos(reflectAngle - 0.8)) * insideSphere;
    reflect *= smoothstep(sphereRadius * 0.3, sphereRadius * 0.9, distFromCenter);
    tileColor += vec3(0.15) * reflect * 0.3;

    // --- Edges ---
    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);
    fragColor = vec4(finalColor, 1.0);
}
