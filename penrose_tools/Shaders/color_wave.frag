// color_wave.frag
#version 120

// Constants
const float PI = 3.14159265359;
const float WAVE_SPEED = 0.0000002;
const float WAVE_LENGTH = 1.0;
const float BASE_DIRECTION = 0.785398;  // PI/4
const float DIRECTION_CHANGE = 1.570796;  // PI/2
const float TWEEN_DURATION = 1000000.0;

// Varying variables
varying float v_tile_type;
varying vec2 v_position;

// Uniform variables
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

float atan2(float y, float x) {
    if (x == 0.0) {
        return sign(y) * PI/2.0;
    }
    return atan(y, x);
}

void main() {
    // Calculate the wave parameters
    float ms_time = time * 1000.0;  // Convert to milliseconds
    
    // Calculate time factor exactly like Python version
    float time_factor = mod(ms_time, TWEEN_DURATION) / TWEEN_DURATION;
    
    // Calculate wave direction
    float wave_direction = BASE_DIRECTION + DIRECTION_CHANGE * sin(time_factor * PI);
    
    // Calculate position angle in radians
    float pos_angle = atan2(v_position.y, v_position.x);
    float position_magnitude = length(v_position);
    
    // Calculate directional influence exactly like Python
    float directional_influence = cos(pos_angle - wave_direction) * position_magnitude;
    
    // Calculate phase
    float phase = WAVE_SPEED * ms_time - directional_influence / WAVE_LENGTH;
    
    // Calculate wave intensity
    float wave_intensity = (sin(phase) + 1.0) * 0.5;
    
    // Interpolate between colors
    vec3 final_color = color1 * (1.0 - wave_intensity) + color2 * wave_intensity;
    
    gl_FragColor = vec4(final_color, 1.0);
}