#!/usr/bin/env python3
"""Build viewer_v3.html using Molstar for guaranteed SS display."""
import os, json, glob, re

ROOT = "/Users/mary/Desktop/LACCASES/15/design/RFDiff2"
OUT  = os.path.join(ROOT, "viewer_v3.html")

# ── helpers ─────────────────────────────────────────────────────────────────
def parse_loop_n(name):
    m = re.match(r'loop(\d+)', name)
    return int(m.group(1)) if m else None

def read(path):
    with open(path) as f:
        return f.read()

# ── load molstar bundle + css ────────────────────────────────────────────────
print("Loading Molstar bundle…")
molstar_js  = read("/tmp/molstar.js")
molstar_css = read("/tmp/molstar.css")
print(f"  JS: {len(molstar_js):,} chars   CSS: {len(molstar_css):,} chars")

# ── read PDB data ─────────────────────────────────────────────────────────────
print("Reading RFDiff PDB data…")
rfdiff_data = {}
for linker_dir in sorted(glob.glob(os.path.join(ROOT, "linker_*"))):
    lid = os.path.basename(linker_dir)
    for loop_dir in sorted(glob.glob(os.path.join(linker_dir, "loop*"))):
        n = parse_loop_n(os.path.basename(loop_dir))
        if n is None: continue
        pdb = os.path.join(loop_dir, "aligned_outputs", "aligned_combined.pdb")
        if os.path.exists(pdb):
            rfdiff_data[f"{lid}_loop{n}"] = read(pdb)
print(f"  {len(rfdiff_data)} entries")

print("Reading ESM PDB data (chain-A aligned models)…")
esm_data = {}
for linker_dir in sorted(glob.glob(os.path.join(ROOT, "linker_*"))):
    lid = os.path.basename(linker_dir)
    for loop_dir in sorted(glob.glob(os.path.join(linker_dir, "loop*"))):
        n = parse_loop_n(os.path.basename(loop_dir))
        if n is None: continue
        adir = os.path.join(loop_dir, "ESMFOLD", "aligned_models")
        mfiles = sorted(glob.glob(os.path.join(adir, "model_*.pdb")),
                        key=lambda p: int(re.search(r'model_(\d+)', p).group(1)))
        if mfiles:
            esm_data[f"{lid}_loop{n}"] = [read(f) for f in mfiles]
print(f"  {len(esm_data)} entries")

# ── build GROUPS ──────────────────────────────────────────────────────────────
LINKER_INFO = {
    "linker_182-2-185": ("Linker 182-2-185", "A155-182 / 2aa / A185-262"),
    "linker_183-1-185": ("Linker 183-1-185", "A155-183 / 1aa / A185-262"),
    "linker_183-2-186": ("Linker 183-2-186", "A155-183 / 2aa / A186-262"),
    "linker_182-3-186": ("Linker 182-3-186", "A155-182 / 3aa / A186-262"),
}
groups = []
for linker_dir in sorted(glob.glob(os.path.join(ROOT, "linker_*"))):
    lid = os.path.basename(linker_dir)
    loops = []
    for loop_dir in sorted(glob.glob(os.path.join(linker_dir, "loop*")),
                           key=lambda p: parse_loop_n(os.path.basename(p)) or 0):
        n = parse_loop_n(os.path.basename(loop_dir))
        if n is None: continue
        key = f"{lid}_loop{n}"
        if key in rfdiff_data:
            loops.append({"n": n, "hasEsm": key in esm_data})
    if loops:
        badge, contig = LINKER_INFO.get(lid, (lid, ""))
        groups.append({"id": lid, "badge": badge, "contig": contig, "loops": loops})

# ── serialize data ─────────────────────────────────────────────────────────────
def esc(s):
    return s.replace("\\","\\\\").replace("`","\\`").replace("$","\\$")

rfdiff_js = "const RFDIFF_DATA = {\n"
for k, v in rfdiff_data.items():
    rfdiff_js += f'  "{k}": `{esc(v)}`,\n'
rfdiff_js += "};"

esm_js = "const ESM_DATA = {\n"
for k, models in esm_data.items():
    mlist = ",\n    ".join(f"`{esc(m)}`" for m in models)
    esm_js += f'  "{k}": [\n    {mlist}\n  ],\n'
esm_js += "};"

groups_js = f"const GROUPS = {json.dumps(groups)};"
print(f"  RFDIFF_DATA: {len(rfdiff_js):,}   ESM_DATA: {len(esm_js):,}")

# ── write HTML ────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RFDiffusion Viewer v3</title>
<style>{molstar_css}</style>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #111827; color: #e5e7eb; display: flex; height: 100vh; overflow: hidden; }}
/* Sidebar */
#sidebar {{ width: 260px; min-width: 260px; background: #1f2937;
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
.loop-row {{ display: flex; align-items: center; margin: 1px 8px; border-radius: 6px;
             overflow: hidden; }}
