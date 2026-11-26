# Shader pack listing (copy into the project page)

**Project type:** Shader (CurseForge: "Shaders"; Modrinth: Shader, loader Iris)
**Name:** Realistic X-Ray Shader
**Summary:** The world as one summed radiograph: everything along each view ray adds up, as on a real X-ray film.
**License:** MIT
**Source:** https://github.com/giamat13/realistic-minecraft-xray
**Logo:** `dist/logo.png`
**File:** `dist/RealisticXRay-Shader.zip` (built with `python tools/build_shaderpack.py`), version 1.0.0, release type Release
**Game versions:** 26.2, 26.3 (keep only the versions you tested)

## Description

The optional companion shader for the Realistic X-Ray resource pack. The resource pack shades each surface by its material. This shader adds up everything along each view ray, like a real exposure.

- Thickness counts: the longer the path through matter, the brighter it gets.
- Dense blocks show through the matter around them.
- Water, plants, panes and items add their attenuation per surface.
- Creatures are summed with everything else.
- Black and white.

**Requirements**

- Iris and Sodium, 26.2 or newer, OpenGL.
- The Realistic X-Ray resource pack, enabled at the top of the list.
- Sodium "Block Face Culling" turned **off**. With it on, the image is wrong (black areas, missing thickness).

**Limits:** the game skips chunk sections completely hidden behind solid ones, so those cannot show.

**Servers:** this shader shows matter behind other blocks. Use it only where the server allows it.

Made with the help of AI (Claude).

Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.
