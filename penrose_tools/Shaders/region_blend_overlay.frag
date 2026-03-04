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

    vec3 tileColor;
    if (pattern_type > 0.9 && pattern_type < 1.1) {
        tileColor = invertColor(blendColors(u_color1, u_color2, 0.3));
    } else if (pattern_type > 1.9 && pattern_type < 2.1) {
        tileColor = invertColor(blendColors(u_color1, u_color2, 0.7));
    } else {
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

    float finalAlpha;
    if (u_overlay_mode < 0.5) {
        finalAlpha = 1.0;
    } else {
        finalAlpha = interactionAlpha;
    }

    float edgeWidth = 0.0048 * u_edge_thickness;
    float aaWidth = 0.0012;
    float edgeDist = distToQuadEdge(v_world_pos);
    float edgeFactor = smoothstep(edgeWidth - aaWidth, edgeWidth, edgeDist);
    vec3 edgeColor = tileColor * 0.15;
    vec3 finalColor = mix(edgeColor, tileColor, edgeFactor);

    // --- Depth mask overlay ---
    if (u_mask_enabled > 0.5) {
        // Map world position to mask UV coordinates
        // Convert world pos to normalized screen coords using camera/zoom
        vec2 rel = v_world_pos - u_mask_camera;
        vec2 mask_uv;
        mask_uv.x = rel.x * u_mask_zoom / (3.0 * u_mask_aspect) + 0.5;
        mask_uv.y = rel.y * u_mask_zoom / 3.0 + 0.5;

        // Clamp to valid range
        mask_uv = clamp(mask_uv, 0.0, 1.0);

        // Sample mask (single channel - use red)
        float maskVal = texture(u_mask_texture, mask_uv).r;

        // Apply mask: blend tile color toward mask_color based on mask intensity
        finalColor = mix(finalColor, u_mask_color, maskVal * 0.8);

        // Boost edge visibility in masked areas
        float maskedEdge = smoothstep(edgeWidth - aaWidth, edgeWidth, edgeDist);
        finalColor = mix(finalColor * 0.3, finalColor, maskedEdge);
    }

    fragColor = vec4(finalColor, finalAlpha);
}
