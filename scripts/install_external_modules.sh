#!/usr/bin/env bash

if [ -z "${EXTRA_MODULES_REPO}" ]; then
    exit
fi

echo "Installing External Modules"

git clone -q "${EXTRA_MODULES_REPO}" "app/modules"

pip -q install --no-cache-dir -r app/modules/req*.txt


