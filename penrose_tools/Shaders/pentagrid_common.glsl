// pentagrid_common.glsl
// Shared pentagrid generation code for procedural Penrose tiling
// Optimized for tile-based mobile GPUs (V3D / Raspberry Pi 5)

#define PI 3.14159265359
#define PN 5

// Precomputed grid directions: vec2(cos(k*2*PI/5), sin(k*2*PI/5))
const vec2 GRID[5] = vec2[5](
    vec2( 1.0,             0.0),
    vec2( 0.30901699437,   0.95105651629),
    vec2(-0.80901699437,   0.58778525229),
    vec2(-0.80901699437,  -0.58778525229),
    vec2(-0.30901699437,  -0.95105651629)
);

// 1.0 / sin((d) * 2*PI/5) for d=0..4.  d=0 unused.
const float INV_DENOM[5] = float[5](
    0.0,
     1.05146222424,
     1.70130161670,
    -1.70130161670,
    -1.05146222424
);

// Grid pair table: 10 pairs (r,s) where 0<=r<s<=4
const int PAIR_R[10] = int[10](0,0,0,0,1,1,1,2,2,3);
const int PAIR_S[10] = int[10](1,2,3,4,2,3,4,3,4,4);

// Globals needed by consumer shaders (eye_spy, plasmaball read these post-findTile)
vec2 grid[PN];
float shift[PN];

float random(vec2 st) {
    return fract(sin(dot(st, vec2(12.9898, 78.233))) * 43758.5453123);
}

float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    float a = random(i);
    float b = random(i + vec2(1.0, 0.0));
    float c = random(i + vec2(0.0, 1.0));
    float d = random(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

vec3 hsvToRgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z * mix(vec3(1.0), rgb, c.y);
}

// Branchless point-in-quad using step() — avoids boolean short-circuit divergence
float pointInQuadF(vec2 p, vec2 v0, vec2 v1, vec2 v2, vec2 v3) {
    vec2 w0 = p - v0, w1 = p - v1, w2 = p - v2, w3 = p - v3;
    float c0 = (v1.x - v0.x) * w0.y - (v1.y - v0.y) * w0.x;
    float c1 = (v2.x - v1.x) * w1.y - (v2.y - v1.y) * w1.x;
    float c2 = (v3.x - v2.x) * w2.y - (v3.y - v2.y) * w2.x;
    float c3 = (v0.x - v3.x) * w3.y - (v0.y - v3.y) * w3.x;
    float allPos = step(0.0, c0) * step(0.0, c1) * step(0.0, c2) * step(0.0, c3);
    float allNeg = step(0.0, -c0) * step(0.0, -c1) * step(0.0, -c2) * step(0.0, -c3);
    return max(allPos, allNeg);
}

// Keep bool version for backward compat with consumer shaders
bool pointInQuad(vec2 p, vec2 v0, vec2 v1, vec2 v2, vec2 v3) {
    return pointInQuadF(p, v0, v1, v2, v3) > 0.5;
}

// Edge distance with single sqrt (saves 3 sqrt calls vs original)
float distToQuadEdge(vec2 p, vec2 v0, vec2 v1, vec2 v2, vec2 v3) {
    vec2 e0 = v1 - v0, w0 = p - v0;
    vec2 e1 = v2 - v1, w1 = p - v1;
    vec2 e2 = v3 - v2, w2 = p - v2;
    vec2 e3 = v0 - v3, w3 = p - v3;
    float t0 = clamp(dot(w0, e0) / dot(e0, e0), 0.0, 1.0);
    float t1 = clamp(dot(w1, e1) / dot(e1, e1), 0.0, 1.0);
    float t2 = clamp(dot(w2, e2) / dot(e2, e2), 0.0, 1.0);
    float t3 = clamp(dot(w3, e3) / dot(e3, e3), 0.0, 1.0);
    vec2 d0 = w0 - t0 * e0, d1 = w1 - t1 * e1;
    vec2 d2 = w2 - t2 * e2, d3 = w3 - t3 * e3;
    return sqrt(min(min(dot(d0, d0), dot(d1, d1)), min(dot(d2, d2), dot(d3, d3))));
}

