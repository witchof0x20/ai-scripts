{ pkgs, python3 }:
let
  python = python3.withPackages (ps: [ ps.pikepdf ]);
in
pkgs.writeShellScriptBin "pdfhide" ''
  exec ${python}/bin/python ${./pdfhide.py} "$@"
''
