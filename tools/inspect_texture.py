"""python3 tools/inspect_texture.py <rel> [<rel> ...]   (rel = path under textures/, e.g. block/stone.png)
Prints colour clusters (k-means, <=6) with share, plus a text map (<=32x32; '.' = transparent)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, texsrc, clusters
SYM = "0123456789"
for rel in sys.argv[1:]:
    im = texsrc.load(rel); arr = np.asarray(im)
    full_h, w = arr.shape[:2]
    arr = clusters.first_frame(arr)
    labels, cen, sh = clusters.kmeans(arr)
    note = f" (animated strip, {full_h // w} frames; first frame shown)" if arr.shape[0] != full_h else ""
    transp = float((arr[..., 3] == 0).mean())
    print(f"== {rel}  {w}x{full_h}{note}  transparent={transp:.0%}  partial_alpha={float(((arr[...,3]>0)&(arr[...,3]<255)).mean()):.0%}")
    for i, (c, s) in enumerate(zip(cen, sh)):
        print(f"  cluster {i}: rgb({c[0]},{c[1]},{c[2]}) share={s:.0%}")
    h, ww = labels.shape; st = max(1, int(np.ceil(max(h, ww) / 32)))
    if st > 1: print(f"  map downsampled x{st}")
    for y in range(0, h, st):
        print("  " + "".join("." if labels[y, x] < 0 else SYM[labels[y, x]] for x in range(0, ww, st)))
