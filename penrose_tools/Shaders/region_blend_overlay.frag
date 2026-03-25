// region_blend_overlay.frag - Multi-effect tile renderer
// Renders ALL common effects via instanced overlay tiles — zero findTile cost.
// Effect mode selects coloring: region_blend, no_effect, rainbow, pulse, sparkle.
// Pattern data comes from per-instance attributes - no texture lookup needed.
#version 140

in vec2 v_world_pos;
flat in vec2 v_v0;
flat in vec2 v_v1;
flat in vec2 v_v2;
flat in vec2 v_v3;
flat in vec4 v_tile_data1; // is_kite, pattern_type, blend_factor, selected
flat in vec4 v_tile_data2; // hovered, anim_phase, anim_type, tile_id

out vec4 fragColor;

uniform vec3 u_color1;
uniform vec3 u_color2;
uniform float u_edge_thickness;
uniform float u_time;
uniform float u_overlay_mode;  // 0 = primary (opaque), 1 = interaction-only (alpha)
uniform float u_effect_mode;   // 0=region_blend, 1=no_effect, 2=rainbow, 3=pulse, 4=sparkle

// Depth mask support
uniform sampler2D u_mask_texture;
uniform float u_mask_enabled;
uniform vec2 u_mask_camera;
uniform float u_mask_zoom;
uniform float u_mask_aspect;
uniform vec3 u_mask_color;

// --- Helpers ---

float distToSegment(vec2 p, vec2 a, vec2 b) {
    vec2 e = b - a;
    vec2 w = p - a;
    float len2 = dot(e, e);
    float t = clamp(dot(w, e) / len2, 0.0, 1.0);
    return length(p - (a + t * e));
}

float distToQuadEdge(vec2 p) {
    float d0 = distToSegment(p, v_v0, v_v1);
    float d1 = distToSegment(p, v_v1, v_v2);
    float d2 = distToSegment(p, v_v2, v_v3);
    float d3 = distToSegment(p, v_v3, v_v0);
    return min(min(d0, d1), min(d2, d3));
}

vec3 hsvToRgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z * mix(vec3(1.0), rgb, c.y);
}

float hash(float n) {
    return fract(sin(n * 127.1 + 311.7) * 43758.5453);
}

// --- Main ---

