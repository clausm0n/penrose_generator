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

    // Edge rendering in camera space (vertices converted from ribbon via (rb - offset) / 2.5)
    // Procedural shader uses edgeWidth = 0.012 in ribbon space
    // Camera space = ribbon / 2.5, so edgeWidth = 0.012 / 2.5 = 0.0048
    float edgeDist = distToQuadEdge(v_world_pos);
    float edgeWidth = 0.0048 * u_edge_thickness;
    float aaWidth = 0.0012;
    float edgeFactor = smoothstep(edgeWidth - aaWidth, edgeWidth, edgeDist);
    vec3 edgeColor = tileColor * 0.15;
    vec3 finalColor = mix(edgeColor, tileColor, edgeFactor);

    fragColor = vec4(finalColor, 1.0);
}

