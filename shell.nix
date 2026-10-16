{ pkgs ? import <nixpkgs> { } }:

# Everything the Music Assistant build needs from the system. Python's own
# dependencies are NOT here: they come from pyproject.toml and
# requirements_all.txt through uv (scripts/setup.sh does that), the same way
# upstream's devenv.nix does it. What nixpkgs provides is the interpreter and
# the native bits those dependencies need at build and run time.
let
  # Single source of truth for the Python version, as upstream's devenv.nix
  # does it too.
  pythonVersion = pkgs.lib.strings.removeSuffix "\n" (builtins.readFile ./.python-version);
  python = pkgs."python${pkgs.lib.replaceStrings [ "." ] [ "" ] pythonVersion}";
in
pkgs.mkShell {
  packages = [
    python
    pkgs.uv
    pkgs.ffmpeg_7 # upstream requires ffmpeg 6.1+; devenv.nix pins the 7 series
    pkgs.git
    pkgs.gcc
    pkgs.gnumake
    pkgs.pkg-config
    pkgs.openssl
    pkgs.curl
    pkgs.pre-commit
  ];

  # aiolibdatachannel ships a prebuilt .so that does not link libstdc++
  # itself, so the loader has to be told to preload it. Upstream's test job
  # sets the same thing.
  LD_PRELOAD = "${pkgs.stdenv.cc.cc.lib}/lib/libstdc++.so.6";

  shellHook = ''
    echo "python $(python --version 2>&1 | cut -d' ' -f2), ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)"
    echo "next: scripts/setup.sh   # .venv + dependencies"
  '';
}
