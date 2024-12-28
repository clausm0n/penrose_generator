#version 140

in vec2 v_position;
in float v_tile_type;
in vec2 v_tile_centroid;
in float v_is_edge;

out vec4 fragColor;

uniform sampler2D current_image;
uniform sampler2D next_image;
uniform float transition_progress;
uniform vec4 image_transform;

vec4 sharpenSample(sampler2D tex, vec2 uv) {
    float offset = 0.001;
    vec4 center = texture2D(tex, uv);
    vec4 up = texture2D(tex, uv + vec2(0.0, offset));
    vec4 down = texture2D(tex, uv + vec2(0.0, -offset));
    vec4 left = texture2D(tex, uv + vec2(-offset, 0.0));
    vec4 right = texture2D(tex, uv + vec2(offset, 0.0));
    
    float strength = 1.0;
    return center * (1.0 + 4.0 * strength) - (up + down + left + right) * strength;
}

void main() {
    // If this is an edge, render solid black.
    if (v_is_edge > 0.5) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    vec2 centered_uv = (v_tile_centroid + 1.0) * 0.5;
    vec2 scaled_uv = (centered_uv - 0.5) * image_transform.xy + 0.5;
    vec2 final_uv = scaled_uv + image_transform.zw;
    final_uv.y = 1.0 - final_uv.y;

    vec4 current_sample = sharpenSample(current_image, final_uv);
    vec4 next_sample = sharpenSample(next_image, final_uv);

    float t = clamp(transition_progress, 0.0, 1.0);
    vec4 final_color = mix(current_sample, next_sample, t);

    bool in_bounds = all(greaterThanEqual(final_uv, vec2(0.0))) &&
                     all(lessThanEqual(final_uv, vec2(1.0)));

    fragColor = in_bounds ? clamp(final_color, 0.0, 1.0) : vec4(0.0, 0.0, 0.0, 1.0);
}