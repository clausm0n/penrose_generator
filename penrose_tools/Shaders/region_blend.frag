// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;
uniform vec2 star_centers[50];      // Centers of star pattern tiles in GL space
uniform vec2 starburst_centers[50]; // Centers of starburst pattern tiles in GL space
uniform vec2 neighbor_centers[500];  // Centers of all tiles in GL space
uniform float neighbor_factors[500]; // Blend factors based on neighbor counts
uniform int num_stars;
uniform int num_starbursts;
uniform int num_neighbors;

varying float v_tile_type;
varying vec2 v_tile_centroid;
varying vec2 v_position;

const float EPSILON = 0.01;  // Increased epsilon for GL space coordinates

vec3 blendColors(vec3 c1, vec3 c2, float factor) {
    return mix(c1, c2, factor);
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

bool isInPattern(vec2 center) {
    // Check if this tile's centroid matches a pattern center
    return distance(v_tile_centroid, center) < EPSILON;
}

void main() {
    vec3 finalColor;
    float blend_factor = 0.5;  // Default blend factor
    bool isSpecial = false;
    
    // Check if this tile is part of a star pattern
    if (v_tile_type > 0.5) {  // Is kite
        for (int i = 0; i < num_stars && i < 50; i++) {
            if (isInPattern(star_centers[i])) {
                // Use special coloring for star pattern
                finalColor = invertColor(blendColors(color1, color2, 0.3));
                isSpecial = true;
                break;
            }
        }
    }
    // Check if this tile is part of a starburst pattern
    else {  // Is dart
        for (int i = 0; i < num_starbursts && i < 50; i++) {
            if (isInPattern(starburst_centers[i])) {
                // Use special coloring for starburst pattern
                finalColor = invertColor(blendColors(color1, color2, 0.7));
                isSpecial = true;
                break;
            }
        }
    }
    
    // If not part of a special pattern, use neighbor-based blending
    if (!isSpecial) {
        // Find the matching neighbor factor
        for (int i = 0; i < num_neighbors && i < 500; i++) {
            if (isInPattern(neighbor_centers[i])) {
                blend_factor = neighbor_factors[i];
                break;
            }
        }
        finalColor = blendColors(color1, color2, blend_factor);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}