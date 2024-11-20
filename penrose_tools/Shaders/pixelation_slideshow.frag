// pixelation_slideshow.frag
#version 140

// Inputs from vertex shader
in vec2 v_position;
in float v_tile_type;
in vec2 v_tile_centroid;

// Output
out vec4 fragColor;

// Uniforms
uniform sampler2D current_image;
uniform sampler2D next_image;
uniform float transition_progress;
uniform vec4 image_transform; // xy = scale, zw = offset

void main() {
    // Simple linear mapping from [-1,1] to [0,1]
    vec2 uv = (v_tile_centroid + 1.0) * 0.5;
    
    // Flip Y coordinate
    uv.y = 1.0 - uv.y;
    
    // Direct scale and offset without centering
    vec2 final_uv = uv * image_transform.xy + image_transform.zw;
    
    // Sample images
    vec4 current_sample = texture2D(current_image, final_uv);
    vec4 next_sample = texture2D(next_image, final_uv);
    
    // Simple linear interpolation for transition
    float t = clamp(transition_progress, 0.0, 1.0);
    vec4 final_color = mix(current_sample, next_sample, t);
    
    // Check bounds
    bool in_bounds = all(greaterThanEqual(final_uv, vec2(0.0))) && 
                    all(lessThanEqual(final_uv, vec2(1.0)));
    
    // Output color or black if out of bounds
    fragColor = in_bounds ? final_color : vec4(0.0, 0.0, 0.0, 1.0);
}