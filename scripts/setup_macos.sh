#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found."
  exit 1
fi

if command -v brew >/dev/null 2>&1; then
  if ! brew list portaudio >/dev/null 2>&1; then
    echo "Installing portaudio via Homebrew..."
    brew install portaudio
  fi
fi

python3 scripts/bootstrap_project.py "$@"

cat <<'EOF'

Next step:
  source scripts/activate_macos.sh
EOF
