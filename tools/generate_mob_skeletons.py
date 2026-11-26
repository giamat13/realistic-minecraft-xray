"""Turn every mob texture into its radiograph.

Bones are opaque bright gray, soft tissue is a sparse ordered dither of dark gray (real partial alpha
only on layers the game draws translucent), and everything else is fully transparent, because most mob
render types discard alpha. Boxes and UVs come from the game's own model classes
(tools/data/mob_geometry.json, see extract_mob_geometry.py). Nothing is derived from this script's
previous output: textures are drawn from geometry, and the few that need the shape of the original
(saddles, soft armor, skeleton copies) read it from the pinned git commit, so re-running is safe.

Usage: python tools/generate_mob_skeletons.py [--list]"""
import io
import itertools
import json
import math
import pathlib
import re
import subprocess
import sys
import zlib
from collections import Counter

import numpy as np
from PIL import Image

sys.dont_write_bytecode = True           # keep tools/ free of __pycache__
import mob_painters as P

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENTITY = ROOT / "assets/minecraft/textures/entity"
SOURCE_COMMIT = "f71a2ae3"            # last commit before any skeleton work: shapes are read from here
SOFT_GRAY, HAZE = 62, (125, 62)       # dithered flesh; (gray, alpha) where translucency exists
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]])
GEOMETRY = json.loads((ROOT / "tools/data/mob_geometry.json").read_text())

NON_MOB_DIRS = {"armorstand", "banner", "beacon", "bed", "bell", "boat", "chest", "chest_boat", "conduit", "cushion",
                "decorated_pot", "enchantment", "end_crystal", "end_portal", "experience", "fishing", "lead_knot",
                "minecart", "player", "projectiles", "shield", "signs", "trident"}
NON_MOB_FILES = {"banner_base", "beacon_beam", "elytra", "enchanting_table_book", "end_gateway_beam", "end_portal",
                 "experience_orb", "fishing_hook", "guardian_beam", "lead_knot", "minecart", "shield_base",
                 "shield_base_nopattern", "trident", "trident_riptide"}


# ======================================================================== which model each texture is drawn on
def render(category, new=(), old=(), flesh=True, translucent=(), roles=()):
    return dict(kind="render", category=category, new=new.split() if new else [], old=old.split() if old else [],
                flesh=flesh, translucent=set(translucent.split() if translucent else []), roles=list(roles))


def other(kind, category, **extra):
    return dict(kind=kind, category=category, **extra)


# Extra roles: (regex on "part/path#cube", role). They are tried before the generic ones.
FISH = [(r"^body(_front|_back)?#0", "fishspine"), (r"^head#", "skull"), (r"nose", "snout")]
ARTHROPOD = [(r"(front|middle|back)_legs", "legrow"), (r"antenna", "chitinleg"), (r"stinger", "spine"), (r"wing", "chitinwing"), (r"leg", "chitinleg"),
             (r"^(bone/)?head#", "chitinhead"), (r"(body|segment|layer|^bone#)", "chitin")]
DRAGON = [(r"^head#0", "snout"), (r"^head#1", "skull"), (r"^head#", "horn"), (r"jaw", "jaw"),
          (r"(neck|tail)\d*#0", "neck"), (r"(neck|tail)\d*#", "spine"), (r"^body#0", "torso"), (r"^body#", "spine"),
          (r"wing(_tip)?#0", "longbone"), (r"wing(_tip)?#1", "wing")]
CAMEL = [(r"^(body/)?head#0", "neck"), (r"^(body/)?head#1", "neckhead"), (r"^(body/)?head#2", "snout")]
LLAMA = [(r"^head#0", "snout"), (r"^head#1", "neckhead"), (r"^head#", "flesh")]
SQUID = [(r"tentacle", "tentacle"), (r"body", "squid")]
SOFT = [(r"(eye|mouth)", "none"), (r"tentacle", "tentacle"), (r".", "soft")]
SHELLFISH = [(r"corals", "coral"), (r"shell", "spiral"), (r"inner_mouth", "none"), (r"mouth", "jaw"),
             (r"body", "flesh")]
TURTLE = [(r"egg_belly", "eggs"), (r"^body#0", "shell"), (r"^body#", "torso"), (r"leg", "flipper")]
SPLIT_TRUNK = [(r"^body#0", "abdomen"), (r"^body#1", "thorax")]           # two boxes: hips and chest
ARMADILLO = [(r"^cube#", "shell"), (r"^body#0", "shell"), (r"^body#1", "torso")]
WITHER = [(r"shoulders", "bonebar"), (r"ribcage#0", "neck"), (r"ribcage#", "rib")]
VILLAGER = [(r"nose", "flesh")]

