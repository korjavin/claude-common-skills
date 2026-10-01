#!/usr/bin/env bash
# Pane watcher for the orchestrator: polls agterm panes and prints ONE stdout line only when the
# orchestrator must act. Run it under the Monitor tool — every stdout line is a notification.
#
#   pane-watch.sh <panes-file>
#
# <panes-file>: one pane per line, "<session-id>[:right] <worktree-path>" (":right" = that session's
# split pane); '#' lines are skipped. Re-read every tick, so add or
# remove panes by editing it — no re-arm needed. Routine prompts are answered by a haiku triage
# call; its decisions go to <panes-file>.log, never to stdout.
#
# Events (stdout):
#   ESCALATE <sid> <reason>   prompt haiku would not answer (destructive, outside worktree, a question)
#   STALE <sid> <N>m          screen unchanged N minutes with no prompt (stuck, or done and idle)
#   GONE <sid>                session text failed (closed / crashed)
#
# Env: PANE_WATCH_INTERVAL (s, default 60), PANE_WATCH_STALE_MIN (default 10), PANE_WATCH_MODEL (haiku)
set -u
panes=${1:?usage: pane-watch.sh <panes-file>}
log="$panes.log"
interval=${PANE_WATCH_INTERVAL:-60}
stale_min=${PANE_WATCH_STALE_MIN:-10}
model=${PANE_WATCH_MODEL:-haiku}
state=$(mktemp -d)
# ponytail: regex gate keeps haiku calls rare; a prompt phrased outside it surfaces as STALE instead
prompt_re='Do you want|\(y/n\)|\[y/N\]|\[Y/n\]|Allow|Approve|Proceed\?|[Cc]ontinue\?|Press Enter|❯ *1\.|1\. Yes|Waiting for (your|user)'

triage() { # $1 sid, $2 worktree, $3 screen → "ANSWER <keys>" | "ESCALATE <reason>"
  claude -p --model "$model" "You supervise a coding agent in a terminal. Its worktree is $2.
The bottom of its screen is below. It is waiting on a prompt. Reply with exactly ONE line:
ANSWER <keys>   — when it is a routine permission (edit/create files, run tests/builds/linters, git
                  add/commit/push of its own branch, gh pr commands, reads) inside its worktree.
                  <keys> is what to type, e.g. 1 or y. Prefer the option that allows once.
ESCALATE <why>  — anything destructive (rm -rf, reset --hard, force push, push to master/main, dropping
                  data), anything outside its worktree, or a question needing a design/product decision.
Screen:
$3" </dev/null 2>/dev/null | grep -E '^(ANSWER|ESCALATE) ' | head -1
}

while :; do
  while read -r sid wt _; do
    [ -n "$sid" ] && [ "${sid#\#}" = "$sid" ] || continue
    tgt=(--target "${sid%%:*}"); [ "$sid" != "${sid#*:}" ] && tgt+=(--pane "${sid#*:}")
    key=${sid//[:\/]/_}
    if ! screen=$(agtermctl session text "${tgt[@]}" --lines 20 </dev/null 2>/dev/null); then
      [ -e "$state/$key.gone" ] || { echo "GONE $sid"; touch "$state/$key.gone"; }
      continue
    fi
    rm -f "$state/$key.gone"
    # ponytail: letters-only hash ignores timers/token counters/spinner glyphs; a hung agent whose
    # spinner verb keeps rotating still looks alive — Step 4's worktree check is the backstop
    h=$(printf %s "$screen" | LC_ALL=C tr -cd 'A-Za-z\n' | shasum | cut -c1-12)
    if [ "$h" != "$(cat "$state/$key.h" 2>/dev/null)" ]; then
      echo "$h" >"$state/$key.h"; date +%s >"$state/$key.t"; rm -f "$state/$key.stale" "$state/$key.seen"
    fi
    if printf %s "$screen" | tail -12 | grep -Eq "$prompt_re"; then
      [ -e "$state/$key.seen" ] && continue   # this exact prompt already handled
      touch "$state/$key.seen"
      verdict=$(triage "$sid" "$wt" "$screen")
      echo "$(date +%T) $sid ${verdict:-ESCALATE triage failed}" >>"$log"
      case $verdict in
        "ANSWER "*) agtermctl session type "${verdict#ANSWER }"$'\n' "${tgt[@]}" </dev/null >/dev/null 2>&1 \
                      || echo "ESCALATE $sid could not type answer" ;;
        "ESCALATE "*) echo "ESCALATE $sid ${verdict#ESCALATE }" ;;
        *) echo "ESCALATE $sid prompt on screen, triage gave no verdict" ;;
      esac
      continue
    fi
    idle=$(( ($(date +%s) - $(cat "$state/$key.t")) / 60 ))
    if [ "$idle" -ge "$stale_min" ] && [ ! -e "$state/$key.stale" ]; then
      echo "STALE $sid ${idle}m"; touch "$state/$key.stale"   # once per stall; resets on any change
    fi
  done <"$panes"
  sleep "$interval"
done
