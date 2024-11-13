// color_wave.frag
precision mediump float;
uniform vec3 color1;
uniform vec3 color2;
uniform float time;
uniform vec2 resolution;

varying float v_tile_type;
varying vec2 v_position;

void main() {
    vec2 center = vec2(0.0, 0.0);
    vec2 pos = v_position - center;
    
    float baseDirection = 3.14159 / 4.0;
    float directionChange = 3.14159 / 2.0;
    float tweenDuration = 1000000.0;
    float timeFactor = mod(time, tweenDuration) / tweenDuration;
    float waveDirection = baseDirection + directionChange * sin(timeFactor * 3.14159);
    
    float directionalInfluence = cos(atan(pos.y, pos.x) - waveDirection) * length(pos);
    float phase = 0.0000002 * time - directionalInfluence;
    
    float waveIntensity = (sin(phase) + 1.0) / 2.0;
    
    vec3 finalColor = mix(color1, color2, waveIntensity);
    gl_FragColor = vec4(finalColor, 1.0);
}