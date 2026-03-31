"""
Align ESMFold trimer PDBs, renumber chains B/C to 1-N, save each as model_N.pdb
with all 3 chains (A, B, C) intact.
"""
import sys, os, glob
from pymol import cmd

esm_dir = sys.argv[1]
out_dir  = sys.argv[2]
os.makedirs(out_dir, exist_ok=True)

files = sorted(f for f in glob.glob(os.path.join(esm_dir, "*.pdb"))
               if os.path.basename(f) not in ("esm_combined.pdb",)
               and "model_" not in os.path.basename(f))[:5]

if not files:
    print("No files found in", esm_dir)
    sys.exit(0)

names = []
for f in files:
    name = os.path.splitext(os.path.basename(f))[0]
    name = name.replace("-","_").replace(".","_").replace("+","_")
    cmd.load(f, name)

    # Renumber chain B: 811->1, 812->2, ...
    # Find offset for chain B
    stored_b = []
    cmd.iterate(f"{name} and chain B", "stored_b.append(int(resi))", space={"stored_b": stored_b})
    if stored_b:
        offset_b = min(stored_b) - 1
        cmd.alter(f"{name} and chain B", f"resi = str(int(resi) - {offset_b})")

    # Renumber chain C: 1621->1, 1622->2, ...
    stored_c = []
    cmd.iterate(f"{name} and chain C", "stored_c.append(int(resi))", space={"stored_c": stored_c})
    if stored_c:
        offset_c = min(stored_c) - 1
        cmd.alter(f"{name} and chain C", f"resi = str(int(resi) - {offset_c})")

    cmd.sort(name)
    names.append(name)

# Align all to first structure using chain A
ref = names[0]
for n in names[1:]:
    cmd.align(f"{n} and chain A", f"{ref} and chain A")

# Save each model with all chains
for i, n in enumerate(names, 1):
    out = os.path.join(out_dir, f"model_{i}.pdb")
    cmd.save(out, n)
    print(f"  Saved {out}")

cmd.quit()
