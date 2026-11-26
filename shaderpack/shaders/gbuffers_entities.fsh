#version 330 compatibility
#define RANGE 96 // [32 48 64 96 128 192 256]
uniform sampler2D gtexture;
in vec2 uv;
in vec4 tint;
in vec3 viewPos;
in vec3 normal;
flat in int blockId;
const float LO_BLOCK = 0.545597;
const float HI_BLOCK = 3.639247;
const float LO_OBJ = -1.874226;
const float HI_OBJ = 1.303458;
const float HARDENING = 0.959739;
const float TAU_WATER_1M = 19.755301;
const float TAU_GLASS_1M = 48.575710;
const float TAU_BONE = 1.329111;
const float TAU_FLESH = 0.612538;
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

// gray of the resource pack back to optical depth
float blockTau(float gray) { return pow(10.0, mix(LO_BLOCK, HI_BLOCK, clamp((gray * 255.0 - 40.0) / 215.0, 0.0, 1.0))); }
float objectTau(float gray) { return pow(10.0, mix(LO_OBJ, HI_OBJ, clamp((gray * 255.0 - 25.0) / 230.0, 0.0, 1.0))); }

/* DRAWBUFFERS:23 */
// buffer 2: entry distances, exit distances, entries, exits
// buffer 3: thin attenuation, creature attenuation, sum of attenuation per metre of the cube faces
void emit(vec4 cubes, vec3 rest) {
    gl_FragData[0] = cubes;
    gl_FragData[1] = vec4(rest, 0.0);
}
void thinSurface(float t) { emit(vec4(0.0), vec3(t, 0.0, 0.0)); }
void creatureSurface(float t) { emit(vec4(0.0), vec3(0.0, t, 0.0)); }

bool inBox(ivec2 p, int x, int y, int w, int h) { return p.x >= x && p.y >= y && p.x < x + w && p.y < y + h; }

// optical depth of the skeleton at a texel of a 64x64 skin; negative = draw nothing
float skeletonSkin(ivec2 p) {
    if (inBox(p, 0, 0, 32, 16)) { // head
        ivec2 f = ivec2(p.x % 8, p.y - 8);
        if (inBox(p, 8, 8, 8, 8)) { // face
            bool eyes = (f.y == 3 || f.y == 4) && (f.x == 1 || f.x == 2 || f.x == 5 || f.x == 6);
            bool nose = f.y == 5 && (f.x == 3 || f.x == 4);
            bool teeth = f.y == 7 && f.x > 0 && f.x < 7 && f.x % 2 == 0;
            if (eyes || nose) return TAU_FLESH;
            if (teeth) return TAU_FLESH;
        }
        return TAU_BONE * 0.7; // skull
    }
    if (inBox(p, 16, 16, 24, 16)) { // body
        if (p.y < 20) return TAU_FLESH;
        int x = p.x - (p.x < 20 ? 16 : p.x < 28 ? 20 : p.x < 32 ? 28 : 32);
        int w = (p.x < 20 || (p.x >= 28 && p.x < 32)) ? 4 : 8;
        int y = p.y - 20;
        bool spine = w == 8 && (x == 3 || x == 4);
        bool ribs = y < 8 && y % 2 == 1 && (w == 4 || (x > 0 && x < 7));
        bool pelvis = y >= 10 && x > 0 && x < w - 1;
        return TAU_FLESH + ((spine || ribs || pelvis) ? TAU_BONE : 0.0);
    }
    // limbs: (u, v) of the four base-layer boxes
    ivec2 limbs[4] = ivec2[4](ivec2(40, 16), ivec2(0, 16), ivec2(16, 48), ivec2(32, 48));
    for (int i = 0; i < 4; i++) {
        if (!inBox(p, limbs[i].x, limbs[i].y, 16, 16)) continue;
        ivec2 q = p - limbs[i];
        if (q.y < 4) return TAU_FLESH;
        int x = q.x % 4;
        bool joint = q.y == 9; // elbow / knee gap
        return TAU_FLESH * 0.6 + ((x == 1 || x == 2) && !joint ? TAU_BONE : 0.0);
    }
    return -1.0; // hat, jacket, sleeves, trousers
}
uniform int entityId;

void main() {
    if (entityId == 1001 && textureSize(gtexture, 0) == ivec2(64)) {
        float d = skeletonSkin(ivec2(uv * 64.0));
        if (d < 0.0) discard;
        creatureSurface(d);
        return;
    }
    vec4 t = texture(gtexture, uv);
    if (t.a < 0.1) discard;
    creatureSurface(objectTau(luma(t.rgb)) * t.a);
}
