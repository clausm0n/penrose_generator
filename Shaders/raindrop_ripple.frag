#version 120
uniform vec3 color1;
uniform vec3 color2;
uniform float time;

const int MAX_RIPPLES = 5;
uniform vec2 ripple_centers[MAX_RIPPLES];
uniform float ripple_start_times[MAX_RIPPLES];

varying vec2 v_tile_center;
varying float v_tile_type;

void main() {
    vec3 base_color = mix(color2, color1, v_tile_type);
    float ripple_effect = 0.0;

    for (int i = 0; i < MAX_RIPPLES; i++) {
        float ripple_age = (time - ripple_start_times[i]) / 1000.0;
        if (ripple_age < 0.0 || ripple_age > 15.0) continue;

        float radius = 25.0 * (1.0 - exp(-ripple_age / 5.0));
        float distance = length(v_tile_center - ripple_centers[i]);

        if (distance <= radius) {
            float ripple_intensity = exp(-ripple_age / 3.0);
            if (abs(distance - radius) < 5.0) {
                float edge_intensity = 1.0 - abs(distance - radius) / 5.0;
                ripple_effect += edge_intensity * ripple_intensity;
            } else if (distance < 5.0) {
                ripple_effect += ripple_intensity;
            } else {
                float color_intensity = (1.0 - distance / radius) * ripple_intensity * 0.5;
                ripple_effect += color_intensity;
            }
        }
    }

    ripple_effect = clamp(ripple_effect, 0.0, 1.0);
    vec3 color = mix(base_color, color2, ripple_effect);
    gl_FragColor = vec4(color, 1.0);
}
