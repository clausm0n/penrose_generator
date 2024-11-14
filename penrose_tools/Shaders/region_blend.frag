// region_blend.frag
#version 120
#extension GL_EXT_gpu_shader4 : enable

uniform vec3 color1;
uniform vec3 color2;
uniform sampler2D pattern_texture;  // Using 2D texture to store pattern data
uniform vec2 texture_size;          // Width and height of the texture

varying float v_tile_type;
varying vec2 v_tile_centroid;

const float EPSILON = 0.005;

vec3 blendColors(vec3 c1, vec3 c2, float factor) {
    return mix(c1, c2, factor);
}

vec3 invertColor(vec3 color) {
    return vec3(1.0) - color;
}

// Find pattern data in texture
vec4 findPattern() {
    // Convert centroid position to texture coordinates
    vec2 texCoord = (v_tile_centroid + 1.0) * 0.5;
    return texture2D(pattern_texture, texCoord);
}

void main() {
    vec4 pattern = findPattern();
    float pattern_type = pattern.r;  // Pattern type stored in red channel
    float blend_factor = pattern.g;  // Blend factor stored in green channel
    
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
