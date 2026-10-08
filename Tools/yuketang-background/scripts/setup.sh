#!/usr/bin/env bash
set -euo pipefail
skill_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m venv "$skill_dir/.venv"
"$skill_dir/.venv/bin/python" -m pip install -r "$skill_dir/requirements.txt"
