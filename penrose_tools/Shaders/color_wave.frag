// color_wave.frag
#version 120

// Constants
const float PI = 3.14159265359;
const float WAVE_SPEED = 0.0000002;
const float WAVE_LENGTH = 1.0;
const float BASE_DIRECTION = PI / 4.0;
const float DIRECTION_CHANGE = PI / 2.0;
const float TWEEN_DURATION = 1000000.0;

// Varying variables
varying float v_tile_type;
varying vec2 v_position;

// Uniform variables
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

float atan2(float y, float x) {
    return x == 0.0 ? sign(y) * PI / 2.0 : atan(y, x);
}

void main() {
    // Get base color based on tile type
    vec3 base_color = v_tile_type > 0.5 ? color1 : color2;
    
    // Calculate wave parameters
    float time_factor = mod(time * 1000.0, TWEEN_DURATION) / TWEEN_DURATION;
    float wave_direction = BASE_DIRECTION + DIRECTION_CHANGE * sin(time_factor * PI);
    
    // Calculate position angle and magnitude
    float pos_angle = atan2(v_position.y, v_position.x);
    float pos_magnitude = length(v_position) * 1000.0; // Scale up for more visible effect
    
    // Calculate directional influence
    float angle_diff = pos_angle - wave_direction;
    float directional_influence = cos(angle_diff) * pos_magnitude;
    
    // Calculate phase and wave intensity
    float phase = WAVE_SPEED * time * 1000.0 - directional_influence / WAVE_LENGTH;
    float wave_intensity = (sin(phase) + 1.0) * 0.5;
    
    // Interpolate between colors based on wave intensity
    vec3 final_color = mix(color1, color2, wave_intensity);
    
    gl_FragColor = vec4(final_color, 1.0);
}