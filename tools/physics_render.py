"""Render every texture from its per-region material assignment using the X-ray physics model.
Usage: python3 tools/physics_render.py [--out DIR] [--only-assigned]
Needs tools/assignments/<rel>.json for each texture (made by the annotators), /tmp/mc sources (texsrc.py)."""
import sys, os, json, pathlib, argparse, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import texsrc, clusters, materials, xray_physics as xp

MATS = materials.load_all()
LOG = np.log10
# Window anchors (physical, not tuned per file):
#   blocks (1 m cube): 0 = 1 m of foliage (nearly invisible), 1 = 1 m of gold (maximum)
#   small objects    : 0 = 0.5 mm of water,                    1 = 5 cm of steel
LO_BLOCK, HI_BLOCK = LOG(xp.tau_eff(MATS["foliage"], 100)), LOG(xp.tau_eff(MATS["gold"], 100))
LO_OBJ, HI_OBJ = LOG(xp.tau_eff(MATS["water"], 0.05)), LOG(xp.tau_eff(MATS["steel"], 5))
RELATIVE_KINDS = {"gui", "font", "misc", "map", "colormap", "palettes", "environment", "particle", "effect"}
DETAIL = 1.2   # texture shading modulates density/path length (cosmetic mottle, clipped to x0.3..x1.7)

def render(rel, arr, asg):
    h, w = arr.shape[:2]
    first = clusters.first_frame(arr)
    cl = asg["clusters"]
    if not cl or not (arr[..., 3] > 0).any():      # fully transparent texture: nothing to attenuate
        return np.zeros((h, w, 4), np.uint8)
    cen = np.array([c["rgb"] for c in cl], float)
    rgb = arr[..., :3].astype(float)
    lum = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]) / 255
    d = ((rgb[:, :, None, :] - cen[None, None]) ** 2).sum(-1)
    lab = d.argmin(-1)
    clum = (0.299 * cen[:, 0] + 0.587 * cen[:, 1] + 0.114 * cen[:, 2]) / 255
    kind = asg.get("kind", rel.split("/")[0])
    is_block = rel.startswith("block/")
    logt = np.zeros((h, w))
    base = {}
    for i, c in enumerate(cl):
        mat = MATS[c["material"]]
        mod = np.clip(1 + DETAIL * (lum - clum[i]), 0.3, 1.7)
        # tau is not linear in thickness for a polychromatic beam -> evaluate on a few thickness multipliers, interpolate
        ms = np.array([0.3, 0.5, 0.75, 1.0, 1.25, 1.5, 1.7])
        taus = np.array([LOG(max(xp.tau_eff(mat, c["thickness_cm"] * m), 1e-9)) for m in ms])
        logt = np.where(lab == i, np.interp(mod, ms, taus), logt)
    if is_block: s = (logt - LO_BLOCK) / (HI_BLOCK - LO_BLOCK)
    else: s = (logt - LO_OBJ) / (HI_OBJ - LO_OBJ)
    s = np.clip(s, 0, 1)
    src_a = arr[..., 3].astype(float)
    valid = src_a > 0
    if is_block:
        gray = 40 + 215 * s
        alpha = (12 + 243 * s) * src_a / 255
    elif kind in RELATIVE_KINDS:
        lt = logt[valid]
        rel_s = (logt - lt.min()) / (lt.max() - lt.min()) if valid.any() and lt.max() > lt.min() else np.full_like(logt, 0.8)
        gray = 60 + 195 * np.clip(rel_s, 0, 1)
        alpha = src_a
    else:
        gray = 25 + 230 * s
        alpha = src_a
    # cosmetic film grain (seeded by path), never on transparent pixels
    rng = np.random.default_rng(zlib.crc32(rel.encode()))
    gray = gray + rng.normal(0, 2.0, size=gray.shape) * (1 if is_block else 0.5)
    g = np.where(valid, np.clip(np.rint(gray), 0, 255), 0).astype(np.uint8)
    a = np.where(valid, np.clip(np.rint(alpha), 0, 255), 0).astype(np.uint8)
    return np.dstack([g, g, g, a])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="assets/minecraft/textures"); ap.add_argument("--only-assigned", action="store_true")
    a = ap.parse_args(); out = pathlib.Path(a.out); adir = pathlib.Path(__file__).with_name("assignments")
    n = miss = 0
    for rel in texsrc.all_paths():
        ap_ = adir / (rel + ".json")
        if not ap_.exists():
            miss += 1
            if not a.only_assigned: print("MISSING ASSIGNMENT", rel)
            continue
        asg = json.loads(ap_.read_text())
        arr = np.asarray(texsrc.load(rel))
        res = render(rel, arr, asg)
        p = out / rel; p.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(res).save(p)
        mc = texsrc.mcmeta(rel)
        if mc is not None: (out / (rel + ".mcmeta")).write_bytes(mc)
        n += 1
    print(f"rendered {n}, missing assignments {miss}")
    return 1 if miss and not a.only_assigned else 0
if __name__ == "__main__":
    sys.exit(main())
