
if [ -z "${EXTRA_MODULES_REPO}" ]; then
    exit
fi

git clone "${EXTRA_MODULES_REPO}" "app/modules"

pip install -r app/modules/req*txt


