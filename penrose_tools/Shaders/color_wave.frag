// color_wave.frag
#version 140

// Constants
const float PI = 3.14159265359;
const float WAVE_SPEED = 0.0000002;
const float WAVE_LENGTH = 1.0;
const float BASE_DIRECTION = 0.785398;  // PI/4
const float DIRECTION_CHANGE = 1.570796;  // PI/2
const float TWEEN_DURATION = 1000000.0;

// Inputs from vertex shader
in float v_tile_type;
in vec2 v_position;
in float v_is_edge;

// Output color
out vec4 fragColor;

// Uniforms
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
    // If this is an edge, render solid black.
    if (v_is_edge > 0.5) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    // Normal color_wave logic
    float ms_time = time * 1000.0;
    float time_factor = mod(ms_time, TWEEN_DURATION) / TWEEN_DURATION;
    float wave_direction = BASE_DIRECTION + DIRECTION_CHANGE * sin(time_factor * PI);

    float pos_angle = atan2(v_position.y, v_position.x);
    float position_magnitude = length(v_position);
    float directional_influence = cos(pos_angle - wave_direction) * position_magnitude;
    float phase = WAVE_SPEED * ms_time - directional_influence / WAVE_LENGTH;
    float wave_intensity = (sin(phase) + 1.0) * 0.5;

    vec3 final_color = mix(color1, color2, wave_intensity);
    fragColor = vec4(final_color, 1.0);
}