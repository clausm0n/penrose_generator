// pong.frag - Pong game on Penrose tiles with depth-camera paddle control
// Two paddles on left/right controlled by depth Y-position of each half.
// When no depth motion, the game plays itself with simple AI.
#version 140

in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;
uniform vec2 u_camera;
uniform float u_zoom;
uniform float u_time;
uniform vec3 u_color1;
uniform vec3 u_color2;
uniform float u_edge_thickness;
uniform float u_gamma[5];

// Depth camera uniforms
uniform sampler2D u_depth_texture;
uniform float u_depth_enabled;
uniform float u_depth_coverage;
uniform vec2 u_depth_centroid;
uniform float u_depth_motion;

// Pong-specific depth uniforms: paddle Y positions from depth data (0=bottom, 1=top)
uniform float u_depth_left_y;   // Y centroid of left half of depth frame
uniform float u_depth_right_y;  // Y centroid of right half of depth frame

#include "pentagrid_common.glsl"

// ---------------------------------------------------------------
// Pong game simulation (deterministic from time)
// ---------------------------------------------------------------

// Hash for deterministic ball resets
float hashTime(float t) {
    return fract(sin(t * 127.1 + 311.7) * 43758.5453);
}

// Simulate pong ball state at time t
// Uses a fixed-step simulation: ball bounces off top/bottom walls and paddles.
// Returns: vec4(ballX, ballY, velX, velY) in normalized [-1,1] court space
// Court: x in [-1, 1], y in [-0.7, 0.7]
// Paddles at x = -0.9 (left), x = 0.9 (right)

struct PongState {
    vec2 ballPos;
    vec2 ballVel;
    float leftPaddleY;
    float rightPaddleY;
    int leftScore;
    int rightScore;
};

// Simple AI: move paddle toward ball with limited speed
float aiPaddle(float paddleY, float ballY, float speed) {
    float diff = ballY - paddleY;
    return paddleY + clamp(diff, -speed, speed);
}

