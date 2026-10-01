#!/usr/bin/env bash
# Port upstream commits one by one (list in scripts/upstream_port_list.txt).
# Each commit is a 3-way merge with base=<sha>^, ours=current HEAD, theirs=<sha>.
# Clean -> committed. Conflict -> skipped, recorded with files. .github stays ours.
set -uo pipefail

UPSTREAM=https://github.com/rikkahub/rikkahub.git
LIST=scripts/upstream_port_list.txt
OUT_BRANCH="port/upstream-2.5.5-run${GITHUB_RUN_NUMBER:-0}"
REPORT=/tmp/port-report.txt

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

# Full upstream history for 2.4.14..2.5.5 so every listed sha and its parent exist.
git fetch --no-tags "$UPSTREAM" "refs/tags/2.5.5:refs/tags/up-2.5.5" || { echo "::error::fetch failed"; exit 1; }
OURS0=$(git rev-parse HEAD)

ok=0; conf=0; missing=0
: > "$REPORT"
CLEAN_LINES=(); CONF_LINES=()

while IFS='|' read -r sha ver item; do
  [ -z "${sha// }" ] && continue
  case "$sha" in \#*) continue;; esac
  full=$(git rev-parse --verify -q "${sha}^{commit}") || { CONF_LINES+=("MISSING ${sha} ${ver} ${item}"); missing=$((missing+1)); continue; }

  set +e
  git merge-tree --write-tree --name-only --merge-base="${full}^" HEAD "$full" > /tmp/mt.out 2>/tmp/mt.err
  code=$?
  set -e
  if [ "$code" -gt 1 ]; then
    CONF_LINES+=("ERROR ${sha} ${ver} ${item}: $(head -c 300 /tmp/mt.err)"); conf=$((conf+1)); set +e; continue
  fi
  files=$(awk 'NR>1 && NF==0 {exit} NR>1 {print}' /tmp/mt.out | grep -v '^\.github/' | sort -u | tr '\n' ' ')
  if [ "$code" -eq 1 ] && [ -n "${files// }" ]; then
    CONF_LINES+=("CONFLICT ${sha} ${ver} ${item} :: ${files}"); conf=$((conf+1)); set +e; continue
  fi

  tree=$(head -n1 /tmp/mt.out)
  git read-tree -u --reset "$tree"
  git rm -r -q --cached .github > /dev/null 2>&1 || true
  rm -rf .github
  git checkout "$OURS0" -- .github
  git add -A
  if git diff --cached --quiet; then
    CLEAN_LINES+=("NOOP ${sha} ${ver} ${item} (already present)")
  else
    git commit -q -m "port(${ver}): ${item} [upstream ${sha}]"
    CLEAN_LINES+=("OK ${sha} ${ver} ${item}")
  fi
  ok=$((ok+1))
  set +e
done < "$LIST"

{
  echo "base=${OURS0} upstream=$(git rev-parse up-2.5.5)"
  echo "applied=${ok} conflicted=${conf} missing=${missing}"
  echo
  echo "== conflicted / skipped (resolve manually, in this order) =="
  printf '%s\n' "${CONF_LINES[@]}"
  echo
  echo "== applied =="
  printf '%s\n' "${CLEAN_LINES[@]}"
} > "$REPORT"

mkdir -p .port
cp "$REPORT" .port/report.txt
git add .port/report.txt
git commit -q -m "port: report (applied=${ok} conflicted=${conf} missing=${missing})"
git push origin "HEAD:refs/heads/${OUT_BRANCH}"
echo "branch=${OUT_BRANCH} applied=${ok} conflicted=${conf} missing=${missing}" >> "$GITHUB_STEP_SUMMARY"
