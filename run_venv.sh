#!/usr/bin/env bash
set -euo pipefail

# This script is safe for both local development and GitHub Codespaces.
# In Codespaces, run it from the workspace root:
#   /workspaces/langchain_autocommit

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
VENV_DIR=".venv"

# Codespaces/container path should resolve from the repo root, not from .venv/bin
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO_ROOT}"

echo "[run_venv] Repo root: ${REPO_ROOT}"
echo "[run_venv] Using Python ${PY_VER} and venv at ${REPO_ROOT}/${VENV_DIR}"

# Prefer pyenv if available; otherwise use system `python3`
if command -v pyenv >/dev/null 2>&1; then
  PY_BIN="$(pyenv which python || true)"
else
  PY_BIN="$(command -v python3 || true)"
fi

if [[ -z "${PY_BIN}" ]]; then
  echo "No python3 found on PATH"
  exit 1
fi

# In the Codespaces container, the Node image may need python3.13-venv installed first.
if ! "${PY_BIN}" -m venv --help >/dev/null 2>&1; then
  echo "[run_venv] python venv support is missing. Attempting to install python3.13-venv..."
  sudo apt-get update
  sudo apt-get install -y python3.13-venv
fi

# Recreate the venv so the container has a clean, predictable environment.
rm -rf "${VENV_DIR}"
"${PY_BIN}" -m venv "${VENV_DIR}"

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r requirements.txt
"${VENV_DIR}/bin/python" -m pip install -e "${REPO_ROOT}"

echo "[run_venv] Environment ready."
echo "[run_venv] Python: ${REPO_ROOT}/${VENV_DIR}/bin/python"
echo "[run_venv] CLI: ${REPO_ROOT}/${VENV_DIR}/bin/autocommit"
echo "[run_venv] To activate later: source ${REPO_ROOT}/${VENV_DIR}/bin/activate"
