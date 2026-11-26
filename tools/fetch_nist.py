"""Download NIST XCOM elemental mass attenuation coefficients (Z=1..92) -> tools/data/nist_elements.json
Source: https://physics.nist.gov/PhysRefData/XrayMassCoef/ElemTab/zNN.html (Hubbell & Seltzer, NISTIR 5632)."""
import re, json, subprocess, pathlib
out = {}
for z in range(1, 93):
    html = subprocess.run(["curl", "-sS", "-m", "30", f"https://physics.nist.gov/PhysRefData/XrayMassCoef/ElemTab/z{z:02d}.html"], capture_output=True, check=True).stdout.decode("latin1")
    pre = html[html.index("<PRE>"):html.index("</PRE>")]
    rows = []
    for ln in pre.splitlines():
        m = re.match(r"^\s*(?:[KLMN]\d?\s+)?([0-9.]+E[+-]\d+)\s+([0-9.]+E[+-]\d+)\s+([0-9.]+E[+-]\d+)", ln)
        if m: rows.append([float(m.group(1)), float(m.group(2)), float(m.group(3))])
    mt = re.search(r"<TITLE>.*?- (.*?)</TITLE>", html, re.S | re.I); sym = mt.group(1).strip() if mt else f"Z{z}"
    out[z] = {"name": sym, "table": rows}
    print(z, sym, len(rows), flush=True)
pathlib.Path("tools/data/nist_elements.json").write_text(json.dumps(out))
