# Resolving the revmux profile

Read this only when no profile is pinned (preflight says so) and the owner gave no `--revmux-profile` — and, without `.revmux/`, only once a huge bead is in scope.

Huge beads go through the develop skill's Step 2b (the revmux loop), and every revmux round uses `<revmux-profile>`; `.revmux/` in the main checkout adds the project's own review rules. Resolve it once, now, so no developer has to ask:

1. The owner's flag or words.
2. The project pin (`revmux config` → the `profile` knob whose `source` is not `default`) — `preflight.sh` already printed it when set.
3. A note in `CLAUDE.md` or `.revmux/profile.md`.
4. Else run the revmux skill's `scripts/preflight.sh comprehensive`: take `comprehensive` when it passes, `claude-only`/`codex-only` when only that binary is present.

You are not interactive: decide, and record the pick and its source on the status board. Telegram only when `.revmux/` defines custom profiles and nothing above chooses between them. A developer returning `NEED-PROFILE` means this was skipped — resolve, then re-spawn it with the profile in the prompt.
