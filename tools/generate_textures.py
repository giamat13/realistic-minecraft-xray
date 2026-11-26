#!/usr/bin/env python3
"""Generate the realistic X-ray texture set from the Minecraft client jar.

Usage: python3 tools/generate_textures.py [path/to/client.jar]

Reads every assets/minecraft/textures/**.png and *.png.mcmeta straight from the
jar and writes them to assets/minecraft/textures/ in this repository, same
relative paths. Output is strictly grayscale (R == G == B). Under block/ the
alpha channel encodes density; every other folder keeps its source alpha.
"""
import argparse
import io
import os
import re
import sys
import time
import zipfile
import zlib

import numpy as np
from PIL import Image

PREFIX = "assets/minecraft/textures/"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(REPO_ROOT, *PREFIX.split("/"))
DEFAULT_JAR = "/tmp/mc/client.jar"

# Folders that get plain luminance grayscale, no density table.
PLAIN_FOLDERS = ("gui/", "font/", "environment/", "particle/", "misc/")

# Density table, first matching rule wins: (keywords, lo, hi, block_alpha).
# Keywords match whole underscore-separated words (plural "s" allowed), so
# "bed" does not catch "bedrock". The ore rule sits between the metal and glass
# rules and is handled separately (see classify()).
PLANT_KEYWORDS = (
    "leaves", "grass", "fern", "vine", "flower", "sapling", "bush", "crop", "wheat",
    "carrot", "potato", "beetroot", "stem", "moss", "azalea", "kelp", "seagrass",
    "coral", "sprout", "roots", "petals", "bamboo", "cactus", "sugar_cane", "pumpkin",
    "melon", "cake", "wool", "carpet", "bed", "banner", "candle", "sponge", "hay",
    "mushroom", "fungus", "wart", "shroomlight", "bread",
)
WOOD_KEYWORDS = (
    "log", "planks", "wood", "bookshelf", "crafting", "barrel", "chest", "door",
    "trapdoor", "fence", "sign", "ladder", "scaffolding", "composter", "lectern",
    "loom", "cartography", "fletching", "smithing", "jukebox", "note_block", "stick",
)
DIRT_KEYWORDS = (
    "dirt", "sand", "gravel", "clay", "mud", "snow", "soul", "farmland", "podzol",
    "mycelium", "netherrack", "path",
)
RULES = [
    (("ancient_debris", "netherite"), 225, 255, 255),
    (("gold", "golden", "diamond", "emerald"), 205, 250, 255),
    (("iron", "raw_iron", "chain", "anvil", "cauldron", "hopper", "rail", "bell",
      "lantern", "copper", "raw_copper", "exposed", "weathered", "oxidized", "waxed",
      "lightning_rod", "redstone_ore", "redstone_block", "lapis", "amethyst", "quartz",
      "heavy_core", "bars", "door_iron", "trial", "vault", "spawner", "beacon",
      "conduit"), 170, 235, 255),
    # ore rule goes here (pixel-based), see classify()
    (("glass", "ice", "water", "slime", "honey", "pane", "portal", "bubble", "cobweb"),
     30, 70, 18),
    (PLANT_KEYWORDS, 35, 90, 25),
    (WOOD_KEYWORDS, 70, 120, 55),
    (DIRT_KEYWORDS, 80, 135, 70),
    (("obsidian", "bedrock", "deepslate", "blackstone", "basalt"), 105, 170, 130),
]
DEFAULT_CLASS = (105, 170, 95)
ORE_ALPHA = 230

# Per-pixel material classes for mixed block textures, first match wins. Each
# entry is (lo, hi, block_alpha). Pixels matching none use the file's own class.
PIXEL_CLASS_RANGES = (
    (35.0, 90.0, 25),     # foliage
    (30.0, 70.0, 18),     # water_blue
    (60.0, 110.0, 45),    # snow_white
    (80.0, 135.0, 70),    # earth_brown
    (105.0, 170.0, 95),   # rock_gray
)
MIXED_MIN_SHARE = 0.12    # a pixel-class must cover this share of valid pixels...
MIXED_MIN_CLASSES = 2     # ...and this many classes must qualify for a mixed texture
MIXED_ALPHA_LIMIT = 200   # only block files whose class alpha is below this are split

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_ORE_RE = re.compile(r"_ores?_")


def _compile(keywords):
    return re.compile("_(?:" + "|".join(re.escape(k) for k in keywords) + ")s?_")


RULE_PATTERNS = [(_compile(kws), lo, hi, a) for kws, lo, hi, a in RULES]


def classify(rel):
    """Return (lo, hi, block_alpha, is_ore) for a path relative to textures/."""
    joined = "_" + "_".join(_TOKEN_RE.findall(rel.lower())) + "_"
    for pat, lo, hi, a in RULE_PATTERNS:
        if pat.search(joined):
            return lo, hi, a, False
    if _ORE_RE.search(joined):
        if "deepslate" in joined or "netherrack" in joined:
            return 120, 160, 90, True
        return 110, 150, 70, True
    return DEFAULT_CLASS + (False,)


