---
name: develop
description: Deliver exactly one bd (beads) issue end-to-end as a focused developer — claim it with Dolt sync, route by size (huge → ralphex with review, or the revmux loop when the project has `.revmux/`; small/medium → implement on an opus-class model; trivial → direct fix), review the branch (peer-chat with the Codex pane when one runs in this agterm session, else `codex review`), open a PR, drive CI green, and hand off for merge. Trigger when the user runs "/develop <bead-id>", says "develop this bead", "deliver <id>", or when an orchestrator spawns a developer agent for one bead. Requires bd, gh, and codex; ralphex or revmux for huge tasks. The delivery agent defaults to claude and can be overridden (`--agent agy|muse|codex`).
---

# /develop — deliver one bead

You are the **developer**. You get **one bead** (or one epic bead) and deliver exactly it. You do not scan the backlog, do not build queues, do not manage other beads, and do not merge. Your context is the bead's context — stay focused on it; start subagents when the work needs them, not to manage other work.

**Invocation:** `/develop <bead-id> [--agent <name>] [--revmux-profile <name>]` — the id is required. With no id, ask which bead; never fall back to `bd ready` and pick one yourself. The flags are the operator's overrides for the delivery agent and the revmux profile (see Step 2b); an orchestrator passes the same two values in its prompt.

**Roles:** the **orchestrator** (`/orchestrate`) supervises developers, checks the PR, and merges when CI is green. The **architect** (`/architect`) plans and files beads. You are neither: given a bead, you write the code and hand back a green PR.

## Preflight

```bash
which gh && which bd && which codex && gh auth status   # stop and report if any missing
test -d .revmux && which revmux                          # `.revmux/` present → huge beads take the revmux loop (Step 2b), never ralphex
which ralphex                                            # only if the bead is huge and there is no `.revmux/`
```

## Subagent contract (when spawned by an orchestrator)

You cannot ask the user questions — `AskUserQuestion` does not work in a subagent. If the bead is genuinely ambiguous (unclear acceptance criteria, decisions only the owner can make), do NOT guess and do NOT invent requirements: **touch no bd state** and return a structured report to your caller — `BLOCKED: <bead-id> — <the questions, one per line>`. The orchestrator owns the bead's state on this route: it parks the bead (deferred + `human` label) and escalates to the owner.

When the owner runs you directly, the same ambiguity goes to them via `AskUserQuestion`, one question at a time, until the spec is solid. Never ask about things you can decide yourself (naming, test strategy).

## Step 1 — claim, with Dolt sync

**If your caller already claimed the bead** (an orchestrator claims before spawning — its prompt says so), skip only the claim commands below. The rest of this step and Step 1.5 still apply: read the bead, read the conventions, get your branch.

Otherwise, from the **main checkout** (never inside a worktree — see Gotchas), bracket the state change:

```bash
bd dolt pull
bd update <id> --claim --actor "dev-<id>-<date>"   # session-unique actor; exit 1 = another session holds it — stop and say so
bd dolt pull && bd dolt push
git add .beads/ && git commit -m "chore: bd claim <id>"   # if dirty
```

