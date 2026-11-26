"""Completeness check across ALL supported versions (needs /tmp/mc/v + client.jar for 26.3)."""
import pathlib, sys, zipfile, json, numpy as np
from PIL import Image
root = pathlib.Path("assets/minecraft/textures")
pack = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
need = {}
for d in sorted(pathlib.Path("/tmp/mc/v").iterdir()):
    if d.is_dir() and (d/"DONE").exists():
        t = d/"assets/minecraft/textures"
        for f in t.rglob("*"):
            if f.is_file(): need.setdefault(f.relative_to(t).as_posix(), d.name)
with zipfile.ZipFile("/tmp/mc/client.jar") as z:
    for n in z.namelist():
        if n.startswith("assets/minecraft/textures/") and not n.endswith("/"):
            need.setdefault(n[len("assets/minecraft/textures/"):], "26.3")
missing = sorted(set(need) - pack)
extra = sorted(pack - set(need))
bad = 0
for p in pack:
    if p.endswith(".png"):
        a = np.asarray(Image.open(root/p).convert("RGBA"))
        if not ((a[..., 0] == a[..., 1]).all() and (a[..., 1] == a[..., 2]).all()): bad += 1
print(f"versions' texture paths: {len(need)}  in pack: {len(pack)}  missing: {len(missing)}  extra: {len(extra)}  non-gray: {bad}")
# models: every 26.3 block model that has textures must exist in overlay
with zipfile.ZipFile("/tmp/mc/client.jar") as z:
    mm = [n for n in z.namelist() if n.startswith("assets/minecraft/models/block/") and n.endswith(".json") and json.loads(z.read(n)).get("textures")]
mo = [n for n in mm if not pathlib.Path("overlay_26_1", n).exists()]
print(f"26.3 block models with textures: {len(mm)}  missing from overlay: {len(mo)}")
# any non-translucent sprite left in overlay?
left = 0
for f in pathlib.Path("overlay_26_1").rglob("*.json"):
    for v in json.loads(f.read_text())["textures"].values():
        if isinstance(v, str) and not v.startswith("#"): left += 1
        if isinstance(v, dict) and not v.get("force_translucent"): left += 1
print("untranslucent sprites in overlay:", left)
sys.exit(1 if missing or bad or mo or left else 0)
