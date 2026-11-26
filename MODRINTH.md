# Modrinth listing (copy into the project page)

**Project type:** Resource Pack
**Name:** Realistic X-Ray
**Slug:** realistic-xray
**Summary (max 256 chars):** A black-and-white X-ray pack that behaves like a real radiograph: dense materials (ores, metals) glow bright and opaque, light ones (stone, dirt, wood, leaves, water) fade away. Covers blocks, items, GUI and mobs.
**Categories:** Utility, Realistic
**Environment:** Client
**License:** choose carefully, see "Licensing" below
**Source:** https://github.com/giamat13/realistic-minecraft-xray
**Version:** 1.0.0, file `dist/RealisticXRay-1.0.0.zip` (built with `python3 tools/build_zip.py 1.0.0`)
**Version type:** Release
**Loaders:** Minecraft (resource pack)
**Game versions:** 1.19.4, 1.20, 1.20.1, 1.20.2, 1.20.3, 1.20.4, 1.20.5, 1.20.6, 1.21, 1.21.1, 1.21.2, 1.21.3, 1.21.4, 1.21.5, 1.21.6, 1.21.7, 1.21.8, 1.21.9, 1.21.10, 1.21.11, 26.1, 26.1.1, 26.1.2, 26.2, 26.3
**Icon:** `pack.png`

## Description

Real X-ray: density decides how a block looks.

- Everything is strictly black and white, and every texture (blocks, items, GUI, mobs, particles) was assigned real materials per region and run through an X-ray attenuation simulation with real NIST XCOM data.
- Dense materials (ancient debris, netherite, gold, diamond, iron, ores) are bright and nearly opaque.
- Medium materials (stone, deepslate, obsidian) are translucent gray.
- Light materials (dirt, sand, wood, leaves, water, glass) almost vanish.
- Heavy-metal ores (gold, copper, iron, redstone) stand out; diamond, coal and emerald are nearly invisible against stone, just like in a real radiograph.
- Mixed textures are split by region: for example the grass strip on a grass block side is see-through while the dirt below is denser. Ores show a faint host rock with bright metal blobs.
- Covers every block, item, GUI element, mob, particle, sky texture and effect in each supported version.

**26.1 and newer:** true partial translucency.
**1.19.4 to 1.21.11:** resource packs cannot make a block translucent, so light blocks disappear entirely (classic x-ray) and dense ones stay solid.

On 1.19.4 to 1.20.1 the game shows an "incompatible pack format" warning; the pack still loads.

Not tested in game by the author yet: please report problems on the issue tracker.

## Changelog (1.0.0)

First release.

## Licensing (read before publishing)

The textures are derived from Mojang's original artwork (converted to grayscale and re-alpha'd by script). Modrinth requires that you have the right to distribute what you upload, and Mojang's terms restrict redistribution of its assets. Derived packs are common, but it is your call: check the Minecraft EULA / Usage Guidelines and consider "All Rights Reserved" or a custom license rather than MIT for the textures. The scripts in `tools/` are MIT.

## Publishing checklist

1. Create the project at https://modrinth.com/dashboard/projects (Resource Pack).
2. Paste the fields above, upload `pack.png` as the icon, and add screenshots (take them in game; `tools/preview.png` shows the textures only).
3. Create a version, upload `dist/RealisticXRay-1.0.0.zip`, select the game versions listed above.
4. Submit for review.
