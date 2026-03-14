---
name: jules-task-from-plan
description: Commits uncommitted plan files from docs/plans/ to master and creates Jules tasks for each one. Use this skill when the user says things like "create jules task", "send plans to jules", "push plans and create jules tasks", "jules from plan", or whenever there are uncommitted markdown files in docs/plans/ that need to be processed. The skill handles the full loop: commit → push → jules new, one plan file at a time.
---

# Jules Task From Plan

This skill processes uncommitted plan files in `docs/plans/` — committing each to master and creating a Jules coding task for it.

## Workflow

For each uncommitted plan file, in order:

1. **Find uncommitted plans** — run `git status --porcelain docs/plans/` and collect any untracked (`??`) or modified (`M`) `.md` files in that directory.

2. **For each file** (process one at a time, in order):

   a. **Derive a short title** — read the file's H1 heading (first line starting with `# `). Shorten it to ≤6 words if longer, keeping the most meaningful words. For example: "Remove Go Vendoring and Upgrade to Go 1.26.1" → "Remove Go Vendoring Upgrade"

   b. **Commit** — stage only this file and commit:
      ```
      git add <path>
      git commit -m "Add plan for <short title>"
      ```

   c. **Push** — push to master:
      ```
      git push origin master
      ```

   d. **Create Jules task**:
      ```
      jules new "Read and implement <path>"
      ```
      where `<path>` is the relative path, e.g. `docs/plans/2026-03-14-remove-go-vendoring-upgrade-1-26-1.md`

3. **Report** — after each file is processed, tell the user which plan was committed and which Jules task was created. Continue to the next file.

## Notes

- Process files one at a time. Do not batch commits.
- If `git push` fails, stop and report the error — do not continue to the next file.
- If `jules new` fails, report the error but continue to the next file (the commit + push already happened).
- If there are no uncommitted plan files, tell the user: "No uncommitted plan files found in docs/plans/."