RULES = [
    (r"enderdragon/dragon_(exploding|fireball)", other("skip", "dissolve mask / projectile")),
    (r"llama/(llama_)?spit|bee/bee_stinger|shulker/spark|equipment/wings/.*", other("skip", "projectile or item")),
    (r"illager/evoker_fangs|guardian/guardian_beam", other("skip", "summoned attack / beam")),
    # layers that are invisible on a radiograph: light, pigment, hair, cloth, air
    (r".*eyes.*", other("clear", "eyes")),
    (r"warden/warden_(bioluminescent_layer|heart|pulsating_spots_\d)", other("clear", "glow layers")),
    (r"breeze/breeze_wind|creeper/creeper_armor|wither/wither_armor", other("clear", "wind / energy aura")),
    (r"sheep/sheep_(wool.*|fur)", other("clear", "wool")),
    (r"horse/horse_markings.*|fish/tropical_[ab]_pattern.*", other("clear", "pigment")),
    (r"(zombie_)?villager/(baby|type|profession)/.*", other("clear", "clothing")),
    (r"zombie/drowned_outer_layer.*|skeleton/(stray|bogged)_overlay", other("clear", "clothing")),
    (r"wolf/wolf_armor_overlay|equipment/wolf_body/armadillo_scute_overlay|equipment/.*/leather_overlay",
     other("clear", "dye")),
    # dense matter stays as the pack already renders it
    (r"(zombie_)?villager/profession_level/.*", other("keep", "metal and mineral badges")),
    (r"(wolf/wolf_armor|iron_golem/iron_golem)_crackiness.*", other("keep", "damage cracks")),
    (r"(iron_golem|copper_golem)/.*|slime/magmacube|blaze(/blaze)?", other("keep", "metal / mineral mob")),
    (r"skeleton/(skeleton|wither_skeleton)", other("keep", "already a skeleton")),
    (r"skeleton/(bogged|stray)", other("copy", "skeleton", source="skeleton/skeleton")),
    # worn gear
    (r"equipment/\w+_saddle/saddle|pig/pig_saddle|strider/strider_saddle", other("gear", "saddle", material="saddle")),
    (r"equipment/(humanoid\w*|horse_body)/leather|horse/armor/horse_armor_leather",
     other("gear", "soft armor", material="leather")),
    (r"equipment/humanoid\w*/turtle_scute", other("gear", "soft armor", material="scute")),
    (r"equipment/wolf_body/armadillo_scute|wolf/wolf_armor", other("gear", "soft armor", material="scute")),
    (r"equipment/(humanoid\w*|horse_body|nautilus_body)/.*|horse/armor/.*", other("keep", "metal armor")),
    (r"equipment/llama_body/.*|llama/decor/.*", other("gear", "carpet", material="cloth")),
    (r"equipment/happy_ghast_body/.*", other("gear", "harness", material="leather")),
    (r"ghast/happy_ghast_ropes", other("gear", "ropes", material="cloth")),
    (r"(wolf/wolf|cat/cat)_collar(_baby)?", other("gear", "collar", material="cloth")),

    # ---- creatures
    (r"allay/allay", render("vertebrate", "allay", translucent="allay", roles=[(r"wing", "chitinwing")])),
    (r"armadillo/armadillo|armadillo", render("vertebrate", "armadillo", roles=ARMADILLO)),
    (r"armadillo/armadillo_baby", render("vertebrate", "armadillo_baby", roles=ARMADILLO)),
    (r"axolotl/axolotl_[a-z]+_baby", render("vertebrate", "axolotl_baby")),
    (r"axolotl/axolotl_[a-z]+", render("vertebrate", "axolotl", "axolotl")),
    (r"bat/bat", render("vertebrate", "bat")),
    (r"bat", render("vertebrate", "bat")),
    (r"bear/polarbear", render("vertebrate", "polar_bear", "polar_bear", roles=SPLIT_TRUNK)),
    (r"bear/polarbear_baby", render("vertebrate", "polar_bear_baby")),
    (r"bee/bee\w*_baby", render("arthropod", "bee_baby", roles=ARTHROPOD)),
    (r"bee/bee\w*", render("arthropod", "bee", "bee", roles=ARTHROPOD)),
    (r"breeze/breeze", render("soft", "breeze", translucent="breeze",
                              roles=[(r"rod", "horn"), (r"eyes|wind", "none"), (r"head", "soft")])),
    (r"camel/camel(_husk)?", render("vertebrate", "camel", "camel", roles=CAMEL)),
    (r"camel/camel_baby", render("vertebrate", "camel_baby", roles=CAMEL)),
    (r"cat/ocelot", render("vertebrate", "ocelot", "ocelot")),
    (r"cat/ocelot_baby", render("vertebrate", "ocelot_baby")),
    (r"cat/cat_\w+_baby", render("vertebrate", "cat_baby")),
    (r"cat/cat_\w+", render("vertebrate", "cat")),
    (r"cat/\w+", render("vertebrate", old="cat")),
    (r"chicken/(chicken_cold|chicken_temperate|chicken_warm)_baby", render("vertebrate", "chicken_baby", roles=[(r"^body#0", "skull")])),
    (r"chicken/(chicken_cold|cold_chicken)", render("vertebrate", "cold_chicken", roles=[(r"^head#1", "flesh")])),
    (r"chicken/(chicken_(temperate|warm)|(temperate|warm)_chicken)", render("vertebrate", "chicken")),
    (r"chicken", render("vertebrate", old="chicken")),
    (r"cow/cow_cold_baby", render("vertebrate", "cold_cow_baby")),
    (r"cow/cow_temperate_baby", render("vertebrate", "cow_baby")),
    (r"cow/cow_warm_baby", render("vertebrate", "warm_cow_baby")),
    (r"cow/mooshroom_\w+_baby", render("vertebrate", "mooshroom_baby")),
    (r"cow/(cow_cold|cold_cow)", render("vertebrate", "cold_cow")),
    (r"cow/(cow_temperate|temperate_cow)", render("vertebrate", "cow")),
    (r"cow/(cow_warm|warm_cow)", render("vertebrate", "warm_cow", roles=[(r"^head#[2-5]", "horn")])),
    (r"cow/mooshroom_(red|brown)", render("vertebrate", "mooshroom")),
    (r"cow/(red|brown)_mooshroom", render("vertebrate", "mooshroom")),
    (r"cow/cow", render("vertebrate", old="cow")),
    (r"creaking/creaking", render("wood", "creaking", flesh=False, roles=[(r".", "wood")])),
    (r"creeper/creeper", render("vertebrate", "creeper creeper_head", "creeper")),
    (r"dolphin/dolphin", render("vertebrate", "dolphin", roles=[(r"(tail|back)_fin", "flesh"), (r"_fin", "flipper")])),
    (r"dolphin/dolphin_baby", render("vertebrate", "dolphin_baby",
                                     roles=[(r"(tail|back)_fin", "flesh"), (r"_fin", "flipper")])),
    (r"dolphin", render("vertebrate", old="dolphin", roles=[(r"(tail|back)_fin", "flesh"), (r"_fin", "flipper")])),
    (r"enderdragon/dragon", render("vertebrate", "ender_dragon dragon_skull", "ender_dragon dragon_skull",
                                   roles=DRAGON)),
    (r"enderman/enderman", render("vertebrate", "enderman", "enderman")),
    (r"endermite/endermite", render("arthropod", "endermite", roles=ARTHROPOD)),
    (r"endermite", render("arthropod", old="endermite", roles=ARTHROPOD)),
    (r"fish/cod", render("vertebrate", "cod", "cod", roles=FISH)),
    (r"fish/salmon", render("vertebrate", "salmon salmon_small salmon_large", "salmon", roles=FISH)),
    (r"fish/pufferfish", render("vertebrate", "pufferfish_big pufferfish_medium pufferfish_small",
                                "pufferfish_big pufferfish_medium pufferfish_small",
                                roles=[(r"^body#", "fishbody"), (r"_fin", "spine"), (r"eye", "none")])),
    (r"fish/tropical_a", render("vertebrate", "tropical_fish_small", "tropical_fish_small", roles=FISH)),
    (r"fish/tropical_b", render("vertebrate", "tropical_fish_large", "tropical_fish_large", roles=FISH)),
    (r"fox/fox\w*_baby", render("vertebrate", "fox_baby")),
    (r"fox/(fox|fox_snow|fox_sleep|fox_snow_sleep)", render("vertebrate", "fox", "fox")),
    (r"fox/snow_fox(_sleep)?", render("vertebrate", old="fox")),
    (r"frog/frog_\w+", render("vertebrate", "frog")),
    (r"frog/\w+_frog", render("vertebrate", old="frog")),
    (r"ghast/ghast(_shooting)?", render("soft", "ghast", "ghast", roles=SOFT)),
    (r"ghast/happy_ghast", render("soft", "happy_ghast", roles=SOFT)),
    (r"ghast/happy_ghast_baby", render("soft", "happy_ghast_baby", roles=[(r"inner_body", "none")] + SOFT)),
    (r"goat/goat", render("vertebrate", "goat", "goat",
                          roles=[(r"^head/nose#", "skull"), (r"^head#2", "none"), (r"^head#", "flesh")])),
    (r"goat/goat_baby", render("vertebrate", "goat_baby")),
    (r"guardian/guardian(_elder)?", render("vertebrate", "guardian elder_guardian", roles=[
        (r"^head#0", "fishbody"), (r"spike", "spine"), (r"eye", "none"), (r"^head#", "flesh"), (r"tail2#1", "fin")])),
    (r"guardian(_elder)?", render("vertebrate", old="guardian elder_guardian", roles=[
        (r"^head#0", "fishbody"), (r"spike", "spine"), (r"eye", "none"), (r"^head#", "flesh"), (r"tail2#1", "fin")])),
    (r"hoglin/(hoglin|zoglin)", render("vertebrate", "hoglin", "hoglin")),
    (r"hoglin/(hoglin|zoglin)_baby", render("vertebrate", "hoglin_baby", roles=[(r"^head#[12]", "horn")])),
    (r"horse/horse_skeleton", render("skeleton", "skeleton_horse", "skeleton_horse", flesh=False)),
    (r"horse/horse_skeleton_baby", render("skeleton", "skeleton_horse_baby", flesh=False)),
    (r"horse/horse_zombie", render("vertebrate", "zombie_horse", "zombie_horse")),
    (r"horse/horse_zombie_baby", render("vertebrate", "zombie_horse_baby")),
    (r"horse/horse_[a-z]+_baby", render("vertebrate", "horse_baby")),
    (r"horse/horse_[a-z]+", render("vertebrate", "horse", "horse")),
    (r"horse/(donkey|mule)", render("vertebrate", "donkey", "donkey")),
    (r"horse/(donkey|mule)_baby", render("vertebrate", "donkey_baby")),
    (r"illager/(evoker|vindicator|pillager|illusioner)",
     render("vertebrate", "evoker pillager", "evoker pillager", roles=VILLAGER)),
    (r"illager/ravager", render("vertebrate", "ravager", "ravager", roles=[(r"head#1", "snout"), (r"^body#0", "thorax"),
                                                                  (r"^body#1", "abdomen")])),
    (r"illager/vex(_charging)?", render("vertebrate", "vex", "vex", translucent="vex", roles=[(r"wing", "chitinwing")])),
    (r"llama/llama_\w+_baby", render("vertebrate", "llama_baby", roles=[(r"^head#0", "neckhead"), (r"^head#1", "snout"), (r"^head#", "flesh")])),
    (r"llama/llama_\w+", render("vertebrate", "llama", roles=LLAMA)),
    (r"llama/(brown|creamy|gray|white)", render("vertebrate", old="llama", roles=LLAMA)),
    (r"nautilus/(nautilus|zombie_nautilus)", render("shell", "nautilus", roles=SHELLFISH)),
    (r"nautilus/zombie_nautilus_coral", render("shell", "zombie_nautilus_coral", roles=SHELLFISH)),
    (r"nautilus/nautilus_baby", render("shell", "nautilus_baby", roles=SHELLFISH)),
    (r"panda/\w+_baby|panda/panda_baby", render("vertebrate", "panda_baby")),
    (r"panda/(panda|panda_[a-z]+)", render("vertebrate", "panda", "panda")),
    (r"panda/[a-z]+_panda", render("vertebrate", old="panda")),
    (r"parrot/parrot_\w+", render("vertebrate", "parrot", "parrot",
                                  roles=[(r"wing", "birdwing"), (r"feather|tail", "flesh"), (r"head2", "skull")])),
    (r"phantom/phantom", render("vertebrate", "phantom")),
    (r"phantom", render("vertebrate", old="phantom")),
    (r"pig/(pig_cold|cold_pig)", render("vertebrate", "cold_pig")),
    (r"pig/(pig_(temperate|warm)|(temperate|warm)_pig)", render("vertebrate", "pig")),
    (r"pig/pig_\w+_baby", render("vertebrate", "pig_baby")),
    (r"pig/pig", render("vertebrate", old="pig")),
    (r"piglin/(piglin|piglin_brute|zombified_piglin)",
     render("vertebrate", "piglin piglin_head", "piglin piglin_head", translucent="piglin piglin_head")),
    (r"piglin/\w+_baby", render("vertebrate", "piglin_baby", translucent="piglin_baby", roles=[(r"^head#0", "snout")])),
    (r"rabbit/rabbit_\w+_baby", render("vertebrate", "rabbit_baby")),
    (r"rabbit/rabbit_\w+", render("vertebrate", "rabbit")),
    (r"rabbit/\w+", render("vertebrate", old="rabbit")),
    (r"sheep/sheep", render("vertebrate", "sheep", "sheep")),
    (r"sheep/sheep_baby", render("vertebrate", "sheep_baby")),
    (r"shulker/shulker(_\w+)?", render("shell", "shulker", "shulker", roles=[(r"lid|base", "boxshell"), (r"head", "soft")])),
    (r"silverfish/silverfish", render("arthropod", "silverfish", roles=ARTHROPOD)),
    (r"silverfish", render("arthropod", old="silverfish", roles=ARTHROPOD)),
    (r"skeleton/parched", render("skeleton", "parched", flesh=False,
                                 roles=[(r"^(head|body|\w+_arm|\w+_leg)#[1-9]", "none")])),
    (r"slime/slime", render("soft", "slime#outer slime", "slime#outer slime", translucent="slime#outer", roles=SOFT)),
    (r"sulfur_cube/sulfur_cube_outer", render("soft", "sulfur_cube", translucent="sulfur_cube", roles=SOFT)),
    (r"sulfur_cube/sulfur_cube_outer_small", render("soft", "sulfur_cube_small", translucent="sulfur_cube_small",
                                                    roles=SOFT)),
    (r"sulfur_cube/sulfur_cube_inner", render("soft", "sulfur_cube#inner", translucent="sulfur_cube#inner", roles=SOFT)),
    (r"sulfur_cube/sulfur_cube_inner_small", render("soft", "sulfur_cube_small#inner",
                                                    translucent="sulfur_cube_small#inner", roles=SOFT)),
    (r"sniffer/sniffer", render("vertebrate", "sniffer", "sniffer", roles=[(r"nose", "snout"), (r"lower_beak", "jaw")])),
    (r"sniffer/snifflet", render("vertebrate", "sniffer_baby", roles=[(r"nose", "snout"), (r"lower_beak", "jaw")])),
    (r"snow_golem/snow_golem", render("soft", "snow_golem", flesh=True, roles=[(r"arm", "wood"), (r".", "soft")])),
    (r"snow_golem", render("soft", old="snow_golem", roles=[(r"arm", "wood"), (r".", "soft")])),
    (r"spider/spider", render("arthropod", "spider", "spider", roles=ARTHROPOD)),
    (r"spider/cave_spider", render("arthropod", "cave_spider", "cave_spider", roles=ARTHROPOD)),
    (r"squid/squid", render("soft", "squid", "squid", roles=SQUID)),
    (r"squid/glow_squid", render("soft", "glow_squid", "glow_squid", roles=SQUID)),
    (r"squid/(glow_)?squid_baby", render("soft", "squid_baby", roles=SQUID)),
    (r"strider/strider(_cold)?", render("vertebrate", "strider", "strider", roles=[(r"^body#", "headbody")])),
    (r"strider/strider(_cold)?_baby", render("vertebrate", "strider_baby", roles=[(r"^body#", "headbody")])),
    (r"tadpole/tadpole", render("vertebrate", "tadpole", "tadpole", roles=[(r"body", "fishbody"), (r"tail", "tadtail")])),
    (r"turtle/turtle", render("vertebrate", "turtle", roles=TURTLE)),
    (r"turtle/turtle_baby", render("vertebrate", "turtle_baby", roles=[(r"^body#", "shell"), (r"leg", "flipper")])),
    (r"turtle/big_sea_turtle", render("vertebrate", old="turtle", roles=TURTLE)),
    (r"villager/villager", render("vertebrate", "villager villager_no_hat", "villager", roles=VILLAGER)),
    (r"villager/villager_baby", render("vertebrate", "villager_baby", roles=VILLAGER)),
    (r"wandering_trader/wandering_trader", render("vertebrate", "wandering_trader", roles=VILLAGER)),
    (r"wandering_trader", render("vertebrate", old="wandering_trader", roles=VILLAGER)),
    (r"warden/warden", render("vertebrate", "warden", "warden", roles=[(r"ribcage", "ribplane"), (r"tendril", "flesh")])),
    (r"witch/witch", render("vertebrate", "witch", roles=VILLAGER)),
    (r"witch", render("vertebrate", old="witch", roles=VILLAGER)),
    (r"wither/wither(_invulnerable)?", render("skeleton", "wither wither_skull", "wither wither_skull", flesh=False,
                                              roles=WITHER)),
    (r"wolf/wolf(_[a-z]+)*_baby", render("vertebrate", "wolf_baby")),
    (r"wolf/wolf(_[a-z]+)*", render("vertebrate", "wolf", "wolf", roles=[
        (r"upper_body", "thorax"), (r"^body#", "abdomen")])),
    (r"zombie/(zombie|husk)", render("vertebrate", "zombie husk zombie_head", "zombie husk zombie_head")),
    (r"zombie/drowned", render("vertebrate", "drowned", "drowned")),
    (r"zombie/(zombie|husk|drowned)_baby", render("vertebrate", "zombie_baby drowned_baby", roles=[(r"^head#1", "none")])),
    (r"zombie_villager/zombie_villager", render("vertebrate", "zombie_villager", "zombie_villager",
                                              roles=[(r"^head#1", "flesh")] + VILLAGER)),
    (r"zombie_villager/zombie_villager_baby", render("vertebrate", "zombie_villager_baby", roles=VILLAGER)),
]

