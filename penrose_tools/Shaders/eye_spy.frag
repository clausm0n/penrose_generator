// eye_spy.frag - Depth-camera-driven eye effect
// All tiles are color1 by default. Tiles inside the eye shape get color2.
// The eye lids squint based on total depth coverage (more data = wider open).
// The pupil follows the centroid of the depth data.
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
uniform float u_depth_enabled;     // >0.5 when depth data is available
uniform float u_depth_coverage;    // 0-1: fraction of depth pixels active
uniform vec2 u_depth_centroid;     // XY centroid of depth data in UV space (0-1)
uniform float u_depth_motion;      // 0-1: smoothed centroid motion magnitude

#include "pentagrid_common.glsl"

// -----------------------------------------------------------------
// Eye geometry: almond shape from two intersecting circular arcs
// Works in local coordinates relative to eye center.
// -----------------------------------------------------------------

// Returns negative when inside the eye, positive outside.
// halfW:    horizontal half-extent of the eye
// opening:  vertical half-extent at the widest point (controls lid gap)
float sdEye(vec2 localP, float halfW, float opening) {
    // The eye is the intersection of two circular arcs.
    // Each arc passes through (-halfW, 0) and (+halfW, 0).
    // The arc radius is chosen so the arc bulges to ±opening at x=0.
    //
    // For a circle passing through (-halfW,0), (halfW,0) with apex at (0, opening):
    //   R = (halfW^2 + opening^2) / (2 * opening)
    //   center_y = opening - R = -(halfW^2 - opening^2) / (2 * opening)

    float hw2 = halfW * halfW;
    float op2 = opening * opening;
    float R = (hw2 + op2) / (2.0 * opening);
    float cy = opening - R;  // negative: circle center is below the apex

    // Upper lid arc: center at (0, -cy), same radius, mirrored
    float d_upper = length(vec2(localP.x, localP.y + cy)) - R;   // inside upper arc: < 0
    float d_lower = length(vec2(localP.x, localP.y - cy)) - R;   // inside lower arc: < 0

    // Inside the eye = inside BOTH arcs (intersection)
    return max(d_upper, d_lower);
}

