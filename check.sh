#!/usr/bin/env bash
# Canonical quality gate — run this on every change. Lint, format check, and full tests.
# Usage: ./check.sh
set -euo pipefail

cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"

echo "==> ruff lint"
uv run ruff check .

echo "==> ruff format check"
uv run ruff format --check .

echo "==> pytest"
uv run pytest

echo "==> all checks passed ✓"
