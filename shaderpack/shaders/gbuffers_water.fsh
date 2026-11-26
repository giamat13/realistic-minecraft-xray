#version 330 compatibility
#define RANGE 96 // [32 48 64 96 128 192 256]
uniform sampler2D gtexture;
in vec2 uv;
in vec4 tint;
in vec3 viewPos;
in vec3 normal;
flat in int blockId;
flat in int inset;
const float LO_BLOCK = 0.545597;
const float HI_BLOCK = 3.639247;
const float LO_OBJ = -1.874226;
const float HI_OBJ = 1.303458;
const float HARDENING = 0.959739;
const float TAU_WATER_1M = 19.755301;
const float TAU_STONE_1M = 52.629721;
const float TAU_DEEPSLATE_1M = 55.983920;
const float TAU_NETHERRACK_1M = 56.432216;
const float TAU_GLASS_1M = 48.575710;
const float TAU_BONE = 1.329111;
const float TAU_FLESH = 0.612538;
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

// gray of the resource pack back to optical depth
float blockTau(float gray) { return pow(10.0, mix(LO_BLOCK, HI_BLOCK, clamp((gray * 255.0 - 40.0) / 215.0, 0.0, 1.0))); }
float objectTau(float gray) { return pow(10.0, mix(LO_OBJ, HI_OBJ, clamp((gray * 255.0 - 25.0) / 230.0, 0.0, 1.0))); }

/* DRAWBUFFERS:23 */
// buffer 2: entry distances, exit distances, entries, exits
// buffer 3: thin attenuation, creature attenuation, attenuation per metre summed over faces, dense extra
void emit(vec4 cubes, vec4 rest) {
    gl_FragData[0] = cubes;
    gl_FragData[1] = rest;
}
void thinSurface(float t) { emit(vec4(0.0), vec4(t, 0.0, 0.0, 0.0)); }
void creatureSurface(float t) { emit(vec4(0.0), vec4(0.0, t, 0.0, 0.0)); }
float levelTau(int level) { return pow(10.0, mix(LO_BLOCK, HI_BLOCK, float(level) / 255.0)); }
// the resource pack's alpha is 1 - transmission, exact for thin things; opaque pixels fall back to the gray
float thinTau(vec4 t, float fromGray) { return t.a < 0.98 ? -log(1.0 - t.a) : fromGray; }

void main() {
    vec4 t = texture(gtexture, uv);
    float far = float(RANGE);
    if (blockId >= 2000 && blockId != 2002) { // a closed shape: measure the path through it
        float d = min(length(viewPos), far);
        bool leaving = dot(normal, viewPos) > 0.0;
        vec4 pass = leaving ? vec4(0.0, d, 0.0, 1.0) : vec4(d, 0.0, 1.0, 0.0);
        if (blockId >= 4000) { // a dense block: ordinary rock outside, plus what it adds in a box just inside
            int host = (blockId - 4000) / 300;
            float rockMu = host == 1 ? TAU_DEEPSLATE_1M : host == 2 ? TAU_NETHERRACK_1M : TAU_STONE_1M;
            if (inset > 0) { // never hidden by neighbours, so its two sides always pair up
                float extra = levelTau((blockId - 4000) % 300) - rockMu;
                emit(vec4(0.0), vec4(0.0, 0.0, 0.0, (leaving ? d : -d) * extra));
            } else {
                emit(pass, vec4(0.0, 0.0, rockMu, 0.0));
            }
            return;
        }
        if (blockId == 2000 && t.a < 0.98) discard; // overlays such as the grass fringe add no depth
        if (blockId >= 3000 && t.a < 0.004) discard; // a hole in the shape
        // glass and ice are one material throughout; the biome colour is never material
        float mu = blockId >= 3000 ? levelTau(blockId - 3000) : blockId == 2001 ? TAU_GLASS_1M
                 : blockId == 2003 ? TAU_WATER_1M : blockTau(luma(t.rgb));
        emit(pass, vec4(0.0, 0.0, mu, 0.0));
        return;
    }
    if (length(viewPos) > far) discard;
    if (blockId == 2002) { thinSurface(0.5 * TAU_WATER_1M); return; } // open mesh: two surfaces = 1 m of water
    if (t.a < 0.004) discard;
    thinSurface(0.5 * thinTau(t, blockTau(luma(t.rgb)))); // two faces make the whole thing
}
