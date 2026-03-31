#!/usr/bin/env python3
"""
build_viewer.py
===============
Builds a self-contained HTML structure viewer combining:
  - RFDiffusion multi-model designs  (aligned_combined.pdb per loop)
  - ESMFold top-1 prediction aligned to the docked reference with ligand
    (ESMFOLD/esm_with_ligand.pdb, falls back to ESMFOLD/top_1.pdb)

The output is a single .html file (~30–60 MB) with Molstar 5.7.0 embedded
inline — no server-side dependencies beyond a basic HTTP server to serve it.

Usage
-----
Edit the USER SETTINGS block below, then run:
  python3 build_viewer.py

The script expects the Molstar bundle files to be pre-downloaded:
  /tmp/molstar.js   (from cdn.jsdelivr.net/npm/molstar@5.7.0/build/viewer/molstar.js)
  /tmp/molstar.css  (from cdn.jsdelivr.net/npm/molstar@5.7.0/build/viewer/molstar.css)

Download with:
  curl -L https://cdn.jsdelivr.net/npm/molstar@5.7.0/build/viewer/molstar.js  -o /tmp/molstar.js
  curl -L https://cdn.jsdelivr.net/npm/molstar@5.7.0/build/viewer/molstar.css -o /tmp/molstar.css

Folder layout expected
----------------------
DESIGNS_ROOT/
  <linker_A>/
    <loop_1>/
      aligned_outputs/
        aligned_combined.pdb      ← multi-MODEL PDB of aligned RFDiff designs
      ESMFOLD/
        esm_with_ligand.pdb       ← ESMFold top-1 aligned + ligand (from align_esm_to_docked.py)
        top_1.pdb                 ← fallback if esm_with_ligand.pdb not present
    <loop_2>/
      ...
  <linker_B>/
    ...

LINKER_INFO dict
----------------
Add an entry for each linker folder:
  "folder_name": ("Display Name", "contig suffix (after loop segment)", "contig prefix (before loop)")

Serve the output
----------------
  python3 -m http.server 8080 --bind 127.0.0.1
  open http://127.0.0.1:8080/viewer.html
"""

import os
import json
import glob
import re

# ── USER SETTINGS ──────────────────────────────────────────────────────────────
DESIGNS_ROOT  = "/path/to/your/designs"    # top-level designs directory
OUTPUT_HTML   = "/path/to/output/viewer.html"
MOLSTAR_JS    = "/tmp/molstar.js"
MOLSTAR_CSS   = "/tmp/molstar.css"

# Linker display info: folder_name -> (display badge, contig suffix, contig prefix)
# Contig prefix = scaffold segment before the designed loop
# Contig suffix = scaffold segment(s) after the designed loop (including any fixed linker)
# Example:  "linker_A_2_B": ("Linker A-2-B", "A151-A / 2aa / B-262", "A1-151")
LINKER_INFO = {
    # "folder_name": ("Display Name", "contig suffix", "contig prefix"),
}

# Display order for linker sections in the sidebar (list of folder names)
LINKER_ORDER = list(LINKER_INFO.keys())
# ───────────────────────────────────────────────────────────────────────────────


def parse_loop_n(name):
    m = re.match(r'loop(\d+)', name)
    return int(m.group(1)) if m else None


def read(path):
    with open(path) as f:
        return f.read()


def esc(s):
    """Escape PDB string for embedding in a JS template literal."""
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")


