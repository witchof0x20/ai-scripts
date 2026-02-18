#!/usr/bin/env python3
"""Split emoji PNGs into 4 non-overlapping SVG layers for multi-filament 3D printing.

For each input image, produces an output directory containing:
  outline.svg  - Black outline around the petals
  flower.svg   - Orange/terracotta petal fill
  middle.svg   - White center circle
  face.svg     - Black spiral eyes and wavy mouth

Usage:
  split.py input1.png output1/ [input2.png output2/ ...]
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def classify_pixels(rgba: np.ndarray) -> np.ndarray:
    """Classify each pixel into: 0=background, 1=black, 2=orange, 3=white.

    Transparent pixels are background. For opaque pixels:
      - Black: R,G,B all < 60
      - White: R,G,B all > 200
      - Orange: warm-toned pixels (R notably > G and B) — the terracotta ~C6,7B,5C
      - Unclassified anti-aliased grays are assigned to nearest classified neighbor.
    """
    r, g, b, a = rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2], rgba[:, :, 3]

    classes = np.zeros(rgba.shape[:2], dtype=np.uint8)

    opaque = a > 128
    is_black = opaque & (r < 60) & (g < 60) & (b < 60)
    is_white = opaque & (r > 200) & (g > 200) & (b > 200)
    # Orange requires warm hue: R must exceed G and B by a margin,
    # filtering out neutral grays from anti-aliasing
    is_orange = opaque & ~is_black & ~is_white & (r > (g + 10)) & (r > (b + 10))

    classes[is_black] = 1
    classes[is_orange] = 2
    classes[is_white] = 3

    # Assign remaining unclassified opaque pixels (anti-aliased grays)
    # to their nearest classified neighbor
    unclassified = opaque & (classes == 0)
    if np.any(unclassified):
        classified = classes > 0
        _, nearest_indices = ndimage.distance_transform_edt(
            ~classified, return_distances=True, return_indices=True
        )
        classes[unclassified] = classes[
            nearest_indices[0][unclassified], nearest_indices[1][unclassified]
        ]

    return classes


def separate_background_white(classes: np.ndarray) -> np.ndarray:
    """Flood-fill from edges to distinguish background white from interior white (middle).

    Returns updated classes where background white pixels become 0 (background).
    """
    h, w = classes.shape
    white_mask = classes == 3

    # Seed from all edge white pixels
    seed = np.zeros_like(white_mask)
    seed[0, :] = white_mask[0, :]
    seed[-1, :] = white_mask[-1, :]
    seed[:, 0] = white_mask[:, 0]
    seed[:, -1] = white_mask[:, -1]

    # Also seed from all transparent/background edge pixels that connect to white
    # Use binary dilation constrained to white_mask to flood-fill
    # First, find all background (class 0) connected to edges
    bg_mask = classes == 0
    edge_seed = np.zeros_like(bg_mask)
    edge_seed[0, :] = True
    edge_seed[-1, :] = True
    edge_seed[:, 0] = True
    edge_seed[:, -1] = True

    # Everything reachable from edges through background is exterior
    exterior_bg = ndimage.binary_dilation(
        edge_seed, structure=np.ones((3, 3)), iterations=0, mask=bg_mask | white_mask
    )

    # White pixels in the exterior region are background
    bg_white = exterior_bg & white_mask
    result = classes.copy()
    result[bg_white] = 0

    return result


def separate_face_from_outline(classes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Separate black pixels into outline vs face.

    The face features (eyes, mouth) sit inside the white center circle but may
    be connected to the outline at the circle border. Instead of connected
    components, fill holes in the middle-white region to recover the full circle,
    then classify black pixels inside as face.
    """
    black_mask = classes == 1
    middle_mask = classes == 3

    # Fill holes in the middle mask to get the full circle area
    # (holes = the black face features like eyes and mouth)
    full_circle = ndimage.binary_fill_holes(middle_mask)

    # Black pixels inside the filled circle = face
    face_mask = black_mask & full_circle
    # Everything else = outline
    outline_mask = black_mask & ~full_circle

    return outline_mask, face_mask


