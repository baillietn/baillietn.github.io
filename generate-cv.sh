#!/bin/bash
# Regenerates every version of the CV from _cv/cv.yml.

set -e
cd "$(dirname "$0")"

echo "CV Generator"
echo "============"

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Installing dependencies..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet -r _cv/requirements.txt
    .venv/bin/playwright install chromium
else
    echo "Dependencies already installed"
fi

echo "Generating the CV from _cv/cv.yml..."
.venv/bin/python _cv/generate.py

echo ""
echo "Done! Commit the generated files to publish them."
