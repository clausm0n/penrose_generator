// tile_overlay.vert - Vertex shader for instanced tile quad overlay
// Each instance is a rhombus tile with 4 world-space corners and per-tile data
#version 140

// Per-vertex: unit quad corner [0,0] [1,0] [1,1] [0,1]
in vec2 a_corner;

// Per-instance: tile vertices in camera/pentagrid space (converted from ribbon via (rb - offset) / 2.5)
in vec2 a_v0;
in vec2 a_v1;
in vec2 a_v2;
in vec2 a_v3;

// Per-instance: tile data
in vec4 a_tile_data1; // is_kite, pattern_type, blend_factor, selected
in vec4 a_tile_data2; // hovered, anim_phase, anim_type, tile_id

// Uniforms
uniform vec2 u_camera;
uniform float u_zoom;
uniform float u_aspect; // width / height

// Outputs to fragment shader
out vec2 v_world_pos;
flat out vec2 v_v0;
flat out vec2 v_v1;
flat out vec2 v_v2;
flat out vec2 v_v3;
flat out vec4 v_tile_data1;
flat out vec4 v_tile_data2;

void main() {
    // Bilinear interpolation of tile corners using unit quad position
    vec2 world_pos = mix(
        mix(a_v0, a_v1, a_corner.x),
        mix(a_v3, a_v2, a_corner.x),
        a_corner.y
    );

    // World space -> clip space
    // Overlay vertices are in camera/pentagrid space (converted from ribbon space
    // in _pack_gpu_buffers via: p = (ribbon - shift_offset) / 2.5).
    // The procedural shader maps: p = clip * 0.5 * vec2(aspect, 1) * (3/zoom) + camera
    // Inverting: clip = (p - camera) * zoom / (1.5 * vec2(aspect, 1))
    vec2 clip;
    clip.x = (world_pos.x - u_camera.x) * u_zoom / (1.5 * u_aspect);
    clip.y = (world_pos.y - u_camera.y) * u_zoom / 1.5;

    gl_Position = vec4(clip, 0.0, 1.0);

    // Pass to fragment shader
    v_world_pos = world_pos;
    v_v0 = a_v0;
    v_v1 = a_v1;
    v_v2 = a_v2;
    v_v3 = a_v3;
    v_tile_data1 = a_tile_data1;
    v_tile_data2 = a_tile_data2;
}

