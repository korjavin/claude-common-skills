---
name: open-pr-review
description: Review open pull requests (especially those authored by coding agents like Jules) — merge clean ones, leave concrete review comments on flawed ones, close obsolete or repeatedly-unfixable ones. Use when the user says things like "review open PRs", "handle open PRs", "review the Jules PRs", "check open PRs on github", or asks to triage a review backlog. The skill encodes workflow for spotting scope mismatches, stale-base issues, obsolete features, and how to give agents 2-3 rounds of iteration before closing.
---

# Open PR Review

This skill reviews open PRs on GitHub and takes action: **merge**, **comment with specific fixes**, or **close** (only after multiple rounds).

It is tuned for PRs authored by coding agents (Jules in particular, but also Antigravity, Claude Code, Cursor, etc.) where scope-mismatch, stale-base duplication of already-merged work, and shallow task completion are common failure modes.

## Core workflow

### 1. Survey all open PRs

```bash
gh pr list --state open --json number,title,author,headRefName,createdAt,updatedAt,mergeable --limit 50
```

Also fetch current master so you can reason about what's already landed:

```bash
git fetch origin master && git log --oneline origin/master -15
```

### 2. Get detail on each PR — in parallel

For every open PR, issue `gh pr view` **concurrently** (single message, multiple tool calls):

```bash
gh pr view <N> --json title,body,files,additions,deletions,statusCheckRollup,mergeable,baseRefOid
```

For small diffs, also fetch `gh pr diff <N>` in the same parallel batch.

### 3. For each PR, evaluate in this order

**a. Is the feature already on master?** If yes → the PR is obsolete. Grep the repo for the key symbols from the PR description/title:

```bash
# Example: PR claims to add SpO2 tracking
git grep -l "SpO2\|spo2" -- internal/ web/
```

If the feature is already implemented independently, close with a link to the merged commit(s).

**b. Does the diff match the description?** Scope mismatch is the most common Jules failure mode. Compare:
- The PR body's claim of what was done
- The actual `files` list and `additions`/`deletions` counts
- The real `gh pr diff` contents

Red flags:
- Body says "Add tests for X" but diff touches unrelated files, or doesn't touch X at all.
- Body describes a 1-line fix but diff has 200+ lines of refactor. This usually means the branch is based on stale master and re-applies work that has since landed.
- Body promises new tests but the new test functions test something entirely different from what the body claims.

**c. Is the base stale?** Compare the PR's `baseRefOid` to current master. If the PR branched from an old commit and touches files that master has since modified, you'll see scope creep in the diff even if the agent only intended a small change. Check `git log` for what landed since the base commit.

**d. Are CI failures real, or pre-existing master issues?**
Don't treat every red check as a PR defect. For lint/test failures:
```bash
gh run view <run-id> --log-failed 2>&1 | grep -E "error|FAIL" | grep -v UNKNOWN | head
```
Then check whether the error already exists on master:
```bash
# Example: lint error on internal/scheduler/foo.go:226
# Check master's version of that file — if it has the same issue, it's not this PR's fault
```
If the failure is pre-existing, ignore it and evaluate the PR on its merits.

