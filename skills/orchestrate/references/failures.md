# When a track goes wrong

Read this only when a developer is stuck, crashed, returned BLOCKED, or finished without shipping. You never fix code yourself — every outcome below ends in a developer subagent doing the work, or a park.

## Look before you act — two lines, not a diff

```bash
git -C <worktree> status --short | wc -l; git -C <worktree> log --oneline origin/master..HEAD | wc -l
```

Uncommitted or committed work there → **never** spawn an `isolation: "worktree"` agent for this bead: that makes a fresh worktree and the old one's work is abandoned (and deleted on cleanup). Continue it instead.

## Outcomes

- **Normal early phase (0–3 min):** a developer with zero commits is reading files. Do not interrupt.
- **Genuinely stuck** (>5 min, no disk activity, silent): work on disk → `SendMessage` the developer the next concrete step. Empty worktree → restate the first step inline.
- **Crashed / fatal error:** work on disk → spawn a **finisher** (below). Truly empty → relaunch once (Step 3) with adjusted guidance. Second failure → park, free the slot, Telegram.
- **Finished-but-unshipped** (commits, exited without push/PR) → spawn a **finisher**.
- **Merge conflict** at Step 5 → `SendMessage` the developer to merge `origin/master` into its branch, resolve, re-push, drive CI green; developer gone → finisher with that task.
- **Returned BLOCKED:** park with the questions, Telegram, refill the slot.

Never release a failed bead to `open` — `bd ready` serves it straight back and the loop repeats forever. Park it.

## Finisher — a developer over an existing worktree

`Agent`, `model: "opus"`, `run_in_background: true`, **no `isolation`**:

```markdown
You are a developer agent finishing bead `<id>` that another developer started and lost. Work ONLY
in the existing worktree `<worktree>` (branch `<branch>`) — do not create another, do not discard
anything in it. Follow the develop skill in subagent mode from where the work stopped: a dead
developer that reached review is indistinguishable on disk from one that died before it, so run
the review step (Step 4, or one revmux round on profile `<revmux-profile>` when `.revmux/` exists —
`.revmux/tasks/<id>/` shows rounds already run), fix valid findings, then push, open the draft PR
with --body-file, drive CI green, mark it ready. <extra task, e.g. "merge origin/master and resolve
the conflict first">. Do NOT merge or touch bd state. Post details as a PR comment (develop Step 7)
and return one line: READY #<pr> <branch> <worktree> findings=<n> | BLOCKED <questions>.
```

## Parking

Parking survives this session ending — the owner usually answers after it is gone.

```bash
<skill-dir>/scripts/bead.sh park <actor> <id> <step-3-fresh|step-5-merge> <#pr|none> "<why / the questions>"
```

It defers the bead 30 days (hides it from `bd ready`), clears the assignee (any later session can claim it), adds the `human` label (findable via `bd human list`), and records the resume stage in notes. A bead parked *with an open PR awaiting sign-off* is `step-5-merge` — un-parking it into fresh development would re-implement work already sitting green. Applies to any bead you park, claimed or not (e.g. Step 0 beads whose questions went to the owner).

**Un-park** when the owner answers: `bead.sh unpark <actor> <id> "<answer>"`. Notes say `Resume-at: step-5-merge` → verify and merge its named PR now; else it returns to `bd ready`. **Never `bd human respond`** — it closes the bead.

A claimed bead still carrying `human` with unanswered questions (its defer expired; `bead.sh claim` WARNs) → re-park it without a second Telegram.
