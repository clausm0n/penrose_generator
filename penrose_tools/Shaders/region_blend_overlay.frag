// region_blend_overlay.frag - Region blend using overlay tile data
// Pattern data comes from per-instance attributes - no texture lookup needed
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
uniform float u_overlay_mode; // 0 = primary (opaque), 1 = interaction-only (alpha)

// Depth mask support
uniform sampler2D u_mask_texture;
uniform float u_mask_enabled;     // 0.0 = off, 1.0 = on
uniform vec2 u_mask_camera;       // camera position for mask UV mapping
uniform float u_mask_zoom;        // zoom for mask UV mapping
uniform float u_mask_aspect;      // viewport aspect ratio for mask UV mapping
uniform vec3 u_mask_color;        // color to blend with mask (highlight color)

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

vec3 blendColors(vec3 col1, vec3 col2, float factor) {
    return mix(col1, col2, clamp(factor, 0.0, 1.0));
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

void main() {
    float is_kite      = v_tile_data1.x;
    float pattern_type  = v_tile_data1.y;
    float blend_factor  = v_tile_data1.z;
    float selected      = v_tile_data1.w;
    float hovered       = v_tile_data2.x;
    float anim_phase    = v_tile_data2.y;
    float anim_type     = v_tile_data2.z;
    float tile_id       = v_tile_data2.w;

    // Base color from tile type (kite vs dart)
    vec3 baseColor = is_kite > 0.5 ? u_color1 : u_color2;

    vec3 tileColor;
    if (pattern_type > 0.9 && pattern_type < 1.1) {
        // Star pattern (kites): inversion of color1
        tileColor = invertColor(u_color1);
    } else if (pattern_type > 1.9 && pattern_type < 2.1) {
        // Starburst pattern (darts): inversion of color2
        tileColor = invertColor(u_color2);
    } else {
        // Region blend: color purely from neighbor-diffused blend_factor
        // 0 = dart-heavy neighborhood → color2, 1 = kite-heavy → color1
        tileColor = blendColors(u_color1, u_color2, blend_factor);
    }

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

    // 5-fold symmetry glow (anim_type == 5)
    if (anim_type > 4.5 && anim_type < 5.5) {
        float sym_intensity = sin(anim_phase * 3.14159) * (1.0 - anim_phase * 0.3);
        // Golden color with per-tile shimmer
        float shimmer = sin(u_time * 3.0 + tile_id * 6.283) * 0.1 + 0.9;
        vec3 symColor = vec3(1.0, 0.85, 0.3) * shimmer;
        tileColor = mix(tileColor, symColor, sym_intensity * 0.7);
        interactionAlpha = max(interactionAlpha, sym_intensity * 0.8);
    }

    float edgeWidth = 0.0048 * u_edge_thickness;
    float aaWidth = 0.0012;
    float edgeDist = distToQuadEdge(v_world_pos);
    float edgeFactor = smoothstep(edgeWidth - aaWidth, edgeWidth, edgeDist);
    vec3 edgeColor = tileColor * 0.15;
    vec3 finalColor = mix(edgeColor, tileColor, edgeFactor);

    // --- Depth mask: per-tile brightness modulation using palette colors ---
    float maskAlpha = 0.0;
    if (u_mask_enabled > 0.5) {
        // Sample mask at tile centroid so each tile gets a uniform value
        vec2 tileCentroid = (v_v0 + v_v1 + v_v2 + v_v3) * 0.25;
        vec2 rel = tileCentroid - u_mask_camera;
        vec2 mask_uv;
        mask_uv.x = rel.x * u_mask_zoom / (3.0 * u_mask_aspect) + 0.5;
        mask_uv.y = rel.y * u_mask_zoom / 3.0 + 0.5;

        float maskVal = 0.0;
        if (mask_uv.x >= 0.0 && mask_uv.x <= 1.0 && mask_uv.y >= 0.0 && mask_uv.y <= 1.0) {
            maskVal = texture(u_mask_texture, mask_uv).r;
        }

        // Use palette colors for depth effect:
        // Background (maskVal ~0): darken tile significantly
        // Foreground (maskVal ~1): brighten tile with color2 accent
        vec3 darkened = finalColor * 0.2;
        vec3 brightened = mix(finalColor, u_color2, 0.35) * 1.4;
        finalColor = mix(darkened, brightened, maskVal);

        // Mask contributes to alpha so tiles become visible over any base effect
        maskAlpha = maskVal * 0.8;
    }

    // Compute final alpha
    float finalAlpha;
    if (u_overlay_mode < 0.5) {
        // Primary opaque overlay (region_blend): always fully visible
        finalAlpha = 1.0;
    } else {
        // Interaction overlay: mask and interactions both contribute visibility
        finalAlpha = max(interactionAlpha, maskAlpha);
    }

    fragColor = vec4(finalColor, finalAlpha);
}
