#!/usr/bin/env bash
set -euo pipefail

GH_CMD=""
if command -v gh >/dev/null 2>&1; then
  GH_CMD="gh"
elif command -v gh.exe >/dev/null 2>&1; then
  GH_CMD="gh.exe"
elif [[ -x "/c/Program Files/GitHub CLI/gh.exe" ]]; then
  GH_CMD="/c/Program Files/GitHub CLI/gh.exe"
else
  echo "GitHub CLI (gh) is required. Install it first: https://cli.github.com/"
  exit 1
fi

if ! "$GH_CMD" auth status >/dev/null 2>&1; then
  echo "You are not authenticated with GitHub CLI. Run: gh auth login"
  exit 1
fi

remote_url="$(git remote get-url origin)"
repo="$(printf '%s' "$remote_url" | sed -E 's#(git@|https://)github.com[:/]##; s#\.git$##')"

if [[ -z "$repo" ]]; then
  echo "Could not detect repository from origin remote URL."
  exit 1
fi

protect_branch() {
  local branch="$1"
  echo "Applying protection to ${repo}:${branch}"

  local payload
  payload=$(cat <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Commit Message Check"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON
)

  "$GH_CMD" api \
    --method PUT \
    -H "Accept: application/vnd.github+json" \
    "repos/${repo}/branches/${branch}/protection" \
    --input - <<<"$payload"
}

protect_branch "main"
protect_branch "stg"
protect_branch "dev"

echo "Branch protection applied for main, stg, dev in ${repo}"
