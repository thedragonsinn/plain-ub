#!/usr/bin/env bash

if [ -z "${EXTRA_MODULES_REPO}" ]; then
    echo "EXTRA_MODULES_REPO not set, Skipping..."
    exit
fi

repo_name=$(basename "${EXTRA_MODULES_REPO}")

echo "Installing ${repo_name} to app/modules"

git clone -q "${EXTRA_MODULES_REPO}" "app/modules"

pip -q install --no-cache-dir -r app/modules/req*.txt

echo "Done"

