# Multi-Agent Peer Chat (`peer-chat`)

Let coding agents (**Claude Code**, **AGY / Antigravity**, and **Codex**) hold direct, peer-to-peer conversations with each other inside `agterm` split panes.

## What it does

Two coding agents run side by side in an `agterm` split session, one per pane, and talk to each other directly:
* **Left Pane (`pane: left`):** Claude Code (or primary agent)
* **Right Pane (`pane: right`):** AGY (Antigravity CLI) or Codex

Each agent sends messages into the other's composer via `peer-chat.py`, and replies arrive in its own pane as an ordinary prompt starting with `Chat from <Sender>: `. You can watch both halves of the exchange without relaying anything by hand.

Supported target configurations:
- **Claude Code (left) <—> AGY (right)**
- **Claude Code (left) <—> Codex (right)**
- **AGY <—> Codex**

## Requirements

- **agterm** 0.24.0 or later (supports `surface cursor`).
- **Python 3.10+**
- Installed agents: `claude`, `agy`, or `codex`.

## Setup

1. Copy `peer-chat.py` to your `PATH` (e.g. `~/.local/bin/peer-chat.py`) and make it executable (`chmod +x`).
2. Copy the agent skill files to their respective skill directories:
   - For **AGY**: copy `SKILL-agy.md` to `~/.agents/skills/peer-chat/SKILL.md`
   - For **Claude Code**: copy `SKILL-claude.md` to `~/.claude/skills/peer-chat/SKILL.md`
   - For **Codex**: copy `SKILL-codex.md` to `~/.codex/skills/peer-chat/SKILL.md`
3. Launch your split session in `agterm`:
   - Left pane: `claude`
   - Right pane: `agy` (or `codex`)

## Usage

Ask either agent to talk to the other:
- In Claude: *"work with agy on the retry bug"* or *"chat with agy about this"*
- In AGY: *"work with claude on the refactor"* or *"chat with claude"*
- In Codex: *"chat with claude"* or *"chat with agy"*

Under the hood, agents invoke `peer-chat.py`:

```sh
# AGY or Codex sending to Claude Code (left pane):
peer-chat.py --to claude --stdin <<'MSG'
your message as one paragraph
MSG

# Claude Code sending to AGY (right pane):
peer-chat.py --to agy --stdin <<'MSG'
your message as one paragraph
MSG

# Claude Code sending to Codex (right pane):
peer-chat.py --to codex --stdin <<'MSG'
your message as one paragraph
MSG
```

### Script Flags
- `--to {claude, codex, agy}`: Target agent to send the message to.
- `--from {claude, codex, agy}` (optional): Explicitly set the sender name. If omitted, `peer-chat.py` automatically detects the sender process running in the opposite pane.
- `--from-label "Label"` (optional): Custom prefix label for the message.
- `--pane {left, right}` (optional): Override the target pane.
- `--target-command NAME` (optional): Name of wrapper executable if the target agent runs via a wrapper script.

## Safety & Verification Checks

1. **Process Matching:** Queries `agtermctl tree --json` to verify the target pane is running the expected executable.
2. **Caret Pre-Check:** Checks `agtermctl surface cursor` to ensure column 2 (empty prompt) before typing. Refuses to type if the prompt is occupied, in a dialog, or has a draft.
3. **Post-Typing Verification:** Ensures text reached the composer before sending the submit key (`\n` for Claude/AGY, `\t` for Codex).
