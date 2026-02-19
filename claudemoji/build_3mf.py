#!/usr/bin/env python3
"""Build a multi-color 3MF file from SVG layers produced by split.py.

For each emoji directory containing outline.svg, flower.svg, middle.svg, face.svg,
extrudes each layer via OpenSCAD and packages them into a single .3mf with
per-triangle material assignments and a thumbnail.

Usage:
  build_3mf.py [--height-mm 2.0] output/<name>/ input/<name>.png
"""

import argparse
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np

# Layer definitions: name, hex color, material index
# outline and face share material 0 (black)
LAYERS = [
    ("outline", "#1A1A1A", 0),
    ("flower", "#C67B5C", 1),
    ("middle", "#FFFFFF", 2),
    ("face", "#1A1A1A", 0),
]

MATERIALS = [
    ("Black", "#1A1A1A"),
    ("Orange", "#C67B5C"),
    ("White", "#FFFFFF"),
]


def _svg_size_mm(svg_path: Path) -> float:
    """Extract the physical width from an SVG's width attribute (in pt)."""
    import re

    text = svg_path.read_text()
    m = re.search(r'width="([0-9.]+)pt"', text)
    if not m:
        raise ValueError(f"Cannot parse width from {svg_path}")
    # 1pt = 25.4/72 mm
    return float(m.group(1)) * 25.4 / 72


def svg_to_stl(svg_path: Path, stl_path: Path, height_mm: float, tmp_dir: Path):
    """Extrude an SVG to STL via OpenSCAD.

    Adds tiny anchor squares at (0,0) and (size,size) so OpenSCAD produces
    consistent XY bounds across all layers regardless of path extents.
    """
    scad_path = tmp_dir / f"{svg_path.stem}.scad"
    svg_abs = str(svg_path.resolve()).replace("\\", "/")
    size = _svg_size_mm(svg_path)
    scad_path.write_text(
        f'linear_extrude(height={height_mm}, convexity=10) {{\n'
        f'  import("{svg_abs}");\n'
        f'  square(0.001);\n'
        f'  translate([{size - 0.001}, {size - 0.001}]) square(0.001);\n'
        f'}}\n'
    )
    result = subprocess.run(
        ["openscad", "--render", "-o", str(stl_path), str(scad_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"OpenSCAD error for {svg_path.name}:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)


def parse_stl(stl_path: Path) -> np.ndarray:
    """Parse an STL file (ASCII or binary). Returns vertices as Nx3x3 float32."""
    data = stl_path.read_bytes()

    # Detect ASCII vs binary: ASCII starts with "solid " followed by a name
    if data[:6] == b"solid " and b"\n" in data[:256]:
        return _parse_ascii_stl(data)
    return _parse_binary_stl(data)


def _parse_binary_stl(data: bytes) -> np.ndarray:
    """Parse a binary STL file. Returns vertices Nx3x3."""
    if len(data) < 84:
        return np.empty((0, 3, 3), dtype=np.float32)

    num_triangles = struct.unpack_from("<I", data, 80)[0]

    tri_dtype = np.dtype([
        ("normal", "<f4", (3,)),
        ("v0", "<f4", (3,)),
        ("v1", "<f4", (3,)),
        ("v2", "<f4", (3,)),
        ("attr", "<u2"),
    ])

    triangles = np.frombuffer(data, dtype=tri_dtype, offset=84, count=num_triangles)
    return np.stack([triangles["v0"], triangles["v1"], triangles["v2"]], axis=1)


def _parse_ascii_stl(data: bytes) -> np.ndarray:
    """Parse an ASCII STL file. Returns vertices Nx3x3."""
    text = data.decode("ascii", errors="replace")
    # Extract all vertex lines
    verts = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("vertex "):
            parts = stripped.split()
            verts.append([float(parts[1]), float(parts[2]), float(parts[3])])

    if not verts:
        return np.empty((0, 3, 3), dtype=np.float32)

    arr = np.array(verts, dtype=np.float32)
    # Group into triangles (3 vertices each)
    num_tris = len(arr) // 3
    return arr[: num_tris * 3].reshape(num_tris, 3, 3)


def build_3mf(
    layer_dir: Path,
    thumbnail_path: Path,
    height_mm: float,
):
    """Build a .3mf file from SVG layers.

    Each layer becomes a separate object in the 3MF so slicers can assign
    different filaments to each part.
    """
    name = layer_dir.name
    output_path = layer_dir / f"{name}.3mf"

    print(f"\n=== Building 3MF: {output_path} ===")

    # Each entry: (layer_name, mat_idx, vertices Nx3x3)
    objects = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        for layer_name, _color, mat_idx in LAYERS:
            svg_path = layer_dir / f"{layer_name}.svg"
            if not svg_path.exists():
                print(f"  Warning: {svg_path} not found, skipping", file=sys.stderr)
                continue

            stl_path = tmp_dir / f"{layer_name}.stl"
            print(f"  Extruding {layer_name}.svg...")
            svg_to_stl(svg_path, stl_path, height_mm, tmp_dir)

            vertices = parse_stl(stl_path)
            num_tris = vertices.shape[0]
            if num_tris == 0:
                print(f"  Warning: {layer_name} produced empty mesh", file=sys.stderr)
                continue

            print(f"  {layer_name}: {num_tris} triangles")
            objects.append((layer_name, mat_idx, vertices))

    if not objects:
        print("Error: no meshes produced", file=sys.stderr)
        sys.exit(1)

    total_tris = sum(v.shape[0] for _, _, v in objects)
    print(f"  Total: {len(objects)} objects, {total_tris} triangles")

    # Build 3MF XML
    model_xml = _build_model_xml(objects)

    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        '  <Default Extension="png" ContentType="image/png"/>\n'
        '</Types>\n'
    )

    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '  <Relationship Target="/Metadata/thumbnail.png" Id="rel1" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"/>\n'
        '</Relationships>\n'
    )

    thumbnail_bytes = thumbnail_path.read_bytes()

    print(f"  Writing {output_path}...")
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)
        zf.writestr("Metadata/thumbnail.png", thumbnail_bytes)

    print(f"  Done! {output_path.stat().st_size / 1024:.0f} KB")

    # Clean up source SVGs now that they're baked into the 3MF
    for layer_name, _color, _mat_idx in LAYERS:
        svg_path = layer_dir / f"{layer_name}.svg"
        if svg_path.exists():
            svg_path.unlink()
            print(f"  Removed {svg_path.name}")


