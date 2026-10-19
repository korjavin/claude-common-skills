#!/usr/bin/env bash
# Usage: wait.sh <channel> [topic] [timeout, default 1h]
# Blocks until one new message arrives; prints it as one JSON line. Exit codes are zulip_watcher's:
# 0 message, 1 API/network/auth error, 2 usage error, 3 timeout (stdout empty).
set -euo pipefail
export PATH="$PATH:$(go env GOPATH)/bin"
command -v zulip_watcher >/dev/null || go install github.com/korjavin/zulip_watcher@latest
# Creds go in the environment of the exec'd process only, never argv. Never echo them, never set -x.
export ZULIP_URL=$(kv get secrets/zulip-claude-bot-site) ZULIP_EMAIL=$(kv get secrets/zulip-claude-bot-email) ZULIP_API_KEY=$(kv get secrets/zulip-claude-bot-key)
args=(-stream "${1:-}" -timeout "${3:-1h}" -json)
[ -n "${2:-}" ] && args+=(-topic "$2")
exec zulip_watcher "${args[@]}"
