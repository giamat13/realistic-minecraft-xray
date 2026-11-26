#version 330

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>

uniform sampler2D Sampler0;

#ifdef DISSOLVE
uniform sampler2D DissolveMaskSampler;
#endif

in float sphericalVertexDistance;
in float cylindricalVertexDistance;
#ifdef PER_FACE_LIGHTING
in vec4 vertexPerFaceColorBack;
in vec4 vertexPerFaceColorFront;
#else
in vec4 vertexColor;
#endif

#ifndef EMISSIVE
in vec4 lightMapColor;
#endif

#ifndef NO_OVERLAY
in vec4 overlayColor;
#endif

in vec2 texCoord0;

out vec4 fragColor;

const float LO_OBJ = -1.874226;
const float HI_OBJ = 1.303458;
const float TAU_BONE = 1.329111;
const float TAU_FLESH = 0.612538;

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

vec4 entityTexel(vec2 at) {
    if (textureSize(Sampler0, 0) == ivec2(64)) {
        ivec2 probes[12] = ivec2[12](ivec2(9, 9), ivec2(12, 12), ivec2(14, 14), ivec2(10, 13), ivec2(22, 22), ivec2(25, 26), ivec2(23, 30), ivec2(45, 22), ivec2(5, 22), ivec2(21, 54), ivec2(37, 54), ivec2(12, 3));
        for (int i = 0; i < 12; i++) {
            vec4 s = texelFetch(Sampler0, probes[i], 0);
            if (s.a > 0.5 && max(s.r, max(s.g, s.b)) - min(s.r, min(s.g, s.b)) > 0.03) {
                float d = 2.0 * skeletonSkin(ivec2(fract(at) * 64.0)); // both sides of the limb
                if (d < 0.0) discard;
                float s01 = clamp((log(d) / log(10.0) - LO_OBJ) / (HI_OBJ - LO_OBJ), 0.0, 1.0);
                return vec4(vec3((25.0 + 230.0 * s01) / 255.0), 1.0 - exp(-d));
            }
        }
    }
    return texture(Sampler0, at);
}

void vanillaMain() {
    vec4 color = entityTexel(texCoord0);
#ifdef ALPHA_CUTOUT
    if (color.a < ALPHA_CUTOUT) {
        discard;
    }
#endif

#ifdef PER_FACE_LIGHTING
    vec4 faceVertexColor = gl_FrontFacing ? vertexPerFaceColorFront : vertexPerFaceColorBack;
#else
    vec4 faceVertexColor = vertexColor;
#endif

#ifdef DISSOLVE
    if (faceVertexColor.a < texture(DissolveMaskSampler, texCoord0).a) {
        discard;
    }
    // The dissolve effect entirely replaces translucency
    faceVertexColor.a = 1.0;
#endif

    color *= faceVertexColor * ColorModulator;
#ifndef NO_OVERLAY
    color.rgb = mix(overlayColor.rgb, color.rgb, overlayColor.a);
#endif
#ifndef EMISSIVE
    color *= lightMapColor;
#endif

    fragColor = apply_fog(color, sphericalVertexDistance, cylindricalVertexDistance, FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd, FogColor);
}

void main() {
    vanillaMain();
    fragColor.rgb = vec3(dot(fragColor.rgb, vec3(0.2126, 0.7152, 0.0722)));
}
