"""Run the real shader pack off screen on a small scene and check it against Beer-Lambert.

The game is not involved: boxes are built here (outward normals, both faces drawn, like the pack asks)
and the GLSL from shaderpack/ renders them with additive blending, then final.fsh makes the picture.
Compatibility built-ins are swapped for uniforms so a core context accepts the source.
Usage: uv run --with moderngl --with numpy --with pillow python tools/simulate_shaderpack.py <out dir>"""
import math, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import moderngl, numpy as np
from PIL import Image
import build_shaderpack as sp

SUBS = {"gl_TextureMatrix[0]": "u_tex", "gl_ModelViewMatrix": "u_mv", "gl_ProjectionMatrix": "u_proj",
        "gl_NormalMatrix": "u_nm", "gl_MultiTexCoord0": "a_uv", "gl_Color": "a_color", "gl_Vertex": "a_pos",
        "gl_Normal": "a_normal", "gl_FragData[0]": "o0", "gl_FragData[1]": "o1", "gl_FragColor": "o0"}
VS_DECL = "uniform mat4 u_tex, u_mv, u_proj; uniform mat3 u_nm; in vec4 a_uv, a_color, a_pos; in vec3 a_normal;\n"
ROOT = pathlib.Path("shaderpack/shaders")
TEX = pathlib.Path("assets/minecraft/textures")
W, H = 640, 360

def core(src, decl):
    for a, b in SUBS.items():
        src = src.replace(a, b)
    return src.replace("#version 330 compatibility\n", "#version 330 core\n" + decl, 1)

ctx = moderngl.create_standalone_context(require=330)

def program(name):
    vs = (ROOT / f"{name}.vsh").read_text()
    if name == "final":
        vs = vs.replace("ftransform()", "vec4(a_pos.xy, 0.0, 1.0)")
    out = "layout(location=0) out vec4 o0; layout(location=1) out vec4 o1;\n"
    return ctx.program(vertex_shader=core(vs, VS_DECL), fragment_shader=core((ROOT / f"{name}.fsh").read_text(), out))

# faces of a box: normal, four corners (counter-clockwise from outside)
FACES = [((0, 0, 1), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]), ((0, 0, -1), [(1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)]),
         ((1, 0, 0), [(1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)]), ((-1, 0, 0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
         ((0, 1, 0), [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)]), ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)])]

def box(lo, size, uvs=None):
    """Triangles (pos, uv, normal). uvs: per face (u0, v0, u1, v1), default the whole texture per metre."""
    verts = []
    for i, (n, corners) in enumerate(FACES):
        u0, v0, u1, v1 = uvs[i] if uvs else (0, 0, 1, 1)
        quad = []
        for k, c in enumerate(corners):
            u, v = [(u0, v1), (u1, v1), (u1, v0), (u0, v0)][k]
            quad.append([lo[0] + c[0] * size[0], lo[1] + c[1] * size[1], lo[2] + c[2] * size[2], 1, u, v, 0, 1, *n])
        verts += [quad[j] for j in (0, 1, 2, 0, 2, 3)]
    return np.array(verts, "f4")

def perspective(fov, aspect, near=0.05, far=1000.0):
    f = 1 / math.tan(math.radians(fov) / 2)
    return np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0], [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)],
                     [0, 0, -1, 0]], "f4")

textures = {}
def texture(path):
    if path not in textures:
        im = Image.open(TEX / path).convert("RGBA")
        if path.startswith("block/"):
            im = im.crop((0, 0, im.width, im.width))
        t = ctx.texture(im.size, 4, im.tobytes()); t.filter = (moderngl.NEAREST, moderngl.NEAREST)
        textures[path] = t
    return textures[path]

