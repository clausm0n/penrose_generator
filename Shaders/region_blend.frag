// region_blend.frag
#version 330 core

in float v_tile_type;
in vec2 v_centroid;
in vec2 v_tile_center;

uniform vec3 color1;
uniform vec3 color2;

out vec4 frag_color;

void main()
{
    // Placeholder blend_factor based on tile_type
    float blend_factor = v_tile_type * 0.5; // Example: blend_factor = 0.5 for kites, 0.0 for darts

    // Invert color for certain conditions (e.g., for kites)
    bool condition = (v_tile_type > 0.5);
    vec3 blended_color = mix(color2, color1, blend_factor);
    if(condition)
    {
        blended_color = vec3(1.0) - blended_color;
    }

    frag_color = vec4(blended_color, 1.0);
}
