
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
    // Convert from [-1,1] to [0,1] space, flipping Y and maintaining aspect ratio
    vec2 uv = vec2(v_tile_centroid.x + 1.0, -v_tile_centroid.y + 1.0) * 0.5;
    
    // Center the UV coordinates before applying transformations
    vec2 centered_uv = uv - 0.5;
    
    // Apply aspect ratio correction and scaling
    centered_uv = centered_uv * image_transform.xy;
    
    // Move back to [0,1] range and apply offset
    vec2 final_uv = centered_uv + 0.5 + image_transform.zw;
    
    // Sample images directly (no gamma correction needed for PNG/JPG)
    vec4 current_color = texture2D(current_image, final_uv);
    vec4 next_color = texture2D(next_image, final_uv);
    
    // Smooth transition
    float t = clamp(transition_progress, 0.0, 1.0);
    t = smoothstep(0.0, 1.0, t);  // Smoothstep for easier easing
    
    // Mix colors directly
    vec4 mixed_color = mix(current_color, next_color, t);
    
    // Check bounds
    bool in_bounds = all(greaterThanEqual(final_uv, vec2(0.0))) && 
                    all(lessThanEqual(final_uv, vec2(1.0)));
    
    // Output final color
    fragColor = in_bounds ? mixed_color : vec4(0.0, 0.0, 0.0, 1.0);
}