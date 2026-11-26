"""Render every texture from its per-region material assignment using the X-ray physics model.
Usage: python3 tools/physics_render.py [--out DIR] [--only-assigned]
Needs tools/assignments/<rel>.json for each texture (made by the annotators), /tmp/mc sources (texsrc.py)."""
import sys, os, json, pathlib, argparse, zlib, subprocess, zipfile
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
RELATIVE_KINDS = {"gui", "font", "map", "colormap", "palettes", "particle", "effect"}
BLEND_MASKS = ("misc/", "environment/")
# The game multiplies water by the biome colour (default #3F76E4). These textures are divided by it in
# advance, so water comes out gray there; the price is that it cannot be brighter than 0x3F.
WATER = ("block/water_still", "block/water_flow", "block/water_overlay")
WATER_TINT = np.array([0x3F, 0x76, 0xE4], float)
MIN_ITEM_ALPHA = 55  # display floor: things fainter than ~0.1 alpha are discarded by the game
MIN_VISIBLE_TAU = 0.02
# thin water in air, and lights in the sky: an X-ray film records neither
AIRBORNE = ("environment/clouds", "environment/rain", "environment/snow", "environment/sun", "environment/moon",
            "environment/celestial", "environment/end_sky", "environment/end_flash")
DETAIL = 1.2   #texture shading modulates density/path length (cosmetic mottle, clipped to x0.3..x1.7)

GAS_DENSITY = 0.05   # g/cm3: flames, plasma and air stop nothing

def full_cube_sprites():
    """Block sprites shown on a face of a one metre cube in the newest jar: the beam crosses 100 cm there."""
    with zipfile.ZipFile(texsrc.JAR) as z:
        prefix = "assets/minecraft/models/block/"
        models = {"block/" + n[len(prefix):-5]: json.loads(z.read(n))
                  for n in z.namelist() if n.startswith(prefix) and n.endswith(".json")}
    short = lambda s: s.split(":", 1)[-1]
    found = set()
    for name in models:
        tex, elements, walk = {}, None, name
        while walk in models:
            m = models[walk]
            for k, v in m.get("textures", {}).items():
                tex.setdefault(k, v)
            if elements is None:
                elements = m.get("elements")
            walk = short(m.get("parent", ""))
        for el in elements or []:
            if el["from"] != [0, 0, 0] or el["to"] != [16, 16, 16]:
                continue
            for face in el.get("faces", {}).values():
                ref, seen = face["texture"], set()
                while isinstance(ref, str) and ref.startswith("#") and ref not in seen:
                    seen.add(ref)
                    ref = tex.get(ref[1:])
                    ref = ref.get("sprite") if isinstance(ref, dict) else ref
                if isinstance(ref, str) and not ref.startswith("#"):
                    found.add(short(ref) + ".png")
    return found

def host_material(clusters):
    """What the body of a block is made of: the solid material covering most of its face."""
    share = {}
    for c in clusters:
        if MATS[c["material"]]["density"] > GAS_DENSITY:
            share[c["material"]] = share.get(c["material"], 0) + c.get("share", 0) + 1e-6
    return MATS[max(share, key=share.get)] if share else None

