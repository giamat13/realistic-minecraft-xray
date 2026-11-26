"""Generate the Iris shader pack in shaderpack/ and zip it. It is an optional companion to the
resource pack (not a replacement) that shows the world as one summed radiograph.

Nothing hides anything: every surface along a view ray adds to two buffers.
  full cubes (block.properties): exit minus entry distances give the length of the ray inside matter;
                the attenuation per metre comes from the resource pack's gray (log of the physics);
  everything open or thin (water, plants, partial blocks, items): attenuation per surface;
  creatures: kept apart, so they can be shown like a dual-energy radiograph, or summed with the rest.
The final pass applies beam hardening and maps log(attenuation) to film brightness.
Usage: python3 tools/build_shaderpack.py"""
import io, json, math, os, pathlib, sys, zipfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import materials, physics_render as pr, xray_physics as xp

OUT = pathlib.Path("shaderpack/shaders")
ACCUMULATE = ("basic", "textured", "terrain", "water", "block", "entities", "hand", "hand_water")
DISCARD = ("skybasic", "skytextured", "clouds", "weather", "armor_glint", "damagedblock", "spidereyes", "beaconbeam")

MATS = materials.load_all()
def tau(material, cm): return float(xp.tau_eff(MATS[material], cm))

CONSTANTS = {
    # decode windows of the resource pack's gray (see physics_render.py)
    "LO_BLOCK": float(pr.LO_BLOCK), "HI_BLOCK": float(pr.HI_BLOCK),
    "LO_OBJ": float(pr.LO_OBJ), "HI_OBJ": float(pr.HI_OBJ),
    # beam hardening of rock: tau(L metres) = tau(1 m) * L ^ HARDENING
    "HARDENING": math.log10(tau("stone", 1000) / tau("stone", 100)),
    "TAU_WATER_1M": tau("water", 100),
    "TAU_GLASS_1M": tau("glass", 100),
    # skeleton drawn for player skins, one surface = half of the path
    "TAU_BONE": tau("bone", 4) / 2, "TAU_FLESH": tau("water", 5) / 2,
}

def defines():
    return "".join(f"const float {k} = {v:.6f};\n" for k, v in CONSTANTS.items())

VERTEX = """#version 330 compatibility
out vec2 uv;
out vec4 tint;
out vec3 viewPos;
out vec3 normal;
in vec4 mc_Entity;
flat out int blockId;

void main() {
    blockId = int(mc_Entity.x + 0.5);
    uv = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    tint = gl_Color;
    viewPos = (gl_ModelViewMatrix * gl_Vertex).xyz;
    normal = gl_NormalMatrix * gl_Normal;
    gl_Position = gl_ProjectionMatrix * vec4(viewPos, 1.0);
    gl_Position.z = 0.0; // one shared depth: every surface passes the depth test, so nothing hides anything
}
"""

HEADER = """#version 330 compatibility
#define RANGE 96 // [32 48 64 96 128 192 256]
uniform sampler2D gtexture;
in vec2 uv;
in vec4 tint;
in vec3 viewPos;
in vec3 normal;
flat in int blockId;
@CONSTANTS@
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
"""

# The player skin layout is fixed, so a skeleton can be drawn for any account skin.
SKIN = """
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
"""

ENTITY_BODY = """
void main() {
    if (@IS_SKIN@) {
        float d = skeletonSkin(ivec2(uv * 64.0));
        if (d < 0.0) discard;
        creatureSurface(d);
        return;
    }
    vec4 t = texture(gtexture, uv);
    if (t.a < 0.1) discard;
    creatureSurface(objectTau(luma(t.rgb)) * t.a);
}
"""

BODIES = {
    "terrain": """
void main() {
    vec4 t = texture(gtexture, uv);
    float far = float(RANGE);
    if (blockId == 2000 || blockId == 2001) { // a closed cube: measure the path through it
        float mu = blockId == 2001 ? TAU_GLASS_1M : blockTau(luma(t.rgb)); // the biome colour is not material
        float d = min(length(viewPos), far);
        bool leaving = dot(normal, viewPos) > 0.0;
        emit(leaving ? vec4(0.0, d, 0.0, 1.0) : vec4(d, 0.0, 1.0, 0.0), vec3(0.0, 0.0, mu));
        return;
    }
    if (length(viewPos) > far) discard;
    if (blockId == 2002) { thinSurface(TAU_WATER_1M); return; } // open mesh: one surface = 1 m of water
    if (t.a < 0.004) discard;
    thinSurface(0.25 * blockTau(luma(t.rgb))); // plants, slabs, doors: two faces make about half a metre
}
""",
    "textured": """
void main() {
    vec4 t = texture(gtexture, uv) * vec4(1.0, 1.0, 1.0, tint.a);
    if (t.a < 0.1 || length(viewPos) > float(RANGE)) discard;
    thinSurface(0.25 * objectTau(luma(t.rgb)) * t.a);
}
""",
    "basic": """
void main() {
    thinSurface(0.05 * tint.a); // selection outline and other guide lines
}
""",
    "block": """
void main() {
    vec4 t = texture(gtexture, uv);
    if (t.a < 0.1 || length(viewPos) > float(RANGE)) discard;
    thinSurface(0.1 * blockTau(luma(t.rgb)));
}
""",
    "entities": "uniform int entityId;\n" + ENTITY_BODY.replace(
        "@IS_SKIN@", "entityId == 1001 && textureSize(gtexture, 0) == ivec2(64)"),  # any player, any skin
    "hand": ENTITY_BODY.replace("@IS_SKIN@", "textureSize(gtexture, 0) == ivec2(64)"),  # the bare arm
}
SHARED = {"water": "terrain", "hand_water": "hand"}