def render(scene, eye=(0, 0, 0), fov=70, size=(W, H)):
    """scene: list of (program, texture path, vertices, {uniforms and mc_Entity}, tint). Returns (cubes, rest, picture)."""
    solid = ctx.texture(size, 4, dtype="f4"); thin = ctx.texture(size, 4, dtype="f4")
    fbo = ctx.framebuffer([solid, thin], ctx.depth_renderbuffer(size))
    fbo.use(); fbo.clear(0, 0, 0, 0, depth=1.0)
    ctx.enable(moderngl.BLEND | moderngl.DEPTH_TEST); ctx.disable(moderngl.CULL_FACE)
    ctx.blend_func = moderngl.ONE, moderngl.ONE
    ctx.depth_func = "<="  # the game's test: an equal depth passes
    view = np.eye(4, dtype="f4"); view[:3, 3] = [-e for e in eye]
    for prog_name, tex, verts, uniforms, tint in scene:
        prog = program(prog_name)
        values = {"u_tex": np.eye(4, dtype="f4"), "u_mv": view, "u_proj": perspective(fov, size[0] / size[1]),
                  "u_nm": np.eye(3, dtype="f4")}
        for k, v in values.items():
            if k in prog:
                prog[k].write(np.ascontiguousarray(v.T).tobytes())
        for k, v in uniforms.items():
            if k in prog:
                prog[k].value = v
        texture(tex).use(0)
        data = np.hstack([verts[:, :4], verts[:, 4:8], np.tile(np.array(tint, "f4"), (len(verts), 1)), verts[:, 8:]])
        ids = np.tile(np.array([uniforms.get("mc_Entity", 0), 0, 0, 0], "f4"), (len(verts), 1))
        buf = ctx.buffer(np.hstack([data, ids]).astype("f4").tobytes())
        content, fmt = [], []
        for attr, n in (("a_pos", 4), ("a_uv", 4), ("a_color", 4), ("a_normal", 3), ("mc_Entity", 4)):
            if attr in prog:
                fmt.append(f"{n}f"); content.append(attr)
            else:
                fmt.append(f"{n * 4}x")
        ctx.vertex_array(prog, [(buf, " ".join(fmt), *content)]).render()
    final = program("final")
    out = ctx.texture(size, 4); target = ctx.framebuffer([out]); target.use(); ctx.disable(moderngl.BLEND | moderngl.DEPTH_TEST)
    solid.use(0); thin.use(1); final["colortex2"].value = 0; final["colortex3"].value = 1
    quad = np.array([[-1, -1, 0, 1, 0, 0, 0, 1], [1, -1, 0, 1, 1, 0, 0, 1], [1, 1, 0, 1, 1, 1, 0, 1], [-1, -1, 0, 1, 0, 0, 0, 1],
                     [1, 1, 0, 1, 1, 1, 0, 1], [-1, 1, 0, 1, 0, 1, 0, 1]], "f4")
    ctx.vertex_array(final, [(ctx.buffer(quad.tobytes()), "4f 4f", "a_pos", "a_uv")]).render()
    f4 = lambda t: np.frombuffer(t.read(), "f4").reshape(size[1], size[0], 4)[::-1]
    pic = np.frombuffer(out.read(), np.uint8).reshape(size[1], size[0], 4)[::-1]
    return f4(solid), f4(thin), pic

WHITE = (1, 1, 1, 1)
def terrain(tex, lo, size):
    block_id = 2001 if tex.endswith("glass") else 0 if tex.endswith("leaves") else 2000
    return ("gbuffers_terrain", f"block/{tex}.png", box(lo, size), {"mc_Entity": block_id}, WHITE)

def player(x, y, z):
    """The wide player model, 1.8 m tall, with the vanilla skin layout."""
    px = 1 / 16 * 0.9375
    parts = [((-4, 24, -4), (8, 8, 8), (0, 0)), ((-4, 12, -2), (8, 12, 4), (16, 16)), ((-8, 12, -2), (4, 12, 4), (40, 16)),
             ((4, 12, -2), (4, 12, 4), (32, 48)), ((-4, 0, -2), (4, 12, 4), (0, 16)), ((0, 0, -2), (4, 12, 4), (16, 48))]
    out = []
    for lo, (w, h, d), (u, v) in parts:
        rects = [(u + d, v + d, w, h), (u + 2 * d + w, v + d, w, h), (u + d + w, v + d, d, h), (u, v + d, d, h),
                 (u + d, v, w, d), (u + d + w, v, w, d)]
        uvs = [(a / 64, b / 64, (a + c) / 64, (b + e) / 64) for a, b, c, e in rects]
        out.append(box((x + lo[0] * px, y + lo[1] * px, z + lo[2] * px), (w * px, h * px, d * px), uvs))
    return ("gbuffers_entities", "entity/player/wide/steve.png", np.vstack(out), {"entityId": 1001}, WHITE)

