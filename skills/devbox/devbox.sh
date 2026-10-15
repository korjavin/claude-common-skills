#!/usr/bin/env bash
# Talk to the owner's Devbox agent (Claude Code on a devbox host) over A2A 0.3 (JSON-RPC). Creds live in stash.
#   devbox.sh start "text" [contextId]  -> non-blocking: returns task/context ids at once (state submitted)
#   devbox.sh wait <taskId> [maxSec]    -> poll every 10s until done (default 1800s), print reply
#   devbox.sh get <taskId>              -> one poll: state (+ reply when finished)
#   devbox.sh send "text" [contextId]   -> blocking: waits for the reply (short questions only)
#   devbox.sh cancel <taskId>           -> tasks/cancel
#   devbox.sh card                      -> agent card
set -euo pipefail
H=$(kv get secrets/a2a-adapter/host); H=${H%/}/
B=$(kv get secrets/a2a-adapter/api-key)

rpc() { # method params-json
  # ponytail: no A2A-Version header — the adapter speaks v0.3 and rejects 1.0 for these method names
  jq -nc --arg m "$1" --argjson p "$2" '{jsonrpc:"2.0",id:1,method:$m,params:$p}' |
    curl -sS -m 900 -X POST "$H" -H "Authorization: Bearer $B" -H 'Content-Type: application/json' -d @-
}
msg() { # text contextId blocking
  jq -nc --arg t "$1" --arg c "$2" --argjson b "$3" --arg id "cc-$(date +%s)-$$" \
    '{message:({kind:"message",messageId:$id,role:"user",parts:[{kind:"text",text:$t}]}
               + (if $c=="" then {} else {contextId:$c} end)),
      configuration:{blocking:$b}}'
}
show() { # task JSON-RPC response on stdin -> header + reply text
  jq -r 'if .error then "ERROR: \(.error)" else
    .result as $t |
    "task=\($t.id) context=\($t.contextId) state=\($t.status.state)" +
    (if ($t.status.state|IN("submitted","working")) then "" else "\n\n" +
      ([$t.artifacts[]?.parts[]?.text // empty] | if length>0 then join("\n")
       else [$t.status.message.parts[]?.text // empty] | join("\n") end) end) end'
}
get() { rpc tasks/get "$(jq -nc --arg i "$1" '{id:$i}')"; }

case "${1:-}" in
  start)  rpc message/send "$(msg "$2" "${3:-}" false)" | show ;;
  send)   rpc message/send "$(msg "$2" "${3:-}" true)" | show ;;
  get)    get "$2" | show ;;
  wait)
    end=$(( $(date +%s) + ${3:-1800} ))
    while :; do
      r=$(get "$2"); s=$(jq -r '.result.status.state // "error"' <<<"$r")
      case "$s" in submitted|working) ;; *) show <<<"$r"; exit 0 ;; esac
      [ "$(date +%s)" -ge "$end" ] && { show <<<"$r"; echo "(still $s — wait again later)"; exit 2; }
      sleep 10
    done ;;
  cancel) rpc tasks/cancel "$(jq -nc --arg i "$2" '{id:$i}')" | jq . ;;
  card)   curl -sS -m 30 -H "Authorization: Bearer $B" "${H}.well-known/agent-card.json" | jq '{name,description,capabilities,skills:[.skills[]?.name]}' ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