# Generic roles, tried in order against the last meaningful part name.
CLOTH = r"hat|jacket|sleeve|pants|mushroom|mole|^eyes?$|_eyes?$|mane$|bridle|reins|saddle|goggles|harness|inner_body|" \
        r"croaking|tongue|coral|bristle|wind|bb_main|whisker|cloak|_chest$"
GENERIC = [(r"ear|gill|red_thing|tendril", "flesh"), (r"hump", "hump"), (r"horn", "horn"),
           (r"lower_beak|jaw|lower_mouth|^mouth$", "jaw"), (r"beak", "beak"), (r"upper_mouth|nose", "snout"),
           (r"neck|head_parts", "neck"), (r"head", "skull"), (r"rod", "bonebar"), (r"spike", "spine"),
           (r"wing", "wing"), (r"fin", "fin"), (r"tentacle", "tentacle"), (r"tail", "tail"),
           (r"leg|arm|foot|feet|hand|haunch|shoulder", "limb"), (r"body", "torso")]
# how much soft tissue each role carries, in sixteenths of the dither matrix
FLESH = {"skull": 4, "snout": 4, "jaw": 3, "torso": 5, "thorax": 5, "abdomen": 5, "headbody": 5, "limb": 4,
         "longbone": 3, "neck": 5, "tail": 3, "neckhead": 5, "wing": 1, "birdwing": 3, "fin": 2, "flipper": 4,
         "fishspine": 4, "fishbody": 4, "flesh": 4, "hump": 4, "ribplane": 0, "shell": 2, "spiral": 1, "eggs": 3,
         "spine": 1, "rib": 0, "legrow": 0, "chitin": 2, "chitinhead": 2, "chitinwing": 1, "soft": 2, "squid": 2, "tentacle": 2,
         "tadtail": 3, "boxshell": 1}


