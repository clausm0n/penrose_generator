// pixelation_slideshow.frag
#version 120

varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_tile_centroid;

uniform sampler2D current_image;
uniform sampler2D next_image;
uniform float transition_progress;
uniform vec4 image_transform; // xy = scale, zw = offset

void main() {
    // Convert from [-1,1] to [0,1] space
    vec2 uv = (v_tile_centroid + 1.0) * 0.5;
    
    // Apply scale and offset from the transform uniform
    vec2 scaled_uv = (uv - 0.5) * image_transform.xy + 0.5 + image_transform.zw;
    
    // Sample both images
    vec4 current_color = texture2D(current_image, scaled_uv);
    vec4 next_color = texture2D(next_image, scaled_uv);
    
    // Smooth transition
    float t = transition_progress;
    t = t * t * (3.0 - 2.0 * t);
    
    // Mix colors with black for out-of-bounds
    vec4 mixed_color = mix(current_color, next_color, t);
    bool in_bounds = scaled_uv.x >= 0.0 && scaled_uv.x <= 1.0 && 
                    scaled_uv.y >= 0.0 && scaled_uv.y <= 1.0;
    
    gl_FragColor = in_bounds ? mixed_color : vec4(0.0, 0.0, 0.0, 1.0);
}
