# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

```bash
# From the repo root (ai-scripts/), enter the dev shell:
nix develop .#claudemoji

# This provides: python3 (with pillow, numpy, scipy), potrace, openscad
```

All commands below assume you're inside the dev shell OR prefixed with `nix develop .#claudemoji -c bash -c "..."`.

## Running the Pipeline

```bash
# Full batch: process all PNGs in input/ → SVGs + 3MF in output/<name>/
sh split_all.sh

# Faceless mode (smartwatch bezel): omits face/middle, generates OpenSCAD + 3MF with retaining ring
sh split_all.sh --faceless --center-diameter-mm 36.4 --depth-mm 4.5

# Individual steps:
python3 split.py [--size-mm 50] input/foo.png output/foo/
python3 build_3mf.py [--height-mm 1.0] output/foo/ input/foo.png
python3 build_3mf.py --faceless output/foo/ input/foo.png
```

## Architecture

### Two-Stage Pipeline

1. **split.py** — Image analysis and vectorization
   - Classifies pixels by color (black/orange/white/background) using thresholds + nearest-neighbor for anti-aliased grays
   - Separates background white from interior white via edge flood-fill (`binary_dilation`)
   - Separates face from outline via `binary_fill_holes` on the white center circle
   - Converts each mask to PBM → runs `potrace` → SVG with corner anchor rectangles for slicer alignment
   - In faceless mode: computes center circle diameter from `area = π(d/2)²`, derives model size from `--center-diameter-mm` ratio, generates parametric OpenSCAD `.scad`

2. **build_3mf.py** — 3D model packaging
   - Normal mode: extrudes each SVG via OpenSCAD `linear_extrude` → STL, packages into 3MF
   - Faceless mode: renders each part from the `.scad` file using `-D part="name"` → STL, packages into 3MF
   - Deduplicates vertices with `np.unique` for manifold meshes
   - Creates per-object material assignments so slicers can assign different filaments

### Faceless Mode (Smartwatch Bezel)

The `.scad` file contains selectable modules (`part` variable):
- `outline` / `flower` — extruded SVG layers with center hole cut
- `ring` — retaining ring for PCB (USB-C cutout at 270°, button holes at configurable angles)
- `bezel_ring` — thin cover ring over display bezel, slightly oversized for slicer merge

Key dimensions are hardcoded in `generate_scad()` in split.py: PCB tolerance (36.7mm), wall thickness (2mm), ring height (5.5mm), USB cutout width (16mm), button angles, bezel layer height, screen diameter.

### Layer/Material Mapping

Normal mode: outline (black), flower (orange), middle (white), face (black — shares material with outline)

Faceless mode: outline (black), flower (orange), ring (black), bezel_ring (orange)

## Key Technical Details

- Corner anchor rectangles in SVGs ensure consistent bounds across layers with different path extents — without these, slicers misalign smaller layers
- Layer dilation (`--dilation-mm`, default 0.05mm) adds overlap between adjacent color regions to prevent gaps from potrace smoothing
- The bezel ring's outer diameter is 0.2mm oversized to overlap into flower/outline, preventing the slicer from drawing separate perimeters at the boundary
- `--resolution-mm` resamples the input image to match machine resolution, reducing SVG complexity (triggers full reclassification)
