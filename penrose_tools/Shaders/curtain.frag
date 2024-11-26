// curtain.frag
#version 140

// Input from vertex shader
in float v_tile_type;
in vec2 v_position;

// Output color
out vec4 fragColor;

// Required uniforms (same as other shaders)
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    // Animation duration in seconds (matches ShaderManager.reveal_duration)
    float duration = 1.5;
    
    // Calculate animation progress
    float curtainPos = clamp(time / duration, 0.0, 1.0);
    
    // Get base color for the tile
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Calculate curtain effect - two curtains moving from center outward
    float leftEdge = smoothstep(-1.0, 0.0, v_position.x + curtainPos * 2.0);
    float rightEdge = smoothstep(1.0, 0.0, v_position.x - curtainPos * 2.0);
    float curtainMask = leftEdge * rightEdge;
    
    // Mix between black and tile color based on curtain position
    vec3 final_color = mix(vec3(0.0), base_color, curtainMask);
    
    fragColor = vec4(final_color, 1.0);
}