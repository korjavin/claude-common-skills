---
name: develop
description: Autonomously work bd (beads) issues end-to-end at a chosen concurrency — claim, spec (with a critical clarify loop), delegate the coding to a worktree-isolated subagent, run a codex review pass, open a PR, drive CI green, hand off for review, and close the bead on merge. Trigger when the user runs "/develop", "/develop N", "/develop N <epic-id>", or asks to "work the backlog", "grind through ready issues", or "develop the epic".
---

# /develop — orchestrate coding subagents over the bd backlog

Run ready bd issues through the full pipeline at concurrency `N`, optionally scoped to one epic. Requires `bd` (beads), `gh`, and `codex` in the project.

**Invocation:** `/develop [N] [epic-id]`
- `N` — how many coding subagents may run at once. Omitted → `1`.
- `epic-id` — optional; if present, only work issues under that epic (its children). Omitted → any ready issue.

**Current toolchain (owner directive, 2026-07-27): code with subagents, review with codex. ralphex is NOT in the loop** — don't invoke `ralphex`, `ralphex-plan`, or author `docs/plans/*` plan files for it. The quality loop it used to provide is now: worktree-isolated coding subagent → `codex review --base master` → fix findings → CI.

## The one hard constraint (read first)

**You (the main agent) are the orchestrator. Subagents cannot ask the user questions** — `AskUserQuestion` only works in the main loop. So this is NOT "spawn N subagents that each do everything." It is:

- **Interactive steps run in the main loop, serialized through the user:** spec-clarification, the "PR ready" ping, and the review handoff. The user can only answer one thing at a time, so serializing these costs nothing.
- **`N` bounds the autonomous, long-running part:** the background coding subagents. That is the only thing worth parallelizing.

You keep a live pool of up to `N` background executors and refill a slot the moment one frees up. Track every in-flight task's state in your narration (a small status table), not in a file.

## Preflight

```bash
which gh && which bd && which codex    # all three required; stop and report if any missing
gh auth status                          # PR + CI steps need this
```

## Step 1 — build the work queue

```bash
bd ready
```

Filter to workable issues:
- **Exclude epics themselves** (`[epic]` rows — type `epic`). Work their children, not the container.
- **If `epic-id` was given**, keep only issues whose parent chain includes it. Use `bd show <epic-id>` to see children, or filter `bd ready` output by the `← <Epic title>` suffix.
- Skip anything already `in_progress` by someone else.

This queue is your backlog. Process it pipelined — do not spec everything up front.

## Step 2 — per-slot pipeline

Repeat until the queue is empty AND no executor is in flight. Whenever a slot is free (fewer than `N` executors active) and the queue is non-empty, fill it:

### 2a. Claim
Pick the next queued issue and claim it immediately so no parallel run takes it:
```bash
bd update <id> --claim
```
Read it fully: `bd show <id>`.

### 2b. Triage — delegate, or fix it yourself?
Before delegating, read the issue and the code it touches and decide:

- **Genuinely trivial / one-touch fix** (a single-line change, a copy tweak, a wrong-condition guard, deleting a dead branch — the *whole* fix fits in your head and touches one place): **fix it directly**, run the relevant test/build, commit on a branch, then go to 2e (codex review) — a delegation round-trip is pure overhead for a change you could type in a minute.
- **Non-trivial work you can spec** (a real feature or multi-file change): **delegate to an executor subagent — 2c onward.** You do NOT need the work pre-researched: the executor does its own context discovery. Don't sit waiting for someone else to hand you a spec.
- **Genuinely can't spec it yet — open-ended debugging with an unknown root cause, or multiple plausible approaches you haven't resolved**: do the root-cause / research first (ordinary investigation, optionally via a read-only `Explore`/`general-purpose` subagent). The moment it resolves into concrete work, it becomes a delegation job.

### 2c. Spec the work (no plan file)
Write the spec **into the executor's prompt**, not into `docs/plans/`. It needs: the bead id + body, the concrete acceptance criteria, the files//subsystems you already know are involved, and any project rule the change brushes against.

