#version 330 compatibility
#define TAU_HALF 20 // [5 10 20 40 80 160]
#define DUAL_ENERGY 0 // [0 1]
#define RANGE 96 // [32 48 64 96 128 192 256]
uniform sampler2D colortex2;
uniform sampler2D colortex3;
uniform float frameTimeCounter;
in vec2 uv;
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
/*
const int colortex2Format = RGBA32F;
const int colortex3Format = RGBA32F;
*/

// film response: rises with the attenuation itself (a digital radiograph) and saturates softly
float expose(float tau, float halfway) { return tau > 0.0 ? pow(tau / (tau + halfway), 0.7) : 0.0; }

void main() {
    vec4 c = texture(colortex2, uv); // entry distances, exit distances, entries, exits
    vec4 r = texture(colortex3, uv); // thin, creatures, attenuation per metre summed over faces, dense extra
    float solid = 0.0;
    float faces = c.z + c.w;
    if (faces > 0.5) {
        if (c.w < 0.5) {
            solid = 0.5 * r.b; // no exit faces arrive (Block Face Culling is on): count half a metre per face
        } else {
            // exits minus entries; faces the game left out leave a surplus, which only counts in pairs.
            // Only exits means the camera is inside matter.
            float path = c.z < 0.5 ? c.y / c.w : max(min(c.z, c.w) * (c.y / c.w - c.x / c.z), 0.0);
            solid = r.b / faces * pow(path, HARDENING);
        }
    }
    float rock = max(solid + r.a, 0.0) + r.r;
#if DUAL_ENERGY == 1
    // not physical: creatures get their own exposure so they show through any amount of rock
    float film = 1.0 - (1.0 - 0.85 * expose(rock, float(TAU_HALF))) * (1.0 - expose(r.g, 3.0));
#else
    float film = expose(rock + r.g, float(TAU_HALF));
#endif
    float grain = fract(sin(dot(gl_FragCoord.xy + frameTimeCounter, vec2(12.9898, 78.233))) * 43758.5453) - 0.5;
    gl_FragColor = vec4(vec3(clamp(film + grain * 0.025, 0.0, 1.0)), 1.0);
}
