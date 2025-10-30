#!/usr/bin/env bash
set -euo pipefail

# very small YAML key extractor: key: "value" or key: value
yaml_get () {
  local key="$1"
  local default="${2:-}"
  local val
  val=$(awk -v k="$key" '
    BEGIN{FS=": *"}
    $1==k {
      # join rest of fields back in case of colon in value
      $1=""; sub(/^: */,"")
      gsub(/"/,"",$0); gsub(/'\''/,"",$0)
      print $0
      exit
    }' params.yaml || true)
  if [[ -z "${val:-}" ]]; then
    echo "$default"
  else
    echo "$val"
  fi
}

PY_VER=$(yaml_get "python_version" "3.10")
VENV_DIR=$(yaml_get "venv_dir" ".venv")

echo "[run_venv] Using Python ${PY_VER} and venv at ${VENV_DIR}"

# Prefer pyenv if available; otherwise use system `python3`
if command -v pyenv >/dev/null 2>&1; then
  PY_BIN="$(pyenv which python || true)"
else
  PY_BIN="$(command -v python3)"
fi

if [[ -z "${PY_BIN}" ]]; then
  echo "No python3 found on PATH"; exit 1
fi

$PY_BIN -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip
pip install -r requirements.txt

echo "[run_venv] Environment ready. To activate later: source ${VENV_DIR}/bin/activate"
