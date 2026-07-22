#!/usr/bin/env python3
"""
jules_manager.py - Utility script to manage Jules AI coding sessions via REST API & gh CLI.

Capabilities:
  1. Auto-Approve Plans: Detects sessions waiting for plan approval and invokes :approvePlan.
  2. Auto-Ensure PRs: Detects finished sessions lacking a PR link and creates a GitHub PR using `gh`.
  3. Auto-Cleanup: Detects sessions whose GitHub PRs are MERGED or CLOSED and deletes/archives them.
  4. Sweep: Executes approve-plans, ensure-prs, and cleanup in a single automated pass.
  5. Create: Starts a session with auto-PR mode enabled and plan approval bypassed.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import subprocess

BASE_URL = "https://jules.googleapis.com/v1alpha"

def get_api_key():
    key = os.environ.get("JULES_API_KEY")
    key_path = os.path.expanduser("~/.keys/jules.key")
    if not key and os.path.exists(key_path):
        try:
            with open(key_path, "r") as f:
                key = f.read().strip()
        except Exception:
            pass
    if not key:
        print("[ERROR] JULES_API_KEY environment variable is not set and ~/.keys/jules.key could not be read.", file=sys.stderr)
        sys.exit(1)
    return key

def api_request(endpoint, method="GET", data=None):
    api_key = get_api_key()
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[HTTP {e.code}] Error on {method} {endpoint}: {err_body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[ERROR] Request failed on {method} {endpoint}: {e}", file=sys.stderr)
        return None

def list_sessions():
    res = api_request("/sessions")
    if not res:
        return []
    return res.get("sessions", [])

def approve_plan(session_id):
    endpoint = f"/sessions/{session_id}:approvePlan"
    print(f"[*] Approving plan for session {session_id}...")
    res = api_request(endpoint, method="POST", data={})
    if res is not None:
        print(f"[SUCCESS] Approved plan for session {session_id}.")
        return True
    return False

def auto_approve_all():
    sessions = list_sessions()
    count = 0
    for sess in sessions:
        sess_id = sess.get("name", "").split("/")[-1]
        state = sess.get("state", "")
        # Check if awaiting approval via state or activities
        if state in ("AWAITING_PLAN_APPROVAL", "AWAITING_USER_INPUT", "PLANNING_COMPLETE"):
            if approve_plan(sess_id):
                count += 1
            continue

        # Check activities for pending approval
        activities_res = api_request(f"/sessions/{sess_id}/activities")
        if activities_res and "activities" in activities_res:
            for act in activities_res["activities"]:
                if act.get("type") == "PLAN_GENERATED" and not act.get("approved", False):
                    if approve_plan(sess_id):
                        count += 1
                    break
    print(f"[*] Auto-approved {count} pending plan(s).")

def get_gh_pr_status(pr_url_or_number):
    try:
        cmd = ["gh", "pr", "view", str(pr_url_or_number), "--json", "state,mergedAt,headRefName"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
        return json.loads(out)
    except Exception:
        return None

def create_gh_pr(branch_name, title, body="Automated PR from Jules session"):
    try:
        cmd = [
            "gh", "pr", "create",
            "--head", branch_name,
            "--title", title,
            "--body", body
        ]
        out = subprocess.check_output(cmd).decode("utf-8").strip()
        print(f"[SUCCESS] Created PR: {out}")
        return out
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to create PR for branch {branch_name}: {e}", file=sys.stderr)
        return None

def ensure_prs():
    sessions = list_sessions()
    created_count = 0
    for sess in sessions:
        sess_id = sess.get("name", "").split("/")[-1]
        state = sess.get("state", "")
        prompt = sess.get("prompt", f"Jules Task {sess_id}")
        
        pr_info = sess.get("pullRequest", {}) or sess.get("pr", {})
        pr_url = pr_info.get("url") if isinstance(pr_info, dict) else None

        # If PR already exists, skip
        if pr_url:
            continue

        # Check branch name from session context/outputs
        src_ctx = sess.get("sourceContext", {})
        branch_name = src_ctx.get("branch") if isinstance(src_ctx, dict) else None
        if not branch_name:
            branch_name = sess.get("branch")
        
        outputs = sess.get("outputs")
        if isinstance(outputs, dict) and outputs.get("branch"):
            branch_name = outputs.get("branch")
        elif isinstance(outputs, list):
            for item in outputs:
                if isinstance(item, dict) and item.get("branch"):
                    branch_name = item.get("branch")
                    break

        if not branch_name or branch_name in ("main", "master"):
            branch_name = f"jules/{sess_id}"

        # Check if local or remote branch exists
        try:
            subprocess.run(["git", "fetch", "origin"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            branch_check = subprocess.run(
                ["git", "rev-parse", "--verify", f"origin/{branch_name}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if branch_check.returncode == 0 or state in ("COMPLETED", "FINISHED", "AWAITING_REVIEW"):
                print(f"[*] Found finished session {sess_id} without PR on branch {branch_name}. Creating PR...")
                pr_url_created = create_gh_pr(branch_name, f"Jules: {prompt}", f"Automated PR for Jules session {sess_id}")
                if pr_url_created:
                    created_count += 1
        except Exception as e:
            print(f"[WARN] Error inspecting git branch for session {sess_id}: {e}")
            
    print(f"[*] Created {created_count} missing PR(s).")

def archive_session(session_id):
    print(f"[*] Archiving/Deleting completed session {session_id}...")
    # HTTP DELETE to remove/archive session
    res = api_request(f"/sessions/{session_id}", method="DELETE")
    # Also try archive endpoint if available
    api_request(f"/sessions/{session_id}:archive", method="POST", data={})
    print(f"[SUCCESS] Session {session_id} archived.")

def cleanup_merged_sessions():
    sessions = list_sessions()
    archived_count = 0
    for sess in sessions:
        sess_id = sess.get("name", "").split("/")[-1]
        pr_info = sess.get("pullRequest", {}) or sess.get("pr", {})
        pr_url = pr_info.get("url") if isinstance(pr_info, dict) else None
        pr_number = pr_info.get("number") if isinstance(pr_info, dict) else None
        
        target = pr_url or pr_number
        if not target:
            continue

        gh_status = get_gh_pr_status(target)
        if gh_status:
            pr_state = gh_status.get("state", "").upper()
            if pr_state in ("MERGED", "CLOSED"):
                print(f"[*] Session {sess_id} PR is {pr_state}. Cleaning up session...")
                archive_session(sess_id)
                archived_count += 1

    print(f"[*] Cleaned up {archived_count} session(s).")

def create_session(prompt, source_repo, branch="main"):
    data = {
        "prompt": prompt,
        "sourceContext": {
            "source": f"sources/github/{source_repo}",
            "branch": branch
        },
        "requirePlanApproval": False,
        "automationMode": "AUTO_CREATE_PR"
    }
    print(f"[*] Creating new session for {source_repo}...")
    res = api_request("/sessions", method="POST", data=data)
    if res:
        sess_id = res.get("name", "").split("/")[-1]
        print(f"[SUCCESS] Created session: {sess_id}")
        return res
    return None

def main():
    parser = argparse.ArgumentParser(description="Jules API Session Manager")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="List all active sessions")
    subparsers.add_parser("approve-plans", help="Auto-approve all pending plans")
    subparsers.add_parser("ensure-prs", help="Detect finished tasks missing PRs and create them")
    subparsers.add_parser("cleanup", help="Archive/Delete sessions with merged or closed PRs")
    subparsers.add_parser("sweep", help="Run approve-plans, ensure-prs, and cleanup in one pass")

    create_p = subparsers.add_parser("create", help="Create a new auto-approving session")
    create_p.add_argument("prompt", help="Prompt description")
    create_p.add_argument("--repo", required=True, help="GitHub repo, e.g. owner/repo")
    create_p.add_argument("--branch", default="main", help="Base branch (default: main)")

    args = parser.parse_args()

    if args.command == "list":
        sessions = list_sessions()
        print(json.dumps(sessions, indent=2))
    elif args.command == "approve-plans":
        auto_approve_all()
    elif args.command == "ensure-prs":
        ensure_prs()
    elif args.command == "cleanup":
        cleanup_merged_sessions()
    elif args.command == "sweep":
        print("=== 1. Auto-Approving Pending Plans ===")
        auto_approve_all()
        print("\n=== 2. Ensuring Pull Requests ===")
        ensure_prs()
        print("\n=== 3. Cleaning Up Merged/Closed Sessions ===")
        cleanup_merged_sessions()
    elif args.command == "create":
        create_session(args.prompt, args.repo, args.branch)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
