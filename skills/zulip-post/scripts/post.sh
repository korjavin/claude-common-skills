#!/usr/bin/env bash
# Usage: post.sh <channel name or id> <topic> <msg.md> [image ...]
# msg.md references images as <upload:basename>. Prints the message id and thumbnail state.
set -euo pipefail
to=$1 topic=$2 msg=$3; shift 3

SITE=$(kv get secrets/zulip-claude-bot-site); SITE=${SITE%/}
AUTH="$(kv get secrets/zulip-claude-bot-email):$(kv get secrets/zulip-claude-bot-key)"

body=$(cat "$msg")
for img in "$@"; do
  uri=$(curl -sS -u "$AUTH" -F "filename=@$img" "$SITE/api/v1/user_uploads" |
    python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("uri") or d.get("url") or "")')
  [ -n "$uri" ] || { echo "upload failed: $img" >&2; exit 1; }
  # Zulip renders a permanent spinner if the message is sent before the thumbnail exists.
  thumb="$SITE/user_uploads/thumbnail/${uri#/user_uploads/}/840x560.webp"
  for _ in $(seq 60); do
    ct=$(curl -sS -o /dev/null -w '%{http_code} %{content_type}' -u "$AUTH" "$thumb" || true)
    [ "$ct" = "200 image/webp" ] && break
    sleep 2
  done
  [ "$ct" = "200 image/webp" ] || echo "warning: thumbnail not ready for $img ($ct)" >&2
  body=${body//<upload:$(basename "$img")>/$uri}
done

case $body in *"<upload:"*) echo "unresolved <upload:...> placeholder in $msg" >&2; exit 1;; esac

id=$(curl -sS -u "$AUTH" "$SITE/api/v1/messages" \
  --data-urlencode type=stream --data-urlencode "to=$to" \
  --data-urlencode "topic=$topic" --data-urlencode "content=$body" |
  python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["id"]) if d["result"]=="success" else sys.exit(d["msg"])')
echo "posted: $id"

[ $# -gt 0 ] || exit 0
curl -sS -u "$AUTH" "$SITE/api/v1/messages/$id" | python3 -c '
import sys,json
c=json.load(sys.stdin)["message"]["content"]
print("thumbnails: BROKEN (placeholder) - re-save the message, see SKILL.md" if "image-loading-placeholder" in c else "thumbnails: ok")'
