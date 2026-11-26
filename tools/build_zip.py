"""Build the Modrinth-ready zip: dist/RealisticXRay-<version>.zip (pack.mcmeta at the zip root)."""
import sys, zipfile, pathlib
ver = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"
out = pathlib.Path("dist"); out.mkdir(exist_ok=True)
zp = out / f"RealisticXRay-{ver}.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in ["pack.mcmeta", "pack.png", "LICENSE", "README.md"]:
        z.write(f)
    for d in sorted(p.name for p in pathlib.Path(".").iterdir() if p.is_dir() and (p.name == "assets" or p.name.startswith("overlay_"))):
        for p in sorted(pathlib.Path(d).rglob("*")):
            if p.is_file():
                z.write(p)
print(zp, round(zp.stat().st_size / 1e6, 1), "MB")
