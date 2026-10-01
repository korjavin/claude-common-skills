#!/usr/bin/env bash
# Session preflight for the orchestrator, from the main checkout. Prints a compact summary only.
set -u
miss=; for t in gh bd codex jq git agtermctl revmux; do command -v $t >/dev/null || miss+=" $t"; done
gh auth status >/dev/null 2>&1 || miss+=" gh-auth"
echo "missing:${miss:- none}"   # agtermctl only matters for pane developers, revmux only with .revmux/
if bd dolt remote list 2>&1 | grep -q 'No remotes'; then echo "dolt: local-only (bead.sh skips sync)"
else bd dolt pull >/dev/null 2>&1 && echo "dolt: remote, pulled" || echo "dolt: remote, PULL FAILED"; fi
git fetch -q origin 2>/dev/null && echo "git: fetched" || echo "git: FETCH FAILED"
echo "actor: orch-$(date +%Y%m%d-%H%M)"
if [ -d .revmux ]; then
  p=$(revmux config 2>/dev/null | jq -r '.knobs[] | select(.name=="profile" and .source!="default") | .value')
  echo "revmux: .revmux/ present, pinned profile: ${p:-none — resolve per references/revmux.md}"
else echo "revmux: no .revmux/ — built-in profiles; resolve per references/revmux.md before routing a huge bead"; fi
prs=$(gh pr list --json number,headRefName -q '.[] | "\(.headRefName) #\(.number)"' 2>/dev/null)
bd list --label human --json 2>/dev/null | jq -r '.[] | "parked: \(.id) \(.title)"'
bd list --status in_progress --json 2>/dev/null | jq -r '.[] | "\(.id) \(.assignee // "-")"' |
  while read -r id who; do
    pr=$(printf '%s\n' "$prs" | awk -v id="$id" 'index($1, id)==1 {print $2; exit}')
    echo "orphan?: $id held by $who, PR: ${pr:-none}"
  done
