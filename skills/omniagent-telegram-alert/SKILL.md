---
name: omniagent-telegram-alert
description: Send the owner a Telegram notification when omniagent needs their attention — blocked on input only they can provide, an approval/confirmation is required, or a failure has stopped work. Use ONLY for attention-required alerts, never for progress updates, success reports, or routine status. Bot token and chat id live in the local stash secret store.
---

# Omniagent → Telegram alert

Fires a message to the owner's personal Telegram via their bot. Reserved for
"omniagent wants your attention" moments:

- blocked and only the owner can unblock (missing credential, ambiguous decision)
- a destructive/outward-facing action needs their explicit approval
- a failure that stops the work (deploy broken, loop dead, CI unrecoverable)

Anything else (progress, success, FYI) — do NOT send. One alert per event; never
re-send the same alert in a loop.

## Send

```bash
T=$(~/stash/kv get secrets/omniagent-tg-token)
C=$(~/stash/kv get secrets/omniagent-tg-chat)
curl -sf "https://api.telegram.org/bot$T/sendMessage" \
  --data-urlencode chat_id="$C" \
  --data-urlencode text="🔔 omniagent: <what happened, one or two sentences, and what you need from the owner>"
```

Plain text only (no parse_mode — Markdown escaping bugs eat alerts). Keep it
under ~500 chars. Never echo the token, the chat id, or the bot's name into
output, logs, files, or commits — they exist only inside stash and this
command's shell variables.

## First-time chat id bootstrap

If `secrets/omniagent-tg-chat` is missing: ask the owner to send any message to
the bot in Telegram, then:

```bash
T=$(~/stash/kv get secrets/omniagent-tg-token)
C=$(curl -sf "https://api.telegram.org/bot$T/getUpdates" | grep -o '"chat":{"id":[0-9-]*' | tail -1 | grep -o '[0-9-]*$')
~/stash/kv set secrets/omniagent-tg-chat "$C"   # straight into stash — never print it
```

## If it fails

- 401/404 from Telegram → token wrong; ask owner to re-set `secrets/omniagent-tg-token`.
- 400 "chat not found" → chat id stale; redo the bootstrap.
- stash unreachable → restart its container (`sudo docker start stash`).

Do not fall back to any other channel; report the delivery failure in the
conversation instead.
