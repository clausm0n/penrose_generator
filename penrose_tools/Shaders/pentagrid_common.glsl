// pentagrid_common.glsl
// Shared pentagrid generation code for procedural Penrose tiling
// This file is included by all procedural effect shaders

#define PI 3.14159265359
#define PN 5

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

void getRhombusVerts(int r, int s, float kr, float ks, out vec2 verts[4]) {
    vec2 pI = grid[r] * (ks - shift[s]) - grid[s] * (kr - shift[r]);
    float denom = grid[s - r].y;
    if (abs(denom) < 0.0001) denom = 0.0001;
    pI = vec2(-pI.y, pI.x) / denom;
    
    vec2 sum = grid[r] * kr + grid[s] * ks;
    for (int k = 0; k < PN; k++) {
        if (k != r && k != s) {
            sum += grid[k] * ceil(dot(pI, grid[k]) + shift[k]);
        }
    }
    
    verts[0] = sum;
    verts[1] = sum + grid[r];
    verts[2] = sum + grid[r] + grid[s];
    verts[3] = sum + grid[s];
}

bool pointInQuad(vec2 p, vec2 v0, vec2 v1, vec2 v2, vec2 v3) {
    vec2 e0 = v1 - v0, e1 = v2 - v1, e2 = v3 - v2, e3 = v0 - v3;
    vec2 w0 = p - v0, w1 = p - v1, w2 = p - v2, w3 = p - v3;
    float c0 = e0.x * w0.y - e0.y * w0.x;
    float c1 = e1.x * w1.y - e1.y * w1.x;
    float c2 = e2.x * w2.y - e2.y * w2.x;
    float c3 = e3.x * w3.y - e3.y * w3.x;
    return (c0 >= 0.0 && c1 >= 0.0 && c2 >= 0.0 && c3 >= 0.0) ||
           (c0 <= 0.0 && c1 <= 0.0 && c2 <= 0.0 && c3 <= 0.0);
}

float distToQuadEdge(vec2 p, vec2 v0, vec2 v1, vec2 v2, vec2 v3) {
    vec2 edges[4]; edges[0] = v1 - v0; edges[1] = v2 - v1; edges[2] = v3 - v2; edges[3] = v0 - v3;
    vec2 starts[4]; starts[0] = v0; starts[1] = v1; starts[2] = v2; starts[3] = v3;
    float minDist = 1e10;
    for (int i = 0; i < 4; i++) {
        vec2 e = edges[i]; vec2 w = p - starts[i];
        float len2 = dot(e, e);
        float t = clamp(dot(w, e) / len2, 0.0, 1.0);
        minDist = min(minDist, length(p - (starts[i] + t * e)));
    }
    return minDist;
}

// Tile data structure populated by findTile
struct TileData {
    bool found;
    bool isFat;
    int r, s;
    float kr, ks;
    vec2 verts[4];
    vec2 center;
    vec2 tileCentroid;  // Note: 'centroid' is a GLSL reserved keyword
    float tileId;
    float edgeDist;
    vec2 rb_p;
};

// Find the tile containing point p
TileData findTile(vec2 p, float gamma[5]) {
    TileData tile;
    tile.found = false;
    
    float pindex[PN];
    tile.rb_p = vec2(0.0);
    
    for (int k = 0; k < PN; k++) {
        shift[k] = gamma[k];
        float theta = PI * 2.0 / float(PN) * float(k);
        grid[k] = vec2(cos(theta), sin(theta));
        pindex[k] = dot(p, grid[k]) + shift[k];
        tile.rb_p += grid[k] * pindex[k];
    }
    
    for (int r = 0; r < PN - 1; r++) {
        if (tile.found) break;
        for (int s = r + 1; s < PN; s++) {
            if (tile.found) break;
            for (int dr = -2; dr <= 2; dr++) {
                if (tile.found) break;
                for (int ds = -2; ds <= 2; ds++) {
                    if (tile.found) break;
                    float kr = floor(pindex[r]) + float(dr);
                    float ks = floor(pindex[s]) + float(ds);
                    vec2 verts[4];
                    getRhombusVerts(r, s, kr, ks, verts);
                    if (pointInQuad(tile.rb_p, verts[0], verts[1], verts[2], verts[3])) {
                        tile.found = true;
                        tile.r = r; tile.s = s;
                        tile.kr = kr; tile.ks = ks;
                        tile.verts = verts;
                        tile.center = (verts[0] + verts[1] + verts[2] + verts[3]) * 0.25;
                        tile.tileCentroid = tile.center * 0.1;
                        int diff = s - r;
                        tile.isFat = (diff == 1 || diff == PN - 1);
                        tile.tileId = random(vec2(kr + float(r) * 100.0, ks + float(s) * 100.0));
                        tile.edgeDist = distToQuadEdge(tile.rb_p, verts[0], verts[1], verts[2], verts[3]);
                    }
                }
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

