"""Black and white for what the game colours in code (particles, entities, held and GUI items, sky, text).

Wraps the vanilla core fragment shaders so their output keeps its brightness but loses its hue.
Left out on purpose: terrain (Sodium does not support resource packs replacing it; water and terrain
are covered by the Improved Transparency composite in shaders/post/transparency.fsh) and the
technical blit / mask shaders, whose output is not a colour on screen.
Usage: python3 tools/generate_shaders.py <26.2 client.jar>"""
import re, sys, zipfile, pathlib, shutil

OUT = pathlib.Path("overlay_26_2/assets/minecraft/shaders/core")
PREFIX = "assets/minecraft/shaders/core/"
SKIP = {"terrain", "animate_sprite_blit", "animate_sprite_interpolate", "blit_screen", "rendertype_water_mask"}
WRAPPER = """
void main() {
    vanillaMain();
    fragColor.rgb = vec3(dot(fragColor.rgb, vec3(0.2126, 0.7152, 0.0722)));
}
"""

def main():
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    done = 0
    with zipfile.ZipFile(sys.argv[1]) as z:
        for name in z.namelist():
            if not (name.startswith(PREFIX) and name.endswith(".fsh")) or pathlib.PurePosixPath(name).stem in SKIP:
                continue
            src = z.read(name).decode("utf-8").replace("\r\n", "\n")
            src, n = re.subn(r"\bvoid\s+main\s*\(\s*(?:void)?\s*\)", "void vanillaMain()", src)
            if n != 1 or not re.search(r"\bout\s+vec4\s+fragColor\s*;", src):
                sys.exit(f"unexpected shader layout: {name}")
            (OUT / pathlib.PurePosixPath(name).name).write_text(src.rstrip() + "\n" + WRAPPER, encoding="utf-8", newline="\n")
            done += 1
    print(f"shaders written: {done}")

if __name__ == "__main__":
    main()
