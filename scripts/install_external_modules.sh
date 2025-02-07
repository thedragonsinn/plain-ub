#!/usr/bin/env bash

[ -z "$EXTRA_MODULES_REPO" ] && { echo "EXTRA_MODULES_REPO not set, Skipping..."; exit; }

repo_name=$(basename "$EXTRA_MODULES_REPO")

echo "Installing ${repo_name} to app/modules"

git clone -q "$EXTRA_MODULES_REPO" "app/modules" || { echo "Failed to clone external repo"; exit; }

pip -q install --no-cache-dir -r app/modules/req*.txt

echo "Done"

