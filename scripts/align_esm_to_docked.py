#!/usr/bin/env python3
"""
align_esm_to_docked.py
======================
For every loop folder that contains both:
  - ESMFOLD/top_1.pdb   (ESMFold best prediction, any number of chains)
  - docked.pdb          (RFDiffusion design docked with ligand; chain A = protein,
                         additional chains = cofactors / small molecules)

This script:
  1. Aligns ESM chain A onto docked chain A (Cα atoms) using PyMOL.
  2. Copies any non-protein chains from docked.pdb into the aligned ESM object.
  3. Saves the result as ESMFOLD/esm_with_ligand.pdb.

The output gives a rough visual of where the ligand would sit relative to the
ESMFold prediction, useful for structure viewer overlays.

Usage
-----
Edit the two variables at the top of this file:
  DESIGNS_ROOT  – path to the top-level directory that contains your linker/loop
                  folder hierarchy  (e.g. /path/to/RFDiffusion_designs)
  PYMOL         – path to the PyMOL executable
  DOCKED_NAME   – filename of the docked reference PDB inside each loop folder
                  (default: "docked.pdb")

Then run:
  python3 align_esm_to_docked.py

Folder layout expected
----------------------
DESIGNS_ROOT/
  <linker_A>/
    <loop_1>/
      docked.pdb                  ← reference: chain A protein + ligand chains
      ESMFOLD/
        top_1.pdb                 ← ESMFold prediction (may be a trimer / monomer)
    <loop_2>/
      ...
  <linker_B>/
    ...

Output
------
DESIGNS_ROOT/<linker>/<loop>/ESMFOLD/esm_with_ligand.pdb
  Contains: aligned ESMFold structure (all chains) + non-protein chains from docked.pdb
"""

import os
import glob
import re

# ── USER SETTINGS ──────────────────────────────────────────────────────────────
DESIGNS_ROOT = "/path/to/your/designs"          # top-level designs directory
PYMOL        = "/path/to/pymol"                 # PyMOL executable
DOCKED_NAME  = "docked.pdb"                     # docked reference filename
# ───────────────────────────────────────────────────────────────────────────────

# Detect which chains in docked.pdb are non-protein (HETATM-only chains)
def get_hetatm_chains(pdb_path):
    """Return set of chain IDs that appear only in HETATM records (ligands/cofactors)."""
    atom_chains   = set()
    hetatm_chains = set()
    with open(pdb_path) as f:
        for line in f:
            if line.startswith("ATOM  "):
                atom_chains.add(line[21])
            elif line.startswith("HETATM"):
                hetatm_chains.add(line[21])
    return hetatm_chains - atom_chains   # chains with no backbone ATOM records


def collect_jobs():
    jobs = []
    for linker_dir in sorted(glob.glob(os.path.join(DESIGNS_ROOT, "*"))):
        if not os.path.isdir(linker_dir):
            continue
        for loop_dir in sorted(glob.glob(os.path.join(linker_dir, "*"))):
            if not os.path.isdir(loop_dir):
                continue
            esm1   = os.path.join(loop_dir, "ESMFOLD", "top_1.pdb")
            docked = os.path.join(loop_dir, DOCKED_NAME)
            out    = os.path.join(loop_dir, "ESMFOLD", "esm_with_ligand.pdb")
            if os.path.exists(esm1) and os.path.exists(docked):
                jobs.append((loop_dir, esm1, docked, out))
    return jobs


def main():
    jobs = collect_jobs()
    print(f"Found {len(jobs)} loop folders with top_1.pdb + {DOCKED_NAME}")
    if not jobs:
        print("Nothing to do — check DESIGNS_ROOT and DOCKED_NAME.")
        return

    # Build a single PyMOL script that processes every job in one session
    pymol_script = "/tmp/run_esm_align.pml"
    with open(pymol_script, "w") as f:
        for i, (loop_dir, esm1, docked, out) in enumerate(jobs):
            tag        = f"j{i}"
            esm_obj    = f"esm_{tag}"
            docked_obj = f"docked_{tag}"
            merged_obj = f"merged_{tag}"

            # Identify non-protein chains to carry over from docked
            lig_chains = get_hetatm_chains(docked)
            if lig_chains:
                lig_sel = " or ".join(
                    f"({docked_obj} and chain {c})" for c in sorted(lig_chains)
                )
                merged_sel = f"{esm_obj} or {lig_sel}"
            else:
                merged_sel = esm_obj

            f.write(f"load {esm1}, {esm_obj}\n")
            f.write(f"load {docked}, {docked_obj}\n")
            f.write(f"align {esm_obj} and chain A and name CA, "
                    f"{docked_obj} and chain A and name CA\n")
            f.write(f"create {merged_obj}, {merged_sel}\n")
            f.write(f"save {out}, {merged_obj}\n")
            f.write(f"delete {esm_obj}\n")
            f.write(f"delete {docked_obj}\n")
            f.write(f"delete {merged_obj}\n")

        f.write("quit\n")

    print(f"Running PyMOL on {len(jobs)} alignments…")
    os.system(f"{PYMOL} -cq {pymol_script}")

    ok = sum(1 for _, _, _, out in jobs if os.path.exists(out))
    print(f"\nDone: {ok}/{len(jobs)} esm_with_ligand.pdb files written")
    for _, _, _, out in jobs:
        status = "OK" if os.path.exists(out) else "MISSING"
        print(f"  [{status}]  {out}")


if __name__ == "__main__":
    main()
