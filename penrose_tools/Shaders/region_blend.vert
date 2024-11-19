// region_blend.vert
#version 120

// Input attributes
attribute vec2 position;
attribute float tile_type;
attribute vec2 tile_centroid;

// Varying variables
varying float v_tile_type;
varying vec2 v_centroid;
varying float v_blend_factor;
varying float v_pattern_type;

// Uniforms
uniform sampler2D pattern_texture;
uniform int texture_width;
uniform int texture_height;

vec2 find_pattern_data(vec2 center_pos) {
    float epsilon = 0.00001;
    
    // Binary search through texture rows
    for (int y = 0; y < texture_height; y++) {
        for (int x = 0; x < texture_width; x++) {
            vec4 pattern_data = texture2D(pattern_texture, vec2(
                (float(x) + 0.5) / float(texture_width),
                (float(y) + 0.5) / float(texture_height)
            ));
            
            vec2 pattern_pos = pattern_data.xy;
            vec2 diff = abs(center_pos - pattern_pos);
            
            if (diff.x < epsilon && diff.y < epsilon) {
                return vec2(pattern_data.z, pattern_data.w);
            }
        }
    }
    
    return vec2(0.0, 0.5);
}

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_centroid = tile_centroid;
    v_tile_type = tile_type;
    
    vec2 pattern_data = find_pattern_data(tile_centroid);
    v_pattern_type = pattern_data.x;
    v_blend_factor = pattern_data.y;
}