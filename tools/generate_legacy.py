"""Backport support for Minecraft 1.19.4 .. 1.21.11.

2. Before 26.1 a resource pack cannot make a block translucent, so light
   cube-shaped blocks (rock, earth, wood, leaves, glass, ...) get an EMPTY
   model (classic x-ray) and dense ones (ores, metals) stay solid.
   These live in the base pack; overlay_26_1 re-adds real translucency.
Input: /tmp/mc/v/<version>/ extracted by the fetch step."""
import io, json, os, sys, pathlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
TEX = pathlib.Path("assets/minecraft/textures")

V = pathlib.Path("/tmp/mc/v")
def key(s): return [int(x) if x.isdigit() else x for x in s.replace("-", ".").split(".")]
legacy = sorted((p.name for p in V.iterdir() if p.is_dir() and (p / "DONE").exists()
                 and key(p.name) < [26]), key=key, reverse=True)
print("legacy versions:", legacy)

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
        p = TEX / (tx + ".png")                      # decide from the PHYSICS-rendered texture, not names
        if not p.exists(): continue
        al = np.asarray(Image.open(p).convert("RGBA"))[..., 3].astype(float)
        if al.mean() > 130 or al.max() > 200:        # dense (metal-bearing / heavy) -> stays solid
            n_keep += 1; continue
        out.mkdir(parents=True, exist_ok=True)
        keep = {k: v for k, v in m.get("textures", {}).items() if k == "particle"}
        (out / f.name).write_text(json.dumps({"textures": keep, "elements": []}, indent=2))
        n_empty += 1
print("empty models:", n_empty, "kept solid:", n_keep)
