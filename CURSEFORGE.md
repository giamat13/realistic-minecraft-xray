# CurseForge listing (copy into the project page)

**Project type:** Resource Pack (Texture Pack)
**Name:** Realistic X-Ray
**Summary:** The game as a real black-and-white radiograph: dense materials are bright, thin things let the beam through, and creatures are skeletons.
**Main category:** 16x
**Additional category:** Miscellaneous
**License:** All Rights Reserved (the textures are derived from the original game art)
**Source:** https://github.com/giamat13/realistic-minecraft-xray
**Logo:** `dist/logo.png` (built with `python tools/make_logo.py`)
**File:** `dist/RealisticXRay-1.0.0.zip` (built with `python tools/build_zip.py 1.0.0`), release type Release
**Game versions:** 1.19.4, 1.20, 1.20.1, 1.20.2, 1.20.3, 1.20.4, 1.20.5, 1.20.6, 1.21, 1.21.1, 1.21.2, 1.21.3, 1.21.4, 1.21.5, 1.21.6, 1.21.7, 1.21.8, 1.21.9, 1.21.10, 1.21.11, 26.1, 26.1.1, 26.1.2, 26.2, 26.3

## Description

Minecraft as an X-ray image. How a thing looks depends on what it is made of: every texture was assigned real materials, region by region, and run through an attenuation simulation with NIST XCOM data.

**This is not a cheat x-ray.** A metre of stone, dirt, wood or glass stops the beam, so you cannot see through full blocks.

- Strictly black and white.
- Dense materials (netherite, gold, iron) are brighter than rock, wood and soil.
- Gold, copper, iron and redstone ores stand out from the rock on the faces you can see. Diamond, coal and emerald barely differ from it, as on a real radiograph.
- Thin or porous things (doors, plants, torches, cobwebs) are partly see-through.
- Creatures are radiographs: skeletons with faint soft tissue, shells for arthropods, faint outlines for boneless creatures.
- Player skins are skeletons: the default ones in every version, and your own account skin on 26.2 and newer, with no mod. A skin that is entirely gray stays as it is.
- Blocks, items, GUI, particles, sky and effects are covered.
- 26.2 and 26.3: no lighting, black sky, gray particles and item tints.

**Setup:** put this pack at the top of the resource pack list. Packs above it replace its textures.

**Versions:** 26.1 and newer have true partial translucency. Resource packs cannot make a block translucent on 1.19.4 to 1.21.11, so there the cubes that let most radiation through are hidden and the rest stay solid. On 1.19.4 to 1.20.1 the game shows an "incompatible pack format" warning; the pack still loads.

Made with the help of AI (Claude). The textures are produced by scripts from the original game textures.

Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.
