#!/usr/bin/env bash
# Dolt-synced bd writes for the orchestrator. Each call prints one OK/FAIL/WARN line per outcome,
# never raw bd/gh/git output. Run from the main checkout. A local-only bd DB (no Dolt remote)
# skips pull/push.
#
#   bead.sh claim  <actor> <id>...                     claim (epic route: epic id + every child id)
#   bead.sh merge  <actor> <pr> <worktree|-> <id>...   ready + merge commit + close ids + remove worktree
#   bead.sh park   <actor> <id> <step-3-fresh|step-5-merge> <pr|none> <why / the questions>
#   bead.sh unpark <actor> <id> <the owner's answer>
set -u
cmd=${1:?usage: see header}; actor=${2:?actor}; shift 2
tmp=$(mktemp)
# Multi-account gh: `git config beads.ghAccount <acct>` once per repo; dolt push/pull and gh then use it.
acct=$(git config --get beads.ghAccount) && [ -n "$acct" ] && export GH_TOKEN=$(gh auth token -u "$acct") \
  GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=credential.helper GIT_CONFIG_VALUE_0= \
  GIT_CONFIG_KEY_1=credential.helper GIT_CONFIG_VALUE_1='!gh auth git-credential'
bd dolt remote list 2>&1 | grep -q 'No remotes' && remote= || remote=1
pull() { [ -z "$remote" ] || bd dolt pull >/dev/null 2>&1; }
push() {
  [ -z "$remote" ] && return 0
  for _ in 1 2; do bd dolt pull >/dev/null 2>&1 && bd dolt push >/dev/null 2>&1 && return 0; done
  echo "FAIL dolt push rejected twice — the write is local-only; run: bd dolt pull && bd dolt push"; exit 1
}
why() { head -1 "$tmp" | cut -c1-200; }
field() { bd show "$1" --json 2>/dev/null | jq -r ".[0].$2 // empty"; }

case $cmd in
claim)
  pull; ok=()
  for id; do
    if ! bd update "$id" --claim --actor "$actor" >"$tmp" 2>&1; then
      echo "FAIL $id $(why)${ok[*]:+ (already claimed by you: ${ok[*]})}"; push; exit 1
    fi
    ok+=("$id")
  done
  push
  for id; do
    a=$(field "$id" assignee); [ "$a" = "$actor" ] || { echo "LOST $id to $a — drop it, don't touch its status"; exit 1; }
    field "$id" labels | grep -q '"human"' && echo "WARN $id carries the human label — read its PARKED notes before spawning"
  done
  [ -n "$(git status --porcelain .beads 2>/dev/null)" ] && git add .beads && git commit -qm "chore: bd claim $*"
  echo "OK claimed $*" ;;
merge)
  pr=${1:?pr}; wt=${2:?worktree or -}; shift 2
  gh pr ready "$pr" >/dev/null 2>&1
  if ! gh pr merge "$pr" --merge >"$tmp" 2>&1 || [ "$(gh pr view "$pr" --json state -q .state)" != MERGED ]; then
    echo "FAIL merge #$pr $(gh pr view "$pr" --json mergeable -q .mergeable 2>/dev/null): $(why)"; exit 1
  fi
  pull
  for id; do bd close "$id" --reason="Merged in #$pr" --actor "$actor" >"$tmp" 2>&1 || echo "FAIL close $id $(why)"; done
  push
  if [ "$wt" != - ] && [ -d "$wt" ]; then
    br=$(git -C "$wt" branch --show-current)
    if [ -n "$(git -C "$wt" status --porcelain --untracked-files=no)" ]; then
      echo "WARN $wt has uncommitted tracked changes — kept, look before removing"
    else
      git worktree remove --force "$wt" && { [ -z "$br" ] || git branch -D "$br" >/dev/null 2>&1; }  # -D: merge commit is on origin, not local master
    fi
  fi
  git worktree prune
  echo "OK merged #$pr, closed $*" ;;
park)
  id=${1:?id}; stage=${2:?stage}; pr=${3:?pr}; shift 3
  pull
  bd update "$id" --status=open --assignee "" --defer +30d --add-label human --actor "$actor" \
    --append-notes "PARKED: $*. PR: $pr. Resume-at: $stage" >"$tmp" 2>&1 || { echo "FAIL park $id $(why)"; exit 1; }
  push; echo "OK parked $id" ;;
unpark)
  id=${1:?id}; shift
  pull
  bd update "$id" --append-notes "OWNER ANSWER: $*" --remove-label human --defer "" --actor "$actor" >"$tmp" 2>&1 \
    || { echo "FAIL unpark $id $(why)"; exit 1; }
  push; echo "OK unparked $id" ;;
*) echo "FAIL unknown command $cmd"; exit 2 ;;
esac
