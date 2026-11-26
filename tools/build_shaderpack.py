"""Generate the Iris shader pack in shaderpack/ and zip it. It is an optional companion to the
resource pack (not a replacement) that shows the world as one summed radiograph.

Every surface that reaches the GPU along a view ray adds to two buffers.
  closed shapes (block.properties): exit minus entry distances give the length of the ray inside matter, and
                the faces give its attenuation per metre; dense blocks add their excess from an inner box
                (made by generate_models.py) that neighbours never hide, so they show when buried;
  everything open or thin (water, plants, panes, items): attenuation per surface;
  creatures: summed with the rest (optionally shown apart, which is a display effect, not physics).
The final pass applies beam hardening and exposes the film: brightness rises with attenuation and saturates.

Needs Sodium "Block Face Culling" off, so that faces pointing away are submitted (a geometry shader keeps
the GPU from culling them). Limit: the game still skips chunk sections hidden behind solid ones.
Usage: python3 tools/build_shaderpack.py"""
import io, json, math, os, pathlib, re, sys, zipfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
from PIL import Image
import materials, physics_render as pr, xray_physics as xp
from generate_models import DENSE

OUT = pathlib.Path("shaderpack/shaders")
ACCUMULATE = ("basic", "textured", "terrain", "water", "block", "entities", "hand", "hand_water")
DISCARD = ("skybasic", "skytextured", "clouds", "weather", "lightning", "armor_glint", "damagedblock", "spidereyes", "beaconbeam")

MATS = materials.load_all()
def tau(material, cm): return float(xp.tau_eff(MATS[material], cm))

CONSTANTS = {
    # decode windows of the resource pack's gray (see physics_render.py)
    "LO_BLOCK": float(pr.LO_BLOCK), "HI_BLOCK": float(pr.HI_BLOCK),
    "LO_OBJ": float(pr.LO_OBJ), "HI_OBJ": float(pr.HI_OBJ),
    # beam hardening of rock: tau(L metres) = tau(1 m) * L ^ HARDENING
    "HARDENING": math.log10(tau("stone", 1000) / tau("stone", 100)),
    "TAU_WATER_1M": tau("water", 100),
    "TAU_STONE_1M": tau("stone", 100),
    "TAU_DEEPSLATE_1M": tau("slate", 100),
    "TAU_NETHERRACK_1M": tau("netherrack", 100),
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
in vec4 at_midBlock; // from each corner to the middle of its block, in 1/64 of a block
flat out int inset;

void main() {
    blockId = int(mc_Entity.x + 0.5);
    inset = max(max(abs(at_midBlock.x), abs(at_midBlock.y)), abs(at_midBlock.z)) < 31.5 ? 1 : 0;
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
flat in int inset;
@CONSTANTS@
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
    if (currentRenderedItemId == 3000) { // a small copy of a block, held or dropped: block gray, a quarter metre
        creatureSurface(0.125 * blockTau(luma(t.rgb)) * t.a);
        return;
    }
    creatureSurface(objectTau(luma(t.rgb)) * t.a);
}
"""

BODIES = {
    "terrain": """
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
    vec4 t = texture(gtexture, uv); // block entities (chests, signs, beds) use object textures
    if (t.a < 0.1 || length(viewPos) > float(RANGE)) discard;
    thinSurface(0.5 * objectTau(luma(t.rgb)) * t.a);
}
""",
    "entities": "uniform int entityId;\nuniform int currentRenderedItemId;\n" + ENTITY_BODY.replace(
        "@IS_SKIN@", "entityId == 1001 && textureSize(gtexture, 0) == ivec2(64)"),  # any player, any skin
    "hand": "uniform int currentRenderedItemId;\n" + ENTITY_BODY.replace(
        "@IS_SKIN@", "currentRenderedItemId != 3000 && textureSize(gtexture, 0) == ivec2(64)"),  # the bare arm
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
#define TAU_HALF 20 // [5 10 20 40 80 160]
#define DUAL_ENERGY 0 // [0 1]
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
"""

# The GPU culls faces that point away; this stage turns them around so both sides of a shape arrive.
GEOMETRY = """#version 330 compatibility
layout(triangles) in;
layout(triangle_strip, max_vertices = 3) out;
in vec2 vUv[];
in vec4 vTint[];
in vec3 vViewPos[];
in vec3 vNormal[];
flat in int vBlockId[];
flat in int vInset[];
out vec2 uv;
out vec4 tint;
out vec3 viewPos;
out vec3 normal;
flat out int blockId;
flat out int inset;

void corner(int i) {
    uv = vUv[i]; tint = vTint[i]; viewPos = vViewPos[i]; normal = vNormal[i]; blockId = vBlockId[i]; inset = vInset[i];
    gl_Position = gl_in[i].gl_Position;
    EmitVertex();
}

void main() {
    // orientation in clip space, valid even when a corner is behind the camera
    bool away = determinant(mat3(gl_in[0].gl_Position.xyw, gl_in[1].gl_Position.xyw, gl_in[2].gl_Position.xyw)) < 0.0;
    corner(0);
    corner(away ? 2 : 1);
    corner(away ? 1 : 2);
    EndPrimitive();
}
"""

def geometry_vertex():
    """The common vertex stage with its outputs renamed, to feed the geometry stage."""
    src = VERTEX
    for name in ("uv", "tint", "viewPos", "normal", "blockId", "inset"):
        src = re.sub(rf"\b{name}\b", "v" + name[0].upper() + name[1:], src)
    return src

BLOCKS_FILE = pathlib.Path("shaderpack/shaders/block.properties")

