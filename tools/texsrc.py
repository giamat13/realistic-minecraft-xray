"""Locate the source (vanilla) texture for a path relative to assets/minecraft/textures/.
Search order: 26.3 client jar, then older versions newest-first (extracted under /tmp/mc/v)."""
import io, pathlib, zipfile
from PIL import Image
JAR = "/tmp/mc/client.jar"; V = pathlib.Path("/tmp/mc/v")
def _key(s): return [int(x) if x.isdigit() else x for x in s.split(".")]
_z = None
def all_paths():
    global _z
    _z = _z or zipfile.ZipFile(JAR)
    p = {n[26:] for n in _z.namelist() if n.startswith("assets/minecraft/textures/") and n.endswith(".png")}
    for d in V.iterdir():
        t = d / "assets/minecraft/textures"
        if (d / "DONE").exists():
            p |= {f.relative_to(t).as_posix() for f in t.rglob("*.png")}
    return sorted(p)
def load(rel):
    global _z
    _z = _z or zipfile.ZipFile(JAR)
    n = "assets/minecraft/textures/" + rel
    if n in _z.namelist(): return Image.open(io.BytesIO(_z.read(n))).convert("RGBA")
    for d in sorted((x for x in V.iterdir() if (x / "DONE").exists()), key=lambda x: _key(x.name), reverse=True):
        f = d / "assets/minecraft/textures" / rel
        if f.exists(): return Image.open(f).convert("RGBA")
    raise FileNotFoundError(rel)
