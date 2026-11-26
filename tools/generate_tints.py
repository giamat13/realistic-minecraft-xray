"""Remove the colours the game multiplies onto items and equipment (leather brown, potions, grass, ...).

An X-ray does not see dye, so every item tint becomes white and the physics-rendered texture shows
as it is. Dyed equipment worn by an entity takes its colour from the item and is grayed by shaders.
Usage: python3 tools/generate_tints.py <26.2 client.jar>"""
import json, sys, zipfile, pathlib, shutil

OVERLAY = pathlib.Path("overlay_26_2")
DIRS = ("assets/minecraft/items/", "assets/minecraft/equipment/")
WHITE = -1

def walk(node):
    """Whiten in place every `tints` entry and undyed equipment colour. Returns the number of changes."""
    n = 0
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "tints" and isinstance(v, list):
                node[k] = [{"type": "minecraft:constant", "value": WHITE} for _ in v]
                n += len(v)
            elif k == "color_when_undyed":
                node[k] = WHITE
                n += 1
            else:
                n += walk(v)
    elif isinstance(node, list):
        for v in node:
            n += walk(v)
    return n

def main():
    for d in DIRS:
        shutil.rmtree(OVERLAY / d, ignore_errors=True)
    files = changes = 0
    with zipfile.ZipFile(sys.argv[1]) as z:
        for name in z.namelist():
            if not (name.startswith(DIRS) and name.endswith(".json")):
                continue
            data = json.loads(z.read(name))
            n = walk(data)
            if n:
                p = OVERLAY / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(data, indent=2))
                files += 1
                changes += n
    print(f"tint files: {files}, colours changed: {changes}")

if __name__ == "__main__":
    main()
