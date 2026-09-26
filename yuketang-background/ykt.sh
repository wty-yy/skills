#!/usr/bin/env bash
set -euo pipefail
skill_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$skill_dir/scripts/ykt.sh" "$@"