FINAL_VERTEX = """#version 330 compatibility
out vec2 uv;
void main() {
    uv = gl_MultiTexCoord0.xy;
    gl_Position = ftransform();
}
"""

FINAL = """#version 330 compatibility
#define WINDOW_LOW -1.5 // [-2.5 -2.0 -1.5 -1.0 -0.5 0.0]
#define WINDOW_HIGH 4.0 // [2.5 3.0 3.5 4.0 4.5 5.0]
#define DUAL_ENERGY 1 // [0 1]
#define RANGE 96 // [32 48 64 96 128 192 256]
uniform sampler2D colortex2;
uniform sampler2D colortex3;
uniform float frameTimeCounter;
in vec2 uv;
@CONSTANTS@
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
"""

BLOCKS_FILE = pathlib.Path("shaderpack/shaders/block.properties")

def block_properties():
    """Full opaque cubes (2000), full glass cubes (2001) and water (2002), read from the client jar.
    Without a jar the committed file is kept."""
    jar = pathlib.Path(os.environ.get("MC_JAR") or pathlib.Path(os.environ.get("APPDATA", "")) / ".minecraft/versions/26.3/26.3.jar")
    if not jar.is_file():
        return BLOCKS_FILE.read_text(encoding="utf-8")
    from PIL import Image
    strip = lambda n: n.split(":")[-1]
    with zipfile.ZipFile(jar) as z:
        names = set(z.namelist()); alpha = {}
        def load(path): return json.loads(z.read(path))
        def opaque(sprite):
            if sprite not in alpha:
                path = f"assets/minecraft/textures/{sprite}.png"
                alpha[sprite] = path in names and Image.open(io.BytesIO(z.read(path))).convert("RGBA").getextrema()[3][0] == 255
            return alpha[sprite]
        def resolve(model):
            textures, elements = {}, None
            while model:
                path = f"assets/minecraft/models/{strip(model)}.json"
                if path not in names:
                    break
                data = load(path)
                for k, v in data.get("textures", {}).items():
                    textures.setdefault(k, v["sprite"] if isinstance(v, dict) else v)
                if elements is None:
                    elements = data.get("elements")
                model = data.get("parent")
            return textures, elements or []
        def full_cube(model, need_opaque):
            textures, elements = resolve(model)
            def sprite(ref):
                for _ in range(8):
                    if not ref.startswith("#"):
                        break
                    ref = textures.get(ref[1:], "")
                    ref = ref["sprite"] if isinstance(ref, dict) else ref
                return strip(ref)
            for e in elements:
                if e["from"] == [0, 0, 0] and e["to"] == [16, 16, 16] and len(e.get("faces", {})) == 6:
                    return not need_opaque or all(opaque(sprite(f["texture"])) for f in e["faces"].values())
            return False
        cubes, glass = [], []
        for path in sorted(n for n in names if n.startswith("assets/minecraft/blockstates/") and n.endswith(".json")):
            block = path.rsplit("/", 1)[1][:-5]
            variants = load(path).get("variants")
            if not variants:
                continue
            models = {m["model"] for v in variants.values() for m in (v if isinstance(v, list) else [v])}
            is_glass = block.endswith("glass")
            if all(full_cube(m, not is_glass) for m in models):
                (glass if is_glass else cubes).append(block)
    return f"block.2000={' '.join(cubes)}\nblock.2001={' '.join(glass)}\nblock.2002=water flowing_water\n"

def properties():
    lines = ["# draw everything along the ray", "occlusion.culling=false"]
    lines += [f"backFace.{layer}=true" for layer in ("solid", "cutout", "cutoutMipped", "translucent")]
    lines += ["sun=false", "moon=false", "stars=false", "sky=false", "vignette=false", "clouds=off",
              "oldLighting=false", "shadow.enabled=false",
              "screen=WINDOW_LOW WINDOW_HIGH DUAL_ENERGY RANGE", "sliders=WINDOW_LOW WINDOW_HIGH DUAL_ENERGY RANGE"]
    for p in ACCUMULATE:
        lines += [f"alphaTest.gbuffers_{p}=off", f"blend.gbuffers_{p}=ONE ONE ONE ONE"]
    return "\n".join(lines) + "\n"

def files():
    head = HEADER.replace("@CONSTANTS@\n", defines())
    out = {"shaders.properties": properties(), "entity.properties": "entity.1001=minecraft:player\n",
           "block.properties": block_properties(), "final.vsh": FINAL_VERTEX, "final.fsh": FINAL.replace("@CONSTANTS@\n", defines()),
           "lang/en_us.lang": "option.WINDOW_LOW=Faintest visible\noption.WINDOW_HIGH=Full white\noption.DUAL_ENERGY=Separate creatures (dual energy)\noption.RANGE=Range (blocks)\n"}
    for p in ACCUMULATE:
        kind = SHARED.get(p, p)
        skin = SKIN if kind in ("entities", "hand") else ""
        out[f"gbuffers_{p}.vsh"] = VERTEX
        out[f"gbuffers_{p}.fsh"] = head + skin + BODIES[kind]
    for p in DISCARD:
        out[f"gbuffers_{p}.vsh"] = VERTEX
        out[f"gbuffers_{p}.fsh"] = "#version 330 compatibility\nvoid main() { discard; }\n"
    return out

def main():
    pathlib.Path("dist").mkdir(exist_ok=True)
    zip_path = pathlib.Path("dist/RealisticXRay-Shader.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files().items():
            p = OUT / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
            z.writestr("shaders/" + name, text)
    print(f"{zip_path}: {len(files())} files")
    print("blocks per class:", [len(l.split("=")[1].split()) for l in block_properties().strip().split("\n")])
    print({k: round(v, 3) for k, v in CONSTANTS.items()})

if __name__ == "__main__":
    main()
