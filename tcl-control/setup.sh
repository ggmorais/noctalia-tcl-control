#!/bin/sh
set -eu

plugin_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
env_dir="$data_home/tcl-control/venv"

if [ "$(id -u)" = 0 ]; then
    echo "Run this script as your desktop user, not root." >&2
    exit 1
fi

echo "Preparing an isolated Python environment (no system packages changed)…"
python3 -m venv "$env_dir"
"$env_dir/bin/python" -m pip install --disable-pip-version-check -r "$plugin_dir/backend/requirements.txt"
"$env_dir/bin/python" "$plugin_dir/backend/configure.py"
echo "Ready. Enable ggmorais/tcl-control in Noctalia, then add its Home shortcut or bar widget."
