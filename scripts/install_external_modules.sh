#!/usr/bin/env bash

if [[ -z "$EXTRA_MODULES_REPO" ]]; then
	echo "EXTRA_MODULES_REPO not set, Skipping..."
	exit
fi

path="app/modules"

if [[ -d "$path" ]]; then
	echo "running git pull on external repo..."
	git -C "$path" fetch --depth=1 origin
	git -C "$path" reset --hard FETCH_HEAD
else
	echo "Installing ${EXTRA_MODULES_REPO##*/} to app/modules..."

	git clone -q "$EXTRA_MODULES_REPO" "$path" || {
		echo "Failed to clone external repo"
		exit
	}
fi

$(type -p uv) pip install --no-cache-dir -r "$path"/req*.txt

echo "Done"
