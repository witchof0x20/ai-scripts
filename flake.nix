{
  description = "AI tools";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay.url = "github:oxalica/rust-overlay";
    crane.url = "github:ipetkov/crane";
  };

  outputs = { self, nixpkgs, flake-utils, rust-overlay, crane }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = (import nixpkgs) {
          inherit system;
          overlays = [ (import rust-overlay) ];
        };
        rust_toolchain =
          p: pkgs.rust-bin.stable.latest;
        craneLib = (crane.mkLib pkgs).overrideToolchain (p: (rust_toolchain p).minimal);
        deps = {
          ffxiv-otp = {
            nativeBuildInputs = [ pkgs.pkg-config pkgs.openssl ];
          };
          hitron-monitor = {
            nativeBuildInputs = [ pkgs.pkg-config pkgs.openssl ];
          };
        };
      in
      rec {
        packages.cal-upload = pkgs.callPackage ./cal-upload/default.nix { };
        packages.reminder = pkgs.callPackage ./reminder/default.nix { };
        packages.hitron-modeminfo = pkgs.callPackage ./hitron/default.nix { };
        packages.ffxiv-otp = craneLib.buildPackage {
          nativeBuildInputs = deps.ffxiv-otp.nativeBuildInputs;
          src = ./ffxiv-otp;
        };
        packages.hitron-monitor = craneLib.buildPackage {
          nativeBuildInputs = deps.hitron-monitor.nativeBuildInputs;
          src = ./hitron;
        };
        packages.gradescope-api = pkgs.callPackage ./gradescope-utils/gradescope-api.nix { };
        devShells.ffxiv-otp = pkgs.mkShell {
          nativeBuildInputs = deps.ffxiv-otp.nativeBuildInputs ++ [
            ((rust_toolchain pkgs).default.override {
              extensions = [ "rust-src" "rustfmt" "rust-analyzer" "clippy" ];
            })
          ];
        };
        devShells.gradescope-utils = pkgs.mkShell {
          nativeBuildInputs = with pkgs; [
            (python3.withPackages (ps: [ packages.gradescope-api ]))
          ];
        };
      }
    )) // {
      nixosModules.reminder = (import ./reminder/module.nix self.packages);
      nixosModules.hitron-monitor = (import ./hitron/module.nix self.packages);
    };
}
