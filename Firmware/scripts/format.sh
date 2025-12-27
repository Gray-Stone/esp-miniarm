#!/usr/bin/env bash
set -euo pipefail

mode="${1:---all}"

if ! command -v yapf >/dev/null 2>&1; then
  echo "yapf not found. Install with: pip install -r requirements-dev.txt" >&2
  exit 1
fi

case "$mode" in
  --all)
    mapfile -t files < <(git ls-files '*.py')
    ;;
  --diff)
    mapfile -t files < <(git diff --name-only --diff-filter=ACMR -- '*.py')
    ;;
  --staged)
    mapfile -t files < <(git diff --name-only --cached --diff-filter=ACMR -- '*.py')
    ;;
  *)
    echo "Usage: $0 [--all|--diff|--staged]" >&2
    exit 2
    ;;
esac

if [ "${#files[@]}" -eq 0 ]; then
  exit 0
fi

python -m yapf --style .style.yapf -i "${files[@]}"

if [ "$mode" = "--staged" ]; then
  git add "${files[@]}"
fi
