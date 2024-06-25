if ! echo "${PATH}" | grep -qi "com.termux"; then
  echo "Not a termux Env, Skipping..."
  exit
fi

ub_core_req_url="https://github.com/thedragonsinn/ub-core/raw/main/requirements.txt"

curl -fsSL ${ub_core_req_url} | grep -Ev "uvloop|psutil" | xargs pip install 

./scripts/install_ub_core.sh "--no-deps"

grep -Ev "google-generativeai|pillow" req.txt | xargs -n 1 pip install