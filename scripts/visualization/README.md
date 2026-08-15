# Manuscript SVG export

This workspace uses **Matplotlib** for data-driven charts and graphs, and
**Graphviz** for structural diagrams. New manuscript visual assets are SVG by
default; do not silently substitute a raster format.

## Setup

Install the Python dependencies from the active project requirements file:

```powershell
python -m pip install -r .\classical-cv\requirements.txt
```

Graphviz also requires its system `dot` renderer. On the reference Windows
workstation it is installed at `C:\Program Files\Graphviz\bin\dot.exe` and is
included on the user PATH. Restart a terminal opened before installation if
`dot -V` is not immediately available.

Verify both exporters without leaving generated files in the repository:

```powershell
python -m scripts.visualization.smoke_test_exporters
```

## Use in a chart script

Call `configure_matplotlib()` before importing `pyplot`, then use the explicit
SVG writer:

```python
from scripts.visualization.manuscript_svg import (
    configure_matplotlib,
    export_matplotlib_svg,
)

configure_matplotlib()
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(5.2, 3.2))
ax.plot(x, y, marker="o")
export_matplotlib_svg(fig, output_dir / "figure_accuracy.svg")
```

The helper preserves text as editable SVG text and rejects `.png`, `.jpg`, and
other raster suffixes by design.

## Use in a diagram script

```python
from scripts.visualization.manuscript_svg import (
    make_graphviz_digraph,
    render_graphviz_svg,
)

diagram = make_graphviz_digraph("pipeline", rankdir="LR")
diagram.node("input", "Input")
diagram.node("output", "Decision")
diagram.edge("input", "output", label="infer")
render_graphviz_svg(diagram, output_dir / "pipeline.svg")
```

The helper verifies the generated file is SVG and transparently locates the
standard Windows Graphviz install for terminals that have not yet reloaded
their PATH.

## Canonical complementarity manuscript figures

The recovery-rate donut and gate-competence stacked-bar figure have a single
approved root-level entry point:

```powershell
python -m scripts.generate_complementarity_figures
```

It regenerates these SVGs under `docs/manuscript/figures/`:

- `fig_recovery_rate_donut.svg`
- `fig_gate_competence_stacked_bars.svg`

Before rendering, the entry point verifies each recorded input against both
`docs/results/RESULTS_MANIFEST.json` and the campaign's
`run_provenance.json`: the artifact must be a `canonical_snapshot`, not marked
`rerun_required`, and match both recorded SHA-256 digests. The individual
generators enforce the same contract, so they cannot silently render an
alternate population supplied through `--input`.

Use the following commands to validate the committed manuscript assets or to
exercise a two-pass byte-repeatability check:

```powershell
python -m scripts.generate_complementarity_figures --verify-only
python -m scripts.generate_complementarity_figures --verify-repeatability
python -m unittest scripts.test_complementarity_figure_generators
```

The canonical source artifacts are the reviewed LSDB-DL41 rerun's
`complementarity_probes.csv` (recovery) and `accuracy_ratio_hybrid.json`
(gate routing). The generated SVG metadata records the verified input path,
SHA-256, and source commit timestamp; the verifier rejects raster-backed SVGs
and missing direct labels. Do not use
`scripts/reporting/generate_complementarity_assets.py` for manuscript redraws:
it is a historical raw-output asset generator, not the provenance-verified
manuscript route.

## Provenance boundary

Existing canonical or historical PNG result artifacts are not to be converted
in place. When a manuscript needs an SVG replacement, regenerate it from the
recorded source data and retain the required run provenance before promoting
it to `docs/results/`.