def part_name(path):
    """Last meaningful segment: rotation helpers (x_r1) and *_cube wrappers inherit their parent's name."""
    segments = path.split("/") or [""]
    if any("tail" in s for s in segments[:-1]) and "fin" not in segments[-1]:
        return "tail"
    while len(segments) > 1 and re.search(r"_r\d+$|_cube$|^HeadMain$", segments[-1]):
        segments.pop()
    return re.sub(r"_r\d+$", "", segments[-1])


# ======================================================================== geometry of one cube
AXES = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]])      # lateral, up, front in model space
L, U, F = 0, 1, 2


class Cube:
    def __init__(self, data, size):
        self.path, self.index, self.faces = data["p"], data["i"], data["f"]
        verts = np.array([v for f in self.faces for v in f["v"]])
        normals = []
        for face in self.faces:
            n = np.array(face["n"], dtype=float)
            if np.linalg.norm(n) and not any(abs(n @ m) > 0.9 * np.linalg.norm(n) for m in normals):
                normals.append(n / np.linalg.norm(n))
        while len(normals) < 3:
            normals.append(np.cross(normals[0], normals[-1] if len(normals) > 1 else AXES[1]))
        order = max(itertools.permutations(range(3)), key=lambda p: sum(abs(normals[p[a]] @ AXES[a]) for a in range(3)))
        self.axes = [normals[order[a]] * (1 if normals[order[a]] @ AXES[a] >= 0 else -1) for a in range(3)]
        projected = [verts[:, :3] @ axis for axis in self.axes]
        self.low = [p.min() for p in projected]
        self.span = [p.max() - p.min() for p in projected]
        self.centre = verts[:, :3].mean(axis=0) @ AXES.T
        # texels along each axis, read from the UV rectangle (model scaling does not change it)
        self.n = [0, 0, 0]
        for face in self.faces:
            v = np.array(face["v"], dtype=float)
            for i, j in ((0, 1), (1, 2)):
                edge = v[j, :3] - v[i, :3]
                length = np.linalg.norm(edge)
                if length < 1e-3:
                    continue
                texels = np.hypot((v[j, 3] - v[i, 3]) * size[0], (v[j, 4] - v[i, 4]) * size[1])
                axis = max(range(3), key=lambda a: abs(edge @ self.axes[a]))
                self.n[axis] = max(self.n[axis], int(round(texels)))
        self.n = [max(1, n) for n in self.n]

    def long_axis(self):
        return max(range(3), key=lambda a: (self.n[a], a == U))

    def thin_axis(self):
        return min(range(3), key=lambda a: (self.span[a], a != U))


