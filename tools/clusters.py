import numpy as np
def first_frame(arr):
    h, w = arr.shape[:2]
    return arr[:w] if h > w and h % w == 0 else arr
def kmeans(arr, kmax=6):
    """Deterministic colour clusters of opaque-ish pixels. Returns (labels HxW with -1=transparent, centers Kx3 uint8, shares)."""
    h, w = arr.shape[:2]
    valid = arr[..., 3] > 0
    labels = -np.ones((h, w), int)
    if not valid.any(): return labels, np.zeros((0, 3), np.uint8), []
    px = arr[..., :3][valid].astype(float)
    uniq = np.unique(px, axis=0)
    k = min(kmax, len(uniq))
    # farthest-point init
    cen = [px.mean(0)]
    for _ in range(k - 1):
        d = np.min([((px - c) ** 2).sum(1) for c in cen], axis=0)
        cen.append(px[int(d.argmax())])
    cen = np.array(cen)
    for _ in range(12):
        lab = np.argmin(((px[:, None] - cen[None]) ** 2).sum(2), axis=1)
        for i in range(k):
            if (lab == i).any(): cen[i] = px[lab == i].mean(0)
    lab = np.argmin(((px[:, None] - cen[None]) ** 2).sum(2), axis=1)
    order = np.argsort(-np.bincount(lab, minlength=k)); remap = np.empty(k, int); remap[order] = np.arange(k)
    labels[valid] = remap[lab]
    centers = np.rint(cen[order]).astype(np.uint8)
    shares = [float((remap[lab] == i).mean()) for i in range(k)]
    return labels, centers, shares
