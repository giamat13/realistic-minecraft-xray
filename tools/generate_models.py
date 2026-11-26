"""Block models for 26.1+: translucent sprites, and X-ray thickness that follows the geometry.

Every block model is made translucent (per-texture `force_translucent`) so the X-ray alpha is honoured.
A texture is shared by many shapes (planks, pressure plate, fence, ...), so for each face the beam path
is capped at the element's depth along that face normal (16 model units = 100 cm). Where that changes
the physics, a variant texture is rendered into textures/block/xray/ and the model is pointed at it.
Usage: python3 tools/generate_models.py   (needs MC_JAR / MC_VERSIONS, see texsrc.py)"""
import sys, os, re, json, zipfile, pathlib, shutil, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import texsrc, physics_render as pr

OVERLAY = pathlib.Path("overlay_26_1/assets/minecraft")
VARIANTS = OVERLAY / "textures/block/xray"
PREFIX = "assets/minecraft/models/block/"
AXIS = {"east": 0, "west": 0, "up": 1, "down": 1, "north": 2, "south": 2}
CM_PER_UNIT = 100 / 16
# dense blocks get a second box just inside, which neighbours never hide: the shader pack sees them buried in rock
DENSE = re.compile(r"block/((deepslate_|nether_)?\w+_ore|ancient_debris|(raw_)?(iron|gold|copper)_block|netherite_block)(_\w+)?$")

def short(name): return name.split(":", 1)[-1]
def sprite_of(v): return v.get("sprite") if isinstance(v, dict) else v

def resolve(models, name):
    """Merged texture map and effective elements of a model, following the parent chain."""
    tex, elements = {}, None
    while name in models:
        m = models[name]
        for k, v in m.get("textures", {}).items():
            tex.setdefault(k, v)
        if elements is None:
            elements = m.get("elements")
        name = short(m.get("parent", ""))
    return tex, elements

def follow(tex, ref):
    """Sprite path behind a face reference such as '#side', or None if the template leaves it open."""
    seen = set()
    while isinstance(ref, str) and ref.startswith("#") and ref not in seen:
        seen.add(ref)
        ref = sprite_of(tex.get(ref[1:]))
    return short(ref) if isinstance(ref, str) and not ref.startswith("#") else None

cache = {}
def variant(sprite, units):
    """Sprite name to use for `sprite` seen through `units` model units, or None if the original is right."""
    key = (sprite, units)
    if key not in cache:
        cache[key] = None
        rel = sprite + ".png"
        asg_file = pathlib.Path(__file__).with_name("assignments") / (rel + ".json")
        depth = units * CM_PER_UNIT
        if sprite.startswith("block/") and asg_file.exists():
            asg = json.loads(asg_file.read_text())
            if any(c["thickness_cm"] > depth + 1e-6 for c in asg["clusters"]):
                for c in asg["clusters"]:
                    c["thickness_cm"] = min(c["thickness_cm"], depth)
                name = f"{sprite[len('block/'):]}_d{round(units * 100)}"
                out = VARIANTS / (name + ".png")
                out.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(pr.render(rel, np.asarray(texsrc.load(rel)), asg)).save(out)
                mc = texsrc.mcmeta(rel)
                if mc is not None:
                    pathlib.Path(str(out) + ".mcmeta").write_bytes(mc)
                cache[key] = "block/xray/" + name
    return cache[key]

def flatten_light(elements):
    """A radiograph has no lamps, shadows or dye: drop tints and shading and light every face fully."""
    for el in elements:
        el["shade"] = False                    # older spelling
        el["shade_direction_override"] = "up"  # 26.x: "up" is the unshaded direction
        el["light_emission"] = 15
        for data in el.get("faces", {}).values():
            data.pop("tintindex", None)

def main():
    with zipfile.ZipFile(texsrc.JAR) as z:
        models = {"block/" + n[len(PREFIX):-5]: json.loads(z.read(n))
                  for n in z.namelist() if n.startswith(PREFIX) and n.endswith(".json")}
    shutil.rmtree(VARIANTS, ignore_errors=True)
    written = shaped = 0
    for name, source in models.items():
        m = copy.deepcopy(source)
        tex, elements = resolve(models, name)
        # only models that supply a real sprite of their own or through their parents need a file
        own = "elements" in source
        if not own and not any(follow(tex, "#" + k) for k in tex):
            continue
        textures = m.setdefault("textures", {})
        new_elements, added = copy.deepcopy(elements or []), {}
        for el in new_elements:
            for face, data in el.get("faces", {}).items():
                axis = AXIS[face]
                units = abs(el["to"][axis] - el["from"][axis])
                if units <= 0 or units >= 16:      # flat sheet (annotated thickness) or full depth
                    continue
                sprite = follow(tex, data["texture"])
                new = sprite and variant(sprite, units)
                if new:
                    key = "xray_" + new.rsplit("/", 1)[1].replace("/", "_")
                    added[key] = "minecraft:" + new
                    data["texture"] = "#" + key
        if added:
            m["elements"] = new_elements
            textures.update(added)
            shaped += 1
        dense = bool(elements) and bool(DENSE.match(name))
        if dense:
            m.setdefault("elements", copy.deepcopy(elements))
            for el in list(m["elements"]):
                if el["from"] == [0, 0, 0] and el["to"] == [16, 16, 16]:
                    inner = copy.deepcopy(el)
                    inner["from"], inner["to"] = [0.25] * 3, [15.75] * 3
                    for data in inner["faces"].values():
                        data.pop("cullface", None)
                    m["elements"].append(inner)
        if not added and not own and not dense and not source.get("textures"):
            continue
        if "elements" in m:
            flatten_light(m["elements"])
        if "elements" in m or "ambientocclusion" in m or "parent" not in m:
            m["ambientocclusion"] = False
        for k, v in textures.items():
            if isinstance(v, str) and not v.startswith("#"):
                textures[k] = {"force_translucent": True, "sprite": v}
            elif isinstance(v, dict):
                v["force_translucent"] = True
        p = OVERLAY / "models" / (name + ".json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(m, indent=2))
        written += 1
    print(f"models written: {written}, with shape thickness: {shaped}, variant textures: {sum(1 for v in cache.values() if v)}")

if __name__ == "__main__":
    main()
