#!/usr/bin/env bash
# Build and zip the plugin for Decky's "Install from zip": out/decky-tartarus.zip
# holds one top-level decky-tartarus/ folder.
set -euo pipefail
cd "$(dirname "$0")/.."

name=decky-tartarus
pnpm build
rm -rf out
mkdir -p "out/$name/dist"
cp dist/index.js "out/$name/dist/"
cp main.py plugin.json package.json LICENSE README.md "out/$name/"
rsync -a --exclude '__pycache__' py_modules "out/$name/"
(cd out && zip -qrX "$name.zip" "$name")
rm -rf "out/$name"
echo "out/$name.zip"
