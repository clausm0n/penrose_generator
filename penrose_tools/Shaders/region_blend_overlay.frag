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

// Edge distance computation in world space
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
        // Star pattern: invert blend of colors
        vec3 blended = blendColors(u_color1, u_color2, 0.3);
        tileColor = invertColor(blended);
    }
    else if (pattern_type > 1.9 && pattern_type < 2.1) {
        // Starburst pattern: invert blend of colors
        vec3 blended = blendColors(u_color1, u_color2, 0.7);
        tileColor = invertColor(blended);
    }
    else {
        // Normal tile: blend based on pre-computed neighbor data
        tileColor = blendColors(u_color1, u_color2, blend_factor);
    }

    // Selection highlight
    if (selected > 0.5) {
        tileColor = mix(tileColor, vec3(1.0, 1.0, 0.0), 0.3);
    }
    // Hover highlight
    if (hovered > 0.5) {
        tileColor = mix(tileColor, vec3(1.0, 1.0, 1.0), 0.15);
    }

    // Determine overlay alpha — fully opaque for region_blend tiles,
    // transparent unless there's an active interaction (hover/select/anim)
    float interactionAlpha = 0.0;
    if (selected > 0.5) interactionAlpha = max(interactionAlpha, 0.35);
    if (hovered > 0.5) interactionAlpha = max(interactionAlpha, 0.2);

    // Animation effects contribute alpha
    if (anim_type > 0.5) {
        // Flip animation (type 1): pulse brightness
        if (anim_type < 1.5) {
            float flip = sin(anim_phase * 3.14159);
            tileColor = mix(tileColor, vec3(1.0), flip * 0.5);
            interactionAlpha = max(interactionAlpha, flip * 0.6);
        }
        // Cascade animation (type 2): rotational color shift
        else if (anim_type < 2.5) {
            float wave = sin(anim_phase * 3.14159);
            float hueShift = anim_phase * 0.5 + tile_id;
            vec3 cascadeColor = vec3(
                0.5 + 0.5 * sin(hueShift * 6.28318),
                0.5 + 0.5 * sin(hueShift * 6.28318 + 2.094),
                0.5 + 0.5 * sin(hueShift * 6.28318 + 4.189)
            );
            tileColor = mix(tileColor, cascadeColor, wave * 0.7);
            interactionAlpha = max(interactionAlpha, wave * 0.7);
        }
        // Ripple animation (type 3): radial pulse
        else if (anim_type < 3.5) {
            float ripple = sin(anim_phase * 3.14159) * (1.0 - anim_phase);
            tileColor = mix(tileColor, vec3(0.8, 0.9, 1.0), ripple * 0.6);
            interactionAlpha = max(interactionAlpha, ripple * 0.5);
        }
    }

    // For tiles that are part of pattern rendering (region_blend mode),
    // they should be fully opaque. Use u_overlay_mode to decide:
    // Mode 0 (primary/region_blend): all tiles fully opaque
    // Mode 1 (interaction-only): only tiles with active interactions are visible
    float finalAlpha;
    if (u_overlay_mode < 0.5) {
        finalAlpha = 1.0;  // Primary mode: fully opaque
    } else {
        finalAlpha = interactionAlpha;  // Interaction-only: transparent unless interacted
    }

    // Edge rendering in camera space (vertices converted from ribbon via (rb - offset) / 2.5)
    // Procedural shader uses edgeWidth = 0.012 in ribbon space
    // Camera space = ribbon / 2.5, so edgeWidth = 0.012 / 2.5 = 0.0048
    float edgeDist = distToQuadEdge(v_world_pos);
    float edgeWidth = 0.0048 * u_edge_thickness;
    float aaWidth = 0.0012;
    float edgeFactor = smoothstep(edgeWidth - aaWidth, edgeWidth, edgeDist);
    vec3 edgeColor = tileColor * 0.15;
    vec3 finalColor = mix(edgeColor, tileColor, edgeFactor);

    // Use finalAlpha for compositing — fully opaque for region_blend primary rendering,
    // semi-transparent for interaction-only overlay on other effects
    fragColor = vec4(finalColor, finalAlpha);
}

