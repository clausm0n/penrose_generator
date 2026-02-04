// procedural.vert
// Shared vertex shader for all procedural Penrose effects
// Simply renders a fullscreen quad
#version 140

in vec2 position;

out vec2 v_uv;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_uv = position * 0.5 + 0.5;
}