// Signed distance to a filled circle
float sdCircle(vec2 p, vec2 center, float radius) {
    return length(p - center) - radius;
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
        fragColor = vec4(0.05, 0.05, 0.05, 1.0);
        return;
    }

    // --- Depth-driven eye parameters ---
    float coverage = clamp(u_depth_coverage, 0.0, 1.0);
    // openness: 0 = shut, 1 = wide open
    // Min openness 0.3 so the eye is always clearly visible
    float openness = mix(0.3, 1.0, coverage);

    // --- Blink ---
    // Periodic blink with varying interval (4-8 seconds) using noise.
    // A blink is a quick close-open (~0.15s down, ~0.2s up).
    // Use a noise-based varying period: hash the cycle index to get 4-8s range
    float basePeriod = 8.0;  // average period
    float cycleIndex = floor(u_time / basePeriod);
    float periodJitter = random(vec2(cycleIndex, 0.0));  // 0-1
    float blinkPeriod = mix(4.0, 8.0, periodJitter);
    // Accumulate time within the current cycle using the jittered period
    float blinkTime = u_time - cycleIndex * basePeriod;
    blinkTime = mod(blinkTime, blinkPeriod);
    // Primary blink: ramp up to closed, then back down to open
    // blinkClose1: 0 = open, peaks at 1 = fully shut
    float blink1 = smoothstep(0.0, 0.08, blinkTime)
                 - smoothstep(0.12, 0.28, blinkTime);
    // Double-blink: use a slow sine to decide if this cycle has one
    float doubleBlink = step(0.6, sin(u_time * 0.37));
    float blink2 = doubleBlink * (
                       smoothstep(0.40, 0.48, blinkTime)
                     - smoothstep(0.52, 0.68, blinkTime));
    // blinkClose: 0 = open, 1 = fully shut
    float blinkClose = clamp(blink1 + blink2, 0.0, 1.0);
    // Squish openness toward near-zero during blink
    openness *= mix(1.0, 0.02, blinkClose);

    // Eye fills most of the viewport
    float aspect = u_resolution.x / u_resolution.y;
    float viewW = gSc * aspect;  // full visible width in pentagrid space
    float viewH = gSc;           // full visible height in pentagrid space

    // The pentagrid rb_p transform scales distances by PN/2 = 2.5
    float rbScale = float(PN) / 2.0;
    float eyeHalfW = viewW * 0.45 * rbScale;              // fit within viewport
    float eyeOpening = viewH * 0.63 * openness * rbScale;
    // When blinking, push lids past closed by ~1.5 tile widths for a solid seam
    float tileWidth = eyeHalfW * 0.03;  // approximate tile scale
    eyeOpening = max(eyeOpening - blinkClose * tileWidth * 1.5, 0.001);

    // Eye center must be in the same dual/rhombus space as tile.center.
    // tile.center comes from getRhombusVerts which works in the rb_p space.
    // rb_p = sum(grid[k] * (dot(p, grid[k]) + shift[k])) — a linear transform of p.
    // Compute this transform for the camera center point.
    vec2 eyeCenter = vec2(0.0);
    for (int k = 0; k < PN; k++) {
        eyeCenter += grid[k] * (dot(u_camera, grid[k]) + shift[k]);
    }

    // Centroid in UV (0-1) -> map to pentagrid space, then to rb_p space
    vec2 depthCentroidPG = vec2(
        (u_depth_centroid.x - 0.5) * viewW + u_camera.x,
        (u_depth_centroid.y - 0.5) * viewH + u_camera.y
    );
    vec2 depthCentroidRB = vec2(0.0);
    for (int k = 0; k < PN; k++) {
        depthCentroidRB += grid[k] * (dot(depthCentroidPG, grid[k]) + shift[k]);
    }
    depthCentroidPG = depthCentroidRB;

    // --- Compute distances for this tile ---
    vec2 tc = tile.center;          // tile centroid in rb_p (dual) space
    vec2 localTC = tc - eyeCenter;  // relative to eye center

    // Eye lid SDF
    float dEye = sdEye(localTC, eyeHalfW, eyeOpening);

    // Constrain pupil within lids
    vec2 pupilOffset = depthCentroidPG - eyeCenter;
    float maxPupilX = eyeHalfW * 0.65;
    float maxPupilY = eyeOpening * 0.60;
    pupilOffset.x = clamp(pupilOffset.x, -maxPupilX, maxPupilX);
    pupilOffset.y = clamp(pupilOffset.y, -maxPupilY, maxPupilY);
    vec2 pupilCenter = eyeCenter + pupilOffset;

    // Pupil and iris radii — small relative to the large eye
    float eyeMinDim = min(eyeHalfW, eyeOpening);
    float pupilRadius = eyeMinDim * 0.15;
    float irisRadius  = eyeMinDim * 0.30;

    // When depth is enabled but no motion, lerp pupil back to center
    if (u_depth_enabled >= 0.5) {
        float motion = clamp(u_depth_motion, 0.0, 1.0);
        pupilCenter = mix(eyeCenter, pupilCenter, motion);
    } else {
        // Gentle idle animation when no depth data at all
        float ax = sin(u_time * 0.5) * maxPupilX * 0.5;
        float ay = cos(u_time * 0.7) * maxPupilY * 0.4;
        pupilCenter = eyeCenter + vec2(ax, ay);
    }

    float dPupil = sdCircle(tc, pupilCenter, pupilRadius);
    float dIris  = sdCircle(tc, pupilCenter, irisRadius);

    // --- Color assignment with smooth blending at boundaries ---
    // Use smoothstep on SDF distances so border tiles blend between zones.
    // blendWidth controls how many tiles-worth of distance the blend spans.
    float blendWidth = eyeMinDim * 0.08;

    // Smooth blend factors: 0 = outside, 1 = inside
    float eyeBlend  = smoothstep(blendWidth, -blendWidth, dEye);
    float irisBlend = smoothstep(blendWidth, -blendWidth, dIris);
    float pupilBlend = smoothstep(blendWidth * 0.7, -blendWidth * 0.7, dPupil);

    // Layer colors from outside in:
    // Outside eye: color1
    // Sclera (inside eye): mix of color1 and color2
    // Iris: color2 with radial gradient
    // Pupil: near-black

    vec3 outsideColor = u_color1;
    vec3 scleraColor  = mix(u_color1, u_color2, 0.5);
    float irisGrad    = smoothstep(0.0, 1.0, clamp(-dIris / irisRadius, 0.0, 1.0));
    vec3 irisColor    = mix(u_color2, u_color2 * 0.35, irisGrad);
    vec3 pupilColor   = u_color2 * 0.08;

    // Blend layers: start from outside color, then blend in each zone
    vec3 tileColor = mix(outsideColor, scleraColor, eyeBlend);
    tileColor = mix(tileColor, irisColor, irisBlend * eyeBlend);
    tileColor = mix(tileColor, pupilColor, pupilBlend * irisBlend * eyeBlend);

    // Lid shadow at the edges of the eye opening (also smoothed)
    float lidShadow = smoothstep(0.0, eyeHalfW * 0.06, max(-dEye, 0.0));
    tileColor *= mix(1.0, mix(0.65, 1.0, lidShadow), eyeBlend);

    // --- Edges ---
    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);
    fragColor = vec4(finalColor, 1.0);
}
