#!/usr/bin/env bash

if ! echo "${PATH}" | grep -qi "com.termux"; then
  echo "Not a termux Env, Skipping..."
  exit
fi

./scripts/install_ub_core.sh

grep -Ev "^#|google-generativeai|pillow" req.txt | xargs -n 1 pip install
