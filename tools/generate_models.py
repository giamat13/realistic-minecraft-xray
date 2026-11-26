"""Make every block model translucent (26.x: per-texture `force_translucent`),
so partial alpha of the X-ray textures is honoured. Reads the vanilla jar."""
import json, sys, zipfile, pathlib
jar = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mc/client.jar"
out = pathlib.Path("assets/minecraft/models/block")
n = 0
with zipfile.ZipFile(jar) as z:
    for name in z.namelist():
        if not (name.startswith("assets/minecraft/models/block/") and name.endswith(".json")):
            continue
        m = json.loads(z.read(name))
        tex = m.get("textures")
        if not tex:
            continue
        for k, v in tex.items():
            if isinstance(v, str):
                if v.startswith("#"):
                    continue
                tex[k] = {"force_translucent": True, "sprite": v}
            elif isinstance(v, dict):
                v["force_translucent"] = True
        p = pathlib.Path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(m, indent=2))
        n += 1
print("models written:", n)
