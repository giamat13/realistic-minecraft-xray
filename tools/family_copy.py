"""Reuse annotations across textures that are the same thing in a different variant
(wood species, dye colour, trim material, frame number ...): copy the material/thickness per cluster rank from an
already-annotated sibling with the same cluster count.  Usage: python3 tools/family_copy.py"""
import sys, os, re, json, pathlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, texsrc, clusters
COLORS = "white orange magenta light_blue yellow lime pink gray light_gray cyan purple blue brown green red black".split()
WOODS = "oak spruce birch jungle acacia dark_oak pale_oak mangrove cherry bamboo crimson warped".split()
TRIM = "amethyst copper diamond emerald gold iron lapis netherite quartz redstone resin".split()
def key(rel):
    s = rel
    for lst in (sorted(COLORS, key=len, reverse=True), WOODS, TRIM):
        for t in lst: s = re.sub(rf"(?<![a-z]){t}(?![a-z])", "_X_", s)
    s = re.sub(r"\d+", "N", s)
    return s
A = pathlib.Path("tools/assignments")
paths = texsrc.all_paths(); done = {r for r in paths if (A / (r + ".json")).exists()}
fam = collections.defaultdict(list)
for r in paths: fam[key(r)].append(r)
copied = 0
for k, g in fam.items():
    src = [r for r in g if r in done]
    if not src or len(g) == len(src): continue
    ref = {}
    for r in src:
        d = json.loads((A / (r + ".json")).read_text()); ref.setdefault(len(d["clusters"]), d)
    for r in g:
        if r in done: continue
        arr = clusters.first_frame(np.asarray(texsrc.load(r)))
        labels, cen, sh = clusters.kmeans(arr)
        d = ref.get(len(cen))
        if d is None: continue
        d2 = {"path": r, "depicts": d["depicts"] + f" (same structure as {d['path']}; variant)", "kind": d["kind"], "clusters": [
            {"id": i, "rgb": [int(v) for v in cen[i]], "share": round(sh[i], 3), "material": d["clusters"][i]["material"], "thickness_cm": d["clusters"][i]["thickness_cm"]} for i in range(len(cen))]}
        p = A / (r + ".json"); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(d2, indent=1)); copied += 1
        done.add(r)
rem = [r for r in paths if r not in done]
print("copied", copied, "remaining", len(rem), "of", len(paths), f"-> {100*(len(paths)-len(rem))/len(paths):.1f}% done")
import shutil; shutil.rmtree("/tmp/mc/batches2", ignore_errors=True); pathlib.Path("/tmp/mc/batches2").mkdir()
for i in range(0, len(rem), 30): pathlib.Path(f"/tmp/mc/batches2/{i//30:03d}.txt").write_text("\n".join(rem[i:i+30]) + "\n")
print(collections.Counter(r.split("/")[0] for r in rem).most_common(8), "batches:", (len(rem) + 29) // 30)
