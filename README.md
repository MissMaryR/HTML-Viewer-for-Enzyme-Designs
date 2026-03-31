# RFDiffusion Loop Design Viewer — Build Notes

Interactive 3D viewer (`viewer_v3.html`) for RFDiffusion laccase loop designs with ESMFold trimer predictions, built using Molstar.

---

## Project Context

Laccase (trimeric multicopper oxidase) loop designs generated with RFDiffusion. The designed loop is inserted between residues 151 and 155 of the laccase sequence. Multiple linker configurations and loop lengths were tested:

- **Linker groups**: `linker_182-2-185`, `linker_183-1-185`, `linker_182-3-186`, `linker_183-2-186`
- **Loop sizes**: 12–30 aa inserts
- **Per loop**: 5 top RFDiff designs scored by LigandMPNN, each run through ESMFold as a trimer

---

## Folder Structure

```
RFDiff2/
  linker_182-2-185/
    loop14/
      aligned_outputs/
        aligned_combined.pdb    # up to 5 RFDiff designs aligned in PyMOL, exported as multi-MODEL PDB
      ESMFOLD/
        top_1.pdb … top_5.pdb  # ESMFold trimer predictions (chains A/B/C, unusual residue numbering)
        aligned_models/
          model_1.pdb … model_5.pdb  # chains B/C renumbered to 1-N, all aligned to chain A of model_1
      top_5_fa_files/
        top_1.fa … top_5.fa    # FASTA sequences: chain:chain:chain format (trimer)
    loop16/ …
  linker_183-1-185/ …
  viewer_v3.html                 # self-contained interactive viewer (Molstar)
  viewer_v3_build/               # this folder — build scripts and notes
```

---

## Viewer Features

- **Sidebar**: organized by linker group → loop size
- **RFDiff button** (click loop row): shows up to 5 aligned RFDiff designs using Molstar auto-preset
  - Cartoon for protein, ball-and-stick for ligand (4EP, chain Y), spacefill for Cu (chain X)
- **ESM button**: shows 5 aligned ESMFold trimer predictions (chains A, B, C)
  - Colored by secondary structure — Molstar computes SS automatically from coordinates
  - Model 1 at full opacity, models 2–5 at 20% opacity as overlays

---

## RFDiff Chain Structure

| Chain | Contents |
|-------|----------|
| A | designed protein (residues 1–273, loop at 152–151+N) |
| X | copper ion (Cu) |
| Y | 4EP ligand |

**Loop residue range**: for loop size N, the designed insert spans residues **152 to 151+N**.

---

## ESMFold Trimer Residue Numbering

ESMFold numbers residues sequentially across all chains in a multimer prediction:

| Chain | Residue range | Offset to renumber to 1 |
|-------|--------------|------------------------|
| A | 1–273 | — |
| B | 811–1083 | −810 |
| C | 1621–1893 | −1620 |

PyMOL renumbering: `cmd.alter("chain B", "resi = str(int(resi) - 810)")`

---

## Build Steps

### Step 1 — Align ESMFold trimers

**Script**: `scripts/align_esm_trimer.py`

For each loop's `ESMFOLD/` folder:
1. Loads each `top_N.pdb` in PyMOL
2. Renumbers chains B and C to start at 1
3. Aligns all 5 structures to `top_1` using chain A
4. Saves each as `ESMFOLD/aligned_models/model_N.pdb` with all 3 chains intact

```bash
PYMOL=/Users/mary/opt/anaconda3/bin/pymol

for esm_dir in linker_*/loop*/ESMFOLD; do
    $PYMOL -cq scripts/align_esm_trimer.py -- "$esm_dir" "$esm_dir/aligned_models" 2>/dev/null
done
```

### Step 2 — Build viewer_v3.html

**Script**: `scripts/build_v3.py`

First, download Molstar 5.7.0 (one time):
```bash
curl -L -o /tmp/molstar.js "https://cdn.jsdelivr.net/npm/molstar@5.7.0/build/viewer/molstar.js"
curl -L -o /tmp/molstar.css "https://cdn.jsdelivr.net/npm/molstar@5.7.0/build/viewer/molstar.css"
```

Then build:
```bash
python3 scripts/build_v3.py
```

What the script does:
1. Reads all `aligned_outputs/aligned_combined.pdb` files → `RFDIFF_DATA` JS object
2. Reads all `ESMFOLD/aligned_models/model_N.pdb` files → `ESM_DATA` JS object (arrays of PDB strings per loop)
3. Embeds Molstar JS + CSS inline
4. Generates sidebar from folder hierarchy (linker → loop)
5. Writes self-contained `viewer_v3.html` (~55 MB, no network required to view)

### Step 3 — Serve and view

Must be served over HTTP (not opened directly as `file://` due to WebGL):

```bash
cd /path/to/RFDiff2
python3 -m http.server 8767 --bind 127.0.0.1
# Open: http://127.0.0.1:8767/viewer_v3.html
```

---

## Dependencies

| Tool | Version | Use |
|------|---------|-----|
| PyMOL | (anaconda) | structure alignment |
| Python | 3.7+ | build scripts |
| Molstar | 5.7.0 | 3D viewer in browser |

---

## Files in This Folder

| File | Description |
|------|-------------|
| `README.md` | this file |
| `scripts/align_esm_trimer.py` | PyMOL script — align ESMFold trimers, renumber chains B/C |
| `scripts/build_v3.py` | generates `viewer_v3.html` from PDB data + Molstar |
