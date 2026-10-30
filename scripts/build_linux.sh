#!/usr/bin/env bash
# ==============================================================================
# orang3D - Linux Standalone Binary Export Script
# Builds portable Linux x86_64 distribution bundle (dist/orang3d-linux-x86_64.tar.gz)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== Building orang3D for Linux ==="

# Check virtual environment
if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

# Ensure PyInstaller is installed
$PYTHON -m pip install --upgrade pyinstaller build

# Run build script
$PYTHON scripts/build_executable.py --clean --archive "$@"

echo "=== Linux Build Completed Successfully! ==="
echo "Check dist/ directory for binaries and archives."
