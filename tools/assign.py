"""Record material assignments. python3 tools/assign.py <batchfile>
Each non-empty line:  rel | what it depicts | 0=material:thickness_cm, 1=material:thickness_cm, ...
Optional last field:  | kind=block|item|gui|entity|...   (default from folder)
Thickness = real path length of the X-ray through that material (cm). Blocks: 100 (1 m cube) unless the block is
partly empty (then use an effective density via a lower-density material or thickness). Items/mobs: real size.
Materials must exist in tools/materials.py or tools/materials_extra/*.json. Writes tools/assignments/<rel>.json"""
import sys, os, json, pathlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, texsrc, clusters, materials
mats = materials.load_all(); out = pathlib.Path(__file__).with_name("assignments"); bad = 0
for ln, line in enumerate(open(sys.argv[1]), 1):
    line = line.strip()
    if not line or line.startswith("#"): continue
    f = [x.strip() for x in line.split("|")]
    try:
        rel, what, spec = f[0], f[1], f[2]
        arr = clusters.first_frame(np.asarray(texsrc.load(rel)))
        labels, cen, sh = clusters.kmeans(arr)
        cl = {}
        for part in spec.split(","):
            cid, rest = part.strip().split("=")
            m, t = rest.split(":")
            assert m in mats, f"unknown material {m}"
            cl[int(cid)] = (m, float(t))
        assert set(cl) == set(range(len(cen))), f"need clusters {list(range(len(cen)))}, got {sorted(cl)}"
        kind = next((x.split("=")[1] for x in f[3:] if x.startswith("kind=")), rel.split("/")[0])
        d = {"path": rel, "depicts": what, "kind": kind, "clusters": [
            {"id": i, "rgb": [int(v) for v in cen[i]], "share": round(sh[i], 3), "material": cl[i][0], "thickness_cm": cl[i][1]} for i in range(len(cen))]}
        p = out / (rel + ".json"); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(d, indent=1))
    except Exception as e:
        bad += 1; print(f"line {ln} ({line[:50]}...): {e}")
print("assigned OK" if not bad else f"{bad} lines failed")