VIEW_AXES = {"frontal": (L, U), "lateral": (F, U), "dorsal": (L, F)}


def oriented(cube, view, painter, trunk, proximal_top=True):
    """Run a painter that works in [along, across] on a face, whichever way the box is turned."""
    a_axis, b_axis = VIEW_AXES[view]
    long = cube.long_axis()
    if long not in (a_axis, b_axis):
        return None
    across = a_axis if long == b_axis else b_axis
    pattern = painter(cube.n[long], cube.n[across])
    # texture coordinates run left to right, top to bottom and front to back
    low_end_first = {L: True, U: False, F: False}                  # does index 0 sit at the low end of the axis?
    towards_trunk_is_high = trunk[long] > cube.centre[long]
    if long == U:
        flip = not proximal_top
    else:
        flip = towards_trunk_is_high == low_end_first[long]
    if flip:
        pattern = pattern[::-1, :]
    if across == L and cube.centre[L] < 0:
        pattern = pattern[:, ::-1]
    return pattern if long == b_axis else pattern.T


def in_plane(cube, view, painter, trunk):
    """For flat parts: painter works in [rows = from the base / leading edge, columns = span]."""
    thin = cube.thin_axis()
    a_axis, b_axis = VIEW_AXES[view]
    if thin in (a_axis, b_axis):
        return None
    span = max((a_axis, b_axis), key=lambda a: (cube.n[a], a == L))
    chord = a_axis if span == b_axis else b_axis
    pattern = painter(cube.n[chord], cube.n[span])
    low_end_first = {L: True, U: False, F: False}
    if (trunk[span] > cube.centre[span]) == low_end_first[span]:
        pattern = pattern[:, ::-1]
    return pattern if span == a_axis else pattern.T


