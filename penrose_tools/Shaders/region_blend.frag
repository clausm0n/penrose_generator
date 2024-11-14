// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;
uniform vec2 star_centers[50];     // Adjust max size as needed
uniform vec2 starburst_centers[50]; // Adjust max size as needed
uniform vec2 neighbor_centers[500]; // Adjust max size as needed
uniform float neighbor_factors[500];
uniform int num_stars;
uniform int num_starbursts;
uniform int num_neighbors;

varying float v_tile_type;
varying vec2 v_tile_centroid;

const float EPSILON = 0.001;

bool approxEqual(vec2 a, vec2 b) {
    return distance(a, b) < EPSILON;
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

vec3 blendColors(vec3 color1, vec3 color2, float factor) {
    return mix(color1, color2, factor);
}

void main() {
    vec3 finalColor;
    float blend_factor = 0.5;  // Default blend factor
    bool isSpecial = false;
    
    // Check if this tile is part of a star
    if (v_tile_type > 0.5) {  // Is kite
        for (int i = 0; i < num_stars; i++) {
            if (approxEqual(v_tile_centroid, star_centers[i])) {
                finalColor = invertColor(blendColors(color1, color2, 0.3));
                isSpecial = true;
                break;
            }
        }
    }
    // Check if this tile is part of a starburst
    else {  // Is dart
        for (int i = 0; i < num_starbursts; i++) {
            if (approxEqual(v_tile_centroid, starburst_centers[i])) {
                finalColor = invertColor(blendColors(color1, color2, 0.7));
                isSpecial = true;
                break;
            }
        }
    }
    
    // If not part of a special pattern, use neighbor-based blending
    if (!isSpecial) {
        // Find the neighbor factor for this tile
        for (int i = 0; i < num_neighbors; i++) {
            if (approxEqual(v_tile_centroid, neighbor_centers[i])) {
                blend_factor = neighbor_factors[i];
                break;
            }
        }
        finalColor = blendColors(color1, color2, blend_factor);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}