// Tile data structure populated by findTile
struct TileData {
    bool found;
    bool isFat;
    int r, s;
    float kr, ks;
    vec2 verts[4];
    vec2 center;
    vec2 tileCentroid;
    float tileId;
    float edgeDist;
    vec2 rb_p;
};

// Find the tile containing point p
TileData findTile(vec2 p, float gamma[5]) {
    TileData tile;
    tile.found = false;

    // Initialize globals and projection indices from constants
    float pindex[PN];
    vec2 rb_p = vec2(0.0);
    for (int k = 0; k < PN; k++) {
        grid[k] = GRID[k];
        shift[k] = gamma[k];
        pindex[k] = dot(p, GRID[k]) + gamma[k];
        rb_p += GRID[k] * pindex[k];
    }
    tile.rb_p = rb_p;

    // Search 10 grid pairs x 4 nearest candidates
    for (int pair = 0; pair < 10; pair++) {
        if (tile.found) break;

        int r = PAIR_R[pair];
        int s = PAIR_S[pair];
        int diff = s - r;
        float invD = INV_DENOM[diff];
        float base_kr = floor(pindex[r]);
        float base_ks = floor(pindex[s]);

        for (int c = 0; c < 4; c++) {
            if (tile.found) break;

            float kr = base_kr + float(c & 1);
            float ks = base_ks + float(c >> 1);

            // Inline rhombus vertex computation
            // Intersection point of grid lines r=kr and s=ks
            vec2 crossTerm = GRID[r] * (ks - gamma[s])
                           - GRID[s] * (kr - gamma[r]);
            vec2 pI = vec2(-crossTerm.y, crossTerm.x) * invD;

            // Compute vertex sum: all 5 ceil terms, then fix r and s
            // (branchless — avoids if(k!=r && k!=s) loop)
            vec2 sum = GRID[0] * ceil(dot(pI, GRID[0]) + gamma[0])
                     + GRID[1] * ceil(dot(pI, GRID[1]) + gamma[1])
                     + GRID[2] * ceil(dot(pI, GRID[2]) + gamma[2])
                     + GRID[3] * ceil(dot(pI, GRID[3]) + gamma[3])
                     + GRID[4] * ceil(dot(pI, GRID[4]) + gamma[4]);
            // Replace the r,s ceil terms with exact kr,ks
            sum += GRID[r] * (kr - ceil(dot(pI, GRID[r]) + gamma[r]))
                 + GRID[s] * (ks - ceil(dot(pI, GRID[s]) + gamma[s]));

            vec2 v0 = sum;
            vec2 v1 = sum + GRID[r];
            vec2 v2 = sum + GRID[r] + GRID[s];
            vec2 v3 = sum + GRID[s];

            if (pointInQuadF(rb_p, v0, v1, v2, v3) > 0.5) {
                tile.found = true;
                tile.r = r;
                tile.s = s;
                tile.kr = kr;
                tile.ks = ks;
                tile.verts[0] = v0;
                tile.verts[1] = v1;
                tile.verts[2] = v2;
                tile.verts[3] = v3;
                tile.center = (v0 + v1 + v2 + v3) * 0.25;
                tile.tileCentroid = tile.center * 0.1;
                tile.isFat = (diff == 1 || diff == 4);
                tile.tileId = random(vec2(kr + float(r) * 100.0,
                                          ks + float(s) * 100.0));
                tile.edgeDist = distToQuadEdge(rb_p, v0, v1, v2, v3);
            }
        }
    }

    return tile;
}

// Apply edge rendering to tile color
vec3 applyEdge(vec3 tileColor, float edgeDist, float edgeThickness) {
    float edgeWidth = 0.012 * edgeThickness;
    float aaWidth = 0.003;
    float edgeFactor = smoothstep(edgeWidth - aaWidth, edgeWidth, edgeDist);
    vec3 edgeColor = tileColor * 0.15;
    return mix(edgeColor, tileColor, edgeFactor);
}