.loop-main {{ flex: 1; padding: 7px 10px; cursor: pointer; font-size: 12px;
              border-radius: 6px 0 0 6px; transition: background .15s; color: #d1d5db; }}
.loop-main:hover {{ background: #374151; }}
.loop-main.active {{ background: #1d4ed8; color: #fff; }}
.esm-btn {{ padding: 7px 9px; background: #374151; cursor: pointer; font-size: 10px;
            font-weight: 700; color: #9ca3af; border-left: 1px solid #4b5563;
            border-radius: 0 6px 6px 0; transition: background .15s; white-space: nowrap; }}
.esm-btn:hover {{ background: #4b5563; color: #e5e7eb; }}
.esm-btn.active {{ background: #065f46; color: #6ee7b7; }}
.pill {{ display: inline-block; background: #374151; color: #9ca3af; border-radius: 4px;
         padding: 1px 5px; font-size: 10px; margin-right: 5px; }}
.loop-main.active .pill {{ background: #1e40af; color: #93c5fd; }}
/* Main panel */
#main {{ flex: 1; display: flex; flex-direction: column; position: relative; }}
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

// ── Molstar setup ─────────────────────────────────────────────────────────────
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

async function loadRFDiff(mainBtn, key, loopStart, loopEnd, label, contig) {{
  if (activeMain) activeMain.classList.remove('active');
  if (activeEsmBtn) activeEsmBtn.classList.remove('active');
  mainBtn.classList.add('active');
  activeMain = mainBtn; activeEsmBtn = null;
  document.getElementById('info-title').textContent = label;
  document.getElementById('info-sub').textContent = contig;
  document.getElementById('placeholder').style.display = 'none';

  await viewer.plugin.clear();

  // Use Molstar's high-level loader — auto preset shows cartoon for protein,
  // ball-and-stick for ligand, spacefill for metal ions automatically
  await viewer.loadStructureFromData(RFDIFF_DATA[key], 'pdb', false, {{ label: key }});
  viewer.plugin.managers.camera.reset();
}}

async function loadESM(esmBtn, key, loopEnd, label) {{
  if (activeEsmBtn) activeEsmBtn.classList.remove('active');
  esmBtn.classList.add('active');
  activeEsmBtn = esmBtn;
  document.getElementById('info-title').textContent = label + ' \u2014 ESMFold';
  document.getElementById('info-sub').textContent = 'Top predictions aligned';
  document.getElementById('placeholder').style.display = 'none';

  await viewer.plugin.clear();

  const models = ESM_DATA[key];
  if (!models || !models.length) return;

  const modelColors = [0x7a9bb5, 0x60a5fa, 0x34d399, 0xf472b6, 0xfb923c];
  const alphas = [1.0, 0.3, 0.3, 0.3, 0.3];

  for (let i = 0; i < models.length; i++) {{
    const data = await viewer.plugin.builders.data.rawData({{ data: models[i], label: key + '_m' + i }});
    const traj = await viewer.plugin.builders.structure.parseTrajectory(data, 'pdb');
    const model = await viewer.plugin.builders.structure.createModel(traj);
    const struct = await viewer.plugin.builders.structure.createStructure(model, {{ name: 'deposited' }});

    await viewer.plugin.builders.structure.representation.addRepresentation(struct, {{
      type: 'cartoon',
      typeParams: {{ alpha: alphas[i] }},
      color: 'secondary-structure',
    }}, {{ tag: 'esm_' + i }});
  }}

  viewer.plugin.managers.camera.reset();
}}

// ── Build sidebar ─────────────────────────────────────────────────────────────
initViewer().then(() => {{
  const list = document.getElementById('list');

  GROUPS.forEach(group => {{
    const sec = document.createElement('div');
    sec.className = 'section-label';
    sec.textContent = group.badge;
    list.appendChild(sec);

    const contigEl = document.createElement('div');
    contigEl.className = 'contig-label';
    contigEl.textContent = '[A1-151/N-N/' + group.contig + ']';
    list.appendChild(contigEl);

    group.loops.forEach(loop => {{
      const n = loop.n;
      const loopEnd = 151 + n;
      const key = group.id + '_loop' + n;
      const label = group.badge + ' \u2014 Loop ' + n + ' aa';
      const contig = '[A1-151/' + n + '-' + n + '/' + group.contig + ']';

      const row = document.createElement('div');
      row.className = 'loop-row';

      const mainBtn = document.createElement('div');
      mainBtn.className = 'loop-main';
      mainBtn.innerHTML = '<span class="pill">' + n + ' aa</span>Loop ' + n;
      mainBtn.addEventListener('click', () => loadRFDiff(mainBtn, key, 152, loopEnd, label, contig));
      row.appendChild(mainBtn);

      if (loop.hasEsm) {{
        const esmBtn = document.createElement('div');
        esmBtn.className = 'esm-btn';
        esmBtn.textContent = 'ESM';
        esmBtn.addEventListener('click', () => loadESM(esmBtn, key, loopEnd, label));
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

with open(OUT, 'w') as f:
    f.write(html)

size_mb = os.path.getsize(OUT) / 1e6
print(f"\nWritten: {OUT}  ({size_mb:.1f} MB)")
