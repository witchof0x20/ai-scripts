// Faceless claudemoji - claudespinny
// Total model size: 124.35mm
// Center hole diameter: 36.40mm
// Center position: (64.77, 62.00)mm

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
face_depth = 4.5;
center_x = 64.7701;
center_y = 62.0025;
padding_margin = 1.0;  // extra radius for foam padding
center_diameter = 36.4 + 2 * padding_margin;

// Retaining ring
pcb_diameter = 38.7;
wall_thickness = 3.0;
ring_height = 6.0;
ring_od = pcb_diameter + 2 * wall_thickness;

// USB-C cutout (12mm port + 2mm clearance each side)
usb_cutout_width = 16.0;
usb_angle = 270;

// Button cutouts: rectangular slots through the full wall
button_slot_width = 5.0;   // tangential width
button_slot_height = 2.5; // Z height (1.5mm button + tolerance, at back of ring)
boot_angle = 162;   // BOOT: 18° CW from west
power_angle = 138; // Power: 24° CW from BOOT (42° CW from west)

// Bezel cover ring (thin ring over display bezel)
screen_diameter = 34.6;
bezel_layer_height = 0.5;

// --- Modules ---

module outline_part() {
    difference() {
        linear_extrude(height=face_depth, convexity=10)
            import("outline.svg");
        translate([center_x, center_y, -0.1])
            cylinder(h=face_depth + 0.2, d=center_diameter, $fn=200);
    }
}

module flower_part() {
    difference() {
        linear_extrude(height=face_depth, convexity=10)
            import("flower.svg");
        translate([center_x, center_y, -0.1])
            cylinder(h=face_depth + 0.2, d=center_diameter, $fn=200);
    }
}

// Rectangular button slot through the full ring wall at a given angle.
// Positioned at the back (open end) of the ring where the buttons are.
module button_slot(angle) {
    rotate([0, 0, angle])
        translate([-button_slot_width/2, pcb_diameter/2 - 0.1, ring_height - button_slot_height - 1.5])
            cube([button_slot_width, wall_thickness + 0.2, button_slot_height + 0.1]);
}

module ring_part() {
    translate([center_x, center_y, face_depth])
    difference() {
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
    }
}

module bezel_ring_part() {
    // Outer diameter slightly oversized to overlap into flower/outline,
    // so the slicer merges them instead of drawing separate perimeters.
    translate([center_x, center_y, 0])
        difference() {
            cylinder(h=bezel_layer_height, d=center_diameter + 1.0, $fn=200);
            translate([0, 0, -0.1])
                cylinder(h=bezel_layer_height + 0.2, d=screen_diameter, $fn=200);
        }
}

// Plain annulus for fitment testing (no character artwork)
module frame_part() {
    translate([center_x, center_y, 0])
    union() {
        // Flat annulus at face depth
        difference() {
            cylinder(h=face_depth, d=ring_od, $fn=200);
            translate([0, 0, -0.1])
                cylinder(h=face_depth + 0.2, d=center_diameter, $fn=200);
        }
        // Bezel ring
        difference() {
            cylinder(h=bezel_layer_height, d=center_diameter + 1.0, $fn=200);
            translate([0, 0, -0.1])
                cylinder(h=bezel_layer_height + 0.2, d=screen_diameter, $fn=200);
        }
        // Retaining ring on back
        translate([0, 0, face_depth])
        difference() {
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
        }
    }
}

// --- Heat set insert fastening (M2 inserts, radial through side walls) ---
insert_od = 3.2;               // M2 heat set insert outer diameter
insert_depth = 3.0;            // insert length (fits in 3mm ring wall)
bolt_clearance = 2.4;          // M2 bolt clearance hole
// 3 insert positions, avoiding USB (270°) and buttons (138°, 162°)
insert_angles = [60, 210, 315];
insert_z = ring_height / 2;    // mid-height of ring

// Radial hole from outer surface inward (for heat set insert or bolt)
module radial_hole(angle, z_pos, diameter, depth, from_radius) {
    rotate([0, 0, angle])
        translate([0, from_radius + 0.1, z_pos])
            rotate([90, 0, 0])
                cylinder(h=depth + 0.1, d=diameter, $fn=50);
}

// --- Back shell ---
back_shell_thickness = 2.0;    // wall and plate thickness
battery_depth = 7.0;           // cavity behind ring for battery + connectors
back_total_depth = ring_height + battery_depth;
back_od = ring_od + 2 * back_shell_thickness;
back_clearance = 0.3;          // gap so shell slides over ring
m2_hole_diameter = 2.4;        // M2 + 0.4mm clearance (was 2.2)

// PCB screw positions relative to PCB center (assembly coords, USB at 270°)
screw_x_offset = 11.04;
screw_y_offset = 10.80;        // +Y = away from USB (toward 90°)
screw_usb_offset = 15.87;      // toward USB (-Y / 270°)

module back_button_slot(angle) {
    // Extends from button position all the way to the open edge (z=0)
    rotate([0, 0, angle])
        translate([-button_slot_width/2, ring_od/2 - 0.1, -0.1])
            cube([button_slot_width, back_shell_thickness + 0.2, ring_height - 1.5 + 0.1]);
}

module back_part() {
    translate([center_x, center_y, face_depth])
    difference() {
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

        // Bolt clearance holes for heat set inserts (radial, through side wall)
        for (a = insert_angles)
            radial_hole(a, insert_z, bolt_clearance, back_shell_thickness, ring_od/2);
    }
}

// --- Part selection ---
if (part == "outline") {
    outline_part();
} else if (part == "flower") {
    flower_part();
} else if (part == "ring") {
    ring_part();
} else if (part == "bezel_ring") {
    bezel_ring_part();
} else if (part == "frame") {
    frame_part();
} else if (part == "back") {
    back_part();
} else {
    // Assembly: all parts together
    outline_part();
    flower_part();
    ring_part();
    bezel_ring_part();
    back_part();
}