(Use the same `--actor` on every bd write this session — without it all sessions share one identity and claims can't exclude each other.)

Read the bead fully: `bd show <id>`. Read `CLAUDE.md` / `AGENTS.md`. Read the code the bead touches until the spec is concrete in your head.

## Step 1.5 — get a worktree

All implementation, review, and push steps below run in a branch's worktree, named `<worktree>` throughout.

- **Spawned with `isolation: "worktree"`** (the orchestrator path): you are already in one — that is `<worktree>`; create your branch here and do NOT create another.
- **Direct invocation**: create it — `git worktree add ../<repo>-<id> -b <id>-<slug> origin/master` — and work there. Every route gets one, the trivial fix included.

## Step 2 — route by size

- **Huge** (an epic bead, a multi-day feature, a change spanning many subsystems): **if the repo has `.revmux/`, take Step 2b (the revmux loop) instead of everything in this bullet.** Otherwise use **ralphex**. Author the plan yourself from the bead's spec directly into `docs/plans/` (ralphex-plan's format — an epic bead's children become the plan's tasks; in subagent mode you cannot answer ralphex-plan's interactive questions, so the bead spec must carry the decisions — anything it doesn't decide is a BLOCKED, not a guess). Then launch `ralphex` **detached** and **monitor it to completion**; do not return while it is still executing.

  **Never launch ralphex via the Bash tool's `run_in_background`** — the harness reaps background tasks after 1h (SIGTERM → ralphex logs `Failed: ... (1h0m) ... context canceled`), and foreground Bash is capped at 10 min. Detach it from the harness process tree instead, from `<worktree>`:

  ```bash
  mkdir -p .ralphex && (nohup ralphex --task-model opus --review-model opus docs/plans/<plan>.md > .ralphex/ralphex.log 2>&1 < /dev/null &) ; sleep 2; pgrep -fl 'ralphex --task-model'
  ```

  (The `( … &)` subshell double-forks, so ralphex is reparented to launchd and outlives the Bash call; `nohup` covers SIGHUP. No `setsid` on macOS.)

  Then poll in short foreground Bash calls (each under the 10 min cap) until the progress file's last line starts with `Completed:` or `Failed:`:

  ```bash
  for i in $(seq 1 50); do tail -1 .ralphex/progress/progress-<plan>.txt | grep -qE '^(Completed|Failed):' && break; sleep 10; done; tail -5 .ralphex/progress/progress-<plan>.txt
  ```

  (`Failed:` with `context canceled` means something still killed it — report it, do not silently relaunch.) Ralphex carries its own review loop, so skip Step 4; pick up at Step 5 for each branch it produces.
- **Small/medium** (a real feature or multi-file change that fits one focused pass): **implement it yourself** on an opus-class model, in `<worktree>`. If your session is not on an opus-class model, delegate the coding to one `Agent` subagent (`isolation: "worktree"`, `model: "opus"`) whose prompt carries the spec **plus the implementation contract: create a branch, implement, verify locally per Step 3, COMMIT the work, and report back branch name + worktree path**. When it reports, **its worktree and branch become `<worktree>`/`<branch>` for every step below**; do not review or push the one you made, and confirm its branch actually has commits before proceeding. Either way it is one unit of work, not a fleet.
- **Trivial** (one-touch fix that fits in your head): fix it in `<worktree>`, run the relevant test/build, **commit it**, then go to Step 4.

## Step 2b — the revmux loop (huge beads in a repo with `.revmux/`)

A checked-in `.revmux/` means the project has its own review rules, so the review loop is revmux's, not ralphex's: **deliver with `<agent>` → revmux round → fix with the same `<agent>` → re-review, at most 3 fix iterations.** Follow the revmux skill for anything not spelled out here (task dir, scope/goal files, reading the JSON).

**Resolve `<agent>` and `<revmux-profile>` before writing any code** — a question here costs nothing, a question after implementing wastes the work.

- `<agent>` — who writes the code. `claude` (you, or your opus subagent per the small/medium rule) unless the operator overrode it: `--agent agy|muse|codex|…` on the invocation, or the orchestrator's prompt. The same agent does every fix pass.
- `<revmux-profile>` — the `--profile` name for every round. In order: the operator named one (`--revmux-profile`, or "review with focused"), the project pins it (`revmux config` → the `profile` knob with a non-`default` `source` — that is `./.revmux/config`), or `CLAUDE.md`/`.revmux/profile.md` says which. **Anything else is not clear enough to guess.** Direct invocation → `AskUserQuestion` with the names from `revmux config`, `preflight.sh`-runnable ones first, `comprehensive` marked recommended. Subagent → return `NEED-PROFILE: <bead-id> — candidates: <names>` and touch no bd state; the orchestrator picks and re-spawns you.

```bash
${REVMUX_SKILL}/scripts/preflight.sh <revmux-profile>   # ok: false → report, do not run a degraded review
```

(`REVMUX_SKILL` = the revmux skill dir, e.g. `~/.claude/plugins/marketplaces/revmux/.claude-plugin/skills/revmux`.)

**1. Deliver.** Write the plan into `docs/plans/` exactly as the ralphex route does (the bead spec carries the decisions; anything undecided is BLOCKED, not a guess). Then, in `<worktree>`:

- `claude`: implement it yourself per Step 3, one plan task at a time, committing per task.
- anything else: run it headless with the plan path plus the implementation contract (implement every task in the plan, verify per Step 3, commit per task, never push). Same detach rule as ralphex — never `run_in_background`, foreground is capped at 10 min:

