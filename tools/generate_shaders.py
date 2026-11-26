"""Black and white for what the game colours in code (particles, entities, held and GUI items, text),
no lighting, and a black sky: nothing on a radiograph is lit, and empty space is unexposed.

Wraps the vanilla core fragment shaders so their output keeps its brightness but loses its hue.
The light map becomes plain white and the sky, sun, stars and clouds emit nothing.
Left out on purpose: terrain (Sodium does not support resource packs replacing it; water and terrain
are covered by the Improved Transparency composite in shaders/post/transparency.fsh) and the
technical blit / mask shaders, whose output is not a colour on screen.
Usage: python3 tools/generate_shaders.py <client.jar> <overlay directory>"""
import re, sys, zipfile, pathlib, shutil

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
            if stem in CONSTANT:
                body = f"\nvoid main() {{\n    vanillaMain();\n    fragColor = {CONSTANT[stem]};\n}}\n"
            (out / (stem + ".fsh")).write_text(src.rstrip() + "\n" + body, encoding="utf-8", newline="\n")
            done += 1
    print(f"shaders written: {done}")

if __name__ == "__main__":
    main()
