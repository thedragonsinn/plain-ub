#!/usr/bin/env bash

grep -qi "com.termux" <<< "$PATH" || { echo "Not a termux Env, Skipping..."; exit; }

mkdir -p "${HOME}/.config/pip" > /dev/null 2>&1

echo -e '[global]\nextra-index-url = https://termux-user-repository.github.io/pypi/' > "${HOME}/.config/pip/pip.conf"

./scripts/install_ub_core.sh

grep -Ev "^#|openai" req.txt | xargs -n 1 pip install