def main():
    print("Loading Molstar bundle…")
    molstar_js  = read(MOLSTAR_JS)
    molstar_css = read(MOLSTAR_CSS)
    print(f"  JS: {len(molstar_js):,} chars   CSS: {len(molstar_css):,} chars")

    print("Reading PDB data…")
    rfdiff_data = {}   # key -> aligned_combined.pdb string
    esm_data    = {}   # key -> esm_with_ligand.pdb (or top_1.pdb) string

    for linker_dir in sorted(glob.glob(os.path.join(DESIGNS_ROOT, "*"))):
        if not os.path.isdir(linker_dir):
            continue
        lid = os.path.basename(linker_dir)
        for loop_dir in sorted(glob.glob(os.path.join(linker_dir, "loop*"))):
            n = parse_loop_n(os.path.basename(loop_dir))
            if n is None:
                continue
            key = f"{lid}_loop{n}"

            # RFDiffusion multi-model PDB
            combined = os.path.join(loop_dir, "aligned_outputs", "aligned_combined.pdb")
            if os.path.exists(combined):
                rfdiff_data[key] = read(combined)

            # ESMFold structure (with ligand preferred)
            esm_lig = os.path.join(loop_dir, "ESMFOLD", "esm_with_ligand.pdb")
            esm_top = os.path.join(loop_dir, "ESMFOLD", "top_1.pdb")
            if os.path.exists(esm_lig):
                esm_data[key] = read(esm_lig)
            elif os.path.exists(esm_top):
                esm_data[key] = read(esm_top)

    print(f"  RFDiff entries: {len(rfdiff_data)}   ESM entries: {len(esm_data)}")

    # Build sidebar groups
    groups = []
    order = LINKER_ORDER if LINKER_ORDER else sorted(
        set(k.rsplit("_loop", 1)[0] for k in set(rfdiff_data) | set(esm_data))
    )
    for lid in order:
        linker_dir = os.path.join(DESIGNS_ROOT, lid)
        if not os.path.isdir(linker_dir):
            continue
        loops = []
        for loop_dir in sorted(
            glob.glob(os.path.join(linker_dir, "loop*")),
            key=lambda p: parse_loop_n(os.path.basename(p)) or 0,
        ):
            n = parse_loop_n(os.path.basename(loop_dir))
            if n is None:
                continue
            key = f"{lid}_loop{n}"
            has_rf  = key in rfdiff_data
            has_esm = key in esm_data
            if has_rf or has_esm:
                loops.append({"n": n, "hasRFDiff": has_rf, "hasEsm": has_esm})
        if loops:
            badge, contig, prefix = LINKER_INFO.get(lid, (lid, "", "A1-?"))
            groups.append({
                "id": lid, "badge": badge,
                "contig": contig, "prefix": prefix,
                "loops": loops,
            })

    # Serialize data for embedding
    rfdiff_js = "const RFDIFF_DATA = {\n"
    for k, v in rfdiff_data.items():
        rfdiff_js += f'  "{k}": `{esc(v)}`,\n'
    rfdiff_js += "};"

    esm_js = "const ESM_DATA = {\n"
    for k, v in esm_data.items():
        esm_js += f'  "{k}": `{esc(v)}`,\n'
    esm_js += "};"

    groups_js = f"const GROUPS = {json.dumps(groups)};"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RFDiffusion + ESMFold Viewer</title>
<style>{molstar_css}</style>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #111827; color: #e5e7eb; display: flex; height: 100vh; overflow: hidden; }}
#sidebar {{ width: 270px; min-width: 270px; background: #1f2937;
           border-right: 1px solid #374151; display: flex; flex-direction: column; overflow: hidden; }}
