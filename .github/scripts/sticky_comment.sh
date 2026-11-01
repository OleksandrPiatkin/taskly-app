#!/usr/bin/env bash
# Create or update ONE test-agent comment on a pull request, identified by a hidden marker.
#
# Usage: sticky_comment.sh <pr-number> <comment.md>
#   Requires GH_TOKEN (pull-requests: write / issues: write) and GITHUB_REPOSITORY (owner/repo).
#   Optional STICKY_AUTHOR (default github-actions[bot]): only that author's comments are updated.
#   The comment file must contain the marker <!-- test-agent-report --> (build_comment.py adds it).
set -euo pipefail

MARKER='<!-- test-agent-report -->'
AUTHOR="${STICKY_AUTHOR:-github-actions[bot]}"

die() { echo "error: $*" >&2; exit 2; }

[[ $# -eq 2 ]] || die "usage: sticky_comment.sh <pr-number> <comment.md>"
pr="$1"; file="$2"
[[ "$pr" =~ ^[1-9][0-9]*$ ]] || die "PR number must be a positive integer, got '$pr'"
[[ -f "$file" ]] || die "comment file not found: $file"
[[ -n "${GH_TOKEN:-}" ]] || die "GH_TOKEN is not set"
[[ "${GITHUB_REPOSITORY:-}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] \
  || die "GITHUB_REPOSITORY must be owner/repo, got '${GITHUB_REPOSITORY:-}'"
grep -qF -- "$MARKER" "$file" || die "comment file does not contain the marker $MARKER"
[[ "$AUTHOR" =~ ^[A-Za-z0-9_.-]+(\[bot\])?$ ]] || die "STICKY_AUTHOR is not a valid login: '$AUTHOR'"
command -v gh >/dev/null || die "gh CLI not found"

# Request body as JSON, built with the stdlib so the comment text is never interpreted by a shell or gh flags.
body="$(mktemp)"
trap 'rm -f -- "$body"' EXIT
python3 -c 'import json, sys; json.dump({"body": open(sys.argv[1], encoding="utf-8").read()}, sys.stdout)' \
  "$file" >"$body"

# --jq runs per page with --paginate, so collect ids from all pages and take the first.
ids="$(gh api --paginate "repos/$GITHUB_REPOSITORY/issues/$pr/comments?per_page=100" \
  --jq ".[] | select(.user.login == \"$AUTHOR\" and (.body | contains(\"$MARKER\"))) | .id")" \
  || die "could not list comments on PR #$pr"
existing="${ids%%$'\n'*}"

if [[ -n "$existing" ]]; then
  [[ "$existing" =~ ^[0-9]+$ ]] || die "unexpected comment id from API: '$existing'"
  gh api -X PATCH "repos/$GITHUB_REPOSITORY/issues/comments/$existing" --input "$body" --jq '.html_url'
  echo "updated comment $existing on PR #$pr" >&2
else
  gh api -X POST "repos/$GITHUB_REPOSITORY/issues/$pr/comments" --input "$body" --jq '.html_url'
  echo "created comment on PR #$pr" >&2
fi
