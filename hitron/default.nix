{ python3Packages }:
python3Packages.buildPythonApplication {
  pname = "hitron-modeminfo";
  version = "0.1.0";
  src = ./.;

  propagatedBuildInputs = with python3Packages; [
    requests
  ];

  format = "other";

  installPhase = ''
    mkdir -p $out/bin
    cp modeminfo.py $out/bin/hitron-modeminfo
  '';
}
