#!/usr/bin/env bash
#
# install.sh — plug-and-play installer for the Cortext memory plugin for Hermes.
#
# What it does (idempotent):
#   1. Ensures the `cortext` library is importable (pip install cortext-memory).
#   2. Symlinks this plugin into $HERMES_HOME/plugins/cortext.
#   3. Prints the next step and a ready-to-paste config.yaml block.
#
# If Hermes is not detected, it explains how to use Cortext as a plain library
# instead (LangChain/LangGraph/your own loop) and exits cleanly.
#
# Usage:
#   ./install.sh                # symlink install (tracks updates)
#   ./install.sh --copy         # copy instead of symlink
#   HERMES_HOME=/path ./install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SRC="$SCRIPT_DIR/cortext"
MODE="${1:-symlink}"

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

echo "› Cortext → Hermes plugin installer"

# 1. Library availability.
if python3 -c "import cortext" >/dev/null 2>&1; then
  echo "  ✓ cortext library already installed"
else
  echo "  • installing cortext-memory from PyPI…"
  python3 -m pip install --upgrade cortext-memory
fi

# 2. Hermes detection.
if [[ ! -d "$HERMES_HOME" ]]; then
  cat <<EOF

  ⚠ Hermes not detected at: $HERMES_HOME
    (set HERMES_HOME if it lives elsewhere)

  You don't need Hermes to use Cortext. It's a framework-agnostic library:

      from cortext import CortextV5
      cortex = CortextV5(namespace="myapp")
      cortex.remember(what="...", who=["alice"])
      context, _ = cortex.recall("what did alice say?")

  Or the neutral chat bridge (LangChain / LangGraph / any loop):

      from cortext.integration import AgentMemoryBridge
      bridge = AgentMemoryBridge(namespace="session-1")
      ctx = bridge.recall_context(user_input)
      bridge.store_turn(user_input, reply)

  See docs/INTEGRATION.md for per-framework examples.
EOF
  exit 0
fi

# 3. Install the plugin.
mkdir -p "$HERMES_HOME/plugins"
DEST="$HERMES_HOME/plugins/cortext"

if [[ "$MODE" == "--copy" ]]; then
  rm -rf "$DEST"
  cp -r "$PLUGIN_SRC" "$DEST"
  echo "  ✓ copied plugin to $DEST"
else
  ln -sfn "$PLUGIN_SRC" "$DEST"
  echo "  ✓ symlinked $DEST → $PLUGIN_SRC"
fi

cat <<EOF

  Next step — activate it:

      hermes memory setup            # pick "cortext", then configure

  …or set it manually in \$HERMES_HOME/config.yaml:

      memory:
        provider: cortext
        cortext:
          namespace: hermes
          max_context_tokens: 300
          validation_policy: warn
          dream_agent: true

  Done. Memory is recalled before each turn and stored after — no tool needed.
EOF
