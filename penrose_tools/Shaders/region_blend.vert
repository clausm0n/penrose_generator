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

// Uniforms
uniform sampler2D pattern_texture;
uniform int texture_width;
uniform int texture_height;

vec2 find_pattern_data(vec2 center_pos) {
    vec2 tex_size = vec2(float(texture_width), float(texture_height));
    float epsilon = 0.001; // Increased epsilon for better floating point comparison
    
    for (int i = 0; i < texture_width * texture_height; i++) {
        int y = i / texture_width;
        int x = i % texture_width;
        
        vec2 tex_coord = vec2(
            (float(x) + 0.5) / tex_size.x,
            (float(y) + 0.5) / tex_size.y
        );
        
        vec4 pattern_data = texture2D(pattern_texture, tex_coord);
        vec2 pattern_pos = pattern_data.xy;
        
        if (abs(pattern_pos.x - center_pos.x) < epsilon && 
            abs(pattern_pos.y - center_pos.y) < epsilon) {
            return vec2(pattern_data.z, pattern_data.w);
        }
    }
    
    return vec2(0.0, 0.5); // Default values if no match found
}

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_centroid = tile_centroid;
    v_tile_type = tile_type;
    
    vec2 pattern_data = find_pattern_data(tile_centroid);
    v_pattern_type = pattern_data.x;
    v_blend_factor = pattern_data.y;
}