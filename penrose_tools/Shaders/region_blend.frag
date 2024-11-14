// region_blend.frag
#version 120

uniform vec3 color1;
uniform vec3 color2;
uniform vec2 tile_centers[1000];     // Adjust max size as needed
uniform float pattern_types[1000];   // 0: normal, 1: star, 2: starburst
uniform float blend_factors[1000];   // Base blend factor from neighbors
uniform float special_blends[1000];  // Special blend factors for patterns
uniform int num_tiles;

varying float v_tile_type;
varying vec2 v_tile_centroid;

const float EPSILON = 0.01;

vec3 blendColors(vec3 c1, vec3 c2, float factor) {
    return mix(c1, c2, factor);
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

void main() {
    vec3 finalColor;
    bool found = false;
    
    // Find this tile's pattern info
    for (int i = 0; i < num_tiles && i < 1000; i++) {
        if (distance(v_tile_centroid, tile_centers[i]) < EPSILON) {
            float pattern = pattern_types[i];
            float blend = blend_factors[i];
            float special = special_blends[i];
            
            if (pattern == 1.0) {  // Star pattern
                finalColor = invertColor(blendColors(color1, color2, special));
            }
            else if (pattern == 2.0) {  // Starburst pattern
                finalColor = invertColor(blendColors(color1, color2, special));
            }
            else {  // Normal tile
                finalColor = blendColors(color1, color2, blend);
            }
            found = true;
            break;
        }
    }
    
    // Fallback if tile not found
    if (!found) {
        finalColor = blendColors(color1, color2, 0.5);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}