PongState simulatePong(float time, float leftInput, float rightInput, float motionBlend) {
    PongState state;

    // Court dimensions (normalized)
    float courtTop = 0.7;
    float courtBottom = -0.7;
    float paddleX_left = -0.88;
    float paddleX_right = 0.88;
    float paddleHalfH = 0.12;

    // Fixed simulation step
    float dt = 1.0 / 60.0;

    // Initialize
    float ballX = 0.0;
    float ballY = 0.0;
    float seed = 0.0;
    float angle = hashTime(seed) * 1.2 - 0.6;
    float side = hashTime(seed + 5.0) > 0.5 ? 1.0 : -1.0;
    float speed = 0.8;
    float velX = cos(angle) * speed * side;
    float velY = sin(angle) * speed;
    float leftPY = 0.0;
    float rightPY = 0.0;
    int leftScore = 0;
    int rightScore = 0;

    // Simulate forward in time
    // Use a fixed-step simulation; game runs continuously and resets
    // only when a side scores 10 points.
    float gameTime = time;
    int steps = int(gameTime / dt);
    steps = min(steps, 3600); // cap at 60s worth of steps

    for (int i = 0; i < 3600; i++) {
        if (i >= steps) break;

        // AI paddle positions (used when no depth motion)
        float aiLeftY = aiPaddle(leftPY, ballY, dt * 1.2);
        float aiRightY = aiPaddle(rightPY, ballY, dt * 1.2);

        // Map depth input (0-1) to court coords (-0.7 to 0.7)
        // Invert: depth Y=1 (top of camera) -> court top, Y=0 -> court bottom
        float depthLeftY = (0.5 - leftInput) * 1.4;
        float depthRightY = (0.5 - rightInput) * 1.4;

        // Blend between AI and depth control
        leftPY = mix(aiLeftY, depthLeftY, motionBlend);
        rightPY = mix(aiRightY, depthRightY, motionBlend);

        // Clamp paddles to court
        leftPY = clamp(leftPY, courtBottom + paddleHalfH, courtTop - paddleHalfH);
        rightPY = clamp(rightPY, courtBottom + paddleHalfH, courtTop - paddleHalfH);

        // Move ball
        ballX += velX * dt;
        ballY += velY * dt;

        // Bounce off top/bottom
        if (ballY > courtTop) {
            ballY = courtTop - (ballY - courtTop);
            velY = -abs(velY);
        }
        if (ballY < courtBottom) {
            ballY = courtBottom + (courtBottom - ballY);
            velY = abs(velY);
        }

        // Left paddle collision
        if (ballX < paddleX_left + 0.04 && ballX > paddleX_left - 0.02 && velX < 0.0) {
            if (abs(ballY - leftPY) < paddleHalfH) {
                ballX = paddleX_left + 0.04;
                velX = abs(velX) * 1.05; // speed up slightly
                // Add angle based on where ball hit the paddle
                float hitPos = (ballY - leftPY) / paddleHalfH;
                velY += hitPos * 0.4;
                speed = length(vec2(velX, velY));
                if (speed > 2.5) {
                    velX = velX / speed * 2.5;
                    velY = velY / speed * 2.5;
                }
            }
        }

        // Right paddle collision
        if (ballX > paddleX_right - 0.04 && ballX < paddleX_right + 0.02 && velX > 0.0) {
            if (abs(ballY - rightPY) < paddleHalfH) {
                ballX = paddleX_right - 0.04;
                velX = -abs(velX) * 1.05;
                float hitPos = (ballY - rightPY) / paddleHalfH;
                velY += hitPos * 0.4;
                speed = length(vec2(velX, velY));
                if (speed > 2.5) {
                    velX = velX / speed * 2.5;
                    velY = velY / speed * 2.5;
                }
            }
        }

        // Score: ball exits left or right
        if (ballX < -1.1) {
            rightScore++;
            // Reset ball
            seed += 1.0;
            angle = hashTime(seed) * 1.2 - 0.6;
            speed = 0.8;
            velX = cos(angle) * speed;
            velY = sin(angle) * speed;
            ballX = 0.0;
            ballY = 0.0;
        }
        if (ballX > 1.1) {
            leftScore++;
            seed += 1.0;
            angle = hashTime(seed) * 1.2 - 0.6;
            speed = 0.8;
            velX = -cos(angle) * speed;
            velY = sin(angle) * speed;
            ballX = 0.0;
            ballY = 0.0;
        }

        // Full game reset when either side reaches 10 points
        if (leftScore >= 10 || rightScore >= 10) {
            leftScore = 0;
            rightScore = 0;
            seed += 10.0;
            angle = hashTime(seed) * 1.2 - 0.6;
            speed = 0.8;
            float resetSide = hashTime(seed + 5.0) > 0.5 ? 1.0 : -1.0;
            velX = cos(angle) * speed * resetSide;
            velY = sin(angle) * speed;
            ballX = 0.0;
            ballY = 0.0;
        }
    }

    state.ballPos = vec2(ballX, ballY);
    state.ballVel = vec2(velX, velY);
    state.leftPaddleY = leftPY;
    state.rightPaddleY = rightPY;
    state.leftScore = leftScore;
    state.rightScore = rightScore;

    return state;
}

// ---------------------------------------------------------------
// Digit rendering for score display (simple 3x5 bitmap font)
// ---------------------------------------------------------------
// Each digit is a 3x5 grid encoded as 15 bits
// Bit layout: row 0 (top) bits 0-2, row 1 bits 3-5, ... row 4 bits 12-14
int digitBits[10] = int[10](
    0x7B6F, // 0: 111 101 101 101 111
    0x2492, // 1: 010 010 010 010 010
    0x73E7, // 2: 111 001 111 100 111
    0x73CF, // 3: 111 001 111 001 111
    0x5BC9, // 4: 101 101 111 001 001
    0x79CF, // 5: 111 100 111 001 111
    0x79EF, // 6: 111 100 111 101 111
    0x7249, // 7: 111 001 001 001 001
    0x7BEF, // 8: 111 101 111 101 111
    0x7BCF  // 9: 111 101 111 001 111
);

