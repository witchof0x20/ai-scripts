# claudemoji

Splits `claudespinny.png` into 4 non-overlapping SVG layers for multi-filament 3D printing.

## Layers

- **outline.svg** - Black outline around the petals
- **flower.svg** - Orange/terracotta petal fill
- **middle.svg** - White center circle
- **face.svg** - Black spiral eyes and wavy mouth

## Usage

```bash
nix develop .#claudemoji
python3 split.py
```

The script produces 4 SVGs in this directory, each with matching canvas dimensions so they overlay correctly.