def paint(role, cube, view, trunk):
    a_axis, b_axis = VIEW_AXES[view]
    na, nb = cube.n[a_axis], cube.n[b_axis]
    cross = lambda: P.cross_section(na, nb)
    if role == "skull":
        return P.skull(view, na, nb)
    if role == "snout":
        return P.snout(view, na, nb)
    if role == "jaw":
        return P.jaw(view, na, nb)
    if role in ("torso", "thorax", "abdomen"):
        upright = cube.n[U] > cube.n[F]
        ribs = {"torso": (0.08, 0.62), "thorax": (0.0, 0.95), "abdomen": None}[role]
        return P.torso(view, na, nb, upright, ribs, role != "thorax")
    if role == "headbody":
        if view == "lateral":
            a = P.torso(view, na, nb, True, (0.55, 0.85))
            head = max(2, nb // 2)
            a[:head, :] = P.skull("lateral", na, head)
        elif view == "frontal":
            a = P.torso(view, na, nb, True, (0.55, 0.85))
            head = max(2, round(nb * 0.6))
            a[:head, :] = P.skull("frontal", na, head)
        else:
            a = P.skull("dorsal", na, nb)
        return a
    if role == "neckhead":
        head = max(2, round(nb * 0.4))
        if view == "dorsal":
            return P.skull("dorsal", na, nb)
        a = P.blank(nb, na)
        a[head:, :] = P.vertebrae(max(1, nb - head), na)[:nb - head, :]
        a[:head, :] = P.skull(view, na, head)
        return a
    if role in ("limb", "flipper", "longbone"):
        if role == "flipper" and min(cube.n) <= 1:
            result = in_plane(cube, view, P.membrane_wing, trunk)
        else:
            result = oriented(cube, view, lambda n, c: P.limb(n, c, True, role == "limb"), trunk)
        if result is None:
            return P.blank(nb, na) if min(cube.span) < 0.01 else cross()
        return result
    if role in ("neck", "tail", "spine", "tadtail", "bonebar", "tentacle", "chitinleg", "ribplane"):
        painter = {
            "neck": lambda n, c: P.vertebrae(n, c),
            "tail": lambda n, c: P.vertebrae(n, c, 1 if c < 6 else 2, 2),
            "tadtail": lambda n, c: P.vertebrae(n, c, 1, 2),
            "spine": lambda n, c: P.vertebrae(n, c, 1, 4),
            "bonebar": lambda n, c: P.filled(c, n),
            "tentacle": lambda n, c: P.jointed_leg(n, c) // 2 if n > 1 else P.blank(n, c),
            "chitinleg": P.jointed_leg,
            "ribplane": lambda n, c: P.blank(n, c),
        }[role]
        if role == "ribplane":
            a = P.blank(nb, na)
            for r in range(1, nb - 1, 3):
                a[r, :] = P.BONE
                a[min(nb - 1, r + 1), na // 3:na - na // 3] = P.THIN
            return a
        result = oriented(cube, view, painter, trunk)
        if result is None:
            return P.blank(nb, na) if role in ("tentacle", "chitinleg") else cross()
        return result
    if role in ("wing", "birdwing", "fin", "chitinwing"):
        painter = {"wing": P.membrane_wing, "birdwing": P.bird_wing, "fin": P.fin_rays,
                   "chitinwing": lambda c, s: P.membrane_wing(c, s) // 2 + (P.membrane_wing(c, s) > 0) * 25}[role]
        if role == "birdwing":                       # a folded wing shows its bones from the side
            result = in_plane(cube, view, painter, trunk) if view == "lateral" else None
        else:
            result = in_plane(cube, view, painter, trunk)
        return P.blank(nb, na) if result is None else result
    if role == "fishspine":
        return P.fish_trunk(view, na, nb)
    if role == "fishbody":
        return P.fish_body(view, na, nb)
    if role in ("chitin", "chitinhead"):
        a = P.chitin(na, nb)
        if role == "chitinhead" and view == "frontal" and na >= 4 and nb >= 4:
            for c in (na // 2 - 2, na // 2 + 1):             # fangs
                a[nb * 5 // 8:nb - 1, c] = P.DENSE
        return a
    if role == "shell":
        return P.shell(view, na, nb)
    if role == "boxshell":
        return P.box_shell(view, na, nb)
    if role == "spiral":
        return P.spiral_shell(view, na, nb)
    if role == "legrow":                                  # one flat card standing for a pair of legs
        a = P.blank(nb, na)
        if view == "frontal":
            a[:, 1::3] = P.THIN
        return a
    if role == "rib":                                     # a single arc, with the gap to the next one open
        a = P.blank(nb, na)
        a[0, :] = P.BONE
        if view == "frontal":
            a[0, ::3] = P.DENSE
        return a
    if role == "coral":
        return P.branches(na, nb)
    if role == "eggs":
        return P.eggs(na, nb)
    if role == "horn":
        return P.filled(na, nb, 132, P.THIN)
    if role == "beak":
        return P.filled(na, nb, P.THIN, P.BONE)
    if role == "soft":
        return P.soft_outline(na, nb)
    if role == "wood":
        return P.wood(na, nb)
    if role == "hump":                                    # fat over the tips of the dorsal spines
        a = P.blank(nb, na)
        if view == "lateral":
            a[nb // 2:, 1::3] = P.THIN
        return a
    if role == "squid":                                   # only the chitin pen and the beak absorb much
        a = P.soft_outline(na, nb)
        if view in ("frontal", "lateral") and nb >= 5:
            col = na // 2 if view == "frontal" else na - max(2, na // 4)
            a[1:nb - 2, col] = 128
            a[nb - 3:nb - 1, max(0, na // 2 - 1):na // 2 + 1] = P.DENSE
        return a
    return P.blank(nb, na)                                # flesh, cloth


def role_of(cube, cubes, spec):
    key = f"{cube.path}#{cube.index}"
    for pattern, role in spec["roles"]:
        if re.search(pattern, key):
            return role
    name = part_name(cube.path)
    if re.search(CLOTH, name) or re.search(r"(^|/)(hat|mushrooms)(/|$)", cube.path):
        return "none"
    role = next((r for pattern, r in GENERIC if re.search(pattern, name)), None)
    if role is None:
        raise SystemExit(f"no role for model part {key!r}")
    if cube.index and role in ("skull", "torso"):
        # further boxes of the same part: muzzles, horns, ears, tusks, clothing
        main = next(c for c in cubes if c.path == cube.path and c.index == 0)
        if role == "torso":
            return "none"
        volume = np.prod(cube.n)
        if volume >= np.prod(main.n):
            return "skull"
        ahead = cube.centre[F] - main.centre[F]
        above = cube.centre[U] - main.centre[U]
        if cube.n[U] >= 2 * max(cube.n[L], cube.n[F]) or (cube.n[L] >= 2 * cube.n[U] and above > 0 and cube.n[F] >= 2):
            return "horn"
        if ahead > main.span[F] / 2 and above <= main.span[U] / 4:
            return "snout"
        return "flesh"
    return role


# ======================================================================== drawing
def noise(name, shape, amount=4):
    rng = np.random.default_rng(zlib.crc32(name.encode()))
    return rng.integers(-amount, amount + 1, shape)


def draw_layer(image, covered, layer, spec, translucent, name):
    height, width = covered.shape
    cubes = [Cube(c, layer["tex"]) for c in layer["cubes"]]
    roles = [role_of(c, cubes, spec) for c in cubes]
    trunks = [c for c, r in zip(cubes, roles) if r in ("torso", "thorax", "fishspine", "fishbody", "chitin", "squid")]
    biggest = max(trunks or cubes, key=lambda c: np.prod(c.n))
    jitter = noise(name, covered.shape)
    layer_mask = np.zeros_like(covered)
    # clothing first, so that bones win wherever two boxes share the same texels
    for i in sorted(range(len(cubes)), key=lambda i: (roles[i] != "none", roles[i] != "flesh", -i)):
        cube, role = cubes[i], roles[i]
        flesh = FLESH.get(role, 0) if spec["flesh"] else 0
        for face in cube.faces:
            v = np.array(face["v"], dtype=float)
            u0, u1 = v[:, 3].min() * width, v[:, 3].max() * width
            v0, v1 = v[:, 4].min() * height, v[:, 4].max() * height
            xs = np.arange(max(0, math.ceil(u0 - 0.501)), min(width, math.floor(u1 - 0.499) + 1))
            ys = np.arange(max(0, math.ceil(v0 - 0.501)), min(height, math.floor(v1 - 0.499) + 1))
            if not len(xs) or not len(ys):
                continue
            normal = np.array(face["n"], dtype=float)
            facing = max(range(3), key=lambda a: abs(normal @ cube.axes[a]))
            view = {F: "frontal", L: "lateral", U: "dorsal"}[facing]
            a_axis, b_axis = VIEW_AXES[view]
            uv = np.array([v[1, 3:] - v[0, 3:], v[2, 3:] - v[0, 3:]]).T
            if abs(np.linalg.det(uv)) < 1e-9:
                continue
            edges = np.array([v[1, :3] - v[0, :3], v[2, :3] - v[0, :3]]).T
            gx, gy = np.meshgrid((xs + 0.5) / width, (ys + 0.5) / height)
            st = np.linalg.solve(uv, np.stack([gx.ravel() - v[0, 3], gy.ravel() - v[0, 4]]))
            points = v[0, :3][:, None] + edges @ st

            def cell(axis, reverse):
                t = (cube.axes[axis] @ points - cube.low[axis]) / cube.span[axis] if cube.span[axis] > 1e-6 \
                    else np.zeros(points.shape[1])
                if reverse:
                    t = 1 - t
                return np.clip((t * cube.n[axis] + 1e-6).astype(int), 0, cube.n[axis] - 1)

            columns = cell(a_axis, a_axis == F).reshape(gx.shape)
            rows = cell(b_axis, b_axis in (U, F)).reshape(gx.shape)
            pattern = paint(role, cube, view, biggest.centre)
            if translucent and role == "soft":                       # jelly: a continuous, see-through wall
                pattern = P.soft_outline(pattern.shape[1], pattern.shape[0], 120, 1)
            values = pattern[rows, columns]
            px, py = np.meshgrid(xs, ys)
            bone = values > 0
            pixel = np.zeros(values.shape + (4,), dtype=np.uint8)
            if flesh:
                empty = values == 0
                if translucent:
                    pixel[empty] = (HAZE[0], HAZE[0], HAZE[0], HAZE[1] * min(flesh, 4) // 4)
                else:
                    dots = empty & (BAYER[py % 4, px % 4] < flesh)
                    shade = np.clip(SOFT_GRAY + jitter[py, px], 0, 255).astype(np.uint8)
                    pixel[dots] = np.stack([shade, shade, shade, np.full_like(shade, 255)], axis=-1)[dots]
            gray = np.clip(values + jitter[py, px], 40, 255).astype(np.uint8)
            pixel[bone] = np.stack([gray, gray, gray, np.full_like(gray, 255)], axis=-1)[bone]
            region = np.ix_(ys, xs)
            keep = layer_mask[region] & (pixel[..., 3] == 0) & (role in ("none", "flesh"))
            if translucent and role == "soft":
                pixel[bone, 3] = 120
            image[region] = np.where(keep[..., None], image[region], pixel)
            layer_mask[region] = True
    return layer_mask


def render_creature(rel, spec, size):
    width, height = size
    image = np.zeros((height, width, 4), dtype=np.uint8)
    covered = np.zeros((height, width), dtype=bool)
    # current layouts first; older layouts only fill texels the current model never reads
    for generation, names in (("new", spec["new"]), ("old", spec["old"])):
        for name in names:
            layer = GEOMETRY[generation].get(name)
            if layer is None:
                raise SystemExit(f"{rel}: no {generation} model layer {name!r}")
            scratch = np.zeros_like(image)
            mask = draw_layer(scratch, covered, layer, spec, name in spec["translucent"], rel)
            fresh = mask & ~covered
            image[fresh] = scratch[fresh]
            covered |= mask
    return Image.fromarray(image, "RGBA")


def original(rel):
    data = subprocess.run(["git", "show", f"{SOURCE_COMMIT}:assets/minecraft/textures/entity/{rel}.png"],
                          cwd=ROOT, capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(data)).convert("RGBA")


SADDLE_LAYERS = {"horse": "horse#saddle", "donkey": "donkey#saddle", "mule": "mule#saddle",
                 "skeleton_horse": "skeleton_horse#saddle", "zombie_horse": "zombie_horse#saddle"}


def render_gear(rel, material):
    """Leather, cloth and scute barely absorb: a dotted outline. Metal fittings stay solid and bright."""
    source = np.array(original(rel))
    mask = source[..., 3] > 25
    height, width = mask.shape
    padded = np.pad(mask, 1)
    inner = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    y, x = np.mgrid[0:height, 0:width]
    edge = mask & ~inner
    gray, dots = {"saddle": (105, (x + y) % 2 == 0), "leather": (100, (x + y) % 2 == 0),
                  "cloth": (80, (x + y) % 3 == 0), "scute": (135, (x + y) % 2 == 0)}[material]
    draw = edge & dots
    if material == "scute":                                          # seams between the plates
        draw |= mask & ((x % 4 == 0) | (y % 4 == 0)) & ((x + y) % 2 == 0)
    image = np.zeros_like(source)
    image[draw] = (gray, gray, gray, 255)
    kind = re.search(r"equipment/(\w+)_saddle", rel)
    layer = GEOMETRY["new"].get(SADDLE_LAYERS.get(kind.group(1), "")) if kind else None
    for data in layer["cubes"] if layer else ():
        bit = data["p"].endswith("saddle_mouth")                     # the steel bit
        seat = data["p"].endswith("body/saddle")                     # carries the stirrup irons
        if not (bit or seat):
            continue
        for face in data["f"]:
            v = np.array(face["v"], dtype=float)
            if seat and abs(face["n"][0]) < 0.9:
                continue
            x0, x1 = int(round(v[:, 3].min() * width)), int(round(v[:, 3].max() * width))
            y0, y1 = int(round(v[:, 4].min() * height)), int(round(v[:, 4].max() * height))
            if x1 <= x0 or y1 <= y0:
                continue
            if bit:
                image[y0:y1, x0:x1] = (225, 225, 225, 255)
            else:
                iron = P.blank(y1 - y0, x1 - x0)
                cx, bottom = (x1 - x0) // 2, y1 - y0 - 1
                for r, c in ((bottom - 3, cx), (bottom - 2, cx - 1), (bottom - 2, cx + 1), (bottom - 1, cx - 1),
                             (bottom - 1, cx + 1), (bottom, cx - 1), (bottom, cx), (bottom, cx + 1)):
                    P.put(iron, r, c, 225)
                image[y0:y1, x0:x1][iron > 0] = (225, 225, 225, 255)
    return Image.fromarray(image, "RGBA")


def mob_textures():
    for path in sorted(ENTITY.rglob("*.png")):
        rel = path.relative_to(ENTITY).with_suffix("").as_posix()
        if rel.split("/")[0] not in NON_MOB_DIRS and rel not in NON_MOB_FILES:
            yield rel, path


def spec_for(rel):
    return next((spec for pattern, spec in RULES if re.fullmatch(pattern, rel)), None)


def main():
    textures = list(mob_textures())
    unknown = [rel for rel, _ in textures if spec_for(rel) is None]
    if unknown:
        raise SystemExit("textures without a rule:\n  " + "\n  ".join(unknown))
    counts = Counter()
    for rel, path in textures:
        spec = spec_for(rel)
        kind = spec["kind"]
        counts[(kind, spec["category"])] += 1
        if "--list" in sys.argv:
            print(f"{kind}\t{spec['category']}\t{rel}")
            continue
        if kind in ("keep", "skip"):
            continue
        with Image.open(path) as current:
            size = current.size
        if kind == "render":
            image = render_creature(rel, spec, size)
        elif kind == "clear":
            image = Image.new("RGBA", size, (0, 0, 0, 0))
        elif kind == "copy":
            image = original(spec["source"])
        else:
            image = render_gear(rel, spec["material"])
        if image.size != size:
            raise SystemExit(f"{rel}: size changed {size} -> {image.size}")
        image.save(path)
    for (kind, category), n in sorted(counts.items()):
        print(f"{kind:7} {category:26} {n}")
    written = sum(n for (kind, _), n in counts.items() if kind not in ("keep", "skip"))
    print(f"mob textures: {len(textures)}, rewritten: {written}")


if __name__ == "__main__":
    main()
