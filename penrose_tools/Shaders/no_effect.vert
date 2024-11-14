// no_effect.vert
#version 120

// Input attributes
attribute vec2 position;       // location=0
attribute float tile_type;     // location=1
attribute vec2 tile_centroid;  // location=2 - this matches ShaderManager's binding

// Varying variables
varying float v_tile_type;

void main() {
    // Pass through tile_type
    v_tile_type = tile_type;
    
    // We don't use tile_centroid but it must be declared 
    // to match the attribute binding in ShaderManager
    
    gl_Position = vec4(position, 0.0, 1.0);
}