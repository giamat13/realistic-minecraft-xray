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

void main() {
    vec4 t = texture(gtexture, uv) * vec4(1.0, 1.0, 1.0, tint.a);
    if (t.a < 0.1 || length(viewPos) > float(RANGE)) discard;
    thinSurface(0.25 * objectTau(luma(t.rgb)) * t.a);
}
