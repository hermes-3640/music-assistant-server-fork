#!/usr/bin/env bash
# End-to-end test for tools/import-upstream, against a synthetic upstream.
#
#   tools/tests/import-upstream.test.sh
#
# It builds an upstream with two stable releases and one beta, and a fork of it
# with its own `main` and `upstream` branches, then imports release by release
# and checks the things that matter: only stable tags are picked, imported
# commits keep their parent's .github, the release tag records which real
# upstream commit it came from, re-running changes nothing, and merging the
# result into main leaves main's own CI alone. Nothing touches the real repo.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

failures=0
check() { # check <what> <got> <want>
  if [ "$2" = "$3" ]; then
    echo "ok:   $1"
  else
    echo "FAIL: $1" >&2
    echo "        got:  $2" >&2
    echo "        want: $3" >&2
    failures=$((failures + 1))
  fi
}

git_q() { git -C "$1" "${@:2}"; }

# --- a synthetic upstream: 1.0.0, 1.0.1 (changes its CI), 1.0.2, and a beta ---
up="$work/upstream"
git init -q -b main "$up"
git_q "$up" config user.name "Upstream Author"
git_q "$up" config user.email "upstream@example.com"
mkdir -p "$up/.github/workflows"
echo "v1" > "$up/.github/workflows/upstream-ci.yml"
echo "a" > "$up/src.txt"
git_q "$up" add -A
git_q "$up" commit -qm "release one"
git_q "$up" tag 1.0.0
echo "v2" > "$up/.github/workflows/upstream-ci.yml"
echo "b" > "$up/src.txt"
git_q "$up" add -A
git_q "$up" commit -qm "release two"
git_q "$up" tag 1.0.1
echo "c" > "$up/src.txt"
git_q "$up" add -A
git_q "$up" commit -qm "release three"
git_q "$up" tag 1.0.2
git_q "$up" tag 1.0.3b1 # a beta: must never be imported

# --- a fork of it, one release behind, with its own CI on main ---
remote="$work/origin.git"
git init -q --bare "$remote"
fork="$work/fork"
git init -q -b main "$fork"
git_q "$fork" config user.name "Fork Author"
git_q "$fork" config user.email "fork@example.com"
git_q "$fork" remote add origin "$remote"
git_q "$fork" fetch -q --no-tags "$up" "+refs/tags/1.0.0:refs/heads/upstream"
git_q "$fork" tag 1.0.0 upstream
git_q "$fork" checkout -q -b main upstream
rm -rf "$fork/.github"
mkdir -p "$fork/.github/workflows"
printf 'name: tests\n' > "$fork/.github/workflows/tests.yml"
echo "this fork" > "$fork/FORK.md"
git_q "$fork" add -A
git_q "$fork" commit -qm "fork setup"
git_q "$fork" push -q origin main upstream --tags

import_release() { # import_release <tag>  -- prints its output, keeps its status
  local out rc=0
  out=$(cd "$fork" && IMPORT_UPSTREAM_URL="$up" IMPORT_FORK_REMOTE=origin \
    IMPORT_UPSTREAM_TAG="$1" "$here/tools/import-upstream" 2>&1) || rc=$?
  printf '%s\n' "$out"
  return "$rc"
}

# --- 1.0.1: a release in which upstream changed its CI ---
import_release 1.0.1 > /dev/null
real_101=$(git_q "$up" rev-parse "1.0.1^{commit}")
kept_101=$(git_q "$fork" rev-parse "refs/tags/1.0.1^{commit}")
check "1.0.1 is rewritten, not upstream's own commit" \
  "$([ "$kept_101" = "$real_101" ] && echo same || echo rewritten)" "rewritten"
check "the 1.0.1 tag records the real upstream commit" \
  "$(git_q "$fork" tag -l --format='%(contents:body)' 1.0.1 | sed -n 's/^upstream-commit: //p')" \
  "$real_101"
check "upstream's code change still arrives (src.txt)" \
  "$(git_q "$fork" show "refs/tags/1.0.1^{commit}:src.txt")" "b"
check "upstream's .github change is frozen out (still v1)" \
  "$(git_q "$fork" show "refs/tags/1.0.1^{commit}:.github/workflows/upstream-ci.yml")" "v1"
check "the imported commit touches no .github path" \
  "$(git_q "$fork" diff --name-only 1.0.0 "refs/tags/1.0.1^{commit}")" "src.txt"
check "upstream's authorship is kept" \
  "$(git_q "$fork" show -s --format=%ae "refs/tags/1.0.1^{commit}")" "upstream@example.com"
check "the branch and the tag were pushed" \
  "$(git_q "$remote" for-each-ref --format='%(refname)' refs/heads/upstream refs/tags/1.0.1 | tr '\n' ' ')" \
  "refs/heads/upstream refs/tags/1.0.1 "

# --- re-running the same release changes nothing ---
check "importing 1.0.1 again says so" \
  "$(import_release 1.0.1)" "1.0.1 is already imported."

# --- 1.0.2: only the commits since the last import are rewritten ---
import_release 1.0.2 > /dev/null
real_102=$(git_q "$up" rev-parse "1.0.2^{commit}")
check "1.0.2's tag records the real upstream commit" \
  "$(git_q "$fork" tag -l --format='%(contents:body)' 1.0.2 | sed -n 's/^upstream-commit: //p')" \
  "$real_102"
check "history did not double up (1.0.0 + 1.0.1 + 1.0.2)" \
  "$(git_q "$fork" rev-list --count refs/heads/upstream)" "3"
check "the second import also touches no .github path" \
  "$(git_q "$fork" diff --name-only 1.0.1 refs/heads/upstream)" "src.txt"

# --- merging the import into main leaves main's CI alone ---
git_q "$fork" checkout -q main
git_q "$fork" merge -q --no-ff --no-edit upstream
check "main kept its own workflow" \
  "$(git_q "$fork" show main:.github/workflows/tests.yml)" "name: tests"
check "upstream's workflow did not come back" \
  "$([ -e "$fork/.github/workflows/upstream-ci.yml" ] && echo present || echo absent)" "absent"

# --- the beta is never imported ---
if import_release 1.0.3b1 > /dev/null 2>&1; then
  echo "FAIL: 1.0.3b1 is refused (a beta is not a stable release)" >&2
  failures=$((failures + 1))
else
  echo "ok:   1.0.3b1 is refused (a beta is not a stable release)"
fi

# --- the newest stable release is what auto-detection picks (1.0.2, not the beta) ---
check "auto-detection picks the newest stable release" \
  "$(cd "$fork" && IMPORT_UPSTREAM_URL="$up" IMPORT_FORK_REMOTE=origin "$here/tools/import-upstream")" \
  "1.0.2 is already imported."

if [ "$failures" != 0 ]; then
  echo "import-upstream.test: $failures failure(s)" >&2
  exit 1
fi
echo "import-upstream.test: ok"
