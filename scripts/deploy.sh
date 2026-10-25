#!/usr/bin/env bash
# Build on the Mac and stage the plugin on the Deck. The copy into the plugins
# folder needs root, so this prints that one command for you to run.
# Decky live-reloads on the copy: never restart plugin_loader (an old plugin
# process can survive the restart and keep the keypad grabbed).
set -euo pipefail

host="${1:?usage: scripts/deploy.sh <host>}"
stage="decky-tartarus-stage"
cd "$(dirname "$0")/.."

pnpm build
rsync -a --delete --exclude '__pycache__' \
  dist main.py plugin.json package.json py_modules LICENSE "$host:~/$stage/"

echo
echo "Staged on $host. Now run:"
echo "  ssh -t $host 'sudo mkdir -p /home/deck/homebrew/plugins/decky-tartarus && sudo cp -r /home/deck/$stage/. /home/deck/homebrew/plugins/decky-tartarus/'"
