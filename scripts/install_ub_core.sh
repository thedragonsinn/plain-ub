#!/usr/bin/env bash

dual_mode_arg=""

[ -n "$USE_DUAL_BRANCH" ] && dual_mode_arg="@dual_mode"

pip -q install --no-cache-dir --force-reinstall "git+https://github.com/thedragonsinn/ub-core${dual_mode_arg}"