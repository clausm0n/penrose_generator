// curtain.frag
#version 140

// Input from vertex shader
in float v_tile_type;
in vec2 v_position;

// Output color
out vec4 fragColor;

// Required uniforms
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    // Animation duration in seconds
    float duration = 1.5;
    
    // Calculate animation progress
    float curtainPos = clamp(time / duration, 0.0, 1.0);
    
    // Get base color for the tile based on type
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Calculate curtain effect with easing
    float t = curtainPos;
    t = t * t * (3.0 - 2.0 * t);  // Smooth step easing
    
    float leftCurtain = smoothstep(-1.0, -0.5, v_position.x + 2.0 * t);
    float rightCurtain = smoothstep(1.0, 0.5, v_position.x - 2.0 * t);
    float curtainMask = leftCurtain * rightCurtain;
    
    // Mix between black and the base color
    vec3 final_color = mix(vec3(0.0), base_color, curtainMask);
    
    fragColor = vec4(final_color, 1.0);
}