// pixelation_slideshow.frag
#version 140

in vec2 v_position;
in float v_tile_type;
in vec2 v_tile_centroid;

out vec4 fragColor;

uniform sampler2D current_image;
uniform sampler2D next_image;
uniform float transition_progress;
uniform vec4 image_transform; // xy = scale, zw = offset

void main() {
    // Center UV coordinates before applying transformation
    vec2 centered_uv = (v_tile_centroid + 1.0) * 0.5;
    
    // Apply scaling relative to center
    vec2 scaled_uv = (centered_uv - 0.5) * image_transform.xy + 0.5;
    
    // Apply offset
    vec2 final_uv = scaled_uv + image_transform.zw;
    
    // Flip Y coordinate for OpenGL coordinate system
    final_uv.y = 1.0 - final_uv.y;
    
    // Sample images
    vec4 current_sample = texture2D(current_image, final_uv);
    vec4 next_sample = texture2D(next_image, final_uv);
    
    // Linear interpolation for transition
    float t = clamp(transition_progress, 0.0, 1.0);
    vec4 final_color = mix(current_sample, next_sample, t);
    
    // Check bounds
    bool in_bounds = all(greaterThanEqual(final_uv, vec2(0.0))) && 
                    all(lessThanEqual(final_uv, vec2(1.0)));
    
    fragColor = in_bounds ? final_color : vec4(0.0, 0.0, 0.0, 1.0);
}