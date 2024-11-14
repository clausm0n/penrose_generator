// pixelation_slideshow.frag
#version 120

varying vec2 v_position;
varying float v_tile_type;
varying vec2 v_centroid;

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
    // Convert centroid from [-1,1] to [0,1] UV space
    vec2 uv = (v_centroid + 1.0) * 0.5;
    
    // Apply image scale and offset
    uv = (uv - 0.5) * image_scale + 0.5 + image_offset;
    
    // Sample both images
    vec4 current_color = texture2D(current_image, uv);
    vec4 next_color = texture2D(next_image, uv);
    
    // Smooth interpolation using cubic function
    float progress = transition_progress;
    progress = progress * progress * (3.0 - 2.0 * progress);
    
    // Mix colors
    vec3 final_color = mix(current_color.rgb, next_color.rgb, progress);
    
    // Handle out-of-bounds UV coordinates by using tile colors
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        final_color = v_tile_type > 0.5 ? color1 : color2;
    }
    
    gl_FragColor = vec4(final_color, 1.0);
}