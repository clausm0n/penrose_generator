// region_blend.vert
#version 140

// Input attributes
in vec2 position;
in float tile_type;
in vec2 tile_centroid;

// Output to fragment shader
out float v_tile_type;
out vec2 v_centroid;
out float v_blend_factor;
out float v_pattern_type;
out float v_is_edge;

// Uniforms
uniform sampler2D pattern_texture;
uniform int texture_width;
uniform int texture_height;
uniform float vertex_offset;

vec2 find_pattern_data(vec2 center_pos) {
    vec2 tex_size = vec2(float(texture_width), float(texture_height));
    float epsilon = 0.001;
    
    // Debug: Check texture dimensions
    if (texture_width <= 0 || texture_height <= 0) {
        return vec2(0.0, tile_type > 0.5 ? 1.0 : 0.0);
    }
    
    for (int i = 0; i < texture_width * texture_height; i++) {
        int y = i / texture_width;
        int x = i % texture_width;
        
        if (y >= texture_height || x >= texture_width) continue;
        
        vec2 tex_coord = vec2(
            (float(x) + 0.5) / float(texture_width),
            (float(y) + 0.5) / float(texture_height)
        );
        
        vec4 pattern_data = texture2D(pattern_texture, tex_coord);
        vec2 pattern_pos = pattern_data.xy;
        
        if (distance(pattern_pos, center_pos) < epsilon) {
            return vec2(pattern_data.z, pattern_data.w);
        }
    }
    
    return vec2(0.0, tile_type > 0.5 ? 1.0 : 0.0);
}

void main() {
    vec2 direction = position - tile_centroid;
    vec2 offset = normalize(direction) * vertex_offset;
    gl_Position = vec4(position + offset, 0.0, 1.0);

    v_tile_type = tile_type;
    v_centroid = tile_centroid;
    
    // Look up pattern data for region logic
    vec2 pattern_data = find_pattern_data(tile_centroid);
    v_pattern_type = pattern_data.x;
    v_blend_factor = pattern_data.y;

    // Mark edges
    v_is_edge = (tile_type == 0.0 && tile_centroid == vec2(0.0, 0.0)) ? 1.0 : 0.0;
}