float renderDigit(vec2 p, int digit, vec2 pos, float size) {
    vec2 local = (p - pos) / size;
    if (local.x < 0.0 || local.x > 3.0 || local.y < 0.0 || local.y > 5.0) return 0.0;
    int col = int(local.x);
    int row = 4 - int(local.y); // flip Y
    if (col > 2 || row > 4 || col < 0 || row < 0) return 0.0;
    int bitIndex = row * 3 + col;
    int bits = digitBits[digit % 10];
    return ((bits >> bitIndex) & 1) == 1 ? 1.0 : 0.0;
}

float renderScore(vec2 p, int score, vec2 pos, float size) {
    score = min(score, 99);
    int tens = score / 10;
    int ones = score - tens * 10;
    float d = 0.0;
    if (tens > 0) {
        d += renderDigit(p, tens, pos - vec2(size * 2.0, 0.0), size);
    }
    d += renderDigit(p, ones, pos, size);
    return d;
}

// ---------------------------------------------------------------
// SDF helpers for pong elements
// ---------------------------------------------------------------

// Rounded rectangle SDF
float sdRoundBox(vec2 p, vec2 center, vec2 halfSize, float radius) {
    vec2 d = abs(p - center) - halfSize + vec2(radius);
    return length(max(d, vec2(0.0))) + min(max(d.x, d.y), 0.0) - radius;
}

// Circle SDF
float sdCircle(vec2 p, vec2 center, float radius) {
    return length(p - center) - radius;
}

