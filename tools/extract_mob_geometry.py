"""Read the real model boxes and UVs of every entity from Minecraft client jars.

Runs tools/mob_geometry/Dump.java against a jar (it calls LayerDefinitions.createRoots() and bakes every
layer), applies the part poses and writes tools/data/mob_geometry.json, which
tools/generate_mob_skeletons.py reads. Only needed again when Mojang changes a model.

Two layouts are stored: "new" (26.x, unobfuscated) and "old" (1.20.1, names resolved through
Mojang's published client mappings) for the legacy texture paths.

Usage: python tools/extract_mob_geometry.py --jar26 <26.x.jar> --json26 <26.x.json> --libs <libraries dir> [...]
       --jar1201 <1.20.1.jar> --json1201 <1.20.1.json> --jdk <bin dir of a JDK 21+>"""
import argparse
import json
import math
import os
import pathlib
import re
import subprocess
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "data" / "mob_geometry.json"
SKIP = ("boat", "chest_boat", "sign", "hanging_sign", "standing_", "wall_", "chest", "double_chest", "banner", "bed_",
        "bell", "book", "conduit", "decorated", "shield", "minecart", "player", "armor_stand", "spin_attack", "trident",
        "leash", "end_crystal", "cushion", "copper_golem_statue")


def classpath(jar, version_json, lib_dirs):
    found = [str(jar)]
    for lib in json.loads(pathlib.Path(version_json).read_text())["libraries"]:
        path = lib.get("downloads", {}).get("artifact", {}).get("path")
        for base in lib_dirs if path else ():
            if (pathlib.Path(base) / path).exists():
                found.append(str(pathlib.Path(base) / path))
                break
    return found


def obfuscated_names(version_json, work):
    """Obfuscated class/method names and the field renames needed to read a pre-26 jar."""
    url = json.loads(pathlib.Path(version_json).read_text())["downloads"]["client_mappings"]["url"]
    if not url.startswith("https://piston-data.mojang.com/"):
        raise SystemExit(f"unexpected mappings host: {url}")
    target = work / "mappings.txt"
    urllib.request.urlretrieve(url, target)
    text = target.read_text(encoding="utf-8")

    def block(name):
        match = re.search(r"^" + re.escape(name) + r" -> ([\w$.]+):\n((?:    .*\n|#.*\n)*)", text, re.M)
        return match.group(1), match.group(2)

    args = []
    geom = "net.minecraft.client.model.geom."
    for name, method in ((geom + "LayerDefinitions", "createRoots"), (geom + "builders.LayerDefinition", "bakeRoot"),
                         ("net.minecraft.SharedConstants", "tryDetectVersion"),
                         ("net.minecraft.server.Bootstrap", "bootStrap")):
        short, body = block(name)
        args.append((short, re.search(r" " + method + r"\(\) -> (\w+)", body).group(1)))
    (roots, create), (_, bake), (shared, detect), (boot, strap) = args
    renames = {}
    for name in ("ModelPart", "ModelPart$Cube", "ModelPart$Polygon", "ModelPart$Vertex", "builders.MaterialDefinition"):
        fields = re.findall(r"^    [\w.$\[\]]+ (\w+) -> (\w+)$", block(geom + name)[1], re.M)
        renames[name.split(".")[-1].split("$")[-1]] = {short: long for long, short in fields}
    return [roots, create, bake, shared, detect, boot, strap], renames


def dump(java_bin, jar, version_json, libs, args, release, work):
    classes = work / f"classes{release or ''}"
    flags = ["--release", str(release)] if release else []
    subprocess.run([str(pathlib.Path(java_bin) / "javac"), *flags, "-d", str(classes),
                    str(ROOT / "mob_geometry" / "Dump.java")], check=True)
    env = dict(os.environ, CLASSPATH=os.pathsep.join([str(classes), *classpath(jar, version_json, libs)]))
    result = subprocess.run([str(pathlib.Path(java_bin) / "java"), "xray.Dump", *args], env=env, cwd=work,
                            capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stderr[-3000:])
    return json.loads(result.stdout)


def rename(node, kind, renames):
    table = renames.get(kind, {})
    return {table.get(k, k): v for k, v in node.items()}


def rotate(point, rx, ry, rz):
    x, y, z = point
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return [x, y, z]


def flatten(raw, renames):
    layers = {}
    for key, entry in raw.items():
        name = key.split(":", 1)[1]
        if name.startswith(SKIP) or re.search(r"#(inner_armor|outer_armor|helmet|chestplate|leggings|boots)$", name):
            continue
        material = rename(entry["def"][0], "MaterialDefinition", renames)
        width, height = material["xTexSize"], material["yTexSize"]
        cubes = []

        def walk(node, path, chain):
            part = rename(node, "ModelPart", renames)
            chain = [part, *chain]
            for index, raw_cube in enumerate(part["cubes"]):
                faces = []
                for raw_polygon in rename(raw_cube, "Cube", renames)["polygons"]:
                    polygon = rename(raw_polygon, "Polygon", renames)
                    verts, normal = [], polygon["normal"]
                    for raw_vertex in polygon["vertices"]:
                        vertex = rename(raw_vertex, "Vertex", renames)
                        pos = vertex["pos"] if "pos" in vertex else [vertex["x"], vertex["y"], vertex["z"]]
                        for p in chain:
                            pos = [pos[0] * p["xScale"], pos[1] * p["yScale"], pos[2] * p["zScale"]]
                            pos = rotate(pos, p["xRot"], p["yRot"], p["zRot"])
                            pos = [pos[0] + p["x"], pos[1] + p["y"], pos[2] + p["z"]]
                        verts.append([round(c, 3) for c in pos] + [round(vertex["u"], 6), round(vertex["v"], 6)])
                    for p in chain:
                        normal = rotate(normal, p["xRot"], p["yRot"], p["zRot"])
                    faces.append({"n": [round(c, 3) for c in normal], "v": verts})
                cubes.append({"p": path, "i": index, "f": faces})
            for child_name, child in part["children"].items():
                walk(child, f"{path}/{child_name}" if path else child_name, chain)

        walk(entry["root"], "", [])
        layers[name.replace("#main", "")] = {"tex": [width, height], "cubes": cubes}
    return dict(sorted(layers.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("jar26", "json26", "jar1201", "json1201", "jdk"):
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--libs", required=True, nargs="+")
    parser.add_argument("--work", help="empty scratch directory (default: a temporary one)")
    a = parser.parse_args()
    work = pathlib.Path(a.work or tempfile.mkdtemp(prefix="mobgeom-")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    geom = "net.minecraft.client.model.geom."
    new_args = [geom + "LayerDefinitions", "createRoots", "bakeRoot", "net.minecraft.SharedConstants",
                "tryDetectVersion", "net.minecraft.server.Bootstrap", "bootStrap"]
    new = flatten(dump(a.jdk, a.jar26, a.json26, a.libs, new_args, None, work), {})
    old_args, renames = obfuscated_names(a.json1201, work)
    old = flatten(dump(a.jdk, a.jar1201, a.json1201, a.libs, old_args, 17, work), renames)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"new": new, "old": old}, separators=(",", ":")) + "\n")
    print(f"{OUT}: {len(new)} new layers, {len(old)} old layers")


if __name__ == "__main__":
    main()
