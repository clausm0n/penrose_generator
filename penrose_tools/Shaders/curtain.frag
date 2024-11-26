// curtain.frag
#version 140

// Input from vertex shader
in float v_tile_type;
in vec2 v_position;

// Output color
out vec4 fragColor;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    // Animation duration in seconds
    float duration = 1.5;
    
    // Calculate curtain position based on time
    float curtainPos = clamp(time / duration, 0.0, 1.0);
    
    // Create two curtains moving from center to edges
    float leftCurtain = smoothstep(-1.0, -0.5, v_position.x + curtainPos * 2.0);
    float rightCurtain = smoothstep(1.0, 0.5, v_position.x - curtainPos * 2.0);
    
    // Combine curtains with a slight overlap in the middle
    float curtainMask = leftCurtain * rightCurtain;
    
    // Get base color for the tile
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Mix between black and the base color based on the curtain mask
    vec3 final_color = mix(vec3(0.0), base_color, curtainMask);
    
    fragColor = vec4(final_color, 1.0);
}