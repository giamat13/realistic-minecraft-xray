"""Make sets consistent: all dye colours of one object share material+thickness per cluster rank (group mode);
every object of one wood species uses that species' wood material; doors/trapdoors/signs use one real thickness each.
Idempotent. Run after annotation, before physics_render.py."""
import sys, os, re, json, pathlib, collections
A = pathlib.Path(__file__).with_name("assignments")
COLORS = sorted("white orange magenta light_blue yellow lime pink gray light_gray cyan purple blue brown green red black".split(), key=len, reverse=True)
WOOD_MAT = {"oak": "wood_oak", "spruce": "wood_soft", "birch": "planks", "jungle": "wood_oak", "acacia": "wood_oak", "dark_oak": "wood_dark",
            "pale_oak": "wood_soft", "mangrove": "wood_oak", "cherry": "wood_soft", "bamboo": "bamboo", "crimson": "wood_dark", "warped": "wood_dark"}
WOODISH = {"wood_oak", "wood_soft", "wood_dark", "planks", "bamboo"}
THICK = [("hanging_sign", 2.0), ("trapdoor", 4.5), ("_door", 4.5), ("sign", 2.0)]   # real thickness in cm, applies to wood/iron slabs
def load(p): return json.loads(p.read_text())
files = sorted(A.rglob("*.json")); data = {f: load(f) for f in files}
changed = 0
# 1. colour sets
grp = collections.defaultdict(list)
for f, d in data.items():
    k = d["path"]
    for c in COLORS: k = re.sub(rf"(?<![a-z]){c}(?![a-z])", "_C_", k)
    if k != d["path"]: grp[(k, len(d["clusters"]))].append(f)
for (k, n), fs in grp.items():
    if len(fs) < 3: continue
    for i in range(n):
        mode = collections.Counter((data[f]["clusters"][i]["material"], data[f]["clusters"][i]["thickness_cm"]) for f in fs).most_common(1)[0][0]
        for f in fs:
            c = data[f]["clusters"][i]
            if (c["material"], c["thickness_cm"]) != mode: c["material"], c["thickness_cm"] = mode; changed += 1
# 2. wood species -> species material; door/sign thickness
for f, d in data.items():
    p = d["path"]
    sp = next((w for w in sorted(WOOD_MAT, key=len, reverse=True) if re.search(rf"(?<![a-z]){w}(?![a-z])", p)), None)
    th = next((t for kw, t in THICK if kw in p.split("/")[-1] and p.startswith("block/")), None)
    for c in d["clusters"]:
        if sp and c["material"] in WOODISH and c["material"] != WOOD_MAT[sp]: c["material"] = WOOD_MAT[sp]; changed += 1
        if th and c["material"] in WOODISH | {"iron", "steel", "copper"} and c["thickness_cm"] > 5 and "leaves" not in p and c["thickness_cm"] != th and th != 2.0:
            c["thickness_cm"] = th; changed += 1
for f, d in data.items(): f.write_text(json.dumps(d, indent=1))
print("harmonized fields:", changed)
