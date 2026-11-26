#!/usr/bin/env python3
"""Verify the generated texture set against the client jar, then write tools/preview.png.

Usage: python3 tools/verify_textures.py [path/to/client.jar]

Exits non-zero if the path sets differ, mcmeta bytes differ, a size or mode
differs, or any output pixel is not grayscale (R == G == B).
"""
import io
import os
import sys
import zipfile

import numpy as np
from PIL import Image

PREFIX = "assets/minecraft/textures/"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(REPO_ROOT, *PREFIX.split("/"))
PREVIEW_PATH = os.path.join(REPO_ROOT, "tools", "preview.png")
DEFAULT_JAR = "/tmp/mc/client.jar"

STAT_PATHS = [
    "block/stone.png", "block/deepslate.png", "block/dirt.png", "block/oak_log.png",
    "block/oak_leaves.png", "block/water_still.png", "block/glass.png", "block/coal_ore.png",
    "block/iron_ore.png", "block/gold_ore.png", "block/diamond_ore.png",
    "block/ancient_debris_side.png", "block/iron_block.png", "block/gold_block.png",
    "block/netherite_block.png",
]

PREVIEW_PATHS = [
    "block/stone.png", "block/deepslate.png", "block/dirt.png", "block/oak_log.png",
    "block/oak_leaves.png", "block/glass.png", "block/coal_ore.png", "block/iron_ore.png",
    "block/gold_ore.png", "block/diamond_ore.png", "block/ancient_debris_side.png",
    "block/iron_block.png", "item/diamond_sword.png", "item/apple.png",
    "gui/sprites/hud/heart/full.png",
]


def collect_outputs():
    pngs, metas = set(), set()
    for dirpath, _, files in os.walk(OUT_ROOT):
        for f in files:
            rel = os.path.relpath(os.path.join(dirpath, f), OUT_ROOT).replace(os.sep, "/")
            if f.endswith(".png.mcmeta"):
                metas.add(PREFIX + rel)
            elif f.endswith(".png"):
                pngs.add(PREFIX + rel)
    return pngs, metas


def block_stats(arr):
    """Mean gray and mean alpha over pixels with alpha > 0 (gray) and all pixels (alpha)."""
    visible = arr[..., 3] > 0
    gray = float(arr[..., 0][visible].mean()) if visible.any() else 0.0
    alpha = float(arr[..., 3].mean())
    return gray, alpha


