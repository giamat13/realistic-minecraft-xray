"""Physics + completeness checks for the rendered pack (needs /tmp/mc sources)."""
import sys, os, json, pathlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import xray_physics as xp, materials, texsrc
M = materials.load_all(); ok = True
def check(name, cond, info=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name, info)
# 1. NIST data fidelity (published values at 100 keV, cm2/g)
check("NIST mu/rho Fe 100keV = 0.3717", abs(xp.mu_rho_element("Fe", 0.1) - 0.3717) < 1e-3)
check("NIST mu/rho Pb 100keV = 5.549", abs(xp.mu_rho_element("Pb", 0.1) - 5.549) < 1e-2)
check("NIST mu/rho water 100keV = 0.1707", abs(xp.mu_rho_material(M["water"]["mass_fractions"], 0.1) - 0.1707) < 1e-3)
# 2. Beer-Lambert: thin slab tau ~ mu*t (bounded by spectrum extremes), exact exponential for monochromatic limit
t = 1e-4; ratio = xp.tau_eff(M["iron"], t) / (M["iron"]["density"] * t)
mus = [xp.mu_rho_material(M["iron"]["mass_fractions"], e / 1000) for e in xp._E]
check("thin-slab tau/(rho t) within spectrum mu range", min(mus) <= ratio <= max(mus), f"{ratio:.3f} in [{min(mus):.3f},{max(mus):.3f}]")
a, b = xp.tau_eff(M["stone"], 10), xp.tau_eff(M["stone"], 20)
check("tau grows with thickness, sub-linear (beam hardening)", 0 < a < b < 2 * a + 1e-9, f"{a:.2f} -> {b:.2f}")
# 3. material ordering at 1 m
order = ["foliage", "water", "stone", "iron", "gold"]
taus = [xp.tau_eff(M[m], 100) for m in order]
check("tau ordering foliage<water<stone<iron<gold", taus == sorted(taus), str([round(x, 1) for x in taus]))
# 4. rendered pack
root = pathlib.Path("assets/minecraft/textures"); paths = texsrc.all_paths(); bad = miss = size = 0; asg = pathlib.Path("tools/assignments")
for r in paths:
    p = root / r
    if not p.exists(): miss += 1; continue
    a = np.asarray(Image.open(p).convert("RGBA"))
    # water is stored pre-divided by the game's blue water tint (see physics_render.WATER)
    if not r.startswith("block/water_") and not ((a[..., 0] == a[..., 1]).all() and (a[..., 1] == a[..., 2]).all()): bad += 1
    if Image.open(p).size != texsrc.load(r).size: size += 1
check("every texture of every version rendered", miss == 0, f"{len(paths)} paths, missing {miss}")
check("all pixels grayscale", bad == 0); check("sizes identical to source", size == 0)
check("every texture has an assignment", all((asg / (r + ".json")).exists() for r in paths))
def lost(r):  # share of the source's visible pixels that cannot be seen (the game drops alpha below 0.1)
    was = np.asarray(texsrc.load(r).convert("RGBA"))[..., 3] > 25
    now = np.asarray(Image.open(root / r).convert("RGBA"))[..., 3] > 25
    return (was & ~now).sum() / max(was.sum(), 1)
INK = {"item/filled_map_markings.png"}  # pigment drawn over the map: nothing for a ray to stop
hidden = [r for r in paths if r.startswith("item/") and r not in INK and lost(r) > 0.05]
check("no item loses its picture", not hidden, str(hidden[:20]))
def stat(n):
    a = np.asarray(Image.open(root / f"block/{n}.png").convert("RGBA")).astype(float); v = a[a[..., 3] > 0]; return v[:, 0].mean(), v[:, 3].mean()