void main() {
    // --- Standard pentagrid tile lookup ---
    vec2 uv = v_uv - 0.5;
    uv.x *= u_resolution.x / u_resolution.y;

    float gSc = 3.0 / u_zoom;
    vec2 p = uv * gSc + u_camera;

    float gamma[5];
    for (int i = 0; i < 5; i++) gamma[i] = u_gamma[i];

    TileData tile = findTile(p, gamma);

    if (!tile.found) {
        fragColor = vec4(0.02, 0.02, 0.05, 1.0);
        return;
    }

    // --- Coordinate mapping ---
    float aspect = u_resolution.x / u_resolution.y;
    float viewW = gSc * aspect;
    float viewH = gSc;
    float rbScale = float(PN) / 2.0;

    // Court center in rb_p space
    vec2 courtCenter = vec2(0.0);
    for (int k = 0; k < PN; k++) {
        courtCenter += grid[k] * (dot(u_camera, grid[k]) + shift[k]);
    }

    // Scale: map normalized court coords to rb_p space
    float courtScale = min(viewW, viewH) * 0.45 * rbScale;

    vec2 tc = tile.center;
    // Tile position in normalized court coords (-1 to 1)
    vec2 courtPos = (tc - courtCenter) / courtScale;

    // --- Simulate game ---
    float motion = 0.0;
    float leftInput = 0.5;
    float rightInput = 0.5;
    if (u_depth_enabled >= 0.5) {
        motion = clamp(u_depth_motion, 0.0, 1.0);
        leftInput = u_depth_left_y;
        rightInput = u_depth_right_y;
    }

    PongState game = simulatePong(u_time, leftInput, rightInput, motion);

    // --- Draw game elements ---
    // All positions in normalized court space

    // Court boundaries
    float courtTop = 0.7;
    float courtBottom = -0.7;
    float courtLeft = -1.0;
    float courtRight = 1.0;
    float paddleHalfH = 0.12;
    float paddleHalfW = 0.025;
    float ballRadius = 0.025;

    // Distance to court boundary (top and bottom walls)
    float wallThickness = 0.02;
    float dTopWall = abs(courtPos.y - courtTop) - wallThickness;
    float dBottomWall = abs(courtPos.y - courtBottom) - wallThickness;
    float dWalls = min(dTopWall, dBottomWall);

    // Center line (dashed)
    float dCenterLine = abs(courtPos.x);
    float dashPattern = step(0.5, fract(courtPos.y * 5.0));
    float centerLine = step(dCenterLine, 0.015) * dashPattern;
    // Only show center line within court
    centerLine *= step(courtBottom, courtPos.y) * step(courtPos.y, courtTop);

    // Left paddle
    float dLeftPaddle = sdRoundBox(courtPos,
        vec2(-0.88, game.leftPaddleY),
        vec2(paddleHalfW, paddleHalfH),
        0.01);

    // Right paddle
    float dRightPaddle = sdRoundBox(courtPos,
        vec2(0.88, game.rightPaddleY),
        vec2(paddleHalfW, paddleHalfH),
        0.01);

    // Ball
    float dBall = sdCircle(courtPos, game.ballPos, ballRadius);

    // Ball trail (motion blur effect)
    vec2 trailDir = normalize(game.ballVel);
    float trailLen = length(game.ballVel) * 0.05;
    float dTrail = 1e10;
    for (int i = 1; i <= 3; i++) {
        vec2 trailPos = game.ballPos - trailDir * trailLen * float(i);
        float r = ballRadius * (1.0 - float(i) * 0.25);
        dTrail = min(dTrail, sdCircle(courtPos, trailPos, r));
    }

    // --- Color assignment ---
    // Blend width for smooth tile transitions
    float blendW = 0.03;

    // Background: dark court
    vec3 bgColor = mix(u_color1, u_color2, 0.5) * 0.05;
    // Court area slightly lighter
    float inCourt = step(courtBottom - 0.05, courtPos.y)
                  * step(courtPos.y, courtTop + 0.05)
                  * step(-1.05, courtPos.x)
                  * step(courtPos.x, 1.05);
    vec3 courtColor = mix(u_color1, u_color2, 0.5) * 0.08;

    vec3 tileColor = mix(bgColor, courtColor, inCourt);

    // Walls
    float wallBlend = smoothstep(blendW, -blendW, dWalls);
    vec3 wallColor = mix(u_color1, u_color2, 0.5) * 0.4;
    tileColor = mix(tileColor, wallColor, wallBlend * inCourt);

    // Center line
    tileColor = mix(tileColor, wallColor * 0.7, centerLine * 0.5);

    // Left paddle - color1
    float leftPaddleBlend = smoothstep(blendW, -blendW, dLeftPaddle);
    tileColor = mix(tileColor, u_color1, leftPaddleBlend);

    // Right paddle - color2
    float rightPaddleBlend = smoothstep(blendW, -blendW, dRightPaddle);
    tileColor = mix(tileColor, u_color2, rightPaddleBlend);

    // Ball trail
    float trailBlend = smoothstep(blendW * 2.0, -blendW, dTrail);
    vec3 trailColor = mix(u_color1, u_color2, 0.5) * 0.5;
    tileColor = mix(tileColor, trailColor, trailBlend * 0.4);

    // Ball - bright white/mixed
    float ballBlend = smoothstep(blendW, -blendW, dBall);
    vec3 ballColor = (u_color1 + u_color2) * 0.5 + vec3(0.3);
    tileColor = mix(tileColor, ballColor, ballBlend);

    // Ball glow
    float ballGlow = exp(-dBall * dBall / (0.01));
    tileColor += ballColor * ballGlow * 0.15;

    // Score display
    float scoreSize = 0.06;
    float leftScoreD = renderScore(courtPos, game.leftScore,
                                    vec2(-0.3, courtTop + 0.15), scoreSize);
    float rightScoreD = renderScore(courtPos, game.rightScore,
                                     vec2(0.2, courtTop + 0.15), scoreSize);
    vec3 scoreColor = mix(u_color1, u_color2, 0.5) * 0.6 + vec3(0.2);
    tileColor = mix(tileColor, u_color1, leftScoreD * 0.8);
    tileColor = mix(tileColor, u_color2, rightScoreD * 0.8);

    // --- Edges ---
    vec3 finalColor = applyEdge(tileColor, tile.edgeDist, u_edge_thickness);
    fragColor = vec4(finalColor, 1.0);
}
