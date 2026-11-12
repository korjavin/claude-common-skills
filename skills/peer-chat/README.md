# Peer chat

Let coding agents — Claude Code, Codex and AGY (Antigravity CLI) — hold a conversation with each other anywhere in one agterm workspace: another session, a companion, or the other half of a split.

Based on umputun's [two-agent-mailbox-chat](https://github.com/umputun/agterm/tree/master/cookbook/two-agent-mailbox-chat) recipe (MIT). Differences: a peer is found through a registry of agent panes in the caller's workspace instead of being the other half of the split, every message carries its sender's `SESSION:PANE` so replies go straight back, and AGY is supported.

## How it works

Messages go into agterm's per-pane mailboxes (`agtermctl msg`, agterm 0.40.0+). Nothing is typed into any composer.

| Agent | Registers through | Woken by |
|---|---|---|
| Claude Code | `claude-hook` (SessionStart, UserPromptSubmit, Stop, `asyncRewake`) | the same hook: mail between turns starts a turn |
| Codex | `codex-hook` (SessionStart) | agterm's `on message` hook → `agterm-hook` → `codex queue` |
| AGY | `agy-hook` (SessionStart) | `peer-chat.py wait`, run by agy as a background task; its completion notice starts agy's next turn |

`say --to codex|agy|claude` picks the single live pane registered as that agent in the caller's workspace; with several it refuses and lists them, and `--to SESSION:PANE` names one exactly. `status` lists the registered peers. Registry and waiter state live in `$TMPDIR/agterm-peer-chat-<uid>/`.

AGY cannot be woken by anything outside it, so it must be listening: the skill has it start `peer-chat.py wait` in the background when a chat starts and after each message. If it is not, `say` reports `receiver: "agy-idle"` and the mail waits; tell agy "listen for peer chat". Pickup took from seconds to about two minutes in testing.

## Setup

1. Link `peer-chat.py` onto your `PATH` (e.g. `~/.local/bin/peer-chat.py`).
2. Install the skills: this directory as `~/.claude/skills/peer-chat`, `SKILL-codex.md` as `~/.codex/skills/peer-chat/SKILL.md`, `SKILL-agy.md` as `~/.gemini/config/skills/peer-chat/SKILL.md`.
3. Claude Code: add to each of `hooks.SessionStart`, `hooks.UserPromptSubmit` and `hooks.Stop` in `~/.claude/settings.json`:
   ```json
   {"hooks": [{"type": "command", "command": "/full/path/peer-chat.py claude-hook", "asyncRewake": true, "rewakeSummary": "peer chat received", "timeout": 2000000}]}
   ```
4. Codex: in `~/.codex/config.toml`, then trust it once in `/hooks`:
   ```toml
   [[hooks.SessionStart]]
   [[hooks.SessionStart.hooks]]
   type = "command"
   command = "/full/path/peer-chat.py codex-hook"
   ```
   and in `~/.codex/rules/default.rules`, so its sandbox lets sends reach agterm's socket:
   ```
   host_executable(name="peer-chat.py", paths=["/full/path/peer-chat.py"])
   prefix_rule(pattern=["peer-chat.py", "say", "--file"], decision="allow")
   ```
   Start Codex with `--no-daemon`; a shared app-server would run hooks with another pane's ids.
5. AGY: `~/.gemini/config/hooks.json`:
   ```json
   {"peer-chat": {"SessionStart": [{"type": "command", "command": "/full/path/peer-chat.py agy-hook", "timeout": 10}]}}
   ```
6. agterm: in `~/.config/agterm/hooks.conf`, then `agtermctl hooks reload`:
   ```
   on message /full/path/peer-chat.py agterm-hook
   ```

Agents already running when you install the hooks are not registered until they restart.

## Limits

- One agterm window: the workspace is looked up in the caller's window.
- Mailboxes do not survive quitting agterm, closing the pane, or `session restart`.
- The Claude hook runs in every Claude Code pane, so any mail sent to such a pane (a script's `msg send`, a `--all` broadcast) starts a turn there; non-chat mail is marked `[agterm mailbox, not a peer chat message]`.
- Codex process inspection uses macOS `sysctl`/`libproc`.

## Tests

`python3 -m unittest test_peer_chat.py`
