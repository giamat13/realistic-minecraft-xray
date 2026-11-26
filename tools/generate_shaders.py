"""Black and white for what the game colours in code (particles, entities, held and GUI items, text),
no lighting, and a black sky: nothing on a radiograph is lit, and empty space is unexposed.

Wraps the vanilla core fragment shaders so their output keeps its brightness but loses its hue.
The light map becomes plain white and the sky, sun, stars and clouds emit nothing.
Left out on purpose: terrain (Sodium does not support resource packs replacing it; water and terrain
are covered by the Improved Transparency composite in shaders/post/transparency.fsh) and the
technical blit / mask shaders, whose output is not a colour on screen.
Usage: python3 tools/generate_shaders.py <client.jar> <overlay directory>"""
import re, sys, zipfile, pathlib, shutil
from build_shaderpack import SKIN, CONSTANTS

PREFIX = "assets/minecraft/shaders/core/"
SKIP = {"terrain", "animate_sprite_blit", "animate_sprite_interpolate", "blit_screen", "rendertype_water_mask",
        "blit_depth", "integrate_depth", "oit_depth_bounds_cull"}
CONSTANT = {"lightmap": "vec4(1.0)", "sky": "vec4(0.0, 0.0, 0.0, 1.0)", "stars": "vec4(0.0)"}
WRAPPER = """
void main() {
    vanillaMain();
    fragColor.rgb = vec3(dot(fragColor.rgb, vec3(0.2126, 0.7152, 0.0722)));
}
"""

# An account skin comes from the server, so no texture can replace it: the entity shader recognises a
# coloured 64x64 texture (everything the pack ships is gray) and draws the skeleton instead of it.
PROBES = ((9, 9), (12, 12), (14, 14), (10, 13), (22, 22), (25, 26), (23, 30), (45, 22), (5, 22), (21, 54), (37, 54), (12, 3))
SKIN_SAMPLE = "texture(Sampler0, texCoord0)"

def skin_helper():
    probes = ", ".join(f"ivec2({x}, {y})" for x, y in PROBES)
    constants = "".join(f"const float {k} = {CONSTANTS[k]:.6f};\n"
                        for k in ("LO_OBJ", "HI_OBJ", "TAU_BONE", "TAU_FLESH"))
    return constants + SKIN + f"""
vec4 entityTexel(vec2 at) {{
    if (textureSize(Sampler0, 0) == ivec2(64)) {{
        ivec2 probes[{len(PROBES)}] = ivec2[{len(PROBES)}]({probes});
        for (int i = 0; i < {len(PROBES)}; i++) {{
            vec4 s = texelFetch(Sampler0, probes[i], 0);
            if (s.a > 0.5 && max(s.r, max(s.g, s.b)) - min(s.r, min(s.g, s.b)) > 0.03) {{
                float d = 2.0 * skeletonSkin(ivec2(fract(at) * 64.0)); // both sides of the limb
                if (d < 0.0) discard;
                float s01 = clamp((log(d) / log(10.0) - LO_OBJ) / (HI_OBJ - LO_OBJ), 0.0, 1.0);
                return vec4(vec3((25.0 + 230.0 * s01) / 255.0), 1.0 - exp(-d));
            }}
        }}
    }}
    return texture(Sampler0, at);
}}
"""

def main():
    out = pathlib.Path(sys.argv[2]) / PREFIX
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    done = 0
    with zipfile.ZipFile(sys.argv[1]) as z:
        for name in z.namelist():
            if not (name.startswith(PREFIX) and name.endswith(".fsh")) or pathlib.PurePosixPath(name).stem in SKIP:
                continue
            src = z.read(name).decode("utf-8").replace("\r\n", "\n")
            src, n = re.subn(r"\bvoid\s+main\s*\(\s*(?:void)?\s*\)", "void vanillaMain()", src)
            if n != 1 or not re.search(r"\bout\s+vec4\s+fragColor\s*;", src):
                sys.exit(f"unexpected shader layout: {name}")
            stem = pathlib.PurePosixPath(name).stem
            body = WRAPPER
            if stem == "entity":
                if src.count("vec4 color = " + SKIN_SAMPLE) != 1:
                    sys.exit(f"unexpected skin sampling: {name}")
                src = src.replace("vec4 color = " + SKIN_SAMPLE, "vec4 color = entityTexel(texCoord0)")
                src = src.replace("void vanillaMain()", skin_helper() + "\nvoid vanillaMain()")
                # helpers that run before main (26.3 calculateFinalColor) are untouched
            if stem in CONSTANT:
                body = f"\nvoid main() {{\n    vanillaMain();\n    fragColor = {CONSTANT[stem]};\n}}\n"
            if "#ifndef OIT_ALPHA_ONLY" in src:  # that variant of the shader has no colour output
                body = re.sub(r"(?m)^(    fragColor.*)$", r"#ifndef OIT_ALPHA_ONLY\n\1\n#endif", body)
            (out / (stem + ".fsh")).write_text(src.rstrip() + "\n" + body, encoding="utf-8", newline="\n")
            done += 1
    print(f"shaders written: {done}")

if __name__ == "__main__":
    main()
