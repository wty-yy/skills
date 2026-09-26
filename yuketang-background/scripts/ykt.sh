#!/usr/bin/env bash
set -euo pipefail
skill_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$skill_dir/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
    printf '%s\n' '缺少 Python 环境，请先运行 scripts/setup.sh' >&2
    exit 1
fi
exec "$python_bin" "$skill_dir/scripts/yuketang.py" "$@"
