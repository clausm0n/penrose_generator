// region_blend.frag - Procedural Penrose with star/starburst detection
// Stars (5 kites) and starbursts (10 darts) are highlighted with inverted colors
// Normal tiles blend based on neighbor tile types
// OPTIMIZED: Uses pre-computed pattern data from CPU instead of per-pixel detection
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
uniform sampler2D u_pattern_texture;

#include "pentagrid_common.glsl"

// --- Pattern lookup from pre-computed texture ---
// Instead of expensive per-pixel pattern detection, we look up pattern data
// from a texture that was computed once on the CPU for all visible tiles.

// Look up pattern data for the current tile from the pattern texture
// Returns: vec2(pattern_type, blend_factor)
//   pattern_type: 0=normal, 1=star, 2=starburst
//   blend_factor: ratio for color blending
vec2 lookupPatternData(vec2 tileCentroid, bool isFat) {
    // The pattern texture contains entries indexed by centroid position (in ribbon space)
    // Each texel: (centroid.x, centroid.y, pattern_type, blend_factor)

    // Get texture dimensions
    ivec2 texSize = textureSize(u_pattern_texture, 0);

    // Search through the texture for matching centroid
    // Tiles in ribbon space have a fixed size (~0.1-0.2 in scaled coordinates)
    // Use a fixed epsilon that accounts for floating point precision
    // and the 0.1 scaling factor applied to centroids
    float epsilon = 0.01;  // Fixed epsilon for centroid matching in scaled ribbon space
    for (int i = 0; i < texSize.x; i++) {
        vec2 texCoord = vec2((float(i) + 0.5) / float(texSize.x), 0.5);
        vec4 data = texture2D(u_pattern_texture, texCoord);

        vec2 storedCentroid = data.xy;
        float patternType = data.z;
        float blendFactor = data.w;

        // Check if centroid matches
        if (distance(storedCentroid, tileCentroid) < epsilon) {
            return vec2(patternType, blendFactor);
        }
    }

    // Default: normal tile with blend based on tile type
    return vec2(0.0, isFat ? 1.0 : 0.0);
}

vec3 blendColors(vec3 col1, vec3 col2, float factor) {
    return mix(col1, col2, clamp(factor, 0.0, 1.0));
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
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

    vec3 tileColor;

    // Calculate tile centroid in ribbon space (scaled by 0.1 to match CPU storage)
    vec2 tileCentroid = tile.tileCentroid;  // Already scaled by 0.1 in findTile()

    // Look up pre-computed pattern data instead of expensive per-pixel detection
    vec2 patternData = lookupPatternData(tileCentroid, tile.isFat);
    float patternType = patternData.x;
    float blendFactor = patternData.y;

    // DEBUG: Visualize blend factor as grayscale
    // tileColor = vec3(blendFactor);

    if (patternType > 0.9 && patternType < 1.1) {
        // Star pattern: invert blend of colors (kites lean toward color1)
        vec3 blended = blendColors(u_color1, u_color2, 0.3);
        tileColor = invertColor(blended);
    }
    else if (patternType > 1.9 && patternType < 2.1) {
        // Starburst pattern: invert blend of colors (darts lean toward color2)
        vec3 blended = blendColors(u_color1, u_color2, 0.7);
        tileColor = invertColor(blended);
    }
    else {
        // Normal tile: blend based on pre-computed neighbor data
        tileColor = blendColors(u_color1, u_color2, blendFactor);
    }

    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);

    fragColor = vec4(finalColor, 1.0);
}