**Critical judgment (this is the point of the step):**
- If the issue is **clear and self-contained**, spec it and launch — do NOT interrogate the user for the sake of it.
- If the issue is **genuinely ambiguous** (unclear acceptance criteria, multiple plausible approaches with real trade-offs, missing decisions only the user can make), STOP and ask the user with `AskUserQuestion`, **one question at a time**, and loop until the spec is solid. Never invent requirements to avoid asking, and never ask about things you can decide yourself (naming, test strategy).
- If an issue is underspecified to the point of "I can't responsibly spec this," say so, leave it claimed-but-unstarted or release it (`bd update <id> --status=open`), flag it (`bd human <id>`), and move to the next queue item rather than burning a slot on guesswork.

Commit any `.beads/` churn from the claim so the tree is clean before launching:
```bash
git add .beads/ && git commit -m "chore: bd export"   # if dirty
```

### 2d. Launch the coding executor (background)
Spawn an `Agent` with `isolation: "worktree"`, `run_in_background: true`, `model: "opus"`. **Coding executors run on opus — do not launch them on a smaller model.** (Read-only investigation/verification subagents may use cheaper models.)

The prompt must tell it to:
1. Read `CLAUDE.md` / `AGENTS.md` first and respect the project's rules.
2. Implement the spec — the whole thing, not a partial pass.
3. **Verify locally before reporting done**: the relevant `go build ./...` + `go test ./...`. **Do NOT run frontend tests locally** (`pnpm test` / vitest) — the sandbox Node is wrong and vitest silently skips, so a local pass proves nothing. GitHub Actions runs them on the PR; that is the verification. Type-check only (`pnpm tsc --noEmit` or the project's lint) if you want a fast local signal.
4. Create a branch and **commit** its work. **Do not push, do not open a PR** — the orchestrator does that after review.
5. Report back: **branch name, worktree path, files touched, what it verified, anything it deliberately left out.**

Record the task id + branch. Multiple executors run concurrently in their own worktrees, so they can't collide.

### 2e. Codex review (this replaces ralphex's external-review loop)
Every branch gets a codex pass before it becomes a PR — executor-produced *and* your own direct fixes from 2b. From the branch's worktree:
```bash
codex review --base master
```
Then triage the findings the way ralphex's evaluation prompt did — do not apply them blindly:
- Read the code at each reported location and trace the flow before believing the finding.
- **Valid** → fix it (in the worktree), re-run the touched tests.
- **Invalid** (intentional design, already mitigated, misunderstood context) → say why in your narration and move on.
- Pre-existing lint/test failures the review surfaces get fixed too, not waved off as "not my branch."

Fixes can be a targeted commit by you, or a follow-up message to the executor (`SendMessage`) if they're substantial. Cap at **2 review passes**; if findings keep landing after that, hand off to the user with what's outstanding.

### 2f. Monitor; retry on failure
Watch executors via their task notifications / `TaskOutput`.
- **Reports done + verified** → 2e, then 2g.
- **Died, hung, or came back with the work unfinished** → read its output for the cause. Transient failure (rate limit, crash) → relaunch once with the same spec plus what went wrong. Cap at **1 relaunch**. If it still fails, stop that task, report the failure reason to the user, release the bead (`bd update <id> --status=open`), free the slot.
- **Never fire-and-forget.** An executor that finished but was never collected leaves a finished-but-unshipped branch. If one goes quiet, inspect its worktree yourself (`git -C <worktree> log origin/master..HEAD`, `git -C <worktree> status`) and take over the handoff.

### 2g. Open the PR
Push the branch and open a **draft** PR:
```bash
git -C <worktree> push -u origin <branch>
gh pr create --draft --head <branch> --title "<id>: <title>" \
  --body "Closes bd <id>.\n\n<summary of the change + codex review outcome>"
```

**Don't re-run the full suite a third time.** The executor verified Go locally (2d) and CI re-runs everything on the PR — a full local `go test ./... -race` pass in between is wasted minutes. Cheap project-specific sanity checks the executor's suite may not cover are still worth a glance (migration-number contiguity, the `go list -deps` import-boundary landmine, a new `window.*` global allowlist). **Frontend branches: push and let CI test them** — that's what 2h is for, don't try to reproduce vitest locally.

### 2h. Drive CI green (do NOT ping the user on red)
```bash
gh pr checks <pr> --watch
```
- **Green** → 2i.
- **Red** → diagnose from `gh pr checks` + failing job logs (`gh run view <run> --log-failed`). Fix in the worktree — a targeted commit, or send the executor back in for a broader pass. Re-push, re-watch. Cap at **2 fix passes**. If still red, THEN tell the user, with the concrete failure and what you tried — this is the one case where you surface red CI.

### 2i. Hand off — or self-merge a trivial, necessary fix
Default: mark the PR ready (`gh pr ready <pr>`) and notify the user: "PR #<pr> for bd `<id>` is ready — CI green." If running detached, use `PushNotification`. Then **leave this task in a `review` state and free the slot** — keep filling other slots and monitoring.

**Exception — self-merge without asking** when ALL hold: (a) the change is small and low-risk (a flaky-test fix, an obvious one-line/one-file bug fix, a config/copy correction), (b) it is clearly necessary (unblocks CI, fixes a P0/P1 regression, removes a recurring failure), and (c) CI is fully green. In that case merge it with the project's convention (`gh pr merge <pr> --merge` here — never `--squash`/`--rebase`), then go straight to 2j. Prefer merging such CI-unblockers *first* so later PRs stop needing reruns. Still hand off (don't self-merge) anything feature-sized, architecturally significant, or where you're unsure — those are the user's call.

