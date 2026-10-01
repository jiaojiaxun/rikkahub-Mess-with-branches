#!/usr/bin/env bash
# Three-way merge of the official upstream BASE_TAG..TARGET_TAG into the current
# branch, using upstream BASE_TAG as the explicit merge base (the fork has no shared
# git history with upstream). Result goes to a NEW branch; the source branch is
# never modified. Conflicts are left as <<<<<<< markers for review.
set -uo pipefail

UPSTREAM=https://github.com/rikkahub/rikkahub.git
OUT_BRANCH="sync/upstream-${TARGET_TAG}-merge-run${GITHUB_RUN_NUMBER:-0}"
TMP=/tmp/sync
mkdir -p "$TMP"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git --version

git fetch --no-tags "$UPSTREAM" \
  "refs/tags/${BASE_TAG}:refs/tags/up-${BASE_TAG}" \
  "refs/tags/${TARGET_TAG}:refs/tags/up-${TARGET_TAG}" || { echo "::error::fetch upstream failed"; exit 1; }

OURS=$(git rev-parse HEAD)

set +e
git merge-tree --write-tree --name-only --merge-base="up-${BASE_TAG}" \
  HEAD "up-${TARGET_TAG}" > "$TMP/mt.out" 2> "$TMP/mt.err"
code=$?
set -e
if [ "$code" -gt 1 ]; then
  echo "::error::git merge-tree failed (exit $code)"; cat "$TMP/mt.err"; exit 1
fi

tree=$(head -n1 "$TMP/mt.out")
# Line 2.. up to the first blank line: conflicted paths. After it: merge messages.
awk 'NR>1 && NF==0 {exit} NR>1 {print}' "$TMP/mt.out" | sort -u > "$TMP/conflicts.txt"
awk 'f {print} NR>1 && NF==0 {f=1}' "$TMP/mt.out" > "$TMP/messages.txt"

# Materialise the merged tree, then keep our own .github/ untouched.
git read-tree -u --reset "$tree"
git rm -r -q --cached .github > /dev/null 2>&1 || true
rm -rf .github
git checkout "$OURS" -- .github

# Never leave conflicted workflow paths in the list (we kept ours).
grep -v '^\.github/' "$TMP/conflicts.txt" > "$TMP/conflicts.filtered" || true
mv "$TMP/conflicts.filtered" "$TMP/conflicts.txt"
n_conf=$(grep -c . "$TMP/conflicts.txt" || true)
n_up=$(git diff --name-only "up-${BASE_TAG}" "up-${TARGET_TAG}" -- . ':(exclude).github' | grep -c . || true)

mkdir -p .sync
cp "$TMP/conflicts.txt" .sync/conflicts.txt
grep -E '^CONFLICT' "$TMP/messages.txt" > .sync/conflict-types.txt || true
{
  echo "mode=merge-tree base=up-${BASE_TAG}($(git rev-parse "up-${BASE_TAG}")) target=up-${TARGET_TAG}($(git rev-parse "up-${TARGET_TAG}")) ours=${OURS}"
  echo "upstream changed paths (excl .github)=${n_up} conflicted=${n_conf} clean=$((n_up - n_conf))"
  echo
  echo "== conflicted paths =="
  cat .sync/conflicts.txt
  echo
  echo "== merge messages =="
  cat "$TMP/messages.txt"
  echo
  echo "== upstream commits (${BASE_TAG}..${TARGET_TAG}) =="
  git log --oneline --no-merges "up-${BASE_TAG}..up-${TARGET_TAG}"
} > .sync/report.txt
rm -f ".sync/upstream-${TARGET_TAG}-report.txt"

git add -A
git commit -q -m "sync: merge upstream ${BASE_TAG}..${TARGET_TAG} via merge-tree (conflicts=${n_conf}/${n_up})

upstream ${TARGET_TAG} = $(git rev-parse "up-${TARGET_TAG}")
explicit merge base = upstream ${BASE_TAG} $(git rev-parse "up-${BASE_TAG}")"
git push origin "HEAD:refs/heads/${OUT_BRANCH}"

echo "::notice::branch=${OUT_BRANCH} conflicts=${n_conf} upstream_paths=${n_up}"
echo "branch=${OUT_BRANCH} conflicts=${n_conf} upstream_paths=${n_up}" >> "$GITHUB_STEP_SUMMARY"
