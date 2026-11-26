"""Material database for the X-ray physics simulation.
Each material: density (g/cm3, effective/bulk as it exists in the object) and
composition as mass fractions per element (from a chemical formula or a dict).
Agents may add materials in tools/materials_extra/*.json:
  {"name": {"density": 2.7, "formula": "CaCO3"}}  or  {"name": {"density": 2.7, "mass_fractions": {"Si":0.5,"O":0.5}}}
"""
import json, pathlib, re
AMASS = dict(H=1.008, He=4.003, Li=6.94, Be=9.012, B=10.81, C=12.011, N=14.007, O=15.999, F=18.998, Ne=20.18,
 Na=22.99, Mg=24.305, Al=26.982, Si=28.086, P=30.974, S=32.06, Cl=35.45, Ar=39.948, K=39.098, Ca=40.078,
 Ti=47.867, V=50.942, Cr=51.996, Mn=54.938, Fe=55.845, Co=58.933, Ni=58.693, Cu=63.546, Zn=65.38, As=74.922,
 Br=79.904, Sr=87.62, Zr=91.224, Mo=95.95, Ag=107.868, Cd=112.41, Sn=118.71, Sb=121.76, I=126.904, Ba=137.327,
 La=138.905, Ce=140.116, Nd=144.24, W=183.84, Os=190.23, Ir=192.217, Pt=195.084, Au=196.967, Hg=200.59,
 Pb=207.2, Bi=208.98, U=238.029, Te=127.6, Se=78.971, Rb=85.468, Y=88.906, Nb=92.906, Pd=106.42, Cs=132.905,
 Ta=180.948, Re=186.207, Tl=204.38, Th=232.038, Ga=69.723, Ge=72.63, Li_=6.94, Gd=157.25, Eu=151.964)
_TOK = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)|(\()|(\))(\d*)")

def parse_formula(f):
    stack = [{}]
    for m in _TOK.finditer(f):
        el, n, op, cl, cn = m.groups()
        if el:
            stack[-1][el] = stack[-1].get(el, 0) + float(n or 1)
        elif op:
            stack.append({})
        elif cl:
            d = stack.pop(); k = float(cn or 1)
            for e, v in d.items(): stack[-1][e] = stack[-1].get(e, 0) + v * k
    atoms = stack[0]
    mass = {e: v * AMASS[e] for e, v in atoms.items()}
    tot = sum(mass.values())
    return {e: m / tot for e, m in mass.items()}

def M(density, formula=None, fr=None):
    comp = parse_formula(formula) if formula else dict(fr)
    s = sum(comp.values()); comp = {e: v / s for e, v in comp.items()}
    return {"density": density, "mass_fractions": comp}