def mask_to_pbm(mask: np.ndarray, path: Path):
    """Write a boolean mask as a PBM (P4 binary) file. Potrace reads black=1 as foreground."""
    h, w = mask.shape
    img = Image.fromarray((mask.astype(np.uint8)) * 255, mode="L")
    img.save(path, format="PPM")


def run_potrace(pbm_path: Path, svg_path: Path):
    """Run potrace to convert a bitmap to SVG, with a full-canvas bounding rect."""
    subprocess.run(
        [
            "potrace",
            "--svg",
            "--invert",
            "--output", str(svg_path),
            "--turdsize", "2",
            str(pbm_path),
        ],
        check=True,
    )
    # Inject tiny filled squares at opposite canvas corners so slicers compute
    # consistent bounds across all layers. Without real geometry at the extremes,
    # slicers center based on path bounds, misaligning smaller layers.
    # Potrace uses a <g> with scale(0.1, -0.1) so internal coords are 10x viewBox.
    svg_text = svg_path.read_text()
    viewbox = svg_text.split('viewBox="')[1].split('"')[0]
    _, _, vw, vh = viewbox.split()
    iw, ih = float(vw) * 10, float(vh) * 10
    anchors = (
        f'<rect x="0" y="0" width="10" height="10" fill="#000000"/>\n'
        f'<rect x="{iw - 10:.0f}" y="{ih - 10:.0f}" width="10" height="10" fill="#000000"/>\n'
    )
    svg_text = svg_text.replace(
        'stroke="none">\n',
        f'stroke="none">\n{anchors}',
        1,
    )
    svg_path.write_text(svg_text)


def process_image(input_path: Path, output_dir: Path):
    """Process a single emoji image into 4 SVG layers."""
    print(f"\n=== Processing {input_path} -> {output_dir}/ ===")

    print("Loading image...")
    img = Image.open(input_path).convert("RGBA")
    rgba = np.array(img)
    h, w = rgba.shape[:2]

    print(f"Image size: {w}x{h}")

    print("Classifying pixels...")
    classes = classify_pixels(rgba)

    print("Separating background white from interior white...")
    classes = separate_background_white(classes)

    print("Separating face from outline...")
    outline_mask, face_mask = separate_face_from_outline(classes)

    orange_mask = classes == 2
    middle_mask = classes == 3

    # Verify non-overlap
    layers = [outline_mask, orange_mask, middle_mask, face_mask]
    total = sum(m.astype(int) for m in layers)
    overlap = np.sum(total > 1)
    if overlap > 0:
        print(f"Warning: {overlap} pixels overlap between layers!", file=sys.stderr)

    layer_names = ["outline", "flower", "middle", "face"]
    layer_masks = [outline_mask, orange_mask, middle_mask, face_mask]

    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        for name, mask in zip(layer_names, layer_masks):
            count = np.sum(mask)
            print(f"  {name}: {count} pixels")

            pbm_path = tmpdir / f"{name}.ppm"
            svg_path = output_dir / f"{name}.svg"

            mask_to_pbm(mask, pbm_path)
            run_potrace(pbm_path, svg_path)
            print(f"  -> {svg_path}")

    print(f"Done! Produced 4 SVGs in {output_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="Split emoji PNGs into SVG layers for multi-filament 3D printing."
    )
    parser.add_argument(
        "pairs",
        nargs="+",
        metavar="INPUT OUTPUT_DIR",
        help="Alternating input PNG and output directory paths",
    )
    args = parser.parse_args()

    if len(args.pairs) % 2 != 0:
        parser.error("Arguments must be pairs of INPUT_PNG OUTPUT_DIR")

    pairs = list(zip(args.pairs[::2], args.pairs[1::2]))

    for input_str, output_str in pairs:
        input_path = Path(input_str)
        output_dir = Path(output_str)

        if not input_path.exists():
            print(f"Error: {input_path} not found", file=sys.stderr)
            sys.exit(1)

        process_image(input_path, output_dir)


if __name__ == "__main__":
    main()
