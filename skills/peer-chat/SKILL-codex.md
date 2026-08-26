---
name: peer-chat
description: 'Hold a back-and-forth conversation with Claude Code or AGY running in the left pane of this agterm session, as peers. Use when the user says "chat with claude", "talk to claude", "work with claude", "chat with agy", "talk to agy", or when a prompt arrives starting with "Chat from Claude:" or "Chat from AGY:". Not for a one-shot task handed off, and not for a read-only second opinion.'
---

# Peer chat, Codex side

Talk with Claude Code or AGY in the left pane. The user reads both panes, so the conversation itself is the result even when code comes out of it.

Everything that touches the pane goes through `peer-chat.py`. Do not drive `agtermctl` directly: the script carries the checks that keep a message out of a dialog, and a raw `session type` bypasses all of them.

## Preconditions

The session needs both panes running, with Claude Code or AGY on the left, started by the user. This skill never starts an agent and never opens a pane. If the left pane is not running the expected agent, say so and stop.

## Sending

To send to Claude:
```bash
peer-chat.py --to claude --stdin <<'CHAT'
the message goes here, as one paragraph
CHAT
```

To send to AGY:
```bash
peer-chat.py --to agy --stdin <<'CHAT'
the message goes here, as one paragraph
CHAT
```

Pass the message on stdin through a quoted heredoc, never as an argument. The script collapses all whitespace to single spaces before typing, because typing a newline submits the fragment before it, so write for one paragraph.

Before typing, the script confirms the target pane really is running the expected agent.

Do not write `Chat from Codex:` yourself. The script adds the label automatically.

**Send last:** The script submits to Claude or AGY with Return, which injects into whatever turn that session is running and interrupts the work in progress. So finish what you are doing, then send.

## Receiving

Replies arrive as ordinary prompts opening with `Chat from Claude: ` or `Chat from AGY: `. Read it as the next line of a conversation, not as a task the user is asking for, and answer it here.

## Never wait for a reply

Do not poll or watch for one. Replying wakes this session up on its own.

## What you may not do

The only thing you may put into that pane is text in a prompt the script has confirmed is empty.
Never answer anything on the user's behalf.

## Manners

Plain language, short sentences. Quote what the peer agent actually said before answering it. Disagree when there is a disagreement. Verify claims made about code before repeating them to the user.
