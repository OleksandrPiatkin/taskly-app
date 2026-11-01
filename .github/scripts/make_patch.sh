#!/usr/bin/env bash
# Write a binary-safe git patch of the working-tree changes relative to HEAD, including new
# untracked files, excluding .agent-results/, .claude/, CLAUDE.md and .github/ (the agent action
# restores .claude/ from the base branch, so those paths may show as modified).
#
# Usage: make_patch.sh <out.patch>
#   An empty patch (no changes) is valid and produces an empty file.
#   Write <out.patch> outside the repository or under .agent-results/, otherwise a stale copy
#   from an earlier run would itself be included in the patch.
set -euo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
  echo "usage: make_patch.sh <out.patch>" >&2
  exit 2
fi

out_dir="$(dirname -- "$1")"
[[ -d "$out_dir" ]] || { echo "error: output directory does not exist: $out_dir" >&2; exit 2; }
out="$(cd -- "$out_dir" && pwd)/$(basename -- "$1")"

root="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "error: not inside a git repository" >&2; exit 2; }
cd -- "$root"
git rev-parse --verify --quiet HEAD >/dev/null || { echo "error: HEAD does not exist" >&2; exit 2; }

pathspec=(. ':(exclude).agent-results' ':(exclude).claude' ':(exclude)CLAUDE.md' ':(exclude).github')

# Record untracked (non-ignored) files as intent-to-add so `git diff HEAD` shows them as new files.
git add --intent-to-add -- "${pathspec[@]}"

tmp="$(mktemp)"
trap 'rm -f -- "$tmp"' EXIT
# Fixed options so user/CI git config (renames, external diff, textconv, colour) cannot change the output.
git -c core.quotepath=on -c diff.noprefix=false -c diff.mnemonicPrefix=false \
  diff --binary --full-index --no-renames --no-ext-diff --no-textconv --no-color \
  --ignore-submodules=none HEAD -- "${pathspec[@]}" >"$tmp"
mv -- "$tmp" "$out"
trap - EXIT

echo "wrote $out ($(wc -c <"$out") bytes, $(grep -c '^diff --git ' "$out" || true) file(s))" >&2
