---
name: claude-recap
description: Recap what the Claude Code session in an agterm session was working on from its transcript. Use when asked to recap the current session, show session recap, or summarize recent agterm Claude work.
allowed-tools: Bash, Read
---

# Claude Recap

Recap what the Claude Code session running in an agterm session was working on by reading and summarizing its transcript in a floating overlay.

## Hotkey in agterm

Press `Ctrl+A` followed by `C` (`ctrl+a>c`) in any agterm session.

## Direct Script Invocation

```bash
~/.local/bin/claude-recap.zsh "$AGTERM_SESSION_ID" "${AGTERM_PANE:-left}"
```

## How it Works

1. Resolves the active agterm session's working directory and transcript path (using `/tmp/claude/panes/<session_id>.<pane>` mapped by the statusline hook).
2. Condenses user prompts and assistant replies into a compact digest.
3. Invokes Claude with `MAX_THINKING_TOKENS=0` and `--safe-mode` to produce a 6-item newest-first summary with status (`done`, `in progress`, `blocked`, or `abandoned`).
4. Displays the summary in an agterm floating session overlay. Pressing any key closes the overlay.
