#!/usr/bin/env bash
#
# rename_to_cortext.sh — rename the Python package/distribution from
# `cortex_v5` (module) / `cortex-v5` (dist) to a single target name.
#
# Self-contained: operates on this repository only.
#
# What it does:
#   1. git-moves the package directory   cortex_v5/ -> <TARGET>/
#   2. rewrites the module identifier     cortex_v5 -> <TARGET>
#   3. rewrites the distribution name      cortex-v5 -> <TARGET>
#      (covers `pip install cortex-v5[..]` in docs too)
#
# The class name `CortexV5` is intentionally left untouched.
# Versioned benchmark labels (v3/v5) and `run_benchmark_v5.py` are untouched.
#
# Usage:   scripts/rename_to_cortext.sh [target_name]    (default: cortext)
# Review afterwards with `git status` / `git diff`.
set -euo pipefail

TARGET="${1:-cortext}"

cd "$(git rev-parse --show-toplevel)"

# Paths we never rewrite or descend into.
PRUNE=( -path ./.git -o -path ./venv -o -path ./.venv -o -path ./dist \
        -o -path ./build -o -path './*.egg-info' -o -path ./.pytest_cache \
        -o -path ./.ruff_cache -o -path './**/__pycache__' )

# 1. Move the package directory.
if [[ -d cortex_v5 && ! -d "$TARGET" ]]; then
  git mv cortex_v5 "$TARGET"
  echo "moved cortex_v5/ -> $TARGET/"
fi

# 2 + 3. Rewrite identifiers inside text files.
mapfile -t FILES < <(
  find . \( "${PRUNE[@]}" \) -prune -o \
    -type f \( -name '*.py' -o -name '*.toml' -o -name '*.md' \
               -o -name '*.cfg' -o -name '*.txt' -o -name '*.ini' \) -print
)

for f in "${FILES[@]}"; do
  if grep -Iq . "$f"; then
    sed -i \
      -e "s/cortex_v5/${TARGET}/g" \
      -e "s/cortex-v5/${TARGET}/g" \
      "$f"
  fi
done

echo "rewrote cortex_v5 / cortex-v5 -> ${TARGET} in ${#FILES[@]} files"
echo
echo "Next steps:"
echo "  - review:  git status && git diff"
echo "  - retest:  pip install -e '.[dev]' && pytest"
echo "  - the class name CortexV5 was left unchanged on purpose"
