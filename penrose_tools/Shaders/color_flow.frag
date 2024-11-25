// color_flow.frag
#version 140

// Input from vertex shader
in float v_tile_type;
in vec2 v_centroid;

// Output color
out vec4 fragColor;

// Uniforms
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

void main() {
    // Convert time to milliseconds and normalize
    float time_ms = time * 1000.0;
    
    // Wave parameters
    float wave_speed = 0.000012;
    float wave_length = 1.0;
    float base_direction = 3.14159 / 4.0;  // pi/4
    float direction_change = 3.14159 / 2.0; // pi/2
    float tween_duration = 1000000.0;
    
    // Calculate time factor for direction change
    float time_factor = mod(time_ms, tween_duration) / tween_duration;
    
    // Calculate wave direction
    float wave_direction = base_direction + direction_change * sin(time_factor * 3.14159);
    
    // Calculate directional influence based on tile position
    float tile_angle = atan(v_centroid.y, v_centroid.x);
    float tile_distance = length(v_centroid);
    float directional_influence = cos(tile_angle - wave_direction) * tile_distance;
    
    // Calculate phase and wave intensity
    float phase = wave_speed * time_ms - directional_influence / wave_length;
    float wave_intensity = (sin(phase) + 1.0) / 2.0;
    
    // Interpolate between colors based on wave intensity
    vec3 final_color = mix(color1, color2, wave_intensity);
    
    // Output final color
    fragColor = vec4(final_color, 1.0);
}