s = {n: stat(n) for n in ["oak_leaves", "dirt", "stone", "oak_planks", "iron_block", "gold_block", "netherite_block", "glass", "oak_door_top"]}
check("1 m solid blocks are opaque (Beer-Lambert)", all(s[n][1] >= 254 for n in ["dirt", "stone", "oak_planks", "iron_block", "gold_block", "netherite_block", "glass"]), {k: round(v[1]) for k, v in s.items()})
check("thin or porous things transmit (door, leaves)", s["oak_door_top"][1] < 200 and s["oak_leaves"][1] < 254)
check("brightness: leaves < planks < dirt < stone < iron_block <= gold_block", s["oak_leaves"][0] < s["oak_planks"][0] < s["dirt"][0] < s["stone"][0] < s["iron_block"][0] <= s["gold_block"][0], {k: round(v[0]) for k, v in s.items()})
def margin(n):
    a = np.asarray(Image.open(root / f"block/{n}.png").convert("RGBA")).astype(float)[..., 0]; return a.max() - np.median(a)
mg = {n: margin(n) for n in ["gold_ore", "redstone_ore", "copper_ore", "iron_ore", "diamond_ore", "coal_ore", "emerald_ore"]}
check("heavy-metal ores stand out of the host rock (gold>redstone>copper>iron margins)", mg["gold_ore"] > mg["redstone_ore"] > mg["copper_ore"] > mg["iron_ore"] > 20, {k: round(v) for k, v in mg.items()})
check("low-Z ores (diamond, coal, emerald) are radiolucent like their host - real physics", max(mg["diamond_ore"], mg["coal_ore"], mg["emerald_ore"]) < 10)
# set consistency: all woods' doors same thickness, colour variants same materials
def mats(n): return [(c["material"], c["thickness_cm"]) for c in json.load(open(asg / f"block/{n}.png.json"))["clusters"]]
cols = ["white", "red", "blue", "green", "black"]
ms = [sorted(set(mats(f"{c}_wool"))) for c in cols]
check("wool colours share materials", all(m == ms[0] for m in ms))
import zipfile
with zipfile.ZipFile(texsrc.JAR) as z:
    mm = [n for n in z.namelist() if n.startswith("assets/minecraft/models/block/") and n.endswith(".json") and json.loads(z.read(n)).get("textures")]
check("every 26.3 block model with textures exists in overlay_26_1", all(pathlib.Path("overlay_26_1", n).exists() for n in mm), f"{len(mm)} models")
left = sum(1 for f in pathlib.Path("overlay_26_1").rglob("*.json") for v in json.loads(f.read_text())["textures"].values()
           if (isinstance(v, str) and not v.startswith("#")) or (isinstance(v, dict) and not v.get("force_translucent")))
check("no non-translucent sprite left in overlay", left == 0)
check("pack.mcmeta valid", "pack" in json.load(open("pack.mcmeta")))
# shape thickness: the same wood is thinner through a pressure plate than through a full block
over = pathlib.Path("overlay_26_1/assets/minecraft")
def face(model, side):
    m = json.loads((over / f"models/block/{model}.json").read_text())
    ref = m["elements"][0]["faces"][side]["texture"][1:]
    sprite = m["textures"][ref]["sprite"].split(":")[-1]
    a = np.asarray(Image.open(over / f"textures/{sprite}.png").convert("RGBA")).astype(float)
    return sprite, a[..., 0].mean(), a[..., 3].mean()
plate = face("oak_pressure_plate", "up")
check("pressure plate top is thinner than planks (less opaque, darker)", plate[2] < s["oak_planks"][1] and plate[1] < s["oak_planks"][0], f"{plate[0]} gray {plate[1]:.0f} alpha {plate[2]:.0f}")
lost = []
for f in (over / "models/block").rglob("*.json"):
    for v in json.loads(f.read_text())["textures"].values():
        sp = v["sprite"] if isinstance(v, dict) else v
        if "block/xray/" in sp and not (over / f"textures/{sp.split(':')[-1]}.png").exists(): lost.append(sp)
check("every shape variant referenced by a model exists", not lost, str(lost[:3]))
sys.exit(0 if ok else 1)
