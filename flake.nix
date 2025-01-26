{
  description = "Nextcloud Calendar Event Uploader";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay.url = "github:oxalica/rust-overlay";
    naersk.url = "github:nix-community/naersk";
  };

  outputs = { self, nixpkgs, flake-utils, rust-overlay, naersk }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = (import nixpkgs) {
          inherit system;
          overlays = [ (import rust-overlay) ];
        };
        rust_toolchain = pkgs.rust-bin.stable.latest;
        naersk' = pkgs.callPackage naersk {
          rustc = rust_toolchain.minimal;
          cargo = rust_toolchain.minimal;
        };
        deps = {
          ffxiv-otp = {
            nativeBuildInputs = [ pkgs.pkg-config pkgs.openssl ];
          };
        };
      in
      {
        packages.cal-upload = pkgs.callPackage ./cal-upload/default.nix { };
        packages.reminder = pkgs.callPackage ./reminder/default.nix { };
        packages.ffxiv-otp = naersk'.buildPackage {
          nativeBuildInputs = deps.ffxiv-otp.nativeBuildInputs;
          src = ./ffxiv-otp;
        };

        devShells.ffxiv-otp = pkgs.mkShell {
          nativeBuildInputs = deps.ffxiv-otp.nativeBuildInputs ++ [
            (rust_toolchain.default.override {
              extensions = [ "rust-src" "rustfmt" "rust-analyzer" "clippy" ];
            })
          ];
        };
      }
    )) // {
      nixosModules.reminder = (import ./reminder/module.nix self.packages);
    };
}
