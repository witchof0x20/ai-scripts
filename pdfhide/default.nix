{ pkgs, python3 }:
let
  python = python3.withPackages (ps: [ ps.pikepdf ps.fpdf2 ]);
in
pkgs.writeShellScriptBin "pdfhide" ''
  exec ${python}/bin/python ${./pdfhide.py} "$@"
''