#sidebar-header {{ padding: 14px 16px 10px; border-bottom: 1px solid #374151; }}
#sidebar-header h1 {{ font-size: 13px; font-weight: 700; color: #f9fafb; letter-spacing: .03em; }}
#sidebar-header p  {{ font-size: 11px; color: #9ca3af; margin-top: 3px; }}
#list {{ flex: 1; overflow-y: auto; padding: 8px 0; }}
#list::-webkit-scrollbar {{ width: 6px; }}
#list::-webkit-scrollbar-thumb {{ background: #374151; border-radius: 3px; }}
.section-label {{ padding: 10px 14px 3px; font-size: 10px; font-weight: 700;
                  text-transform: uppercase; letter-spacing: .08em; color: #6b7280; }}
.contig-label  {{ padding: 2px 14px 6px; font-size: 9px; color: #4b5563; font-family: monospace; }}
.loop-row {{ display: flex; align-items: center; margin: 1px 8px;
             border-radius: 6px; overflow: hidden; }}
.loop-main {{ flex: 1; padding: 7px 10px; cursor: pointer; font-size: 12px;
              border-radius: 6px 0 0 6px; transition: background .15s; color: #d1d5db; }}
.loop-main.solo {{ border-radius: 6px; }}
.loop-main:hover  {{ background: #374151; }}
.loop-main.active {{ background: #1d4ed8; color: #fff; }}
.esm-btn {{ padding: 7px 9px; background: #374151; cursor: pointer; font-size: 10px;
            font-weight: 700; color: #9ca3af; border-left: 1px solid #4b5563;
            border-radius: 0 6px 6px 0; transition: background .15s; white-space: nowrap; }}
.esm-btn:hover  {{ background: #4b5563; color: #e5e7eb; }}
.esm-btn.active {{ background: #065f46; color: #6ee7b7; }}
.pill {{ display: inline-block; background: #374151; color: #9ca3af;
         border-radius: 4px; padding: 1px 5px; font-size: 10px; margin-right: 5px; }}
.loop-main.active .pill {{ background: #1e40af; color: #93c5fd; }}
#main {{ flex: 1; display: flex; flex-direction: column; }}
#info-bar {{ padding: 8px 16px; background: #1f2937; border-bottom: 1px solid #374151;
             display: flex; align-items: baseline; gap: 10px; }}
#info-title {{ font-size: 13px; font-weight: 600; color: #f9fafb; }}
#info-sub   {{ font-size: 11px; color: #6b7280; }}
#viewer-wrap {{ flex: 1; position: relative; background: #0d1117; }}
#molstar-container {{ position: absolute; inset: 0; }}
#placeholder {{ position: absolute; inset: 0; display: flex; align-items: center;
                justify-content: center; color: #4b5563; font-size: 14px; pointer-events: none; }}
</style>
</head>
<body>
<div id="sidebar">
  <div id="sidebar-header">
    <h1>RFDiffusion Designs</h1>
    <p>Loop &amp; Linker Viewer</p>
  </div>
  <div id="list"></div>
</div>
<div id="main">
  <div id="info-bar">
    <span id="info-title">RFDiffusion Loop Viewer</span>
    <span id="info-sub"></span>
  </div>
  <div id="viewer-wrap">
    <div id="molstar-container"></div>
    <div id="placeholder">&larr; Select a structure to view</div>
  </div>
</div>
<script>{molstar_js}</script>
<script>
{rfdiff_js}
{esm_js}
{groups_js}

let viewer = null;
let activeMain = null;
let activeEsmBtn = null;

async function initViewer() {{
  viewer = await molstar.Viewer.create('molstar-container', {{
    layoutIsExpanded: false,
    layoutShowControls: false,
    layoutShowRemoteState: false,
    layoutShowSequence: false,
    layoutShowLog: false,
    layoutShowLeftPanel: false,
    viewportShowExpand: true,
    viewportShowSelectionMode: false,
    viewportShowAnimation: false,
    pdbProvider: 'rcsb',
    emdbProvider: 'rcsb',
  }});
}}

async function loadRFDiff(mainBtn, key, label, contig) {{
  if (activeMain) activeMain.classList.remove('active');
  if (activeEsmBtn) {{ activeEsmBtn.classList.remove('active'); activeEsmBtn = null; }}
  mainBtn.classList.add('active');
  activeMain = mainBtn;
  document.getElementById('info-title').textContent = label;
  document.getElementById('info-sub').textContent = contig;
  document.getElementById('placeholder').style.display = 'none';
  await viewer.plugin.clear();
  await viewer.loadStructureFromData(RFDIFF_DATA[key], 'pdb', false, {{ label: key }});
  viewer.plugin.managers.camera.reset();
}}

async function loadESM(esmBtn, key, label) {{
  if (activeEsmBtn) activeEsmBtn.classList.remove('active');
  esmBtn.classList.add('active');
  activeEsmBtn = esmBtn;
  document.getElementById('info-title').textContent = label + ' \u2014 ESMFold';
  document.getElementById('info-sub').textContent = 'Top-1 prediction + docked ligand';
  document.getElementById('placeholder').style.display = 'none';
  await viewer.plugin.clear();
  await viewer.loadStructureFromData(ESM_DATA[key], 'pdb', false, {{ label: key + '_esm' }});
  viewer.plugin.managers.camera.reset();
}}

initViewer().then(() => {{
  const list = document.getElementById('list');
  GROUPS.forEach(group => {{
    const sec = document.createElement('div');
    sec.className = 'section-label';
    sec.textContent = group.badge;
    list.appendChild(sec);

    const contigEl = document.createElement('div');
    contigEl.className = 'contig-label';
    contigEl.textContent = '[' + group.prefix + '/N-N/' + group.contig + ']';
    list.appendChild(contigEl);

    group.loops.forEach(loop => {{
      const n      = loop.n;
      const key    = group.id + '_loop' + n;
      const label  = group.badge + ' \u2014 Loop ' + n + ' aa';
      const contig = '[' + group.prefix + '/' + n + '-' + n + '/' + group.contig + ']';

      const row = document.createElement('div');
      row.className = 'loop-row';

      const hasBoth = loop.hasRFDiff && loop.hasEsm;
      const mainBtn = document.createElement('div');
      mainBtn.className = 'loop-main' + (hasBoth ? '' : ' solo');
      mainBtn.innerHTML = '<span class="pill">' + n + ' aa</span>Loop ' + n;

      if (loop.hasRFDiff) {{
        mainBtn.addEventListener('click', () => loadRFDiff(mainBtn, key, label, contig));
      }} else {{
        mainBtn.style.color = '#6ee7b7';
        mainBtn.addEventListener('click', () => loadESM(mainBtn, key, label));
      }}
      row.appendChild(mainBtn);

      if (hasBoth) {{
        const esmBtn = document.createElement('div');
        esmBtn.className = 'esm-btn';
        esmBtn.textContent = 'ESM';
        esmBtn.addEventListener('click', () => loadESM(esmBtn, key, label));
        row.appendChild(esmBtn);
      }}
      list.appendChild(row);
    }});
  }});
}});
</script>
</body>
</html>
"""

    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    with open(OUTPUT_HTML, "w") as f:
        f.write(html)

    size_mb = os.path.getsize(OUTPUT_HTML) / 1e6
    print(f"\nWritten: {OUTPUT_HTML}  ({size_mb:.1f} MB)")
    print("Serve with:  python3 -m http.server 8080 --bind 127.0.0.1")


if __name__ == "__main__":
    main()
