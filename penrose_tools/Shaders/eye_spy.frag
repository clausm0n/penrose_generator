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

    // Eye fills most of the viewport
    float aspect = u_resolution.x / u_resolution.y;
    float viewW = gSc * aspect;  // full visible width in pentagrid space
    float viewH = gSc;           // full visible height in pentagrid space

    float eyeHalfW = viewW * 1.1;                        // tips extend past viewport edges
    float eyeOpening = viewH * 0.9 * openness;           // tall sweeping lids

    // Eye center is at camera center
    vec2 eyeCenter = u_camera;

    // Centroid in UV (0-1) -> map to pentagrid space for pupil position
    vec2 depthCentroidPG = vec2(
        (u_depth_centroid.x - 0.5) * viewW + u_camera.x,
        (u_depth_centroid.y - 0.5) * viewH + u_camera.y
    );

    // --- Compute distances for this tile ---
    vec2 tc = tile.center;          // tile centroid in pentagrid space
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

    // Gentle idle animation when no depth data
    if (u_depth_enabled < 0.5) {
        float ax = sin(u_time * 0.5) * maxPupilX * 0.5;
        float ay = cos(u_time * 0.7) * maxPupilY * 0.4;
        pupilCenter = eyeCenter + vec2(ax, ay);
    }

    float dPupil = sdCircle(tc, pupilCenter, pupilRadius);
    float dIris  = sdCircle(tc, pupilCenter, irisRadius);

    // --- Color assignment ---
    vec3 tileColor = u_color1;  // default: all tiles are color1

    bool insideEye   = dEye < 0.0;
    bool insideIris  = dIris < 0.0 && insideEye;
    bool insidePupil = dPupil < 0.0 && insideEye;

    if (insidePupil) {
        // Pupil: dark
        tileColor = u_color2 * 0.08;
    } else if (insideIris) {
        // Iris: color2 with radial gradient
        float irisGrad = smoothstep(0.0, 1.0, -dIris / irisRadius);
        tileColor = mix(u_color2, u_color2 * 0.35, irisGrad);
    } else if (insideEye) {
        // Sclera (white of the eye)
        tileColor = vec3(0.95, 0.95, 0.93);
    }

    // Lid shadow at the edges of the eye opening
    if (insideEye) {
        float lidShadow = smoothstep(0.0, eyeHalfW * 0.06, -dEye);
        tileColor *= mix(0.65, 1.0, lidShadow);
    }

    // --- Edges ---
    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);
    fragColor = vec4(finalColor, 1.0);
}
