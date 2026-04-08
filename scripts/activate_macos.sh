#!/usr/bin/env bash

if [ -n "${ZSH_VERSION:-}" ]; then
  SCRIPT_PATH="${(%):-%N}"
elif [ -n "${BASH_VERSION:-}" ]; then
  SCRIPT_PATH="${BASH_SOURCE[0]}"
else
  SCRIPT_PATH="$0"
fi

PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"

if [ ! -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
  echo "Virtual environment not found at $PROJECT_ROOT/.venv"
  return 1 2>/dev/null || exit 1
fi

if [ ! -f "$PROJECT_ROOT/.project-env.sh" ]; then
  echo "Environment file not found at $PROJECT_ROOT/.project-env.sh"
  echo "Run ./scripts/setup_macos.sh first."
  return 1 2>/dev/null || exit 1
fi

source "$PROJECT_ROOT/.venv/bin/activate"
source "$PROJECT_ROOT/.project-env.sh"

echo "Activated multimodal toolkit environment."
echo "Python: $(command -v python)"
