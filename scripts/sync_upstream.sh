#!/usr/bin/env bash
# Apply the official upstream diff BASE_TAG..TARGET_TAG onto the current branch.
# Every upstream hunk is applied by git itself (no hand porting), conflicts are left
# as markers, and the result goes to a NEW branch sync/upstream-<tag>-run<N>; the
# source branch is never modified.
set -uo pipefail

UPSTREAM=https://github.com/rikkahub/rikkahub.git
OUT_BRANCH="sync/upstream-${TARGET_TAG}-run${GITHUB_RUN_NUMBER:-0}"
REPORT_DIR=.sync
REPORT="$REPORT_DIR/upstream-${TARGET_TAG}-report.txt"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git fetch --no-tags "$UPSTREAM" \
  "refs/tags/${BASE_TAG}:refs/tags/up-${BASE_TAG}" \
  "refs/tags/${TARGET_TAG}:refs/tags/up-${TARGET_TAG}" || { echo "::error::fetch upstream failed"; exit 1; }

mkdir -p "$REPORT_DIR"
{
  echo "base=${BASE_TAG} target=${TARGET_TAG} ours=$(git rev-parse HEAD)"
  echo "merge-base(ours, target): $(git merge-base HEAD "up-${TARGET_TAG}" 2>/dev/null || echo none)"
  echo
  echo "== upstream commits (${BASE_TAG}..${TARGET_TAG}) =="
  git log --oneline --no-merges "up-${BASE_TAG}..up-${TARGET_TAG}"
  echo
  echo "== upstream changed files =="
  git diff --stat=200,160 "up-${BASE_TAG}" "up-${TARGET_TAG}"
  echo
  echo "== files ours changed relative to upstream ${BASE_TAG} (excluding .github) =="
  git diff --name-status "up-${BASE_TAG}" HEAD -- . ':(exclude).github'
} > "$REPORT"

# .github/ excluded: GITHUB_TOKEN may not push workflow-file changes.
git diff --binary "up-${BASE_TAG}" "up-${TARGET_TAG}" -- . ':(exclude).github' > /tmp/up.patch

set +e
git apply --3way --whitespace=nowarn /tmp/up.patch > /tmp/apply.log 2>&1
code=$?
set -e

unmerged=$(git diff --name-only --diff-filter=U)
mode="3way"
if [ "$code" -ne 0 ] && [ -z "$unmerged" ]; then
  # 3-way could not even start (e.g. missing preimage); fall back to per-hunk rejects.
  mode="reject-fallback"
  git reset -q --hard HEAD
  set +e
  git apply --reject --index --whitespace=nowarn /tmp/up.patch >> /tmp/apply.log 2>&1
  code=$?
  set -e
fi
rejects=$(git ls-files --others --exclude-standard | grep '\.rej$' || true)
n_conf=$(printf '%s\n' "$unmerged" | grep -c . || true)
n_rej=$(printf '%s\n' "$rejects" | grep -c . || true)

{
  echo
  echo "== apply mode=${mode} exit=${code} conflicted=${n_conf} rejects=${n_rej} =="
  cat /tmp/apply.log
  echo
  echo "== conflicted files (contain <<<<<<< markers) =="
  printf '%s\n' "$unmerged"
  echo
  echo "== reject files (.rej) =="
  printf '%s\n' "$rejects"
} >> "$REPORT"

git add -A
git commit -q -m "sync: apply upstream ${BASE_TAG}..${TARGET_TAG} (mode=${mode}, conflicts=${n_conf}, rejects=${n_rej})"
git push origin "HEAD:refs/heads/${OUT_BRANCH}"

echo "::notice::branch=${OUT_BRANCH} mode=${mode} conflicts=${n_conf} rejects=${n_rej}"
echo "branch=${OUT_BRANCH} mode=${mode} conflicts=${n_conf} rejects=${n_rej}" >> "$GITHUB_STEP_SUMMARY"