def render(rel, arr, asg, fill=False):
    h, w = arr.shape[:2]
    first = clusters.first_frame(arr)
    cl = asg["clusters"]
    if rel.startswith(AIRBORNE) or not cl or not (arr[..., 3] > 0).any():      # nothing that attenuates
        return np.zeros((h, w, 4), np.uint8)
    cen = np.array([c["rgb"] for c in cl], float)
    rgb = arr[..., :3].astype(float)
    lum = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]) / 255
    d = ((rgb[:, :, None, :] - cen[None, None]) ** 2).sum(-1)
    lab = d.argmin(-1)
    if rel.startswith(BLEND_MASKS):
        # screen effects and sky: the game uses brightness as a blend mask (black = no effect),
        # so keep the exact source luminance instead of a density gray
        g = np.where(arr[..., 3] > 0, np.rint(lum * 255), 0).astype(np.uint8)
        return np.dstack([g, g, g, arr[..., 3]]).astype(np.uint8)
    clum = (0.299 * cen[:, 0] + 0.587 * cen[:, 1] + 0.114 * cen[:, 2]) / 255
    kind = asg.get("kind", rel.split("/")[0])
    is_block = rel.startswith("block/")
    logt = np.zeros((h, w))
    # a solid cube has no holes: behind each surface detail lies the rest of the metre
    host = host_material(cl) if fill and (arr[..., 3] == 255).all() else None
    for i, c in enumerate(cl):
        mat = MATS[c["material"]]
        mod = np.clip(1 + DETAIL * (lum - clum[i]), 0.3, 1.7)
        # tau is not linear in thickness for a polychromatic beam -> evaluate on a few thickness multipliers, interpolate
        ms = np.array([0.3, 0.5, 0.75, 1.0, 1.25, 1.5, 1.7])
        taus = np.array([xp.tau_eff(mat, c["thickness_cm"] * m) for m in ms])
        if host is not None:
            if mat["density"] <= GAS_DENSITY:      # a cavity or a flame: three quarters of the block remain
                taus = taus + xp.tau_eff(host, 75.0)
            elif c["thickness_cm"] < 100:
                taus = taus + xp.tau_eff(host, 100.0 - c["thickness_cm"])
        taus = LOG(np.maximum(taus, 1e-9))
        logt = np.where(lab == i, np.interp(mod, ms, taus), logt)
    if is_block: s = (logt - LO_BLOCK) / (HI_BLOCK - LO_BLOCK)
    else: s = (logt - LO_OBJ) / (HI_OBJ - LO_OBJ)
    s = np.clip(s, 0, 1)
    src_a = arr[..., 3].astype(float)
    valid = src_a > 0
    if is_block:
        gray = 40 + 215 * s
        # real opacity 1 - transmission (Beer-Lambert); s only sets the gray. Water's own alpha is
        # the game's see-through look, so it is ignored.
        alpha = -np.expm1(-10.0 ** logt) * (np.where(valid, 255.0, 0.0) if rel.startswith(WATER) else src_a)
    elif rel.startswith("particle/") or (rel.startswith("item/") and kind not in RELATIVE_KINDS):
        gray = 25 + 230 * s    # the same scale as every object (the shader pack decodes it back)
        # smoke, flame and the like attenuate nothing measurable, so they do not show at all
        alpha = np.where(10.0 ** logt < MIN_VISIBLE_TAU, 0.0,
                         np.maximum(-np.expm1(-10.0 ** logt) * 255, MIN_ITEM_ALPHA) * src_a / 255)
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
    if rel.startswith(WATER):
        v = g / max(g.max(), 1) * WATER_TINT.min()
        rgb = np.clip(np.rint(v[..., None] * 255 / WATER_TINT), 0, 255).astype(np.uint8)
        return np.dstack([rgb, a])
    return np.dstack([g, g, g, a])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="assets/minecraft/textures"); ap.add_argument("--only-assigned", action="store_true")
    a = ap.parse_args(); out = pathlib.Path(a.out); adir = pathlib.Path(__file__).with_name("assignments")
    n = miss = 0
    cubes = full_cube_sprites()
    for rel in texsrc.all_paths():
        ap_ = adir / (rel + ".json")
        if not ap_.exists():
            miss += 1
            if not a.only_assigned: print("MISSING ASSIGNMENT", rel)
            continue
        asg = json.loads(ap_.read_text())
        arr = np.asarray(texsrc.load(rel))
        res = render(rel, arr, asg, fill=rel in cubes)
        p = out / rel; p.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(res).save(p)
        mc = texsrc.mcmeta(rel)
        if mc is not None: (out / (rel + ".mcmeta")).write_bytes(mc)
        n += 1
    print(f"rendered {n}, missing assignments {miss}")
    if a.out == ap.get_default("out"):   # creatures are painted as radiographs on top of the flat render
        for script in ("generate_mob_skeletons.py", "generate_player_skins.py"):
            subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name(script))], check=True)
    return1 if miss and not a.only_assigned else 0
if __name__ == "__main__":
    sys.exit(main())
