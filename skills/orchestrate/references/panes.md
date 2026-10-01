# Pane developers (muse / agy via peer-chat) — owner ruling 2026-09-17

When the owner names a pane agent as the coder ("use muse in the right pane", "use agy in parallel"),
the developers are those agents and **the orchestrator does no git work on their behalf**: no
branch cutting, no worktree creation, no `--import`, no pushing, no PR opening. Your tokens are
too expensive for that. The split is:

- **`/new` before every new job (owner ruling 2026-09-19).** A pane agent keeps the previous
  bead's context; a fresh job on a stale context is how it drags old files, old branches and old
  findings into the new one. So each time you hand a pane agent a *new* bead — the first one and
  every one after a merge — reset it first, and only then send the brief path over `peer-chat.py`.
  **Never send `/new` through `peer-chat.py`** (owner 2026-09-20): peer-chat wraps it as a chat line
  ("Chat from Claude: /new"), the agent merely *answers* "fresh page" and keeps its whole context.
  The reset is the REAL slash command typed into the agent's composer via agterm, then Enter:
  `agtermctl session type --target $AGTERM_SESSION_ID --pane right "/new"` and then
  `agtermctl session type --target $AGTERM_SESSION_ID --pane right $'\r'` (two calls; confirm the
  pane shows the agent's fresh-session banner before briefing — `agtermctl session text --target
  $AGTERM_SESSION_ID --pane right --lines 20`). Note the slash-command popup: the FIRST `\r` selects
  the completion, so read the composer, and send a second `\r` if `/new` is still sitting there.
  **If the status line says `new session failed: /new cannot resume the current session`** (muse
  1.3.0 does this; `/clear` fails the same way), restart the binary instead: type `/exit` + Enter,
  wait for the shell prompt, type the launch command the owner uses (`muse --disable-sandbox` —
  check `ps -o command -p $(pgrep -f muse-bin)` first) + Enter, and wait for the banner. The pane's
  parent is a fish shell, so `/exit` returns to it rather than closing the pane. If the agent still
  has a background task, `/exit` opens a "Local work is still active — 1. Exit anyway / 2. Stay" dialog:
  type `1` + Enter. Do each step as its OWN short call and read the pane between steps — a single
  scripted sequence with fixed sleeps types the next command into the wrong dialog. Send-backs on the
  *same* bead do not get a reset. The same applies to any reused executor: start the job on a
  cleared context.
- **You:** claim the bead (`scripts/bead.sh claim`), write the brief file
  `/private/tmp/peer-chat-brief-<id>.md` (the bead id — the agent runs `bd show <id>` itself — the
  three process rules, the in-flight file exclusion list, the worktree path the agent must create
  for itself, the reply command, `gh pr checks <pr> --watch` for CI (never `sleep`), and the report contract: details to `/private/tmp/report-<id>.md`,
  one-line reply `READY #<pr> <branch> <worktree> findings=<n>` or `BLOCKED <questions>`), send the
  path over `peer-chat.py`, add the pane to the watcher's panes file (below). On READY, spawn a CI
  watcher if CI is still running, then the verifier with `pane: yes` (SKILL.md Step 5) — it runs the
  codex review on the pushed head and checks the mutations, not you. Answer a design question in
  one message; never take over its branch.
- **Them:** `git worktree add ../<repo>-<agent> origin/master` (each agent its own worktree,
  never the main checkout when two run at once), the project's setup step there (e.g. `godot --headless --path . --import`), the
  branch, the code, the assertions + mutations, the full self-check glob on the pushed head, the
  draft PR via `--body-file`, the report file.
- Two pane agents run in parallel only on merge-disjoint beads; put the other's files in each brief's
  exclusion list. Route small, well-bounded beads to agy; behaviour-changing beads to muse.
- Send-backs go as a findings file + one peer-chat line; two failed rounds → park + Telegram.

## Scaling the pane fleet under agterm

When `$AGTERM_SESSION_ID` is set you are inside an agterm workspace and can grow and shrink the fleet yourself — this is how you reach the concurrency `N` with pane agents, not just the panes the owner opened:

- **Start** an agent terminal per free slot: `agtermctl session new --workspace active --cwd <repo> --name <agent>-<id> --no-select --command "<launch cmd>"` (`muse --disable-sandbox`, `agy`, `codex`, … — the same command the owner uses). Wait for its banner (`agtermctl session text --target <sid> --lines 20`), then brief it over `peer-chat.py` exactly as above. Record the session id on the status board and append `<sid> <worktree>` to the watcher's panes file.
- **Codex terminals** serve as review/second-opinion brains, not only coders — spin one up when reviews queue behind a busy one, close it when the queue drains.
- **Stop** a terminal when its bead is merged/parked and no queued bead fits it: `/exit` the agent, then `agtermctl session close --target <sid>`, and delete its line from the panes file. Idle terminals cost attention; don't keep them "just in case". Never close a session you did not start (the owner's own panes) — reset those with `/new` instead.
- Use `agtermctl tree` to re-find your sessions after compaction; name them `<agent>-<bead-id>` so the tree is self-describing.

## Pane babysitting — the watcher, not you

Pane agents (muse especially) stall on permission prompts, dialogs and "shall I continue?" pauses. **Never poll panes yourself** — every `session text` read lands in your context. While any pane agent is active, run the bundled watcher under `Monitor` (`timeout_ms: 1800000`, re-arm on expiry):

```bash
<skill-dir>/scripts/pane-watch.sh /private/tmp/orch-panes-<actor>
```

The panes file holds one line per pane — `<sid>[:right] <worktree>` — and is re-read every minute: append a line when you brief a pane, delete it when the pane stops. No re-arm on fleet changes. The watcher reads each pane's last 20 lines, answers routine permission prompts inside the worktree itself via a haiku triage call (decisions go to `<panes-file>.log`, not to you), and prints a line — your only notification — just when you must act:

- `ESCALATE <sid> <reason>` — destructive or out-of-worktree prompt, or a question it won't answer. Read that one pane (`--lines 20`), then answer, or deny and redirect it in one line.
- `STALE <sid> <N>m` — screen unchanged 10 min with no prompt. Check the worktree (`git -C <wt> log -1 --format=%cr`); finished → expect its report; otherwise urge it with one peer-chat line naming the next concrete step; a second STALE → treat as stuck per `references/failures.md`.
- `GONE <sid>` — session vanished: crashed handling per `references/failures.md`.

Silence means the fleet is moving — don't check "just in case". Tune with `PANE_WATCH_STALE_MIN` / `PANE_WATCH_INTERVAL`. `tail` the log only when an agent did something surprising.
