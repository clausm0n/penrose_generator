// pixelation_slideshow.frag
#version 330 core

in float v_tile_type;
in vec2 v_centroid;
in vec2 v_tile_center;

uniform vec3 color1;
uniform vec3 color2;
uniform float time; // Time in milliseconds

out vec4 frag_color;

void main()
{
    // Transition duration in seconds
    float transition_duration = 5.0;
    
    // Calculate progress based on time
    float progress = mod(time / 1000.0, transition_duration * 2.0);
    if (progress > transition_duration)
        progress = transition_duration * 2.0 - progress;
    
    // Smooth interpolation using smoothstep-like function
    progress = progress * progress * (3.0 - 2.0 * progress);
    
    vec3 color = mix(color1, color2, progress);
    frag_color = vec4(color, 1.0);
}