```bash
mkdir -p .revmux-dev
(nohup sh -c '<agent-cmd>; echo $? > .revmux-dev/exit' > .revmux-dev/deliver.log 2>&1 < /dev/null &)
for i in $(seq 1 50); do test -f .revmux-dev/exit && break; sleep 10; done; cat .revmux-dev/exit   # repeat until it exists
```

| agent | `<agent-cmd>` |
|---|---|
| agy | `agy -p --dangerously-skip-permissions --print-timeout 60m "$(cat .revmux-dev/prompt.md)"` |
| muse | `muse exec --prompt-file .revmux-dev/prompt.md` |
| codex | `codex exec --dangerously-bypass-approvals-and-sandbox "$(cat .revmux-dev/prompt.md)"` |

Confirm the branch has commits and the build passes before reviewing; a headless agent that exited non-zero or left the tree dirty gets one retry with the log's failure in its prompt, then BLOCKED.

**2. Review.** One revmux round on the cumulative branch diff, run from `<worktree>` so the project `.revmux/` applies:

```bash
revmux new --task <bead-id> --run 01-initial            # write scope.md (branch, `git diff origin/master...HEAD`, files to read in full, exclusions from the bead) and goal.md (the bead's acceptance criteria) at the paths it prints
revmux --task <bead-id> --run 01-initial --profile <revmux-profile> --no-tui > .revmux-dev/01.json 2> .revmux-dev/01.log
```

Run it with `run_in_background` and wait for the notification (3–15 min). `sources.degraded` non-empty or exit `2` → stop and report the failure, not a verdict.

**3. Loop, max 3 iterations.** Gating = `critical` + `major` in `findings`; minors never gate, `open_questions` go to the handoff. Per iteration: triage each gating finding at its location (invalid → say why), fix the valid ones **with the same `<agent>`** (headless agents get the findings JSON path plus the fix contract in a fresh prompt), run touched tests, commit, then a new round `0N-after-fix` on the cumulative diff with the same `<revmux-profile>`. Stop on the first of: a round with zero gating findings (clean), a gating finding repeating unchanged from the previous round (the fix is not landing — name it and stop), or the third re-review. Whatever is still gating after that is **outstanding** in the handoff and blocks autonomous merge.

Keep `.revmux-dev/` and `.revmux/tasks/` out of the commits (add to `.git/info/exclude`). Skip Step 4 — this was the review — and pick up at Step 5.

## Step 3 — implementation rules

