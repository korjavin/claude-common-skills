---
name: jules-api
description: Interact with Google's Jules AI coding agent via REST API (v1alpha) instead of CLI. Supports creating sessions, listing sources, polling activities, sending follow-up messages, approving plans, auto-creating missing PRs, auto-approving plans, auto-archiving merged sessions, and headless API key auth.
---

# Jules REST API Skill

This skill provides guidance, scripts, and commands for programmatically interacting with **Jules**, Google's autonomous AI coding agent, via its **REST API (`v1alpha`)** instead of the `jules` CLI tool.

## Key Automation Capabilities

1. **Auto-Approve Plans (`approve-plans`)**: Automatically detects sessions waiting for plan approval and calls `POST /v1alpha/sessions/{id}:approvePlan`. Also sets `"requirePlanApproval": false` on new session creations.
2. **Auto-Create PRs (`ensure-prs`)**: Detects sessions where Jules finished coding but did not open a GitHub Pull Request, automatically issuing `gh pr create` for the session branch.
3. **Auto-Archive Merged Sessions (`cleanup`)**: Monitors session Pull Requests on GitHub. When a PR is `MERGED` or `CLOSED`, it automatically archives/deletes the session (`DELETE /v1alpha/sessions/{id}`).

---

## Automated Session Manager Script

The skill includes a zero-dependency Python script at `.agents/skills/jules-api/scripts/jules_manager.py`.

### Quick Usage Commands

```bash
# Run all automated tasks (auto-approve plans + ensure missing PRs + cleanup merged sessions)
python3 .agents/skills/jules-api/scripts/jules_manager.py sweep

# Auto-approve any plans currently stuck waiting for user approval
python3 .agents/skills/jules-api/scripts/jules_manager.py approve-plans

# Detect finished sessions missing PRs and open them via `gh`
python3 .agents/skills/jules-api/scripts/jules_manager.py ensure-prs

# Archive/Delete sessions whose PRs are MERGED or CLOSED on GitHub
python3 .agents/skills/jules-api/scripts/jules_manager.py cleanup

# Create a new session with plan approval bypassed & auto PR mode enabled
python3 .agents/skills/jules-api/scripts/jules_manager.py create "Your task description" --repo owner/repo --branch main
```

---

## API Specification & Authentication

* **Base URL:** `https://jules.googleapis.com/v1alpha`
* **Authentication Header:** `X-Goog-Api-Key: $JULES_API_KEY`
* **API Key Setup:** Export `JULES_API_KEY` in environment.

---

## Quick Reference / REST Commands

### 1. List Available Sources (Connected Repositories)

```bash
curl -s -H "X-Goog-Api-Key: $JULES_API_KEY" \
  https://jules.googleapis.com/v1alpha/sources
```

### 2. Create a Coding Session (With Plan Auto-Approval & Auto-PR)

```bash
curl -s -X POST \
  -H "X-Goog-Api-Key: $JULES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Implement feature X",
    "sourceContext": {
      "source": "sources/github/OWNER/REPO",
      "branch": "main"
    },
    "requirePlanApproval": false,
    "automationMode": "AUTO_CREATE_PR"
  }' \
  https://jules.googleapis.com/v1alpha/sessions
```

### 3. Approve Proposed Execution Plan Manually

```bash
curl -s -X POST \
  -H "X-Goog-Api-Key: $JULES_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' \
  https://jules.googleapis.com/v1alpha/sessions/SESSION_ID:approvePlan
```

### 4. Delete / Archive a Session

```bash
curl -s -X DELETE \
  -H "X-Goog-Api-Key: $JULES_API_KEY" \
  https://jules.googleapis.com/v1alpha/sessions/SESSION_ID
```
