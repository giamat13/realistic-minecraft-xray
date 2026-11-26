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
    vec4 t = texture(gtexture, uv); // block entities (chests, signs, beds) use object textures
    if (t.a < 0.1 || length(viewPos) > float(RANGE)) discard;
    thinSurface(0.5 * objectTau(luma(t.rgb)) * t.a);
}
