#!/usr/bin/env python3
"""Split emoji PNGs into 4 SVG layers for multi-filament 3D printing.

For each input image, produces an output directory containing:
  outline.svg  - Black outline around the petals
  flower.svg   - Orange/terracotta petal fill
  middle.svg   - White center circle
  face.svg     - Black spiral eyes and wavy mouth

Usage:
  split.py [--size-mm 50] [--dilation-mm 0.1] input1.png output1/ [input2.png output2/ ...]
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


def dilate_mask(mask: np.ndarray, pixels: int) -> np.ndarray:
    """Dilate a boolean mask by the given number of pixels."""
    if pixels <= 0:
        return mask
    return ndimage.binary_dilation(mask, iterations=pixels)


def run_potrace(pbm_path: Path, svg_path: Path, size_mm: float | None):
    """Run potrace to convert a bitmap to SVG, with a full-canvas bounding rect."""
    cmd = [
        "potrace",
        "--svg",
        "--invert",
        "--output", str(svg_path),
        "--turdsize", "2",
    ]
    if size_mm is not None:
        cmd += ["--width", f"{size_mm}mm"]
    cmd.append(str(pbm_path))

    subprocess.run(cmd, check=True)

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


def compute_center_circle(classes: np.ndarray) -> tuple[float, float, float]:
    """Compute the center circle's centroid and diameter in pixels.

    Uses binary_fill_holes on the white (middle) region to recover
    the full circle, then derives diameter from area = pi*(d/2)^2.

    Returns (cx, cy, diameter) in pixel coordinates (top-left origin).
    """
    middle_mask = classes == 3
    full_circle = ndimage.binary_fill_holes(middle_mask)

    area_pixels = float(np.sum(full_circle))
    diameter_pixels = 2 * np.sqrt(area_pixels / np.pi)

    ys, xs = np.where(full_circle)
    cx = float(np.mean(xs))
    cy = float(np.mean(ys))

    return cx, cy, diameter_pixels


def generate_scad(
    output_dir: Path,
    layer_names: list[str],
    size_mm: float,
    center_cx_mm: float,
    center_cy_mm: float,
    center_diameter_mm: float,
    depth_mm: float,
):
    """Generate an OpenSCAD program with front face parts and retaining ring.

    The .scad file supports part selection via the `part` variable for STL export:
      part="outline"  - just the outline layer
      part="flower"   - just the flower layer
      part="ring"     - just the retaining ring
      part="assembly" - everything together (default, for preview)
    """
    name = output_dir.name
    scad_path = output_dir / f"{name}.scad"

    # Watch/ring dimensions
    padding_margin = 1.0      # extra radius for foam padding around PCB and screen
    pcb_diameter = 36.7 + 2 * padding_margin  # 36.5mm PCB + 0.2mm tolerance + padding
    wall_thickness = 3.0      # 2mm pocket + 1mm bevel
    ring_height = 6.0         # screen front to PCB back = 6mm
    ring_od = pcb_diameter + 2 * wall_thickness

    # USB-C cutout: 12mm port + 2mm clearance each side
    usb_cutout_width = 16.0
    # USB-C is at 270° (bottom / 6 o'clock) in the XY plane
    usb_angle = 270

    # Button cutout parameters
    # The button assemblies fit within a 24° arc at the PCB edge (~7.7mm) but
    # not 18° (~5.8mm). Simple rectangular slots through the full wall let the
    # buttons jut out freely. Rectangular pushers can be inserted later.
    button_slot_width = 5.0   # tangential width of the slot
    button_slot_height = 2.5  # Z height (1.5mm button + 1mm tolerance)
    # Standard math angles (CCW from +X). West = 180°, CW from west = decreasing.
    boot_angle = 180 - 18        # BOOT: 18° CW from west = 162°
    power_angle = 180 - (18+24)  # Power: 24° CW from BOOT = 42° CW from west = 138°

    # Bezel cover ring: thin ring covering the display bezel
    screen_diameter = 34.6    # 34.2mm screen + 0.4mm tolerance
    bezel_layer_height = 0.50 # ~3 print layers (accounts for thicker first layer)

    scad_content = f'''\
// Faceless claudemoji - {name}
// Total model size: {size_mm:.2f}mm
// Center hole diameter: {center_diameter_mm:.2f}mm
// Center position: ({center_cx_mm:.2f}, {center_cy_mm:.2f})mm

// Select which part to render:
//   "assembly"    - all parts (default, for preview)
//   "outline"     - outline layer only
//   "flower"      - flower layer only
//   "ring"        - retaining ring only
//   "bezel_ring"  - bezel cover ring only
//   "frame"      - plain annulus for fitment testing
//   "back"       - back shell with screw holes
part = "assembly";

// --- Dimensions ---
face_depth = {depth_mm};
center_x = {center_cx_mm:.4f};
center_y = {center_cy_mm:.4f};
padding_margin = {padding_margin};  // extra radius for foam padding
center_diameter = {center_diameter_mm} + 2 * padding_margin;

// Retaining ring
pcb_diameter = {pcb_diameter};
wall_thickness = {wall_thickness};
ring_height = {ring_height};
ring_od = pcb_diameter + 2 * wall_thickness;

// USB-C cutout (12mm port + 2mm clearance each side)
usb_cutout_width = {usb_cutout_width};
usb_angle = {usb_angle};

// Button cutouts: rectangular slots through the full wall
button_slot_width = {button_slot_width};   // tangential width
button_slot_height = {button_slot_height}; // Z height (1.5mm button + tolerance, at back of ring)
boot_angle = {boot_angle};   // BOOT: 18° CW from west
power_angle = {power_angle}; // Power: 24° CW from BOOT (42° CW from west)

// Bezel cover ring (thin ring over display bezel)
screen_diameter = {screen_diameter};
bezel_layer_height = {bezel_layer_height};

// Heat set insert fastening (M2 inserts, radial through side walls)
insert_od = 3.2;               // M2 heat set insert outer diameter
insert_depth = 3.0;            // insert length (fits in 3mm ring wall)
bolt_clearance = 2.4;          // M2 bolt clearance hole
insert_angles = [60, 210, 315]; // avoiding USB (270°) and buttons (138°, 162°)
insert_z = ring_height / 2;    // mid-height of ring

// Back shell dimensions
back_shell_thickness = 2.0;    // wall and plate thickness
battery_depth = 7.0;           // cavity behind ring for battery + connectors
back_total_depth = ring_height + battery_depth;
back_od = ring_od + 2 * back_shell_thickness;
back_clearance = 0.3;          // gap so shell slides over ring
m2_hole_diameter = 2.4;        // M2 + 0.4mm clearance
screw_x_offset = 11.04;
screw_y_offset = 10.80;        // +Y = away from USB (toward 90°)
screw_usb_offset = 15.87;      // toward USB (-Y / 270°)

// --- Modules ---

module outline_part() {{
    difference() {{
        linear_extrude(height=face_depth, convexity=10)
            import("outline.svg");
        translate([center_x, center_y, -0.1])
            cylinder(h=face_depth + 0.2, d=center_diameter, $fn=200);
    }}
}}

module flower_part() {{
    difference() {{
        linear_extrude(height=face_depth, convexity=10)
            import("flower.svg");
        translate([center_x, center_y, -0.1])
            cylinder(h=face_depth + 0.2, d=center_diameter, $fn=200);
    }}
}}

// Rectangular button slot through the full ring wall at a given angle.
// Positioned at the back (open end) of the ring where the buttons are.
module button_slot(angle) {{
    rotate([0, 0, angle])
        translate([-button_slot_width/2, pcb_diameter/2 - 0.1, ring_height - button_slot_height - 1.5])
            cube([button_slot_width, wall_thickness + 0.2, button_slot_height + 0.1]);
}}

module ring_part() {{
    translate([center_x, center_y, face_depth])
    difference() {{
        // Ring body
        cylinder(h=ring_height, d=ring_od, $fn=200);

        // Inner bore (PCB slides in)
        translate([0, 0, -0.1])
            cylinder(h=ring_height + 0.2, d=pcb_diameter, $fn=200);

        // USB-C cable cutout (full height slot)
        rotate([0, 0, usb_angle])
            translate([-usb_cutout_width/2, pcb_diameter/2 - 1, -0.1])
                cube([usb_cutout_width, wall_thickness + 2, ring_height + 0.2]);

        // BOOT button slot
        button_slot(boot_angle);

        // Power button slot
        button_slot(power_angle);

        // Heat set insert holes (radial, from outer surface into wall)
        for (a = insert_angles)
            radial_hole(a, insert_z, insert_od, insert_depth, ring_od/2);
    }}
}}

module bezel_ring_part() {{
    // Outer diameter slightly oversized to overlap into flower/outline,
    // so the slicer merges them instead of drawing separate perimeters.
    translate([center_x, center_y, 0])
        difference() {{
            cylinder(h=bezel_layer_height, d=center_diameter + 1.0, $fn=200);
            translate([0, 0, -0.1])
                cylinder(h=bezel_layer_height + 0.2, d=screen_diameter, $fn=200);
        }}
}}

// Plain annulus for fitment testing (no character artwork)
module frame_part() {{
    translate([center_x, center_y, 0])
    union() {{
        // Flat annulus at face depth
        difference() {{
            cylinder(h=face_depth, d=ring_od, $fn=200);
            translate([0, 0, -0.1])
                cylinder(h=face_depth + 0.2, d=center_diameter, $fn=200);
        }}
        // Bezel ring
        difference() {{
            cylinder(h=bezel_layer_height, d=center_diameter + 1.0, $fn=200);
            translate([0, 0, -0.1])
                cylinder(h=bezel_layer_height + 0.2, d=screen_diameter, $fn=200);
        }}
        // Retaining ring on back
        translate([0, 0, face_depth])
        difference() {{
            cylinder(h=ring_height, d=ring_od, $fn=200);
            translate([0, 0, -0.1])
                cylinder(h=ring_height + 0.2, d=pcb_diameter, $fn=200);
            rotate([0, 0, usb_angle])
                translate([-usb_cutout_width/2, pcb_diameter/2 - 1, -0.1])
                    cube([usb_cutout_width, wall_thickness + 2, ring_height + 0.2]);
            button_slot(boot_angle);
            button_slot(power_angle);
            // Heat set insert holes
            for (a = insert_angles)
                radial_hole(a, insert_z, insert_od, insert_depth, ring_od/2);
        }}
    }}
}}

// Radial hole from outer surface inward (for heat set insert or bolt)
module radial_hole(angle, z_pos, diameter, depth, from_radius) {{
    rotate([0, 0, angle])
        translate([0, from_radius + 0.1, z_pos])
            rotate([90, 0, 0])
                cylinder(h=depth + 0.1, d=diameter, $fn=50);
}}

module back_button_slot(angle) {{
    // Extends from button position all the way to the open edge (z=0)
    rotate([0, 0, angle])
        translate([-button_slot_width/2, ring_od/2 - 0.1, -0.1])
            cube([button_slot_width, back_shell_thickness + 0.2, ring_height - 1.5 + 0.1]);
}}

module back_part() {{
    translate([center_x, center_y, face_depth])
    difference() {{
        // Outer shell (extends beyond ring for battery cavity)
        cylinder(h=back_total_depth, d=back_od, $fn=200);

        // Inner bore: ring section (slides over ring with clearance)
        translate([0, 0, -0.1])
            cylinder(h=ring_height + 0.1, d=ring_od + back_clearance, $fn=200);

        // Inner bore: battery cavity behind ring (open to PCB diameter)
        translate([0, 0, ring_height - 0.1])
            cylinder(h=battery_depth - back_shell_thickness + 0.2, d=pcb_diameter, $fn=200);

        // USB-C cutout: extends from PCB bore through the full back shell wall
        rotate([0, 0, usb_angle])
            translate([-usb_cutout_width/2, pcb_diameter/2 - 1, -0.1])
                cube([usb_cutout_width, back_od/2 - pcb_diameter/2 + 2, back_total_depth + 0.2]);

        // Button cutouts through side wall
        back_button_slot(boot_angle);
        back_button_slot(power_angle);

        // M2 PCB screw holes through back plate
        translate([screw_x_offset, screw_y_offset, back_total_depth - back_shell_thickness - 0.1])
            cylinder(h=back_shell_thickness + 0.2, d=m2_hole_diameter, $fn=50);
        translate([-screw_x_offset, screw_y_offset, back_total_depth - back_shell_thickness - 0.1])
            cylinder(h=back_shell_thickness + 0.2, d=m2_hole_diameter, $fn=50);
        translate([0, -screw_usb_offset, back_total_depth - back_shell_thickness - 0.1])
            cylinder(h=back_shell_thickness + 0.2, d=m2_hole_diameter, $fn=50);

        // Bolt clearance holes for heat set inserts (radial, through outer wall)
        for (a = insert_angles)
            radial_hole(a, insert_z, bolt_clearance, back_shell_thickness, back_od/2);
    }}
}}

// --- Part selection ---
if (part == "outline") {{
    outline_part();
}} else if (part == "flower") {{
    flower_part();
}} else if (part == "ring") {{
    ring_part();
}} else if (part == "bezel_ring") {{
    bezel_ring_part();
}} else if (part == "frame") {{
    frame_part();
}} else if (part == "back") {{
    back_part();
}} else {{
    // Assembly: all parts together
    outline_part();
    flower_part();
    ring_part();
    bezel_ring_part();
    back_part();
}}
'''

    scad_path.write_text(scad_content)
    print(f"  -> {scad_path}")


def process_image(
    input_path: Path,
    output_dir: Path,
    size_mm: float | None,
    dilation_mm: float,
    resolution_mm: float | None,
    faceless: bool = False,
    center_diameter_mm: float | None = None,
    depth_mm: float | None = None,
):
    """Process a single emoji image into SVG layers."""
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

    # Compute center circle geometry (needed for faceless mode scaling)
    cx_px, cy_px, diameter_px = compute_center_circle(classes)
    center_ratio = diameter_px / w
    print(f"Center circle: diameter={diameter_px:.1f}px, ratio={center_ratio:.4f}, center=({cx_px:.1f}, {cy_px:.1f})")

    if faceless:
        # In faceless mode, model size is derived from center diameter
        size_mm = center_diameter_mm / center_ratio
        print(f"Faceless mode: center {center_diameter_mm}mm -> model size {size_mm:.2f}mm")

    # Downsample to match machine resolution if specified
    if resolution_mm is not None and size_mm is not None:
        target_px = round(size_mm / resolution_mm)
        orig_w, orig_h = w, h
        if orig_w > target_px or orig_h > target_px:
            img = img.resize((target_px, target_px), Image.LANCZOS)
            rgba = np.array(img)
            h, w = rgba.shape[:2]
            print(f"Resampled {orig_w}x{orig_h} -> {target_px}x{target_px} ({resolution_mm}mm resolution, {1 / resolution_mm:.0f} px/mm)")

            # Reclassify after resampling
            print("Reclassifying after resample...")
            classes = classify_pixels(rgba)
            classes = separate_background_white(classes)
            outline_mask, face_mask = separate_face_from_outline(classes)
            cx_px, cy_px, diameter_px = compute_center_circle(classes)

    # Convert dilation from mm to pixels
    if size_mm is not None and dilation_mm > 0:
        px_per_mm = w / size_mm
        dilation_px = max(1, round(dilation_mm * px_per_mm))
        print(f"Dilation: {dilation_mm}mm = {dilation_px}px (at {px_per_mm:.1f} px/mm)")
    else:
        dilation_px = 0

    if size_mm is not None:
        print(f"Output size: {size_mm}mm x {size_mm}mm")

    orange_mask = classes == 2

    if faceless:
        layer_names = ["outline", "flower"]
        layer_masks = [outline_mask, orange_mask]
    else:
        middle_mask = classes == 3
        layer_names = ["outline", "flower", "middle", "face"]
        layer_masks = [outline_mask, orange_mask, middle_mask, face_mask]

    # Dilate each mask so adjacent layers overlap slightly, preventing
    # gaps from potrace smoothing and slicer tolerances
    if dilation_px > 0:
        print(f"Dilating masks by {dilation_px}px...")
        layer_masks = [dilate_mask(m, dilation_px) for m in layer_masks]

    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        for name, mask in zip(layer_names, layer_masks):
            count = np.sum(mask)
            print(f"  {name}: {count} pixels")

            pbm_path = tmpdir / f"{name}.ppm"
            svg_path = output_dir / f"{name}.svg"

            mask_to_pbm(mask, pbm_path)
            run_potrace(pbm_path, svg_path, size_mm)
            print(f"  -> {svg_path}")

    if faceless:
        # Center position in mm (SVG/OpenSCAD coords: Y is flipped from raster)
        px_per_mm = w / size_mm
        center_cx_mm = cx_px / px_per_mm
        center_cy_mm = (h - cy_px) / px_per_mm

        generate_scad(
            output_dir,
            layer_names,
            size_mm,
            center_cx_mm,
            center_cy_mm,
            center_diameter_mm,
            depth_mm,
        )
        print(f"Done! Produced {len(layer_names)} SVGs + OpenSCAD in {output_dir}/")
    else:
        print(f"Done! Produced {len(layer_names)} SVGs in {output_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="Split emoji PNGs into SVG layers for multi-filament 3D printing."
    )
    parser.add_argument(
        "--size-mm",
        type=float,
        default=50,
        help="Output SVG square width in mm (default: 50). Ignored in faceless mode.",
    )
    parser.add_argument(
        "--dilation-mm",
        type=float,
        default=0.2,
        help="Overlap dilation between layers in mm to prevent gaps (default: 0.2)",
    )
    parser.add_argument(
        "--resolution-mm",
        type=float,
        default=None,
        help="Machine resolution in mm (e.g. 0.05). Resamples input to match, reducing SVG complexity.",
    )
    parser.add_argument(
        "--faceless",
        action="store_true",
        help="Omit face and center circle. Emits only outline+flower SVGs and an OpenSCAD program with a center hole.",
    )
    parser.add_argument(
        "--center-diameter-mm",
        type=float,
        default=None,
        help="Diameter of the center hole in mm (required with --faceless). Model size is derived from this.",
    )
    parser.add_argument(
        "--depth-mm",
        type=float,
        default=None,
        help="Extrusion depth in mm for the OpenSCAD program (required with --faceless).",
    )
    parser.add_argument(
        "pairs",
        nargs="+",
        metavar="INPUT OUTPUT_DIR",
        help="Alternating input PNG and output directory paths",
    )
    args = parser.parse_args()

    if args.faceless:
        if args.center_diameter_mm is None:
            parser.error("--center-diameter-mm is required with --faceless")
        if args.depth_mm is None:
            parser.error("--depth-mm is required with --faceless")

    if len(args.pairs) % 2 != 0:
        parser.error("Arguments must be pairs of INPUT_PNG OUTPUT_DIR")

    pairs = list(zip(args.pairs[::2], args.pairs[1::2]))

    for input_str, output_str in pairs:
        input_path = Path(input_str)
        output_dir = Path(output_str)

        if not input_path.exists():
            print(f"Error: {input_path} not found", file=sys.stderr)
            sys.exit(1)

        process_image(
            input_path,
            output_dir,
            args.size_mm,
            args.dilation_mm,
            args.resolution_mm,
            faceless=args.faceless,
            center_diameter_mm=args.center_diameter_mm,
            depth_mm=args.depth_mm,
        )


if __name__ == "__main__":
    main()