def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    failed = 0
    def check(name, ok, detail=""):
        nonlocal failed
        failed += not ok
        print(("PASS " if ok else "FAIL ") + name, detail)
    C = (H // 2, W // 2)
    def length_of(scene):
        s, _, pic = render(scene, fov=20)
        entries, exits, n_in, n_out = (float(v) for v in s[C])
        path = exits / n_out if n_in < 0.5 else min(n_in, n_out) * (exits / n_out - entries / n_in)
        return path, float(pic[C][0])
    one = length_of([terrain("stone", (-4, -4, -6), (8, 8, 1))])
    three = length_of([terrain("stone", (-4, -4, -8), (8, 8, 3))])
    two = length_of([terrain("stone", (-4, -4, -6), (8, 8, 1)), terrain("stone", (-4, -4, -10), (8, 8, 1))])
    check("1 m wall measures 1 m", abs(one[0] - 1) < 0.02, f"{one[0]:.3f}")
    check("3 m wall measures 3 m", abs(three[0] - 3) < 0.05, f"{three[0]:.3f}")
    check("two 1 m walls measure 2 m (the gap is air)", abs(two[0] - 2) < 0.05, f"{two[0]:.3f}")
    check("thicker is brighter, a far wall is not hidden", one[1] < two[1] <= three[1] + 6 and two[1] > one[1] + 3,
          f"film 1m={one[1]:.0f} 2x1m={two[1]:.0f} 3m={three[1]:.0f}")
    far = length_of([terrain("stone", (-4, -4, -200), (8, 8, 190))])
    check("matter beyond the range is cut at the range", abs(far[0] - 86) < 1, f"{far[0]:.1f}")
    inside = length_of([terrain("stone", (-4, -4, -3), (8, 8, 6))])
    check("camera inside rock measures the way out", abs(inside[0] - 3) < 0.05, f"{inside[0]:.3f}")
    films = {m: length_of([terrain(m, (-4, -4, -6), (8, 8, 1))])[1] for m in ("oak_planks", "dirt", "stone", "iron_block", "gold_block")}
    v = list(films.values())
    check("denser materials are brighter", all(a < b + 2 for a, b in zip(v, v[1:])) and v[0] < v[-1] - 30, str({k: round(x) for k, x in films.items()}))
    _, _, empty = render([], fov=20)
    check("air is black", empty[..., 0].mean() < 4, f"{empty[..., 0].mean():.1f}")
    _, rest, pic = render([terrain("oak_leaves", (-2, -2, -22), (4, 4, 1))], fov=20)
    check("a block with holes does not count the air in front of it", rest[..., 0].max() < 40 and pic[..., 0].mean() < 190,
          f"max tau {rest[..., 0].max():.1f}, film {pic[..., 0].mean():.0f}")
    pane = render([terrain("glass", (-4, -4, -6), (8, 8, 1))], fov=20)[2]
    check("a glass cube is uniform, not a frame", pane[..., 0].min() > 80, f"film min {pane[..., 0].min()}")
    rock = [terrain("stone", (-8, -6, -30), (16, 12, 20))]
    behind = render(rock, fov=50)[2][..., 0].astype(float)
    with_player = render(rock + [player(0, -0.9, -2.5)], fov=50)[2][..., 0].astype(float)
    diff = np.abs(with_player - behind)
    changed = diff[diff > 6]
    check("a player stays visible in front of 20 m of rock (dual energy)", changed.size > 500 and np.median(changed) > 12,
          f"pixels {changed.size}, median change {np.median(changed) if changed.size else 0:.0f}")
    _, rest, pic = render([player(-0.0, -0.9, -2.5)], fov=50)
    body = rest[..., 1][rest[..., 1] > 0]
    check("a player shows bone and fainter flesh", body.size > 500 and np.percentile(body, 95) > 3 * np.percentile(body, 15),
          f"tau p15={np.percentile(body, 15):.2f} p95={np.percentile(body, 95):.2f}")
    Image.fromarray(pic).convert("L").save(out / "player.png")

    # demo scene: sky, a player in front of a wall with ores and a cave behind it, a second player behind rock
    ground = [terrain("stone", (-12, -6, -30), (24, 4, 28)), terrain("dirt", (-12, -2, -30), (6, 1, 28))]
    wall = [terrain("stone", (-6, -2, -12), (3, 4, 1)), terrain("iron_block", (-3, -2, -12), (1, 1, 1)),
            terrain("oak_planks", (-3, -1, -12), (1, 3, 1)), terrain("glass", (-2, -2, -12), (1, 3, 1)),
            terrain("gold_block", (2, -1, -12), (1, 1, 1)), terrain("dirt", (3, -2, -12), (3, 4, 1)),
            terrain("diamond_ore", (-5, -4, -9), (1, 1, 1)), terrain("gold_ore", (1, -4, -8), (1, 1, 1)),
            terrain("oak_leaves", (4, -2, -8), (2, 2, 2))]
    _, _, pic = render(ground + wall + [player(-1, -2, -6), player(0.8, -2, -16), player(4.5, 1.5, -14)], eye=(0, 0.6, 1), fov=70)
    Image.fromarray(pic).convert("L").resize((W * 2, H * 2), 0).save(out / "scene.png")
    print("failed:", failed, "| images in", out)
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
