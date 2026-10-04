---
name: stash
description: Read, store, list and delete secrets and config in the owner's local stash (umputun/stash) key-value store via the `kv` CLI. Use whenever a task needs a credential, token, password, API key, hostname or other config value ("get the token from stash", "kv get", "save this secret", "where is the password for X"), when the owner hands over a secret to keep, or when a skill says a value "lives in stash". Never put secrets in files, commits, chat or memory — stash is the only place they live.
---

# stash — local secret & config store

[umputun/stash](https://github.com/umputun/stash) runs as the docker container
`stash` on `127.0.0.1:8080` (compose in `~/Projects/stash`). Access it only
through the `kv` wrapper (`~/.local/bin/kv`, already carries URL and token):

```bash
kv get <key>            # value to stdout; exit 22 if missing / no access
kv set <key> [value]    # value from arg, or from stdin if omitted
kv del <key>
kv ls [prefix]          # JSON array of key metadata (no values)
```

## Keys

- `secrets/...` — encrypted at rest (any key with a `secrets` path segment).
  **Every credential goes here.** Layout: `secrets/<project-or-service>/<name>`
  (e.g. `secrets/mullbot/portainer-admin-password`). Some older keys are flat
  (`secrets/thingverse-email`) — reuse existing names, don't rename.
- Anything else (`smtp/...`, hostnames, URLs) — plain config, not encrypted.
- Find a key before guessing: `kv ls secrets/ | jq -r '.[].key' | grep -i <word>`.

## Rules

1. **Never print a secret value.** No bare `kv get` whose output lands in the
   transcript. Capture into a variable and use it in the **same** Bash call
   (shell state does not persist between calls):
   ```bash
   T=$(kv get secrets/foo/token) || { echo "missing secrets/foo/token"; exit 1; }
   curl -sf -H "Authorization: Bearer $T" https://api.example.com/...
   ```
   Need to check it's non-empty? `[ -n "$T" ] && echo set`, or `${#T}` — not the value.
2. **Never write a secret** into repo files, commits, PR/issue text, logs,
   memory, docs, or `set -x` output. If a deploy needs a `.env`, generate it
   from `kv get` at the target, gitignored, only when asked.
3. **Storing a new secret** the owner pasted or a command produced: pipe it
   straight in, don't echo it back:
   ```bash
   printf %s "$V" | kv set secrets/<project>/<name>
   ```
   Then tell the owner only the key name.
4. **Overwrite or delete = confirm first.** Git history is not enabled on this
   instance; a `kv set` over an existing key or a `kv del` is irreversible. Check
   with `kv ls <key>` before writing.
5. **Don't read stash's own files** — `~/Projects/stash/.env`, `.master-key`,
   `stash-auth.yml`, `data/`. Go through `kv` only.
6. **Missing key** (exit 22): ask the owner to add it, naming the exact key —
   `kv set secrets/<project>/<name>` in their own terminal (paste, Ctrl-D), not
   via `!` (that puts the value into the conversation). Never invent or hardcode
   a fallback value.

## Remote hosts

stash listens on localhost only. To give a remote host a secret, read it
locally and pipe over SSH — never put it on the command line of the remote:

```bash
kv get secrets/foo/token | ssh host 'umask 077; cat > ~/.foo-token'
```

## If it fails

- `curl -s localhost:8080/ping` ≠ `pong` → `docker start stash`
  (or `docker compose -f ~/Projects/stash/docker-compose.yml up -d`).
- 401/403 → `kv` token lacks access to that prefix; report to the owner, don't
  touch `stash-auth.yml`.
