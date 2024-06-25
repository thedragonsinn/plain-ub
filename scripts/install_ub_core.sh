dual_mode_arg=""

if [ ! -z "${USE_DUAL_BRANCH}" ]; then
    dual_mode_arg="@dual_mode"
fi

pip -q install --no-cache-dir --force-reinstall $1 "git+https://github.com/thedragonsinn/ub-core${dual_mode_arg}"