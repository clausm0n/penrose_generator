// pixelation_slideshow.frag
#version 120

varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_tile_centroid;

uniform vec3 color1;
uniform vec3 color2;
uniform float time;

// Image data uniforms
uniform sampler2D current_image;
uniform sampler2D next_image;
uniform float transition_progress;
uniform vec2 image_scale;
uniform vec2 image_offset;

void main() {
    // Convert tile centroid from [-1,1] to [0,1] UV space
    vec2 uv = (v_tile_centroid + 1.0) * 0.5;
    
    // Scale and offset the UV coordinates to match the image aspect ratio
    vec2 scaled_uv = uv;
    scaled_uv = (scaled_uv - 0.5) / image_scale + 0.5;
    scaled_uv = scaled_uv - image_offset;
    
    // Sample both images
    vec4 current_color = texture2D(current_image, scaled_uv);
    vec4 next_color = texture2D(next_image, scaled_uv);
    
    // Use base tile colors if UV coordinates are out of bounds
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Check if UV coordinates are within valid range
    bool valid_uv = scaled_uv.x >= 0.0 && scaled_uv.x <= 1.0 && 
                    scaled_uv.y >= 0.0 && scaled_uv.y <= 1.0;
    
    // Calculate smooth transition progress
    float smooth_progress = transition_progress * transition_progress * (3.0 - 2.0 * transition_progress);
    
    // Mix colors based on transition progress
    vec3 image_color = mix(current_color.rgb, next_color.rgb, smooth_progress);
    
    // Use image color if UV is valid, otherwise use base tile color
    vec3 final_color = valid_uv ? image_color : base_color;
    
    gl_FragColor = vec4(final_color, 1.0);
}