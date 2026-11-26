"""Make every default player skin a skeleton, built from the pack's rendered skeleton texture.

Skeleton limbs are 2 px thick and player limbs 3-4 px, so each bone face is centred on the player
face and the rest stays transparent. A second, opaque file is written for uploading as an account
skin (the game fills the base layer of uploaded skins, so there the gaps are dark instead).
Run after the skeleton texture is final.
Usage: python3 tools/generate_player_skins.py"""
import pathlib
from PIL import Image

ENTITY = pathlib.Path("assets/minecraft/textures/entity")

def faces(u, v, w, h, d):
    """Face rectangles (x, y, width, height) of a box in the standard entity UV layout."""
    return [(u + d, v, w, d), (u + d + w, v, w, d), (u, v + d, d, h), (u + d, v + d, w, h),
            (u + d + w, v + d, d, h), (u + 2 * d + w, v + d, w, h)]

def paste_bone(skin, skeleton, src_uv, dst_uv, width):
    for (sx, sy, sw, sh), (dx, dy, dw, dh) in zip(faces(*src_uv, 2, 12, 2), faces(*dst_uv, width, 12, 4)):
        skin.paste(skeleton.crop((sx, sy, sx + sw, sy + sh)), (dx + (dw - sw) // 2, dy + (dh - sh) // 2))

def build(skeleton, arm_width):
    skin = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for box in ((0, 0, 32, 16), (16, 16, 40, 32)):            # head and body use the same layout
        skin.paste(skeleton.crop(box), box[:2])
    paste_bone(skin, skeleton, (40, 16), (40, 16), arm_width)  # right arm
    paste_bone(skin, skeleton, (40, 16), (32, 48), arm_width)  # left arm
    paste_bone(skin, skeleton, (0, 16), (0, 16), 4)            # right leg
    paste_bone(skin, skeleton, (0, 16), (16, 48), 4)           # left leg
    return skin

def main():
    skeleton = Image.open(ENTITY / "skeleton/skeleton.png").convert("RGBA")
    count = 0
    for folder, arm in (("wide", 4), ("slim", 3)):
        skin = build(skeleton, arm)
        for path in sorted((ENTITY / "player" / folder).glob("*.png")):
            skin.save(path)
            count += 1
    wide = build(skeleton, 4)
    upload = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for box in ((0, 0, 32, 16), (16, 16, 40, 32), (40, 16, 56, 32), (0, 16, 16, 32), (32, 48, 48, 64), (16, 48, 32, 64)):
        upload.paste((12, 12, 12, 255), box)
    upload.alpha_composite(wide)
    pathlib.Path("dist").mkdir(exist_ok=True)
    upload.save("dist/skeleton-skin.png")
    print(f"default skins replaced: {count}, upload file: dist/skeleton-skin.png")

if __name__ == "__main__":
    main()
