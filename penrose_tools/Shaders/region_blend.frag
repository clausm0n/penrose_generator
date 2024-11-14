
// region_blend.frag
#version 120
#extension GL_EXT_gpu_shader4 : enable

uniform vec3 color1;
uniform vec3 color2;
uniform sampler2D pattern_texture;
uniform vec2 texture_size;
uniform vec4 pattern_bounds;  // minX, minY, maxX, maxY in tile coordinate space

varying float v_tile_type;
varying vec2 v_tile_centroid;

const float EPSILON = 0.005;

vec3 blendColors(vec3 c1, vec3 c2, float factor) {
    return mix(c1, c2, factor);
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

vec4 findPattern() {
    // Convert centroid to normalized coordinates based on pattern bounds
    vec2 normalized = (v_tile_centroid - pattern_bounds.xy) / (pattern_bounds.zw - pattern_bounds.xy);
    return texture2D(pattern_texture, normalized);
}

void main() {
    vec4 pattern = findPattern();
    float pattern_type = pattern.r;
    float blend_factor = pattern.g;
    
    vec3 finalColor;
    if (pattern_type > 0.5 && pattern_type < 1.5) {
        // Star pattern
        finalColor = invertColor(blendColors(color1, color2, 0.3));
    }
    else if (pattern_type > 1.5) {
        // Starburst pattern
        finalColor = invertColor(blendColors(color1, color2, 0.7));
    }
    else {
        // Normal tile
        finalColor = blendColors(color1, color2, blend_factor);
    }
    
    gl_FragColor = vec4(finalColor, 1.0);
}