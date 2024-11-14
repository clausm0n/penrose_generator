// region_blend.frag
precision mediump float;

uniform vec3 color1;
uniform vec3 color2;

varying float v_tile_type;
varying vec2 v_tile_centroid;

// Function to create a pseudo-random value based on position
float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
}

void main() {
    vec3 baseColor;
    float blend_factor;
    
    // Simulate neighbor counting using position-based randomization
    float neighbor_random = random(v_tile_centroid);
    
    // Create regions by using distance from tile centroid
    float dist = length(v_tile_centroid);
    float region_factor = sin(dist * 10.0) * 0.5 + 0.5;
    
    // Combine random neighbor simulation with region factor
    blend_factor = mix(0.3, 0.7, region_factor * neighbor_random);
    
    // For kites (tile_type == 1.0), create star-like patterns
    if (v_tile_type > 0.5) {
        float star_pattern = step(0.8, sin(atan(v_tile_centroid.y, v_tile_centroid.x) * 5.0));
        if (star_pattern > 0.5) {
            // Invert colors for star pattern
            baseColor = vec3(1.0) - mix(color1, color2, blend_factor);
        } else {
            baseColor = mix(color1, color2, blend_factor);
        }
    } 
    // For darts (tile_type == 0.0), create starburst-like patterns
    else {
        float starburst_pattern = step(0.8, sin(atan(v_tile_centroid.y, v_tile_centroid.x) * 10.0));
        if (starburst_pattern > 0.5) {
            // Invert colors for starburst pattern
            baseColor = vec3(1.0) - mix(color1, color2, blend_factor);
        } else {
            baseColor = mix(color1, color2, blend_factor);
        }
    }
    
    gl_FragColor = vec4(baseColor, 1.0);
}