def _unit(lum, mask):
    """Normalise lum to 0..1 over the pixels in mask (0.5 when flat)."""
    v = lum[mask]
    mn, mx = float(v.min()), float(v.max())
    if mx - mn < 1e-9:
        return np.full(lum.shape, 0.5)
    return np.clip((lum - mn) / (mx - mn), 0.0, 1.0)


def _stretch(lum, valid, lo, hi):
    return lo + (hi - lo) * _unit(lum, valid)


def _ore_split(lum, rgb, valid, host_lo, host_hi, host_alpha):
    """Split a texture into ore blobs (bright, opaque) and host rock."""
    med = float(np.median(lum[valid]))
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    ore = valid & ((np.abs(lum - med) > 0.18) | (sat > 0.35))
    host = valid & ~ore
    gray = np.zeros_like(lum)
    alpha = np.zeros_like(lum)
    if ore.any():
        gray = np.where(ore, 200.0 + 50.0 * _unit(lum, ore), gray)
        alpha = np.where(ore, float(ORE_ALPHA), alpha)
    if host.any():
        gray = np.where(host, host_lo + (host_hi - host_lo) * _unit(lum, host), gray)
        alpha = np.where(host, float(host_alpha), alpha)
    return gray, alpha


def _hsv(rgb):
    """Return (hue in degrees, saturation, value) for an HxWx3 float RGB array."""
    mx = rgb.max(axis=-1)
    d = mx - rgb.min(axis=-1)
    sat = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0.0)
    ds = np.maximum(d, 1e-9)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    sector = np.where(mx == r, np.mod((g - b) / ds, 6.0),
                      np.where(mx == g, (b - r) / ds + 2.0, (r - g) / ds + 4.0))
    hue = np.where(d > 1e-9, np.mod(60.0 * sector, 360.0), 0.0)
    return hue, sat, mx


def _pixel_classes(rgb, valid):
    """Class index per pixel: 0..4 from PIXEL_CLASS_RANGES, 5 = file's own class, -1 = transparent."""
    hue, sat, val = _hsv(rgb)
    conds = (
        (sat > 0.25) & (hue >= 70) & (hue <= 170),                 # foliage
        (sat > 0.25) & (hue >= 170) & (hue <= 260) & (val > 0.4),  # water_blue
        (sat < 0.12) & (val > 0.85),                               # snow_white
        (sat > 0.2) & (hue >= 10) & (hue <= 45) & (val < 0.65),    # earth_brown
        (sat < 0.2) & (val > 0.15) & (val <= 0.85),                # rock_gray
    )
    cls = np.full(valid.shape, -1, np.int16)
    left = valid.copy()
    for k, cond in enumerate(conds):
        take = left & cond
        cls[take] = k
        left &= ~take
    cls[left] = len(conds)
    return cls


def _majority3(cls, n):
    """3x3 majority vote over a class map; transparent (-1) pixels stay -1 and vote for nothing."""
    h, w = cls.shape
    pad = np.pad(cls, 1, constant_values=-1)
    votes = np.zeros((n,) + cls.shape, np.int16)
    for dy in range(3):
        for dx in range(3):
            win = pad[dy:dy + h, dx:dx + w]
            for k in range(n):
                votes[k] += (win == k)
    votes *= 2  # doubled so a tie goes to the pixel's own class
    for k in range(n):
        votes[k] += (cls == k)
    best = np.argmax(votes, axis=0).astype(np.int16)
    return np.where(cls >= 0, best, -1).astype(np.int16)


def _mixed_split(rgb, lum, valid, src_a, own_lo, own_hi, own_alpha):
    """Per-pixel (gray, alpha) for a block texture made of several materials, or None if not mixed."""
    ranges = PIXEL_CLASS_RANGES + ((own_lo, own_hi, own_alpha),)
    cls = _pixel_classes(rgb, valid)
    n_valid = float(valid.sum())
    shares = [float((cls == k).sum()) / n_valid for k in range(len(ranges))]
    if sum(s >= MIXED_MIN_SHARE for s in shares) < MIXED_MIN_CLASSES:
        return None
    cls = _majority3(cls, len(ranges))
    gray = np.zeros(valid.shape)
    alpha = np.zeros(valid.shape)
    for k, (lo, hi, a) in enumerate(ranges):
        m = cls == k
        if m.any():
            gray = np.where(m, lo + (hi - lo) * _unit(lum, m), gray)
            alpha = np.where(m, src_a * a / 255.0, alpha)
    return gray, alpha