def write_preview(zf_names_ok):
    scale, pad, cols = 4, 8, 5
    tiles = []
    for rel in PREVIEW_PATHS:
        path = os.path.join(OUT_ROOT, *rel.split("/"))
        if not os.path.exists(path):
            print(f"  preview: missing {rel}, skipped")
            continue
        with Image.open(path) as im:
            tile = im.convert("RGBA")
            tile = tile.resize((tile.width * scale, tile.height * scale), Image.NEAREST)
        tiles.append(tile)
    if not tiles:
        return
    cell = max(max(t.width, t.height) for t in tiles) + pad
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell + pad, rows * cell + pad), (24, 24, 24))
    for idx, tile in enumerate(tiles):
        x = pad + (idx % cols) * cell + (cell - pad - tile.width) // 2
        y = pad + (idx // cols) * cell + (cell - pad - tile.height) // 2
        canvas.paste(tile.convert("RGB"), (x, y), mask=tile.split()[3])
    canvas.save(PREVIEW_PATH)
    print(f"wrote preview {PREVIEW_PATH} ({len(tiles)} tiles)")


def main(argv=None):
    jar = (argv or sys.argv[1:] or [DEFAULT_JAR])[0]
    fails = []
    with zipfile.ZipFile(jar) as zf:
        jar_pngs = {n for n in zf.namelist() if n.startswith(PREFIX) and n.endswith(".png")}
        jar_metas = {n for n in zf.namelist() if n.startswith(PREFIX) and n.endswith(".png.mcmeta")}
        out_pngs, out_metas = collect_outputs()

        # (a) PNG path set
        if out_pngs == jar_pngs:
            print(f"(a) PNG path set matches jar: {len(out_pngs)} files")
        else:
            fails.append(f"(a) PNG sets differ: missing {len(jar_pngs - out_pngs)}, extra {len(out_pngs - jar_pngs)}")

        # (b) mcmeta path set and bytes
        if out_metas == jar_metas:
            bad = [n for n in sorted(jar_metas)
                   if open(os.path.join(REPO_ROOT, *n.split("/")), "rb").read() != zf.read(n)]
            if bad:
                fails.append(f"(b) {len(bad)} mcmeta files differ in bytes, e.g. {bad[0]}")
            else:
                print(f"(b) mcmeta path set matches jar and bytes are identical: {len(jar_metas)} files")
        else:
            fails.append(f"(b) mcmeta sets differ: missing {len(jar_metas - out_metas)}, extra {len(out_metas - jar_metas)}")

        # (c) size and mode equal source, (d) grayscale everywhere
        size_bad, mode_bad, gray_bad = [], [], []
        for name in sorted(jar_pngs & out_pngs):
            with Image.open(io.BytesIO(zf.read(name))) as src:
                src_size = src.size
            rel = name[len(PREFIX):]
            with Image.open(os.path.join(OUT_ROOT, *rel.split("/"))) as out:
                if out.size != src_size:
                    size_bad.append(f"{rel} {out.size} != {src_size}")
                if out.mode != "RGBA":
                    mode_bad.append(f"{rel} mode {out.mode}")
                arr = np.asarray(out.convert("RGBA"))
            if not (np.array_equal(arr[..., 0], arr[..., 1]) and np.array_equal(arr[..., 1], arr[..., 2])):
                gray_bad.append(rel)
        if size_bad:
            fails.append(f"(c) {len(size_bad)} size mismatches, e.g. {size_bad[0]}")
        if mode_bad:
            fails.append(f"(c) {len(mode_bad)} non-RGBA outputs, e.g. {mode_bad[0]}")
        if not size_bad and not mode_bad:
            print(f"(c) all {len(jar_pngs & out_pngs)} outputs match source size and are RGBA")
        if gray_bad:
            fails.append(f"(d) {len(gray_bad)} files are not grayscale, e.g. {gray_bad[0]}")
        else:
            print("(d) every output pixel has R == G == B")

    # (e) statistics and ordering
    print("(e) statistics (mean gray over alpha>0, mean alpha over all pixels):")
    stats = {}
    for rel in STAT_PATHS:
        path = os.path.join(OUT_ROOT, *rel.split("/"))
        if not os.path.exists(path):
            print(f"  {rel:34s} MISSING")
            continue
        with Image.open(path) as im:
            arr = np.asarray(im.convert("RGBA"))
        gray, alpha = block_stats(arr)
        stats[rel] = alpha
        line = f"  {rel:34s} gray {gray:6.1f}  alpha {alpha:6.1f}"
        if rel == "block/coal_ore.png":
            blobs = arr[..., 3][arr[..., 3] >= 200]
            blob_alpha = float(blobs.mean()) if blobs.size else 0.0
            stats["coal_blobs"] = blob_alpha
            line += f"  blob-pixel alpha {blob_alpha:6.1f}"
        print(line)

    needed = ["block/netherite_block.png", "block/ancient_debris_side.png", "block/gold_block.png",
              "block/iron_block.png", "coal_blobs", "block/stone.png", "block/dirt.png",
              "block/oak_log.png", "block/oak_leaves.png", "block/water_still.png", "block/glass.png"]
    if all(k in stats for k in needed):
        metal = min(stats[k] for k in needed[:4])
        blob = stats["coal_blobs"]
        stone, dirt, log = stats["block/stone.png"], stats["block/dirt.png"], stats["block/oak_log.png"]
        low = max(stats["block/oak_leaves.png"], stats["block/water_still.png"], stats["block/glass.png"])
        ordered = metal > blob > stone > dirt > log > low
        print(f"  ordering metal({metal:.0f}) > ore blobs({blob:.0f}) > stone({stone:.0f}) > "
              f"dirt({dirt:.0f}) > oak_log({log:.0f}) > leaves/water/glass({low:.0f}): "
              + ("PASS" if ordered else "FAIL"))
    else:
        print("  ordering check skipped, some stats are missing")

    write_preview(True)

    if fails:
        print("\nFAILED:")
        for f in fails:
            print("  " + f)
        return 1
    print("\nchecks (a)-(d) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
