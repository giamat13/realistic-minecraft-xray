"""Render the generated entity shaders on the GPU: any coloured 64x64 skin must come out as a
skeleton, and the pack's own gray textures must pass through unchanged.
Usage: python tools/test_skin_shader.py   (needs numpy, moderngl)"""
import re, sys, pathlib
import numpy as np
import moderngl

STUBS = """
uniform vec4 ColorModulator; uniform vec4 FogColor;
uniform float FogEnvironmentalStart, FogEnvironmentalEnd, FogRenderDistanceStart, FogRenderDistanceEnd;
vec4 apply_fog(vec4 c, float a, float b, float d, float e, float f, float g, vec4 h) { return c; }
"""

def program(ctx, overlay, extra=""):
    src = pathlib.Path(overlay, "assets/minecraft/shaders/core/entity.fsh").read_text(encoding="utf-8")
    src = re.sub(r"(?m)^\s*#(moj_import|include) .*$", "", src)
    head = "#version 330\n#extension GL_ARB_separate_shader_objects : require\n"
    src = re.sub(r"(?m)^\s*#(version|extension) .*$", "", src)
    defines = "#define NO_OVERLAY\n#define EMISSIVE\n#define ALPHA_CUTOUT 0.1\n" + extra
    located = "layout(location = 0) in float sphericalVertexDistance" in src
    def at(n): return f"layout(location = {n}) " if located else ""
    vertex = head + f"""in vec2 corner;
{at(0)}out float sphericalVertexDistance;
{at(1)}out float cylindricalVertexDistance;
{at(2)}out vec4 vertexColor;
{at(6)}out vec2 texCoord0;
void main() {{
    sphericalVertexDistance = 0.0; cylindricalVertexDistance = 0.0; vertexColor = vec4(1.0);
    texCoord0 = corner * 0.5 + 0.5;
    gl_Position = vec4(corner, 0.0, 1.0);
}}
"""
    return ctx.program(vertex_shader=vertex, fragment_shader=head + defines + STUBS + src)

def render(ctx, prog, image):
    texture = ctx.texture((64, 64), 4, image.tobytes())
    texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    texture.use(0)
    for name, value in (("Sampler0", 0), ("ColorModulator", (1.0, 1.0, 1.0, 1.0))):
        if name in prog:
            prog[name].value = value
    target = ctx.framebuffer(color_attachments=[ctx.texture((64, 64), 4)])
    target.use()
    target.clear(0.0, 0.0, 0.0, 0.0)
    quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], "f4").tobytes())
    ctx.vertex_array(prog, [(quad, "2f", "corner")]).render(moderngl.TRIANGLE_STRIP)
    return np.frombuffer(target.read(components=4), np.uint8).reshape(64, 64, 4)  # row y = texel row y

def main():
    ctx = moderngl.create_standalone_context(require=330)
    failed = 0
    def check(name, ok, detail=""):
        nonlocal failed
        failed += not ok
        print("PASS" if ok else "FAIL", name, detail)
    skin = np.zeros((64, 64, 4), np.uint8)
    skin[:] = (200, 140, 100, 255)  # a coloured account skin, opaque everywhere like an uploaded one
    gray = np.zeros((64, 64, 4), np.uint8)
    gray[:] = (90, 90, 90, 200)
    gray[::2] = (210, 210, 210, 255)
    try:
        program(ctx, "overlay_26_3", "#define OIT_ALPHA_ONLY\nvoid executeAlphaOnlyPhase(float z, float a) {}\n")
        check("overlay_26_3: depth-bounds variant compiles", True)
    except moderngl.Error as error:
        check("overlay_26_3: depth-bounds variant compiles", False, str(error)[-300:])
    for overlay in ("overlay_26_2", "overlay_26_3"):
        prog = program(ctx, overlay)
        out = render(ctx, prog, skin)
        px = lambda x, y: [int(v) for v in out[y, x]]
        check(f"{overlay}: gray output", bool((np.ptp(out[..., :3].astype(int), axis=2) <= 1).all()))
        check(f"{overlay}: spine brighter than flesh", px(23, 24)[0] * px(23, 24)[3] > px(21, 24)[0] * px(21, 24)[3] > 0,
              f"{px(23, 24)} vs {px(21, 24)}")
        check(f"{overlay}: eye sockets darker than skull", px(9, 11)[3] < px(9, 9)[3], f"{px(9, 11)} vs {px(9, 9)}")
        check(f"{overlay}: hat layer is invisible", px(40, 12)[3] == 0, str(px(40, 12)))
        slim = skin.copy()
        slim[16:32, 54:56] = 0  # slim skins leave these arm columns empty
        check(f"{overlay}: slim arm has bone", render(ctx, prog, slim)[24, 45, 3] > render(ctx, prog, slim)[24, 44, 3])
        check(f"{overlay}: pack textures pass through", bool((np.abs(render(ctx, prog, gray).astype(int) - gray) <= 1).all()))
    print("failed:", failed)
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
