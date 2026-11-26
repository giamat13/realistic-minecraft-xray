"""Backport support for Minecraft 1.19.4 .. 1.21.11.

1. Textures that exist only in older versions are converted with the same
   X-ray rules (newest version wins when a path exists in several).
2. Before 26.1 a resource pack cannot make a block translucent, so light
   cube-shaped blocks (rock, earth, wood, leaves, glass, ...) get an EMPTY
   model (classic x-ray) and dense ones (ores, metals) stay solid.
   These live in the base pack; overlay_26_1 re-adds real translucency.
Input: /tmp/mc/v/<version>/ extracted by the fetch step."""
import io, json, os, sys, pathlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import generate_textures as gt

V = pathlib.Path("/tmp/mc/v")
def key(s): return [int(x) if x.isdigit() else x for x in s.replace("-", ".").split(".")]
legacy = sorted((p.name for p in V.iterdir() if p.is_dir() and (p / "DONE").exists()
                 and key(p.name) < [26]), key=key, reverse=True)
print("legacy versions:", legacy)

# 1. textures
new_png = new_meta = 0
for ver in legacy:
    root = V / ver / "assets/minecraft/textures"
    for f in sorted(root.rglob("*")):
        rel = f.relative_to(root).as_posix()
        dst = pathlib.Path(gt.OUT_ROOT) / rel
        if dst.exists():
            continue
        if f.name.endswith(".png"):
            arr = np.asarray(Image.open(f).convert("RGBA"))
            dst.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(gt.process(rel, arr)).save(dst)
            new_png += 1
        elif f.name.endswith(".png.mcmeta"):
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(f.read_bytes())
            new_meta += 1
print("extra legacy textures:", new_png, "mcmeta:", new_meta)

# 2. empty models for light cube blocks
CUBES = ("cube", "cube_all", "cube_column", "cube_column_horizontal", "cube_bottom_top",
         "cube_top", "cube_directional", "cube_mirrored_all", "cube_mirrored",
         "cube_column_mirrored", "template_single_face", "leaves", "block")
def tex_of(m):
    t = m.get("textures", {})
    for k in ("all", "side", "end", "top", "up", "north", "texture", "particle"):
        v = t.get(k)
        if isinstance(v, str) and not v.startswith("#"):
            return v.replace("minecraft:", "")
    return None
out = pathlib.Path("assets/minecraft/models/block"); done = set(); n_empty = n_keep = 0
for ver in legacy:
    for f in sorted((V / ver / "assets/minecraft/models/block").glob("*.json")):
        if f.name in done: continue
        done.add(f.name)
        m = json.loads(f.read_text())
        parent = m.get("parent", "").replace("minecraft:", "").replace("block/", "")
        tx = tex_of(m)
        if parent not in CUBES or not tx or "elements" in m: continue
        lo, hi, alpha, ore = gt.classify(tx + ".png")
        if ore or alpha > 130:
            n_keep += 1; continue
        out.mkdir(parents=True, exist_ok=True)
        keep = {k: v for k, v in m.get("textures", {}).items() if k == "particle"}
        (out / f.name).write_text(json.dumps({"textures": keep, "elements": []}, indent=2))
        n_empty += 1
print("empty models:", n_empty, "kept solid:", n_keep)
