"""X-ray transmission physics (Beer-Lambert, polychromatic) with real NIST XCOM elemental data.

Imaging chain (all parameters documented, nothing keyword based):
  source   : tungsten-like bremsstrahlung, Kramers spectrum N(E) ~ (E0-E)/E, E0 = 100 keV (100 kVp)
  filter   : 2.5 mm aluminium (removes the soft end of the spectrum, like a real tube)
  object   : each pixel = one material (mass fractions, density g/cm3) with a path length t (cm)
             mixture rule: mu/rho = sum_i w_i (mu/rho)_i ; tau(E) = (mu/rho) * rho * t
  detector : energy-integrating, signal weight ~ E
  result   : transmitted fraction T = sum N E exp(-tau(E)) / sum N E ;  effective optical depth tau_eff = -ln T
Film display (windowing, as in radiography): brightness and opacity grow with log10(tau_eff) between two physical
anchors (see physics_render.py)."""
import json, pathlib
import numpy as np
DATA = json.loads(pathlib.Path(__file__).with_name("data").joinpath("nist_elements.json").read_text())
from materials import AMASS
Z_OF = dict(H=1, He=2, Li=3, Be=4, B=5, C=6, N=7, O=8, F=9, Ne=10, Na=11, Mg=12, Al=13, Si=14, P=15, S=16, Cl=17, Ar=18, K=19,
 Ca=20, Ti=22, V=23, Cr=24, Mn=25, Fe=26, Co=27, Ni=28, Cu=29, Zn=30, Ga=31, Ge=32, As=33, Se=34, Br=35, Rb=37, Sr=38, Y=39,
 Zr=40, Nb=41, Mo=42, Pd=46, Ag=47, Cd=48, Sn=50, Sb=51, Te=52, I=53, Cs=55, Ba=56, La=57, Ce=58, Nd=60, Eu=63, Gd=64, Ta=73,
 W=74, Re=75, Os=76, Ir=77, Pt=78, Au=79, Hg=80, Tl=81, Pb=82, Bi=83, Th=90, U=92)
E0_KEV = 100.0
EGRID = np.arange(10.0, E0_KEV, 2.0) + 1.0   # keV bin centres 11..99
_cache = {}

def mu_rho_element(sym, e_mev):
    """NIST mass attenuation coefficient (cm2/g) at e_mev, log-log interpolation, absorption edges respected."""
    key = (sym, round(float(e_mev), 6))
    if key in _cache: return _cache[key]
    t = np.array(DATA[str(Z_OF[sym])]["table"])
    e, mu = t[:, 0], t[:, 1]
    i = int(np.searchsorted(e, e_mev, side="right") - 1)  # last row with e<=E (post-edge value on edges)
    i = max(0, min(i, len(e) - 2))
    e1, e2, m1, m2 = e[i], e[i + 1], mu[i], mu[i + 1]
    if e2 == e1: v = m2
    else: v = float(np.exp(np.log(m1) + (np.log(e_mev) - np.log(e1)) * (np.log(m2) - np.log(m1)) / (np.log(e2) - np.log(e1))))
    _cache[key] = v
    return v

def mu_rho_material(fractions, e_mev):
    return sum(w * mu_rho_element(s, e_mev) for s, w in fractions.items())

def spectrum():
    """Kramers spectrum, 2.5 mm Al filtration, energy-integrating detector weighting. Returns (E_keV, weights)."""
    n = (E0_KEV - EGRID) / EGRID
    filt = np.exp(-np.array([mu_rho_element("Al", e / 1000) for e in EGRID]) * 2.70 * 0.25)
    w = n * filt * EGRID
    return EGRID, w / w.sum()
_E, _W = spectrum()
_MU_CACHE = {}

def tau_eff(material, thickness_cm):
    """Effective optical depth -ln(T) of `thickness_cm` of `material` ({density, mass_fractions}) in the polychromatic beam."""
    key = (id(material), round(thickness_cm, 6))
    if key in _MU_CACHE: return _MU_CACHE[key]
    mur = np.array([mu_rho_material(material["mass_fractions"], e / 1000) for e in _E])
    tau = mur * material["density"] * thickness_cm
    a = np.log(_W) - tau
    m = a.max()
    log_s = m + np.log(np.exp(a - m).sum())      # log sum w exp(-tau), stable for huge tau
    out = float(-log_s)                          # sum(w)=1 so log S0 = 0
    _MU_CACHE[key] = out
    return out
