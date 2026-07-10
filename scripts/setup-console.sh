#!/usr/bin/env bash
#
# Initialize the upstream harness `console` package as a sparse git submodule.
#
# The console UI lives inside the microsoft/agent-framework repo as an
# unpublished sample (no PyPI package). Rather than vendoring it, we reference it
# via a git submodule at external/agent-framework, pinned to the SHA recorded in
# .gitmodules (the python-1.9.0 tag). To avoid downloading the whole (large)
# repo, we use a blobless partial clone plus a cone-mode sparse-checkout that
# materializes only the harness console directory.
#
# Idempotent: safe to re-run. harness/harness_agent.py adds the resulting
# directory to sys.path so `import console` works.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SUB="external/agent-framework"
SPARSE_PATH="python/samples/02-agents/harness/console"
URL="$(git config -f .gitmodules submodule."$SUB".url)"

echo "==> Setting up sparse submodule '$SUB' (console only)"

# Blobless, no-checkout clone keeps the download tiny; git only fetches file
# contents on demand and we never check out the full tree.
if [ ! -e "$SUB/.git" ]; then
  echo "==> Cloning $URL (blobless, no checkout)"
  git clone --filter=blob:none --no-checkout "$URL" "$SUB"
fi

echo "==> Restricting checkout to $SPARSE_PATH"
git -C "$SUB" sparse-checkout init --cone
git -C "$SUB" sparse-checkout set "$SPARSE_PATH"

# Check out the exact commit pinned by the parent repo (.gitmodules / index).
echo "==> Checking out pinned submodule commit"
git submodule update --init "$SUB"

echo "==> Done. Console package available at:"
echo "    $ROOT/$SUB/$SPARSE_PATH"