def block_properties():
    """Full opaque cubes (2000), full glass cubes (2001) and water (2002), read from the client jar.
    Without a jar the committed file is kept."""
    jar = pathlib.Path(os.environ.get("MC_JAR") or pathlib.Path(os.environ.get("APPDATA", "")) / ".minecraft/versions/26.3/26.3.jar")
    if not jar.is_file():
        return BLOCKS_FILE.read_text(encoding="utf-8")
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
        def sprites(textures, element):
            for face in element.get("faces", {}).values():
                ref = face["texture"]
                for _ in range(8):
                    if not ref.startswith("#"):
                        break
                    ref = textures.get(ref[1:], "")
                    ref = ref["sprite"] if isinstance(ref, dict) else ref
                yield strip(ref)
        def full_cube(model, need_opaque):
            textures, elements = resolve(model)
            for e in elements:
                if e["from"] == [0, 0, 0] and e["to"] == [16, 16, 16] and len(e.get("faces", {})) == 6:
                    return not need_opaque or all(map(opaque, sprites(textures, e)))
            return False
        def closed(model):
            """Every box has volume, all six faces and opaque textures: entries and exits pair up."""
            textures, elements = resolve(model)
            return bool(elements) and all(
                len(e.get("faces", {})) == 6 and all(a < b for a, b in zip(e["from"], e["to"]))
                and all(map(opaque, sprites(textures, e))) for e in elements)
        def level(models):
            """Attenuation per metre of a block's material (from the full-size pack textures), as 0..255."""
            taus = []
            for model in sorted(models):
                textures, elements = resolve(model)
                for e in elements:
                    taus += [t for t in map(sprite_tau, sprites(textures, e)) if t]
            if not taus:
                return 0
            s = (math.log10(sum(taus) / len(taus)) - pr.LO_BLOCK) / (pr.HI_BLOCK - pr.LO_BLOCK)
            return int(round(min(max(float(s), 0.0), 1.0) * 255))
        classes = {}
        def add(code, block): classes.setdefault(code, []).append(block)
        for path in sorted(n for n in names if n.startswith("assets/minecraft/blockstates/") and n.endswith(".json")):
            block = path.rsplit("/", 1)[1][:-5]
            variants = load(path).get("variants")
            if not variants:
                continue
            models = {m["model"] for v in variants.values() for m in (v if isinstance(v, list) else [v])}
            if block in ("ice", "frosted_ice", "slime_block", "honey_block"):
                add(2003, block)
            elif block.endswith("glass"):
                if all(full_cube(m, False) for m in models):
                    add(2001, block)
            elif DENSE.match("block/" + block) and all(full_cube(m, True) for m in models):
                host = 1 if block.startswith("deepslate_") else 2 if block.startswith(("nether_", "ancient_")) else 0
                add(4000 + 300 * host + level(models), block)
            elif all(full_cube(m, True) for m in models):
                add(2000, block)
            elif all(closed(m) for m in models):
                add(3000 + level(models), block)
    classes[2002] = ["water", "flowing_water"]
    return "".join(f"block.{code}={' '.join(blocks)}\n" for code, blocks in sorted(classes.items()))

def sprite_tau(sprite):
    """Mean attenuation per metre shown by a pack texture, decoded like the shader does."""
    path = pathlib.Path("assets/minecraft/textures") / (sprite + ".png")
    if not path.is_file():
        return None
    a = np.asarray(Image.open(path).convert("RGBA"), float)
    gray = a[..., 0][a[..., 3] > 0]
    if not gray.size:
        return None
    s = np.clip((gray - 40) / 215, 0, 1)
    return float((10 ** (pr.LO_BLOCK + s * (pr.HI_BLOCK - pr.LO_BLOCK))).mean())

def item_properties():
    """Items that are small copies of full blocks (their textures use the block gray)."""
    names = []
    for line in block_properties().strip().split("\n"):
        key, blocks = line.split("=", 1)
        if key == "block.2000" or int(key.split(".")[1]) >= 4000:
            names += blocks.split()
    return "item.3000=" + " ".join(names) + "\n"

def properties():
    lines = ["# draw everything along the ray", "occlusion.culling=false"]
    lines += ["sun=false", "moon=false", "stars=false", "sky=false", "vignette=false", "clouds=off",
              "oldLighting=false", "shadow.enabled=false",
              "screen=TAU_HALF DUAL_ENERGY RANGE", "sliders=TAU_HALF DUAL_ENERGY RANGE"]
    for p in ACCUMULATE:
        lines += [f"alphaTest.gbuffers_{p}=off", f"blend.gbuffers_{p}=ONE ONE ONE ONE"]
    return "\n".join(lines) + "\n"

def files():
    head = HEADER.replace("@CONSTANTS@\n", defines())
    out = {"shaders.properties": properties(), "entity.properties": "entity.1001=minecraft:player\n",
           "block.properties": block_properties(), "item.properties": item_properties(), "final.vsh": FINAL_VERTEX, "final.fsh": FINAL.replace("@CONSTANTS@\n", defines()),
           "lang/en_us.lang": "option.TAU_HALF=Exposure (higher shows denser matter)\noption.DUAL_ENERGY=Creatures through rock (not physical)\noption.RANGE=Range (blocks)\n"}
    for p in ACCUMULATE:
        kind = SHARED.get(p, p)
        skin = SKIN if kind in ("entities", "hand") else ""
        out[f"gbuffers_{p}.vsh"] = VERTEX
        out[f"gbuffers_{p}.fsh"] = head + skin + BODIES[kind]
        if kind == "terrain":
            out[f"gbuffers_{p}.vsh"] = geometry_vertex()
            out[f"gbuffers_{p}.gsh"] = GEOMETRY
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
