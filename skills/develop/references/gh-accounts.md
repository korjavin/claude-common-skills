# Multiple gh accounts — unblocking a 403

The owner keeps several GitHub accounts logged in to `gh`; the **active** one may lack access to this repo. Symptom: `git push`/`gh pr …` fails with `403` / `Permission to <owner>/<repo> denied to <account>` / `Resource not accessible`.

Don't `gh auth switch` — that changes global state for every other session on the machine. Pick the right account per command via env instead:

```bash
gh auth status 2>&1 | grep 'account'                 # logged-in accounts
gh repo view --json viewerPermission -q .viewerPermission   # per account: GH_TOKEN=$(gh auth token -u <acct>) …
GH_TOKEN=$(gh auth token -u <acct>) gh pr create …   # gh honours GH_TOKEN
GH_TOKEN=$(gh auth token -u <acct>) git -c credential.helper= -c credential.helper='!gh auth git-credential' push
```

Usually the account matching the repo owner works. Shell state doesn't persist between Bash calls, so prefix every gh/git-remote command; tell spawned subagents which account to use in their prompt. No logged-in account has access → that's a blocker for the owner (Telegram when unattended).