**e. Is "MERGEABLE" actually mergeable?**
`gh pr view --json mergeable` reflects git's **textual** merge. It does not catch:
- Duplicate function/type names added in different positions by two PRs (Go, Rust, etc. won't compile).
- Semantic conflicts where two PRs both modify a contract and disagree on direction.
If two open PRs (or one PR + a recently-merged PR) both added `TestFooEmpty` at different positions in the same file, GitHub says MERGEABLE but the resulting code won't compile. Cross-check by reading master's current state of the touched files.

### 4. Take action

**Merge** when:
- Diff matches description, focused scope.
- All *real* CI checks green (ignoring pre-existing master failures).
- No duplicate-definition hazards against master.

```bash
gh pr merge <N> --squash --delete-branch
```

**Comment with concrete fixes** when the PR is fixable. Write comments the way you'd want to receive them:
- State what's working and what's broken.
- Include actual code snippets the agent can copy-paste, not just descriptions.
- Reference specific `file:line` locations.
- Offer clear choices when there are multiple valid approaches (e.g., "Path A: implement end-to-end / Path B: narrow to test-only").

```bash
gh pr comment <N> --body "$(cat <<'EOF'
... concrete, actionable feedback ...
EOF
)"
```

**Close** only after:
- The PR is categorically obsolete (feature already landed independently), OR
- The diff is so misaligned with the task that the agent needs to start over, OR
- **3 rounds of feedback** have not produced a mergeable PR.

```bash
gh pr close <N> --comment "..."
```

## Rules for agent-authored PRs

**Give 2-3 rounds before closing.** Agents can iterate — closing on the first failed attempt wastes their earlier work and forces a full restart. Only close-on-first-try if the PR is categorically obsolete.

**Do not ask agents to rebase.** Jules and most coding agents cannot rebase a branch. If a PR conflicts with master:
- Ask the agent to make a specific code change (e.g., "revert this one line in `foo.go`") rather than "rebase onto master."
- Or resolve the conflict yourself locally and push.
- Or tell the user their merge button would work fine.

**Ask for specific edits, not behavior descriptions.** Instead of "make validation match implementation," write out which lines to change and what to replace them with. Provide copy-paste-ready code blocks.

**Each round, escalate specificity.** Round 1 can be prose-level ("scope mismatch — the refactor doesn't belong here"). Round 2 and 3 should be file-path-and-line-number specific with exact code diffs.

## Common failure patterns and templates

### Pattern: "Branched from stale master, scope exploded"
```
Scope mismatch. The PR description says "<narrow change>" but the diff also
re-applies a <N>+ line <topic> refactor (<list of files>).

That refactor is **already merged** on master (commit `<sha>` — `<func name>`).
The branch was based off `<old sha>`, before that landed, so it re-introduces
a duplicate — which is why the PR is in CONFLICTING state.

The only change matching the description is a <N>-line edit in `<file>`.

**To fix:** open a fresh PR from current master with just the intended change.
(Don't rebase — just re-push the focused change as new commits.)
```

### Pattern: "Validation/implementation mismatch"
```
The <validation function> change doesn't match the implementation — accepting
<new input> will cause a confusing downstream failure, not actually support it.

`<file:line>` (`<function>`) still only handles <old input>. A <new input>
will fail with `<error>`. So after this PR, a user who uploads <new input>
would pass validation but see that error, which is worse UX than the
pre-existing rejection.

To actually support <new input>, the <extraction/parse/handler> path needs
to branch:
- If <old input>: <existing behavior>.
- If <new input>: <describe the new path>.

**Two options:**
1. Extend the scope: add <specific helper>, plumb through <handler>.
2. Narrow the scope: revert the <validation> change, keep only the new tests.
```

### Pattern: "MERGEABLE but duplicate definition"
```
One blocker: `<name>` was just added to master via #<N> (merged at `<sha>`).
This PR's base is `<old sha>` (before that merge), so the diff still shows
`<name>` as a new function — but once merged, `<file>` will have **two**
functions with the same name and won't compile. GitHub reports MERGEABLE
because git resolves it textually, but <compiler> will fail.

**To fix:** remove `<name>` from this PR in `<file>`. Keep the other
additions — those are still new.
```

### Pattern: "Stray unrelated change blocking merge"
```
<Good summary of what's right>. This is nearly merge-ready.

**One remaining blocker:** there's a stray <N>-line change in `<unrelated file>`:

```diff
<the problematic hunk>
```

This is unrelated to <the PR's topic>, and master already <did the same thing>
via #<N> (`<sha>`). That's why GitHub reports CONFLICTING.

**To fix:** <concrete instruction — usually "restore/remove these N lines">.
```

## Parallel-tool-call hygiene

When reviewing multiple PRs, always batch independent operations in a single message:
- All `gh pr view --json` calls for different PRs → parallel.
- `gh pr view` + `gh pr diff` for the same PR → parallel (one reads JSON, other reads text).
- `git fetch` + `gh pr list` → parallel.

Dependent calls must be sequential:
- `gh pr view` (to see status) → `gh run view --log-failed` (only if a check failed).
- `gh pr merge` → `gh pr view --json state` (to confirm).

## Waiting for CI

When a PR has in-progress checks and you expect them to complete:

```bash
until gh pr view <N> --json statusCheckRollup -q '.statusCheckRollup | map(select(.status != "COMPLETED")) | length' | grep -q '^0$'; do sleep 15; done
gh pr view <N> --json statusCheckRollup -q '.statusCheckRollup[] | {name, conclusion}'
```

Avoid polling without a terminating condition. Avoid very short sleeps that burn cache.

## Running non-interactively

When invoking with the Antigravity CLI (`agy`), ensure you provide necessary permissions for the GitHub CLI and git tools. For instance, if running automated reviews, grant command permissions for `gh` and `git`.

## What to report to the user

After reviewing, summarize in 3-5 lines:
- Which PRs merged (with link/number).
- Which PRs got comments (and the one-sentence ask).
- Which PRs closed (and why).

Skip narration of every tool call. The user can see the PR comments and commits — they don't need a play-by-play.
