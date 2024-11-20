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
    // Convert from [-1,1] to [0,1] UV space, with Y flipped
    vec2 uv = (vec2(v_tile_centroid.x, -v_tile_centroid.y) + 1.0) * 0.5;
    
    // Center the UV coordinates before scaling
    vec2 centered_uv = uv - 0.5;
    
    // Apply scale and offset
    vec2 scaled_uv = (centered_uv * image_transform.xy) + 0.5 + image_transform.zw;
    
    // Sample images
    vec4 current_color = texture2D(current_image, scaled_uv);
    vec4 next_color = texture2D(next_image, scaled_uv);
    
    // Smooth transition using cubic interpolation
    float t = clamp(transition_progress, 0.0, 1.0);
    t = t * t * (3.0 - 2.0 * t);
    
    // Mix colors and handle out-of-bounds
    vec4 mixed_color = mix(current_color, next_color, t);
    bool in_bounds = all(greaterThanEqual(scaled_uv, vec2(0.0))) && 
                    all(lessThanEqual(scaled_uv, vec2(1.0)));
    
    // Output final color
    fragColor = in_bounds ? mixed_color : vec4(0.0, 0.0, 0.0, 1.0);
}