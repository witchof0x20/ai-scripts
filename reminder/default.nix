{ python3Packages }:
python3Packages.buildPythonApplication {
  pname = "discord-reminder";
  version = "0.1.0";
  src = ./.;

  propagatedBuildInputs = with python3Packages; [
    requests
  ];

  format = "other";

  installPhase = ''
    mkdir -p $out/bin
    cp reminder.py $out/bin/discord-reminder
  '';
}