def _build_model_xml(
    objects: list[tuple[str, int, np.ndarray]],
) -> str:
    """Build the 3D model XML for the 3MF.

    Each layer is a separate <object> so slicers treat them as distinct parts
    that can each be assigned a different filament/extruder.
    """
    parts = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>\n')
    parts.append(
        '<model unit="millimeter" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">\n'
    )

    # Materials
    parts.append('  <resources>\n')
    parts.append('    <basematerials id="1">\n')
    for mat_name, mat_color in MATERIALS:
        parts.append(f'      <base name="{mat_name}" displaycolor="{mat_color}"/>\n')
    parts.append('    </basematerials>\n')

    # One object per layer
    obj_ids = []
    next_id = 2
    for layer_name, mat_idx, vertices in objects:
        obj_id = next_id
        next_id += 1
        obj_ids.append(obj_id)

        # Deduplicate vertices so adjacent triangles share vertex indices
        # (without this, every triangle has 3 unique vertices → non-manifold)
        flat = vertices.reshape(-1, 3)
        unique_verts, inverse = np.unique(flat, axis=0, return_inverse=True)
        tri_indices = inverse.reshape(-1, 3)

        parts.append(f'    <object id="{obj_id}" name="{layer_name}" type="model">\n')
        parts.append('      <mesh>\n')

        # Vertices
        parts.append('        <vertices>\n')
        for v in unique_verts:
            parts.append(f'          <vertex x="{v[0]}" y="{v[1]}" z="{v[2]}"/>\n')
        parts.append('        </vertices>\n')

        # Triangles
        parts.append('        <triangles>\n')
        for v0, v1, v2 in tri_indices:
            parts.append(
                f'          <triangle v1="{v0}" v2="{v1}" v3="{v2}" pid="1" p1="{mat_idx}"/>\n'
            )
        parts.append('        </triangles>\n')

        parts.append('      </mesh>\n')
        parts.append('    </object>\n')

    # Group object: references layer objects as components
    group_id = next_id
    parts.append(f'    <object id="{group_id}" type="model">\n')
    parts.append('      <components>\n')
    for obj_id in obj_ids:
        parts.append(f'        <component objectid="{obj_id}"/>\n')
    parts.append('      </components>\n')
    parts.append('    </object>\n')

    parts.append('  </resources>\n')

    # Build — reference the group
    parts.append('  <build>\n')
    parts.append(f'    <item objectid="{group_id}"/>\n')
    parts.append('  </build>\n')
    parts.append('</model>\n')

    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Build a multi-color 3MF from SVG layers."
    )
    parser.add_argument(
        "--height-mm",
        type=float,
        default=1.0,
        help="Extrusion height in mm (default: 1.0)",
    )
    parser.add_argument(
        "layer_dir",
        type=Path,
        help="Directory containing outline.svg, flower.svg, middle.svg, face.svg",
    )
    parser.add_argument(
        "thumbnail",
        type=Path,
        help="PNG file to use as 3MF thumbnail",
    )
    args = parser.parse_args()

    if not args.layer_dir.is_dir():
        print(f"Error: {args.layer_dir} is not a directory", file=sys.stderr)
        sys.exit(1)
    if not args.thumbnail.exists():
        print(f"Error: {args.thumbnail} not found", file=sys.stderr)
        sys.exit(1)

    build_3mf(args.layer_dir, args.thumbnail, args.height_mm)


if __name__ == "__main__":
    main()
