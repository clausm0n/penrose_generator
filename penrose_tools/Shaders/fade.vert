// fade.vert
#version 140

in vec2 position;
out vec2 v_texcoord;

uniform float vertex_offset;

void main() {
    vec2 direction = position - vec2(0.0, 0.0);  // Use origin for fade effect
    vec2 offset = normalize(direction) * vertex_offset;
    gl_Position = vec4(position + offset, 0.0, 1.0);
    v_texcoord = position * 0.5 + 0.5;  // Convert to texture coordinates
}