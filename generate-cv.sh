#!/bin/bash

set -e

echo "CV PDF Generator"
echo "================"

if ! command -v npm &> /dev/null; then
    echo "Error: npm is not installed. Please install Node.js first."
    exit 1
fi

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
else
    echo "Dependencies already installed"
fi

echo "Generating vectorial PDF..."
npm run export-pdf

echo ""
echo "Done! Your PDF is ready to download from the website."
