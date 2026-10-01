#!/usr/bin/env bash
# Port upstream commits one by one (list in scripts/upstream_port_list.txt).
# Each commit is a 3-way merge with base=<sha>^, ours=current HEAD, theirs=<sha>.
# Clean -> committed. Conflict -> skipped and recorded with its files.
# .github/ always stays ours (GITHUB_TOKEN cannot push workflow changes).
#
# No `set -e` on purpose: grep with no match exits 1, which under -e/pipefail
# aborted run 1 on the first clean commit. Each step checks its own status.
set -uo pipefail

die() { echo "::error file=scripts/port_upstream.sh::$*"; exit 1; }

UPSTREAM=https://github.com/rikkahub/rikkahub.git
LIST=scripts/upstream_port_list.txt
OUT_BRANCH="port/upstream-2.5.5-run${GITHUB_RUN_NUMBER:-0}"
REPORT=/tmp/port-report.txt

[ -f "$LIST" ] || die "missing $LIST"
git --version
git config user.name "github-actions[bot]" || die "git config failed"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com" || die "git config failed"

# Full upstream history up to 2.5.5 so every listed sha and its parent exist.
git fetch --no-tags "$UPSTREAM" "refs/tags/2.5.5:refs/tags/up-2.5.5" || die "fetch upstream failed"
OURS0=$(git rev-parse HEAD) || die "rev-parse HEAD failed"

ok=0; noop=0; conf=0; missing=0
CLEAN_LINES=(); CONF_LINES=()

while IFS='|' read -r sha ver item || [ -n "${sha:-}" ]; do
  sha="${sha//[[:space:]]/}"
  [ -z "$sha" ] && continue
  case "$sha" in \#*) continue;; esac

  full=$(git rev-parse --verify -q "${sha}^{commit}")
  if [ -z "$full" ]; then
    CONF_LINES+=("MISSING ${sha} ${ver} ${item}"); missing=$((missing+1)); continue
  fi

  git merge-tree --write-tree --name-only --merge-base="${full}^" HEAD "$full" > /tmp/mt.out 2> /tmp/mt.err
  code=$?
  if [ "$code" -gt 1 ]; then
    CONF_LINES+=("ERROR ${sha} ${ver} ${item}: $(head -c 300 /tmp/mt.err | tr '\n' ' ')")
    conf=$((conf+1)); continue
  fi

  files=$(awk 'NR>1 && NF==0 {exit} NR>1 {print}' /tmp/mt.out | { grep -v '^\.github/' || true; } | sort -u | tr '\n' ' ')
  if [ "$code" -eq 1 ] && [ -n "${files// }" ]; then
    CONF_LINES+=("CONFLICT ${sha} ${ver} ${item} :: ${files}")
    conf=$((conf+1)); continue
  fi

  tree=$(head -n1 /tmp/mt.out)
  git read-tree -u --reset "$tree" || die "read-tree failed at ${sha}"
  git rm -r -q --cached .github > /dev/null 2>&1
  rm -rf .github
  git checkout "$OURS0" -- .github || die "restore .github failed at ${sha}"
  git add -A || die "git add failed at ${sha}"

  if git diff --cached --quiet; then
    CLEAN_LINES+=("NOOP ${sha} ${ver} ${item} (already present)"); noop=$((noop+1))
  else
    git commit -q -m "port(${ver}): ${item} [upstream ${sha}]" || die "commit failed at ${sha}"
    CLEAN_LINES+=("OK ${sha} ${ver} ${item}"); ok=$((ok+1))
  fi
done < "$LIST"

{
  echo "base=${OURS0} upstream=$(git rev-parse up-2.5.5)"
  echo "applied=${ok} already_present=${noop} conflicted=${conf} missing=${missing}"
  echo
  echo "== conflicted / skipped (resolve manually, in this order) =="
  printf '%s\n' ${CONF_LINES[@]+"${CONF_LINES[@]}"}
  echo
  echo "== applied =="
  printf '%s\n' ${CLEAN_LINES[@]+"${CLEAN_LINES[@]}"}
} > "$REPORT"

mkdir -p .port
cp "$REPORT" .port/report.txt
git add .port/report.txt || die "add report failed"
git commit -q -m "port: report (applied=${ok} noop=${noop} conflicted=${conf} missing=${missing})" || die "commit report failed"
git push origin "HEAD:refs/heads/${OUT_BRANCH}" || die "push ${OUT_BRANCH} failed"

echo "::notice::branch=${OUT_BRANCH} applied=${ok} noop=${noop} conflicted=${conf} missing=${missing}"
echo "branch=${OUT_BRANCH} applied=${ok} noop=${noop} conflicted=${conf} missing=${missing}" >> "$GITHUB_STEP_SUMMARY"
