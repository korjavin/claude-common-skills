#!/usr/bin/env bash
# Talk to the Hermes agent over A2A 1.0 (JSON-RPC). Creds live in stash.
#   hermes.sh send "text" [contextId]   -> blocking SendMessage, prints reply text + task/context ids
#   hermes.sh tasks                     -> ListTasks
#   hermes.sh get <taskId>              -> GetTask
#   hermes.sh cancel <taskId>           -> CancelTask
#   hermes.sh card                      -> agent card (skills/capabilities)
set -euo pipefail
H=$(kv get secrets/hermes/a2a_host); H=${H%/}/
B=$(kv get secrets/hermes/a2a_bearer)

rpc() { # method params-json
  jq -nc --arg m "$1" --argjson p "$2" '{jsonrpc:"2.0",id:1,method:$m,params:$p}' |
    curl -sS -m 600 -X POST "$H" -H "Authorization: Bearer $B" \
      -H 'Content-Type: application/json' -H 'A2A-Version: 1.0' -d @-
}

case "${1:-}" in
  send)
    p=$(jq -nc --arg t "$2" --arg c "${3:-}" --arg id "cc-$(date +%s)-$$" \
      '{message:({messageId:$id,role:"ROLE_USER",parts:[{text:$t}]} + (if $c=="" then {} else {contextId:$c} end)),
        configuration:{blocking:true}}')
    rpc SendMessage "$p" | jq -r '
      if .error then "ERROR: \(.error)" else
      (.result.task // .result) as $t |
      "task=\($t.id) context=\($t.contextId) state=\($t.status.state)\n\n" +
      ([$t.status.message.parts[]?.text] | join("\n")) end' ;;
  tasks)  rpc ListTasks '{}' | jq . ;;
  get)    rpc GetTask "$(jq -nc --arg i "$2" '{id:$i}')" | jq . ;;
  cancel) rpc CancelTask "$(jq -nc --arg i "$2" '{id:$i}')" | jq . ;;
  card)   curl -sS -m 30 -H "Authorization: Bearer $B" "${H}.well-known/agent-card.json" | jq '{name,description,capabilities,skills:[.skills[].name]}' ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
