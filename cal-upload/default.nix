{ pkgs, python3 }:
let pythonPkgs = python3.pkgs; in
pythonPkgs.buildPythonApplication {
  pname = "cal-upload";
  version = "0.1.0";
  format = "pyproject";

  src = ./.;

  nativeBuildInputs = with pythonPkgs; [
    setuptools
  ];

  propagatedBuildInputs = with pythonPkgs; [
    caldav
    icalendar
    pyperclip
  ];

  preBuild = ''
    cat > pyproject.toml << EOF
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "nextcloud-cal-upload"
    version = "0.1.0"
    EOF

    cat > setup.py << EOF
    from setuptools import setup
    setup(
        name="nextcloud-cal-upload",
        version="0.1.0",
        py_modules=["cal_upload"],
        entry_points={
            "console_scripts": [
                "cal-upload=cal_upload:main",
            ],
        },
    )
    EOF
    mkdir -p $out/bin
    mv cal_upload.py $out/bin/cal-upload
  '';
}