void main() {
    float is_kite      = v_tile_data1.x;
    float pattern_type  = v_tile_data1.y;
    float blend_factor  = v_tile_data1.z;
    float selected      = v_tile_data1.w;
    float hovered       = v_tile_data2.x;
    float anim_phase    = v_tile_data2.y;
    float anim_type     = v_tile_data2.z;
    float tile_id       = v_tile_data2.w;

    vec3 baseColor = is_kite > 0.5 ? u_color1 : u_color2;
    vec3 tileColor;

    // --- Effect-specific coloring ---
    if (u_effect_mode < 0.5) {
        // 0: region_blend — pattern-aware blending
        if (pattern_type > 0.9 && pattern_type < 1.1) {
            tileColor = vec3(1.0) - u_color1;  // star invert
        } else if (pattern_type > 1.9 && pattern_type < 2.1) {
            tileColor = vec3(1.0) - u_color2;  // starburst invert
        } else {
            tileColor = mix(u_color1, u_color2, clamp(blend_factor, 0.0, 1.0));
        }
    } else if (u_effect_mode < 1.5) {
        // 1: no_effect — simple kite/dart coloring
        tileColor = baseColor;
    } else if (u_effect_mode < 2.5) {
        // 2: rainbow — hue cycling per tile
        float h = tile_id + u_time * 0.1;
        float sat = is_kite > 0.5 ? 0.9 : 0.6;
        tileColor = hsvToRgb(vec3(h, sat, 1.0));
    } else if (u_effect_mode < 3.5) {
        // 3: pulse — radial waves from origin
        vec2 centroid = (v_v0 + v_v1 + v_v2 + v_v3) * 0.25 * 0.1;
        float dist = length(centroid);
        float pulse = sin(dist * 8.0 - u_time * 3.0) * 0.5 + 0.5;
        tileColor = mix(baseColor * 0.3, baseColor, pulse);
    } else {
        // 4: sparkle — per-tile phase cycling
        float randSpeed = hash(tile_id) * 0.1 + 0.2;
        float randOffset = hash(tile_id + 73.0) * 6.28318;
        float phase = fract(u_time * randSpeed * 0.3 + randOffset);

        if (phase < 0.25) {
            float t = smoothstep(0.0, 1.0, phase / 0.25);
            tileColor = mix(u_color1, vec3(0.0), t);
        } else if (phase < 0.5) {
            float t = smoothstep(0.0, 1.0, (phase - 0.25) / 0.25);
            tileColor = mix(vec3(0.0), u_color2, t);
        } else if (phase < 0.75) {
            float t = smoothstep(0.0, 1.0, (phase - 0.5) / 0.25);
            tileColor = mix(u_color2, vec3(0.0), t);
        } else {
            float t = smoothstep(0.0, 1.0, (phase - 0.75) / 0.25);
            tileColor = mix(vec3(0.0), u_color1, t);
        }
    }

    // --- Interaction effects (shared by all modes) ---
    if (selected > 0.5) tileColor = mix(tileColor, vec3(1.0, 1.0, 0.0), 0.3);
    if (hovered > 0.5) tileColor = mix(tileColor, vec3(1.0, 1.0, 1.0), 0.15);

    float interactionAlpha = 0.0;
    if (selected > 0.5) interactionAlpha = max(interactionAlpha, 0.35);
    if (hovered > 0.5) interactionAlpha = max(interactionAlpha, 0.2);

    if (anim_type > 2.5 && anim_type < 3.5) {
        float ripple = sin(anim_phase * 3.14159) * (1.0 - anim_phase);
        tileColor = mix(tileColor, vec3(0.8, 0.9, 1.0), ripple * 0.6);
        interactionAlpha = max(interactionAlpha, ripple * 0.5);
    }

    if (anim_type > 4.5 && anim_type < 5.5) {
        float sym_intensity = sin(anim_phase * 3.14159) * (1.0 - anim_phase * 0.3);
        float shimmer = sin(u_time * 3.0 + tile_id * 6.283) * 0.1 + 0.9;
        vec3 symColor = vec3(1.0, 0.85, 0.3) * shimmer;
        tileColor = mix(tileColor, symColor, sym_intensity * 0.7);
        interactionAlpha = max(interactionAlpha, sym_intensity * 0.8);
    }

    // --- Edge rendering ---
    float edgeWidth = 0.0048 * u_edge_thickness;
    float aaWidth = 0.0012;
    float edgeDist = distToQuadEdge(v_world_pos);
    float edgeFactor = smoothstep(edgeWidth - aaWidth, edgeWidth, edgeDist);
    vec3 edgeColor = tileColor * 0.15;
    vec3 finalColor = mix(edgeColor, tileColor, edgeFactor);

    // --- Depth mask ---
    float maskAlpha = 0.0;
    if (u_mask_enabled > 0.5) {
        vec2 tileCentroid = (v_v0 + v_v1 + v_v2 + v_v3) * 0.25;
        vec2 rel = tileCentroid - u_mask_camera;
        vec2 mask_uv;
        mask_uv.x = rel.x * u_mask_zoom / (3.0 * u_mask_aspect) + 0.5;
        mask_uv.y = rel.y * u_mask_zoom / 3.0 + 0.5;

        float maskVal = 0.0;
        if (mask_uv.x >= 0.0 && mask_uv.x <= 1.0 && mask_uv.y >= 0.0 && mask_uv.y <= 1.0) {
            maskVal = texture(u_mask_texture, mask_uv).r;
        }

        vec3 darkened = finalColor * 0.2;
        vec3 brightened = mix(finalColor, u_color2, 0.35) * 1.4;
        finalColor = mix(darkened, brightened, maskVal);
        maskAlpha = maskVal * 0.8;
    }

    // --- Alpha ---
    float finalAlpha;
    if (u_overlay_mode < 0.5) {
        finalAlpha = 1.0;  // Primary opaque
    } else {
        finalAlpha = max(interactionAlpha, maskAlpha);  // Interaction-only
    }

    fragColor = vec4(finalColor, finalAlpha);
}
