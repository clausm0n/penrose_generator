// raindrop_ripple.frag
#version 330 core

in float v_tile_type;
in vec2 v_centroid;
in vec2 v_tile_center;

uniform vec3 color1;
uniform vec3 color2;
uniform float time; // Time in milliseconds

const int MAX_RIPPLES = 5;
uniform vec2 ripple_centers[MAX_RIPPLES];
uniform float ripple_start_times[MAX_RIPPLES];

out vec4 frag_color;

void main()
{
    vec3 base_color = mix(color2, color1, v_tile_type);
    vec3 final_color = base_color;

    for(int i = 0; i < MAX_RIPPLES; i++)
    {
        // Compute elapsed time since ripple started
        float elapsed = time - ripple_start_times[i];
        if(elapsed <= 0.0)
            continue;

        // Convert elapsed time to seconds
        float elapsed_sec = elapsed / 1000.0;

        // Define ripple parameters
        float max_duration = 15.0; // seconds
        if(elapsed_sec > max_duration)
            continue;

        float radius = 25.0 * (1.0 - exp(-elapsed_sec / 5.0));
        float distance = length(v_centroid - ripple_centers[i]);

        if(distance <= radius)
        {
            float ripple_age = elapsed_sec;
            float ripple_intensity = exp(-ripple_age / 3.0);

            if(abs(distance - radius) < 5.0)
            {
                float edge_intensity = 1.0 - abs(distance - radius) / 5.0;
                final_color = mix(final_color, color2, edge_intensity * ripple_intensity);
            }
            else if(distance < 5.0)
            {
                final_color = mix(final_color, color2, ripple_intensity);
            }
            else
            {
                float color_intensity = (1.0 - distance / radius) * ripple_intensity * 0.5;
                final_color = mix(final_color, color2, color_intensity);
            }
        }
    }

    frag_color = vec4(final_color, 1.0);
}
