#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Yasin-Core Termux bootstrap.
# Termux is a first-class deployment target; use the current Termux Python.

if [ "$(uname -o 2>/dev/null || true)" != "Android" ] && [ "${PREFIX:-}" != "/data/data/com.termux/files/usr" ]; then
  echo "ERROR: this bootstrap is for Termux on Android." >&2
  exit 1
fi

pkg update -y
pkg upgrade -y
pkg install -y python git clang make pkg-config openssl openssl-tool libffi cmake patchelf

PYTHON_BIN="${PREFIX}/bin/python"
"${PYTHON_BIN}" --version

rm -rf .venv
"${PYTHON_BIN}" -m venv .venv
# Keep the environment isolated. Yasin-Core has no native Python dependency that
# requires Termux's global site-packages; this avoids accidental contamination.
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
python -m pip install "pytest>=7.4,<10"

python - <<'PY'
import importlib.metadata as metadata
import sys
import yasin_core

print(f"Python: {sys.version}")
print(f"Yasin-Core: {metadata.version('yasin-core')}")
print(f"Yasin-Core import: OK ({yasin_core.__file__})")
PY

python -m pytest -q

printf '%s\n' \
  'Yasin-Core Termux installation completed successfully.' \
  'Activate: source .venv/bin/activate' \
  'Tests: python -m pytest -q'
