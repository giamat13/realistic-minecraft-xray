"""The project logo: a real radiograph (attenuation summed along every ray) of a blocky skeleton.

Writes pack.png (256x256, shown by the game) and dist/logo.png (1024x1024, for the store pages).
Usage: python tools/make_logo.py   (needs numpy, pillow)"""
import pathlib
import numpy as np
from PIL import Image, ImageFilter

SIZE = 1024
FINE = 4                      # voxels per model pixel
GRID = (40, 34, 20)           # model pixels: x (right), y (down), z (towards the viewer)
FLESH, BONE, DENSE = 0.028, 0.30, 0.75

def model():
    """A head and chest in game proportions: faint soft tissue around bright bone."""
    v = np.zeros(tuple(n * FINE for n in GRID), np.float32)
    def box(x0, x1, y0, y1, z0, z1, value):
        v[tuple(slice(int(round(a * FINE)), int(round(b * FINE))) for a, b in ((x0, x1), (y0, y1), (z0, z1)))] = value
    c = GRID[0] / 2
    def pair(x0, x1, *rest):  # mirrored left and right
        box(c + x0, c + x1, *rest)
        box(c - x1, c - x0, *rest)

    # soft tissue: head, neck, torso, arms
    box(c - 8, c + 8, 1, 17, 2, 18, FLESH * 0.8)
    box(c - 8, c + 8, 17, 34, 6, 14, FLESH)
    pair(8, 16, 17, 34, 6, 14, FLESH)

    # skull: a rounded hollow shell, so its edges come out brighter, as bone does
    gx, gy, gz = np.meshgrid(*[(np.arange(n * FINE) + 0.5) / FINE for n in GRID], indexing="ij")
    def blob(center, radius, power, value):
        inside = sum(np.abs((g - m) / r) ** power for g, m, r in zip((gx, gy, gz), center, radius)) <= 1
        v[inside] = value
    blob((c, 8.4, 10), (7.2, 7.0, 7.4), 3.2, BONE * 1.05)
    blob((c, 8.4, 10), (5.9, 5.6, 6.0), 3.2, FLESH * 0.8)
    box(c - 4.5, c + 4.5, 12, 16.5, 7, 16.5, BONE * 0.34)      # jaw
    for side in (-1, 1):                                       # eye sockets, dark right through
        blob((c + side * 3.1, 8.8, 10), (2.3, 2.1, 12), 2.6, FLESH * 0.45)
    for i, half in enumerate((0.35, 0.7, 1.1, 1.3)):           # nose
        box(c - half, c + half, 10.6 + i * 0.55, 11.15 + i * 0.55, 3, 18, FLESH * 0.6)
    box(c - 4.5, c + 4.5, 14.05, 14.55, 7, 18, FLESH * 0.5)    # the bite
    for x in np.arange(-3.9, 3.6, 1.3):                        # teeth
        box(c + x, c + x + 0.85, 13, 14.05, 13.5, 17, DENSE * 0.55)
        box(c + x, c + x + 0.85, 14.55, 15.5, 13.5, 17, DENSE * 0.55)

    # spine, collar bones, ribs, breastbone
    for y in np.arange(16.5, 34, 2):
        box(c - 1.5, c + 1.5, y, y + 1.5, 7, 10, BONE)
    pair(1, 9, 18, 19.25, 10, 12.5, BONE)
    for i, y in enumerate(np.arange(20.5, 32, 2.5)):
        reach = 7 - max(i - 2, 0)
        pair(1.5, reach, y, y + 1, 6.5, 8, BONE * 1.2)               # back of the rib
        pair(reach - 1.25, reach, y + 0.25, y + 1.25, 7, 13, BONE * 1.5)    # side
        pair(1.5, reach, y + 1, y + 1.75, 12, 13.25, BONE * 0.8)     # front, a little lower
    box(c - 0.75, c + 0.75, 20, 28, 12.5, 13.5, BONE * 0.7)

    # shoulders and upper arms with marrow
    pair(9.5, 14.5, 17.5, 21, 7.5, 12.5, BONE * 0.8)
    pair(11, 13.5, 21, 34, 8.5, 11.5, BONE)
    pair(11.75, 12.75, 22, 34, 9.25, 10.75, FLESH)
    return v

def radiograph(v, yaw, width):
    """Sum the voxels along parallel rays, seen from a slightly turned direction."""
    span = GRID[0] * FINE * 0.98
    u = (np.arange(width) + 0.5) / width * span - span / 2
    w = (np.arange(width) + 0.5) / width * span - span * 0.47
    depth = np.arange(-span * 0.6, span * 0.6, 0.5)
    cx, cy, cz = (n * FINE / 2 for n in GRID)
    total = np.zeros((width, width), np.float32)
    for d in depth:
        x = np.floor(cx + u * np.cos(yaw) + d * np.sin(yaw)).astype(int)
        z = np.floor(cz - u * np.sin(yaw) + d * np.cos(yaw)).astype(int)
        y = np.floor(cy + w).astype(int)
        ix = (x >= 0) & (x < v.shape[0]) & (z >= 0) & (z < v.shape[2])
        iy = (y >= 0) & (y < v.shape[1])
        column = np.where(ix, np.clip(x, 0, v.shape[0] - 1), 0)
        layer = np.where(ix, np.clip(z, 0, v.shape[2] - 1), 0)
        sheet = v[column[None, :], np.clip(y, 0, v.shape[1] - 1)[:, None], layer[None, :]]
        total += sheet * (ix[None, :] & iy[:, None])
    return total * 0.5 / FINE

LETTERS = {
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
}

def title(text, cell):
    mask = np.zeros((7, 6 * len(text) - 1), np.uint8)
    for i, letter in enumerate(text):
        mask[:, 6 * i:6 * i + 5] = [[int(p) for p in row] for row in LETTERS[letter]]
    return mask.repeat(cell, 0).repeat(cell, 1) * 255

def glow(a, radius):
    return np.asarray(Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)), np.float32) / 255

def main():
    film = 1.0 - np.exp(-radiograph(model(), np.radians(7), SIZE) / 2.1)
    film = np.clip(film * 1.08, 0, 1) ** 1.12
    film = film + 0.28 * glow(film, 14)
    # a darker band behind the title keeps it readable over the ribs
    ramp = np.clip((np.arange(SIZE) - SIZE * 0.66) / (SIZE * 0.14), 0, 1)[:, None]
    film = film * (1 - 0.82 * ramp)
    letters = title("X-RAY", 28)
    layer = np.zeros((SIZE, SIZE), np.float32)
    top, left = SIZE - letters.shape[0] - 64, (SIZE - letters.shape[1]) // 2
    layer[top:top + letters.shape[0], left:left + letters.shape[1]] = letters / 255
    film = film * (1 - glow(layer, 18) * 0.5)
    film = np.where(layer > 0, 0.97, film) + 0.45 * glow(layer, 16) * (1 - layer)
    y, x = (np.mgrid[0:SIZE, 0:SIZE] / SIZE) - 0.5
    film = film * (1 - 0.55 * np.clip(x * x + y * y - 0.12, 0, None) * 2)
    film = film + np.random.default_rng(7).normal(0, 0.012, film.shape) + 0.015
    image = Image.fromarray(np.clip(film * 255, 0, 255).astype(np.uint8), "L").convert("RGB")
    pathlib.Path("dist").mkdir(exist_ok=True)
    image.save("dist/logo.png")
    image.resize((256, 256), Image.LANCZOS).save("pack.png")
    print("written: dist/logo.png, pack.png")

if __name__ == "__main__":
    main()