def process(rel, rgba):
    """Convert one RGBA array (HxWx4 uint8) to its realistic X-ray version."""
    h, w = rgba.shape[:2]
    out = np.zeros((h, w, 4), np.uint8)
    src_a = rgba[..., 3].astype(np.float64)
    valid = src_a > 0
    if not valid.any():
        return out

    rgb = rgba[..., :3].astype(np.float64) / 255.0
    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    is_block = rel.startswith("block/")

    if rel.startswith(PLAIN_FOLDERS):
        gray = _stretch(lum, valid, 0.0, 255.0)
        alpha = src_a
    else:
        lo, hi, block_alpha, is_ore = classify(rel)
        if not is_block:
            # Mild version for items, mobs, paintings, maps, colormaps etc.
            lo = max(20.0, lo * 0.5)
            hi = min(255.0, hi + 30.0)
            gray = _stretch(lum, valid, lo, hi)
            alpha = src_a
        elif is_ore:
            gray, ap = _ore_split(lum, rgb, valid, lo, hi, block_alpha)
            alpha = src_a * ap / 255.0
        else:
            mixed = None
            if block_alpha < MIXED_ALPHA_LIMIT:
                mixed = _mixed_split(rgb, lum, valid, src_a, lo, hi, block_alpha)
            if mixed is not None:
                gray, alpha = mixed
            else:
                gray = _stretch(lum, valid, lo, hi)
                alpha = src_a * block_alpha / 255.0

    g = np.clip(np.rint(gray), 0, 255).astype(np.int16)
    a = np.clip(np.rint(alpha), 0, 255).astype(np.int16)

    if is_block:
        # Deterministic film grain, seeded by the path so reruns are identical.
        rng = np.random.default_rng(zlib.crc32(rel.encode("utf-8")))
        noise = rng.integers(-5, 6, size=(h, w), dtype=np.int16)
        g = np.where(a > 0, np.clip(g + noise, 0, 255), g)

    g = np.where(valid, g, 0).astype(np.uint8)
    a = np.where(valid, a, 0).astype(np.uint8)
    out[..., 0] = g
    out[..., 1] = g
    out[..., 2] = g
    out[..., 3] = a
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate realistic X-ray textures from a client jar.")
    ap.add_argument("jar", nargs="?", default=DEFAULT_JAR, help="path to the Minecraft client jar")
    args = ap.parse_args(argv)

    t0 = time.time()
    errors = []
    with zipfile.ZipFile(args.jar) as zf:
        names = zf.namelist()
        pngs = sorted(n for n in names if n.startswith(PREFIX) and n.endswith(".png"))
        metas = sorted(n for n in names if n.startswith(PREFIX) and n.endswith(".png.mcmeta"))
        print(f"jar: {args.jar}\n{len(pngs)} PNGs, {len(metas)} mcmeta files", flush=True)

        os.makedirs(OUT_ROOT, exist_ok=True)

        for i, name in enumerate(pngs, 1):
            rel = name[len(PREFIX):]
            dst = os.path.join(OUT_ROOT, *rel.split("/"))
            try:
                with Image.open(io.BytesIO(zf.read(name))) as im:
                    arr = np.asarray(im.convert("RGBA"))
                out = process(rel, arr)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                Image.fromarray(out).save(dst)
            except Exception as exc:  # keep going, report at the end
                errors.append((name, repr(exc)))
            if i % 500 == 0:
                print(f"  processed {i}/{len(pngs)} PNGs", flush=True)

        for name in metas:
            dst = os.path.join(OUT_ROOT, *name[len(PREFIX):].split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(zf.read(name))

    print(f"wrote {len(pngs)} PNGs and {len(metas)} mcmeta files in {time.time() - t0:.1f}s", flush=True)
    if errors:
        for name, err in errors[:20]:
            print(f"ERROR {name}: {err}", file=sys.stderr)
        print(f"{len(errors)} files failed", file=sys.stderr)
        return 1
    return 0


def _selftest():
    """Synthetic grass-on-dirt side texture: top 5 rows green, rest brown."""
    arr = np.zeros((16, 16, 4), np.uint8)
    arr[:5, :, :3] = (60, 160, 40)
    arr[5:, :, :3] = (110, 75, 45)
    arr[..., 3] = 255
    out = process("block/grass_block_side.png", arr)
    top = float(out[:5, :, 3].mean())
    bottom = float(out[5:, :, 3].mean())
    assert top < 40, f"top alpha too high: {top:.1f}"
    assert bottom > 55, f"bottom alpha too low: {bottom:.1f}"
    assert np.array_equal(out[..., 0], out[..., 1]) and np.array_equal(out[..., 1], out[..., 2]), "not grayscale"
    print(f"selftest passed: top alpha {top:.1f}, bottom alpha {bottom:.1f}")
    return 0


if __name__ == "__main__" and "--selftest" in sys.argv:
    sys.exit(_selftest())

if __name__ == "__main__":
    sys.exit(main())
