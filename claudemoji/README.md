# claudemoji

Splits emoji PNGs into 4 non-overlapping SVG layers for multi-filament 3D printing, then packages them into ready-to-print `.3mf` files with colors pre-assigned.

## Layers

Each emoji produces:
- **outline.svg** - Black outline around the petals
- **flower.svg** - Orange/terracotta petal fill
- **middle.svg** - White center circle
- **face.svg** - Black facial features

## Output

Each emoji directory contains:
- 4 SVG layers (as above)
- A `.3mf` file with all layers extruded, color-assigned, and the source PNG as thumbnail

The 3MF uses 3 materials:
| Material | Color | Layers |
|----------|-------|--------|
| Black | #1A1A1A | outline, face |
| Orange | #C67B5C | flower |
| White | #FFFFFF | middle |

## Usage

```bash
nix develop .#claudemoji

# Process all PNGs in input/ -> output/<name>/ (SVGs + 3MF)
sh split_all.sh

# Or run steps individually:
# 1. Generate SVG layers
python3 split.py emoji1.png output/emoji1/ emoji2.png output/emoji2/

# 2. Build 3MF from layers
python3 build_3mf.py output/emoji1/ input/emoji1.png
python3 build_3mf.py --height-mm 3.0 output/emoji1/ input/emoji1.png
```

## Adding new emojis

Drop PNG files into `input/` and run `split_all.sh`. Each input gets its own subdirectory under `output/` with 4 SVGs and a `.3mf` file ready for slicing.
