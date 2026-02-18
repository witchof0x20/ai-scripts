# claudemoji

Splits emoji PNGs into 4 non-overlapping SVG layers for multi-filament 3D printing.

## Layers

Each emoji produces:
- **outline.svg** - Black outline around the petals
- **flower.svg** - Orange/terracotta petal fill
- **middle.svg** - White center circle
- **face.svg** - Black facial features

## Usage

```bash
nix develop .#claudemoji

# Process all PNGs in input/ -> output/<name>/
sh split_all.sh

# Or process specific images manually
python3 split.py emoji1.png output/emoji1/ emoji2.png output/emoji2/
```

## Adding new emojis

Drop PNG files into `input/` and run `split_all.sh`. Each input gets its own subdirectory under `output/` with 4 SVGs that have matching canvas dimensions for correct overlay in slicers.
