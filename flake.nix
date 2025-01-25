{
  description = "Nextcloud Calendar Event Uploader";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        packages.cal-upload = pkgs.callPackage ./cal-upload/default.nix { };
        packages.reminder = pkgs.callPackage ./reminder/default.nix { };
      }
    )) // {
      nixosModules.reminder = (import ./reminder/module.nix self.packages);
    };
}
