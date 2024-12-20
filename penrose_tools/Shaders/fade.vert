// fade.vert
attribute vec2 position;
varying vec2 v_texcoord;

void main() {
    gl_Position = vec4(position, 0.0, 1.0);
    v_texcoord = position * 0.5 + 0.5;  // Convert to texture coordinates
}