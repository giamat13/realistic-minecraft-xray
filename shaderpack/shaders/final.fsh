#version 330 compatibility
#define WINDOW_LOW -1.5 // [-2.5 -2.0 -1.5 -1.0 -0.5 0.0]
#define WINDOW_HIGH 4.0 // [2.5 3.0 3.5 4.0 4.5 5.0]
#define DUAL_ENERGY 1 // [0 1]
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
const float TAU_GLASS_1M = 48.575710;
const float TAU_BONE = 1.329111;
const float TAU_FLESH = 0.612538;
/*
const int colortex2Format = RGBA32F;
const int colortex3Format = RGBA32F;
*/

// log of the attenuation, mapped between "air" and "full white"
float window(float tau, float low, float high) {
    return tau > 0.0 ? clamp((log(tau) / log(10.0) - low) / (high - low), 0.0, 1.0) : 0.0;
}

void main() {
    vec4 c = texture(colortex2, uv); // entry distances, exit distances, entries, exits
    vec3 r = texture(colortex3, uv).rgb;
    float solid = 0.0;
    if (c.z + c.w > 0.5) {
        float mu = r.b / (c.z + c.w);
        if (c.w < 0.5) {
            solid = 0.5 * r.b; // no exit faces arrive (Sodium Block Face Culling is on): count surfaces
        } else {
            // exits minus entries; faces the game culled leave a surplus, which only counts in pairs.
            // Only exits means the camera is inside matter.
            float path = c.z < 0.5 ? c.y / c.w : max(min(c.z, c.w) * (c.y / c.w - c.x / c.z), 0.0);
            solid = mu * pow(path, HARDENING);
        }
    }
    float rock = solid + r.r;
#if DUAL_ENERGY == 1
    // two exposures at different energies separate bone and tissue from the rock around them
    float back = 0.85 * window(rock, float(WINDOW_LOW), float(WINDOW_HIGH));
    float life = window(r.g, -0.6, 1.3);
    float film = 1.0 - (1.0 - back) * (1.0 - life);
#else
    float film = window(rock + r.g, float(WINDOW_LOW), float(WINDOW_HIGH));
#endif
    float grain = fract(sin(dot(gl_FragCoord.xy + frameTimeCounter, vec2(12.9898, 78.233))) * 43758.5453) - 0.5;
    gl_FragColor = vec4(vec3(clamp(film + grain * 0.025, 0.0, 1.0)), 1.0);
}