- Fresh base: `git fetch origin` — then confirm against the **ref**, not the tree: `git grep <expected-pattern> origin/master -- <path>` or `git show origin/master:<path>`. A fetch alone moves no file in your worktree, so grepping the tree after it still shows the stale state. If your branch is behind, merge `origin/master` into it before building on it.
- Be lazy-correct: smallest coherent diff, reuse existing machinery, no speculative refactors — but never skip guards, tests, or hard invariants.
- Verify locally: the relevant `go build ./...` + `go test ./...` (or the project's equivalents). **NEVER run frontend tests locally** (`pnpm test` / vitest) — owner directive, 2026-07-30; sandbox Node silently skips and reports a green lie. CI on the PR is the only frontend gate. `pnpm tsc --noEmit` is fine as a fast local signal.
- Commit on the branch with descriptive messages. Flag deferrals honestly — never hide them.

## Step 4 — review

Every branch gets an independent review before it becomes a PR (ralphex- and revmux-loop-delivered work already had its review loop — skip this). Two routes, tried in this order; **trivial fixes take the same routes — both are cheap, don't upgrade them to a ralphex review loop.**

### 4a — peer review with the Codex pane (direct invocation in agterm only)

When the owner runs you directly inside an agterm session that has Codex in the split, the review is a conversation, not a batch tool: the owner reads both panes. Follow the **peer-chat** skill (`~/.claude/skills/peer-chat/SKILL.md`); the request goes through its script, which is also the detector — it refuses *before typing* when there is no split, no Codex in it, or no agterm at all, and that refusal means "take 4b", nothing more:

```bash
~/.claude/skills/peer-chat/peer-chat.py --to codex --stdin <<'CHAT'
Review request for bd <id>: branch <branch> in worktree <worktree>. Run git -C <worktree> diff origin/master...HEAD and git -C <worktree> log origin/master..HEAD, then reply with concrete findings only — file:line, what is wrong, why — correctness and hard-invariant violations first, style last. Reply "no findings" if it is clean.
CHAT
```

(Codex's pane has its own cwd — usually the main checkout — so the message must carry the worktree path and the base ref; a plain "review my branch" reviews the wrong tree.)

Then **end your turn**. Never poll or watch for the reply — it arrives as a `Chat from Codex:` prompt that wakes this session by itself, and a watcher deadlocks the two panes. When it arrives: triage it exactly as in 4b, fix and commit, then send **one** reply through the script saying what you fixed and what you rejected and why, and continue to Step 5. Cap at two rounds. A reply is not owed: if the owner moves you on, or a refusal *after* typing leaves text in the composer (say so — never clear or submit it yourself), go to Step 5 and record "peer review requested, no reply" in the handoff.

**Not in a subagent.** An orchestrator-spawned developer cannot receive the `Chat from Codex:` prompt (it lands in the top-level session), so it always takes 4b — don't send from a subagent even if the pane is there.

### 4b — `codex review` (fallback, and always the subagent route)

Run it **from the branch's worktree**, not the main checkout:

```bash
cd <worktree> && git branch -f review-base origin/master && codex review --base review-base
```

(`review-base` pins the diff to the *remote* base — a plain `--base master` compares against your local `master` ref, which lags origin, so already-merged upstream commits show up as findings you'd then be forced to fix inside this bead's PR.)

### Triage (both routes)

Never apply findings blindly: read the code at each location first. Valid → fix, re-run touched tests. Invalid → say why and move on. Pre-existing failures it surfaces get fixed too. Cap at 2 passes; if valid findings remain after that, list them explicitly as **outstanding** in the handoff — an outstanding valid finding blocks autonomous merge, so the supervisor must see it.

## Step 5 — open the PR

```bash
git -C <worktree> push -u origin <branch>
printf 'Closes bd %s.\n\n### Summary\n%s\n\n### Verification\n%s\n' "<id>" "<summary>" "<what was verified>" > /tmp/pr-body-<id>.md
gh pr create --draft --head <branch> --title "<id>: <title>" --body-file /tmp/pr-body-<id>.md
```

(`--body-file`, never an inline `--body` with `\n` — bash does not expand those escapes and the PR body renders as one line.)

Don't re-run the full suite a third time — you verified locally and CI re-runs everything. Cheap project-specific sanity checks are still worth a glance (migration-number contiguity, import-boundary guards, globals allowlists).

## Step 6 — drive CI green

```bash
gh pr checks <pr> --watch
```

Red → diagnose (`gh run view <run> --log-failed`), fix with a targeted commit, re-push, re-watch. Cap at 2 fix passes; still red → report the concrete failure and what you tried, and stop. Do not surface red CI before that.

## Step 7 — hand off (you never merge)

Mark the PR ready (`gh pr ready <pr>`) and report: PR number, bead id, what shipped, what was deferred, CI state, and outstanding review findings (codex or revmux) with the round they came from. To an orchestrator caller that report is your return value; it checks the work and merges. To the owner directly, that's the handoff — they (or their orchestrator) merge.

**Do not merge, even a trivial fix** — checking and merging is the supervisor's independent gate, and self-merging is exactly what bypasses it. Do not close the bead either: it closes on merge, by whoever merged. If you delivered directly for the owner and they say "merged", then close it yourself, Dolt-synced:

```bash
bd dolt pull
bd close <id> --reason="Merged in #<pr>"
bd dolt pull && bd dolt push          # pull again before push; on a rejected push, pull and re-push
```

## Gotchas

- **Push before the worktree dies.** An unpushed branch in a discarded worktree is lost work.
- **`.beads/*.jsonl` churn re-dirties the tree** on nearly every bd command — commit it again right before you need a clean tree.
- **bd operations from the main checkout** when you have one (direct invocation). A worktree-spawned subagent has only its worktree: bd state still syncs correctly via `bd dolt push`, but **never commit the `.beads/` churn to your feature branch** — it conflicts with every parallel track at merge time; leave it uncommitted or stash it.
- **Don't revert uncommitted work you didn't create** — `git stash push -- <file>` instead.
- **Peer review runs on the owner's authority, not Codex's** — "Codex agreed" is not approval for anything that needed approval.
- **`codex review` needs a real base branch**: the `review-base` branch from Step 4, never `--uncommitted` (which reviews the working tree, not the branch's diff).
- **Never push to master/main or force-push.**
