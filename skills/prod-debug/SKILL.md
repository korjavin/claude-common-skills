---
name: prod-debug
description: Debug issues on the production server over SSH. Trigger when the user asks to "debug on prod", "check prod", investigate production behavior, look at production logs, inspect prod env vars, or diagnose a bug that may only reproduce in production.
---

# Production debugging

The user runs this project's containers on a personal server reachable over SSH:

- **Host:** `pet.kfamcloud.com`
- **Container management:** Portainer UI + `sudo podman` on the host
- **Access:** SSH key already configured (no password prompt expected)

This skill exists because the user is tired of repeating these details every time. Use it whenever they ask to debug, inspect, or reproduce something against production.

## Workflow

1. **SSH in** — `ssh pet.kfamcloud.com` (use Bash with `run_in_background: false` for short commands; combine `ssh pet.kfamcloud.com '<remote command>'` for one-shots).
2. **Find the right container** — `sudo podman ps` to list, match by image/name (project containers usually carry `medtracker`, `bot`, etc. in the name).
3. **Read logs** — `sudo podman logs --tail 200 <container>` for recent output, add `--since 30m` to bound by time, or `-f` if the user explicitly wants a tail (run in background).
4. **Inspect env / config** — `sudo podman inspect <container>` for full config, or `sudo podman exec <container> env` for the live environment. Mask secret values when echoing them back to the user.
5. **Reproduce / probe** — `sudo podman exec -it <container> sh` for an interactive shell, or one-off `sudo podman exec <container> <cmd>` for targeted checks (DB queries, file reads, curl to internal endpoints).
6. **Describe the bug** — once you have evidence, summarize: what you observed, where in the code it likely originates (cite `file:line`), and the smallest fix or next diagnostic step. Do **not** apply fixes to prod directly — propose a code change in the repo instead.

## Guardrails

- **Read-only by default.** Logs, `inspect`, `exec ... env`, read-only DB queries are fine without confirmation. Anything that mutates prod state (restarting containers, editing files in the container, running migrations, deleting data, `podman rm`, `podman stop`, Portainer redeploys) requires explicit user confirmation first.
- **Do not exfiltrate secrets.** If env vars or logs contain tokens / passwords / API keys, summarize their presence ("OPENAI_API_KEY is set") rather than printing the value.
- **Don't leak the hostname externally.** The hostname is intentionally kept out of git (this skill lives under `.claude/`, which is in `.gitignore`). Don't write it into committed files, PR descriptions, issue comments, or commit messages.

## Quick reference

```bash
# List containers
ssh pet.kfamcloud.com 'sudo podman ps'

# Tail last 200 log lines
ssh pet.kfamcloud.com 'sudo podman logs --tail 200 <container>'

# Logs from the last 30 minutes
ssh pet.kfamcloud.com 'sudo podman logs --since 30m <container>'

# Live env in the container
ssh pet.kfamcloud.com 'sudo podman exec <container> env'

# Open an interactive shell
ssh pet.kfamcloud.com -t 'sudo podman exec -it <container> sh'
```
