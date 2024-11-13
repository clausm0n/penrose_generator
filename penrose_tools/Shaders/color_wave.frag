// color_wave.frag
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
    // Wave parameters
    float wave_speed = 0.0000002;
    float wave_length = 1.0;

    float base_direction = 3.14159265359 / 4.0; // pi/4
    float direction_change = 3.14159265359 / 2.0; // pi/2
    float tween_duration = 1000000.0; // milliseconds
    float time_factor = mod(time, tween_duration) / tween_duration;
    float wave_direction = base_direction + direction_change * sin(time_factor * 3.14159265359);

    // Compute angle and magnitude of tile_position
    float angle = atan(v_centroid.y, v_centroid.x);
    float magnitude = length(v_centroid);

    // Directional influence
    float directional_influence = cos(angle - wave_direction) * magnitude;

    // Phase
    float phase = wave_speed * time - directional_influence / wave_length;

    // Wave intensity
    float wave_intensity = (sin(phase) + 1.0) / 2.0;

    // Final color
    vec3 final_color = mix(color1, color2, wave_intensity);

    frag_color = vec4(final_color, 1.0);
}
