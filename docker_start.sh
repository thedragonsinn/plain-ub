#!/usr/bin/env bash

export PIP_ROOT_USER_ACTION=ignore

if [ -d "ubot" ]; then
    rm -rf ubot
    echo "removed older ubot dir"
fi

run_extra_boot_scripts() {
  local directory="scripts"

  if [[ -d "$directory" ]]; then

    if [[ -n "$(ls -A "$directory")" ]]; then

      for file in "$directory"/*; do

        if [[ -f "$file" && -x "$file" ]]; then

          echo "Executing $file"
          "$file"

        fi
      done
    fi
  fi
}


echo "${GH_TOKEN}" > ~/.git-credentials
git config --global credential.helper store

git clone -q --depth=1 "${UPSTREAM_REPO:-"https://github.com/thedragonsinn/plain-ub"}" ubot
cd ubot
pip -q install --no-cache-dir -r req*.txt
run_extra_boot_scripts

bash run
