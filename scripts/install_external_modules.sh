
if [ -z "${EXTRA_MODULES_REPO}" ]; then
    exit
fi

git clone "${EXTRA_MODULES_REPO}" "app/modules"

pip -q install --no-cache-dir -r req*.txt


