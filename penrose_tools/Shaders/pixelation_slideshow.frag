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
    // Convert from [-1,1] to [0,1] space, maintaining Y orientation
    vec2 uv = vec2(v_tile_centroid.x + 1.0, -v_tile_centroid.y + 1.0) * 0.5;
    
    // Apply scaling and offset transformation
    vec2 scaled_uv = (uv - 0.5) * image_transform.xy + 0.5;
    scaled_uv += image_transform.zw;
    
    // Sample images with gamma correction
    vec4 current_color = pow(texture2D(current_image, scaled_uv), vec4(2.2));
    vec4 next_color = pow(texture2D(next_image, scaled_uv), vec4(2.2));
    
    // Smooth transition using cubic interpolation
    float t = clamp(transition_progress, 0.0, 1.0);
    t = t * t * (3.0 - 2.0 * t);  // Smoothstep
    
    // Mix colors with gamma correction
    vec4 mixed_color = mix(current_color, next_color, t);
    
    // Convert back from linear to sRGB space
    mixed_color = pow(mixed_color, vec4(1.0/2.2));
    
    // Check bounds
    bool in_bounds = all(greaterThanEqual(scaled_uv, vec2(0.0))) && 
                    all(lessThanEqual(scaled_uv, vec2(1.0)));
    
    // Output final color
    fragColor = in_bounds ? mixed_color : vec4(0.0, 0.0, 0.0, 1.0);
}