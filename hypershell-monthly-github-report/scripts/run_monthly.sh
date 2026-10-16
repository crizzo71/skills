#!/bin/zsh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
unset GITHUB_TOKEN GH_TOKEN
exec python3 "$SCRIPT_DIR/generate_monthly_report.py" "$@"