### 2j. On merge → close the bead
When the user says a PR is merged (or you detect `gh pr view <pr> --json state` = MERGED):
```bash
bd close <id> --reason="Merged in #<pr>"
```
Refill the freed slot from the queue.

## Review handoff (interleaved)

After 2i a task waits on the user. When the user responds about a PR — "merge it", "change X", "close it" — act on that specific PR: merge it using the project's merge convention (check CLAUDE.md/AGENTS.md — some repos require plain merge commits and forbid squash/rebase); or feed requested changes back to that branch (targeted commit, or send the executor back in), re-run 2e–2g, re-hand-off. Other slots keep running while you handle review.

## Status reporting

Each turn, show a compact table of in-flight tasks so the user always knows the pool state:

```
bd id      state        pr    note
abc-xxx    coding       —     executor running, ~20 min in
abc-yyy    review       #431  CI green, awaiting your review
abc-zzz    ci-fixing    #430  1/2 fix passes, lint failing
abc-www    codex        —     2 findings, fixing 1
```

## Gotchas

- **The executor's worktree is temporary.** Collect the branch (push it) before the worktree gets cleaned up. An unpushed branch in a discarded worktree is lost work — push at 2g, promptly.
- **`.beads/*.jsonl` churn re-dirties the tree.** bd rewrites the export on nearly every command, so commit it again right before you need a clean tree.
- **Don't revert uncommitted work you didn't create** — it may be someone's in-progress edit. `git stash push -- <file>` instead, and pop it after.
- **Do bd operations from the main checkout**, never inside an executor worktree (they share the git dir but not the working tree).
- **Frontend tests are CI's job, not yours.** Local vitest under the sandbox Node silently skips and reports a green lie — that has shipped broken frontend tests before. Push the branch and read `gh pr checks` / `gh run view <run> --log-failed` instead. Same for anything else the local env can't run faithfully.
- **`codex review` needs a real base.** Use `--base master` (this project's default branch) — not `--uncommitted`, which reviews the working tree rather than the branch's diff.

## Guardrails

- **Never push to the base branch or force-push without the user's say-so.** Merge only when the user approves a specific PR — the one standing exception is a trivial, necessary, CI-green fix (see 2i). Anything feature-sized or uncertain still waits for the user. Always follow the project's merge convention.
- **Claim before speccing** so parallel runs never collide on the same bead.
- **Respect the project's rules** (read CLAUDE.md / AGENTS.md at the start of a run, and make executors do the same) — call it out if a spec would violate one.
- If `N` executors would exceed sane local resources, cap it and say so.