_cellulose = "C6H10O5"
MATERIALS = {
 "vacuum": M(1e-6, "H"), "air": M(0.0012, fr=dict(N=.755, O=.232, Ar=.013)),
 "water": M(1.0, "H2O"), "ice": M(0.917, "H2O"), "snow_packed": M(0.3, "H2O"), "snow_powder": M(0.08, "H2O"),
 "steam": M(0.0006, "H2O"), "saltwater": M(1.025, fr=dict(H=.108, O=.857, Na=.011, Cl=.019, Mg=.0013, S=.0009)),
 "granite": M(2.65, fr=dict(O=.485, Si=.34, Al=.08, K=.035, Na=.027, Ca=.01, Fe=.01, Mg=.003)),
 "stone": M(2.7, fr=dict(O=.485, Si=.34, Al=.08, K=.03, Na=.025, Ca=.02, Fe=.015, Mg=.005)),
 "andesite": M(2.7, fr=dict(O=.47, Si=.28, Al=.09, Ca=.05, Na=.03, Fe=.05, Mg=.02, K=.01)),
 "diorite": M(2.8, fr=dict(O=.46, Si=.27, Al=.09, Ca=.06, Na=.03, Fe=.06, Mg=.02, K=.01)),
 "basalt": M(3.0, fr=dict(O=.44, Si=.23, Al=.08, Ca=.07, Fe=.09, Mg=.04, Na=.02, Ti=.01, K=.005)),
 "slate": M(2.8, fr=dict(O=.48, Si=.28, Al=.10, K=.03, Fe=.05, Mg=.02, Na=.01, C=.01)),
 "obsidian": M(2.4, fr=dict(O=.49, Si=.34, Al=.07, Na=.04, K=.04, Fe=.02)),
 "tuff": M(2.0, fr=dict(O=.49, Si=.32, Al=.08, K=.03, Na=.03, Ca=.02, Fe=.03)),
 "limestone": M(2.7, "CaCO3"), "calcite": M(2.71, "CaCO3"), "dolomite": M(2.85, "CaMg(CO3)2"), "chalk": M(2.0, "CaCO3"),
 "gypsum": M(2.3, "CaSO4(H2O)2"), "sandstone": M(2.2, "SiO2"), "quartz": M(2.65, "SiO2"), "sand": M(1.6, "SiO2"),
 "gravel": M(1.7, "SiO2"), "clay": M(1.8, "Al2Si2O5(OH)4"), "mud": M(1.7, fr=dict(O=.55, Si=.2, Al=.06, H=.06, Fe=.03, C=.05, Ca=.02)),
 "soil": M(1.5, fr=dict(O=.5, Si=.27, Al=.07, Fe=.03, C=.03, H=.02, Ca=.02, K=.02, Mg=.01, Na=.01)),
 "humus": M(1.0, fr=dict(C=.5, O=.4, H=.06, N=.03, Si=.01)),
 "brick": M(1.9, fr=dict(O=.5, Si=.25, Al=.1, Fe=.06, Ca=.04, K=.03, Mg=.01, Na=.01)),
 "terracotta": M(1.9, fr=dict(O=.5, Si=.25, Al=.1, Fe=.06, Ca=.04, K=.03, Mg=.01, Na=.01)),
 "concrete": M(2.3, fr=dict(O=.53, Si=.34, Ca=.044, Al=.034, Na=.016, Fe=.014, K=.013, H=.01)),
 "netherrack": M(2.5, fr=dict(O=.46, Si=.2, Fe=.15, Mg=.08, Al=.05, Ca=.03, S=.03)),
 "glass": M(2.5, fr=dict(O=.48, Si=.34, Na=.1, Ca=.07, Mg=.01)),
 "ceramic_glaze": M(2.4, fr=dict(O=.5, Si=.3, Al=.1, Na=.05, Ca=.05)),
 "amethyst": M(2.65, "SiO2"), "emerald": M(2.7, "Be3Al2Si6O18"),
 "lapis_lazuli": M(2.8, fr=dict(O=.4, Si=.17, Al=.15, Na=.1, Ca=.08, S=.08, Cl=.01, Fe=.01)),
 "diamond": M(3.51, "C"), "graphite": M(2.2, "C"), "coal": M(1.4, fr=dict(C=.8, O=.1, H=.05, N=.01, S=.01, Si=.03)), "charcoal": M(0.4, "C"),
 "iron": M(7.87, "Fe"), "steel": M(7.85, fr=dict(Fe=.985, C=.01, Mn=.005)), "stainless": M(7.9, fr=dict(Fe=.7, Cr=.18, Ni=.08, Mn=.02, C=.02)),
 "iron_oxide": M(5.2, "Fe2O3"), "hematite": M(5.26, "Fe2O3"), "magnetite": M(5.17, "Fe3O4"), "pyrite": M(5.0, "FeS2"),
 "iron_ore_rock": M(3.8, fr=dict(Fe=.35, O=.35, Si=.15, Al=.04, Ca=.03, Mg=.03, S=.01)),
 "copper": M(8.96, "Cu"), "malachite": M(3.9, "Cu2CO3(OH)2"), "copper_ore_rock": M(3.2, fr=dict(O=.45, Si=.25, Cu=.1, Fe=.08, Al=.07, S=.05)),
 "bronze": M(8.8, fr=dict(Cu=.88, Sn=.12)), "brass": M(8.5, fr=dict(Cu=.7, Zn=.3)),
 "gold": M(19.3, "Au"), "silver": M(10.49, "Ag"), "lead": M(11.34, "Pb"), "tin": M(7.31, "Sn"), "zinc": M(7.14, "Zn"),
 "aluminum": M(2.7, "Al"), "titanium": M(4.51, "Ti"), "nickel": M(8.9, "Ni"), "chromium": M(7.19, "Cr"), "platinum": M(21.45, "Pt"),
 "tungsten": M(19.3, "W"), "tungsten_carbide": M(15.6, "WC"), "scheelite": M(6.1, "CaWO4"), "osmium": M(22.6, "Os"),
 "uranium": M(19.1, "U"), "cinnabar": M(8.1, "HgS"), "mercury": M(13.5, "Hg"), "galena": M(7.5, "PbS"),
 "netherite": M(14.0, fr=dict(W=.5, Au=.25, Fe=.15, C=.1)), "ancient_debris": M(10.0, fr=dict(W=.55, Ca=.05, O=.2, Fe=.1, Au=.05, Si=.05)),
 "redstone_dust": M(5.0, "Fe2O3"), "glowstone": M(2.3, "CaSO4"), "phosphor": M(3.6, "Zn2SiO4"), "sulfur": M(2.07, "S"),
 "wood_oak": M(0.75, _cellulose), "wood_soft": M(0.45, _cellulose), "wood_dark": M(0.85, _cellulose), "planks": M(0.65, _cellulose),
 "bamboo": M(0.6, _cellulose), "paper": M(0.8, _cellulose), "textile": M(0.3, _cellulose), "wool": M(0.25, fr=dict(C=.5, O=.22, N=.16, H=.065, S=.04)),
 "foliage": M(0.15, fr=dict(C=.45, O=.4, H=.06, N=.03, Ca=.02, K=.02, Mg=.01, P=.01)), "grass": M(0.15, fr=dict(C=.45, O=.4, H=.06, N=.03, Ca=.02, K=.02, Mg=.01, P=.01)),
 "plant_tissue": M(0.7, fr=dict(O=.6, C=.28, H=.09, N=.02, K=.01)), "fruit": M(0.8, fr=dict(O=.84, C=.1, H=.1, K=.005)), "vegetable": M(0.9, fr=dict(O=.85, C=.09, H=.1, N=.005, K=.004)),
 "fungus": M(0.5, fr=dict(O=.55, C=.35, H=.07, N=.03)), "moss": M(0.15, fr=dict(C=.45, O=.4, H=.06, N=.03, Ca=.02, K=.02, Mg=.01, P=.01)),
 "cactus": M(0.6, fr=dict(O=.8, C=.12, H=.1, Ca=.01)), "sponge": M(0.12, _cellulose), "straw": M(0.15, _cellulose),
 "seed_grain": M(0.8, fr=dict(C=.45, O=.45, H=.065, N=.025, P=.005)), "starch": M(0.6, _cellulose), "bread": M(0.35, _cellulose), "sugar": M(1.5, "C12H22O11"),
 "honey": M(1.4, "C6H12O6"), "wax": M(0.96, "C31H64"), "chocolate": M(1.2, fr=dict(C=.55, O=.3, H=.08, N=.03, Ca=.01, Mg=.01)),
 "soft_tissue": M(1.06, fr=dict(H=.102, C=.143, N=.034, O=.708, Na=.002, P=.003, S=.003, Cl=.002, K=.003)),
 "muscle": M(1.05, fr=dict(H=.102, C=.143, N=.034, O=.710, Na=.001, P=.002, S=.003, K=.004)),
 "fat": M(0.95, fr=dict(H=.114, C=.598, N=.007, O=.278, Na=.001, S=.001, Cl=.001)),
 "bone": M(1.85, fr=dict(H=.034, C=.155, N=.042, O=.435, Na=.001, Mg=.002, P=.103, S=.003, Ca=.225)),
 "tooth_enamel": M(2.9, "Ca5(PO4)3OH"), "hydroxyapatite": M(3.16, "Ca5(PO4)3OH"), "blood": M(1.06, fr=dict(H=.102, C=.11, N=.033, O=.745, Na=.001, Fe=.001, Cl=.003)),
 "leather": M(0.9, fr=dict(C=.5, O=.25, N=.17, H=.065, S=.01)), "keratin": M(0.2, fr=dict(C=.5, O=.22, N=.17, H=.065, S=.03)),
 "feather": M(0.1, fr=dict(C=.5, O=.22, N=.17, H=.065, S=.03)), "silk": M(0.03, fr=dict(C=.45, O=.3, N=.18, H=.06)), "slime": M(1.0, "H2O"),
 "organic_gel": M(1.0, fr=dict(H=.1, O=.8, C=.09, N=.01)), "egg": M(1.03, fr=dict(O=.75, C=.12, H=.1, N=.02, Ca=.01)), "shell_chitin": M(1.4, "C8H13O5N"),
 "plastic": M(0.95, "C2H4"), "rubber": M(1.1, "C5H8"), "pvc": M(1.4, "C2H3Cl"), "tnt": M(1.65, "C7H5N3O6"), "gunpowder": M(1.7, fr=dict(K=.7 * .4, N=.1, S=.1, C=.15, O=.4)),
 "lava": M(2.6, fr=dict(O=.44, Si=.23, Al=.08, Ca=.07, Fe=.09, Mg=.04, Na=.02, Ti=.01)), "magma_rock": M(2.8, fr=dict(O=.44, Si=.23, Al=.08, Ca=.07, Fe=.09, Mg=.04, Na=.02, Ti=.01)),
 "dye_pigment": M(1.3, fr=dict(C=.6, O=.2, H=.06, N=.1, Ti=.04)), "ink": M(1.0, fr=dict(H=.1, O=.8, C=.1)), "potion_liquid": M(1.02, "H2O"),
 "fire": M(0.0003, "H"), "smoke": M(0.001, fr=dict(C=.5, O=.5)), "plasma_particle": M(0.0005, "H"),
 "sculk": M(1.0, fr=dict(H=.1, C=.14, N=.03, O=.7, P=.01, S=.01, Ca=.01)), "prismarine": M(2.2, fr=dict(O=.55, Si=.2, Mg=.1, Ca=.05, Al=.05, H=.05)),
 "chorus_flesh": M(0.7, fr=dict(O=.6, C=.28, H=.09, N=.02, K=.01)), "end_stone": M(1.9, fr=dict(O=.5, Si=.3, Ca=.1, Al=.05, Mg=.05)),
 "purpur": M(2.2, fr=dict(O=.5, Si=.25, Ca=.1, Mg=.05, Mn=.01, Al=.09)),
}
# bedrock is fictional: modelled as a dense mafic/ultramafic rock
MATERIALS["bedrock"] = M(3.3, fr=dict(O=.42, Si=.2, Fe=.12, Mg=.12, Al=.08, Ca=.06))

def load_all():
    mats = dict(MATERIALS)
    for f in sorted(pathlib.Path(__file__).with_name("materials_extra").glob("*.json")):
        for k, v in json.loads(f.read_text()).items():
            mats[k] = M(v["density"], v.get("formula"), v.get("mass_fractions"))
    return mats
