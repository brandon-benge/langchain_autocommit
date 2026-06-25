#!/bin/bash
# Wrapper script for autocommit that ensures virtual environment is activated

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate the virtual environment
source "$SCRIPT_DIR/../venv/bin/activate"

# Run the autocommit CLI via the package module
python3 -m autocommit.cli "$@"