{ lib
, python3Packages
, fetchFromGitHub
, uv
}:

python3Packages.buildPythonPackage rec {
  pname = "gradescopeapi";
  version = "0.1.0"; # Update version as appropriate
  format = "pyproject";

  #  src = fetchFromGitHub {
  #    owner = "nyuoss";
  #    repo = "gradescope-api";
  #    # You'll need to update this with the specific commit or tag you want to use
  #    rev = "main"; # Replace with specific commit hash or tag for reproducibility
  #    sha256 = "sha256-k4q9XLDVqqCN0ugoVhKlcUW/i3DMIRTyDVg7Oi9uwBs=";
  #  };

  src = "${./gradescope-api}";

  nativeBuildInputs = with python3Packages; [
    setuptools
    uv
    hatchling
  ];

  propagatedBuildInputs = with python3Packages; [
    pytest
    beautifulsoup4
    fastapi
    python-dateutil
    python-dotenv
    requests-toolbelt
    tzdata
  ];

  pythonImportsCheck = [ "gradescopeapi" ]; # Adjust the import name if different

  meta = with lib; {
    description = "Python client for the Gradescope API";
    homepage = "https://github.com/nyuoss/gradescope-api";
    license = licenses.mit; # Update with the actual license
    maintainers = with maintainers; [ ];
  };
}
