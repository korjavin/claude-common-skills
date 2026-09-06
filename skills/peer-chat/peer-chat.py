#!/usr/bin/env python3
"""Send one peer-chat message between Claude Code, Codex, and AGY (Antigravity CLI) in an agterm split."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any

SUBMIT_DELAY = 0.15
# Claude Code can take longer than a single UI frame to redraw a newly typed
# composer while it is processing tool output.  Keep the confirmation safety
# check, but give that redraw time to arrive before withholding Return.
PROBE_TIMEOUT = 3.0
# Claude's background-agent status redraws can briefly move the terminal cursor
# away from the composer even while the composer itself is empty.  Retry these
# transient states quietly; callers only need the eventual delivery result.
RETRY_ATTEMPTS = 41
RETRY_DELAY = 1.0
BOX_LINES = 40
EMPTY_CURSOR_COLUMN = 2
MIN_WRAPPED_PROBE = 40
RULE_RE = re.compile(r"^\s*[─—-]{10,}\s*$")
CODEX_PROMPT_RE = re.compile(r"^\s*›[\s ]*(.*?)\s*$")
CLAUDE_PROMPT_RE = re.compile(r"^\s*❯[\s ]*(.*?)\s*$")
AGY_PROMPT_RE = re.compile(r"^\s*[❯›>⟩][\s ]*(.*?)\s*$")  # ⟩ is Muse Code's prompt
PASTED_RE = re.compile(r"^\[Pasted (?:Content \d+ chars?|text #\d+)\]")


@dataclass(frozen=True)
class Profile:
    pane: str
    agent: str
    command: str
    submit: str


PROFILES = {
    "claude": Profile("left", "claude", "claude", "\n"),
    "codex": Profile("right", "codex", "codex", "\t"),
    "agy": Profile("right", "agy", "agy", "\n"),
    "muse": Profile("right", "muse", "muse", "\n"),
}


class PromptBlocked(RuntimeError):
    """The target is not ready before any text was written."""


def ctl(*args: str) -> str:
    command = os.environ.get("AGTERMCTL", "agtermctl")
    result = subprocess.run(
        [command, *args],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"agtermctl {' '.join(args)} failed: {detail}")
    return result.stdout


def tree() -> Any:
    return json.loads(ctl("tree", "--json"))


def checkout_key(path: str) -> str:
    command = [
        "git", "-C", path, "rev-parse", "--path-format=absolute", "--git-common-dir"
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return os.path.realpath(path)
    if result.returncode == 0 and result.stdout.strip():
        return os.path.realpath(result.stdout.strip())
    return os.path.realpath(path)


def walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if "id" in value and ("foreground" in value or "splitForeground" in value):
            yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def command_name(value: str) -> str:
    name = os.path.basename(value.strip())
    if not name or name in {".", ".."} or any(char.isspace() for char in name):
        raise ValueError("target command must be one executable name or path")
    return name


def target_profile(
    target: str,
    explicit_command: str | None,
    explicit_pane: str | None = None,
) -> Profile:
    profile = PROFILES[target]
    env_name = f"PEER_CHAT_{profile.agent.upper()}_COMMAND"
    configured = explicit_command or os.environ.get(env_name) or profile.command
    pane = explicit_pane or profile.pane
    return replace(profile, command=command_name(configured), pane=pane)


def runs(foreground: Any, command: str) -> bool:
    if not isinstance(foreground, list):
        return False
    pattern = re.compile(rf"(?:^|[/\s]){re.escape(command)}(?:$|[\s-])")
    return any(pattern.search(str(part)) for part in foreground)


def has_target(info: dict[str, Any], profile: Profile) -> bool:
    # A single-pane session (no split) is a valid LEFT target: its foreground IS the agent.
    if not info.get("hasSplit") and profile.pane != "left":
        return False
    field = "foreground" if profile.pane == "left" else "splitForeground"
    return runs(info.get(field), profile.command)


def find_node(sid: str) -> dict[str, Any]:
    needle = sid.lower()
    matches = [
        info
        for info in walk(tree())
        if str(info.get("id", "")).lower().startswith(needle)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"no such session: {sid}")
    raise RuntimeError(f"ambiguous session prefix {sid!r}")


def require_target(sid: str, profile: Profile) -> str:
    info = find_node(sid)
    if not info.get("hasSplit") and profile.pane != "left":
        raise RuntimeError(f"session {sid} has no split")
    if not has_target(info, profile):
        raise RuntimeError(
            f"{profile.agent} target pane is not running {profile.command!r}; "
            "for a wrapper, pass --target-command NAME"
        )
    return str(info["id"])


def resolve_session(explicit: str | None, profile: Profile) -> str:
    sid = explicit or os.environ.get("AGTERM_SESSION_ID")
    if sid:
        return require_target(sid, profile)
    wanted = checkout_key(os.getcwd())
    matches = [
        str(info["id"])
        for info in walk(tree())
        if has_target(info, profile)
        and info.get("cwd")
        and checkout_key(str(info["cwd"])) == wanted
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(
            "this checkout maps to no session running the expected "
            f"{profile.agent}-{profile.pane} layout; "
            "for a wrapper, pass --target-command NAME"
        )
    raise RuntimeError(
        "more than one session shares this checkout; pass --session ID or launch "
        "the agent with shell_environment_policy.set.AGTERM_SESSION_ID"
    )


def detect_sender_label(
    sid: str,
    profile: Profile,
    from_agent: str | None,
    from_label: str | None,
) -> str:
    if from_label:
        label = from_label.strip()
        return label if label.endswith(":") else f"{label}: "
    if from_agent:
        sender_str = "AGY" if from_agent.lower() == "agy" else from_agent.capitalize()
        return f"Chat from {sender_str}: "

    info = find_node(sid)
    opposite_pane = "right" if profile.pane == "left" else "left"
    field = "foreground" if opposite_pane == "left" else "splitForeground"
    fg = info.get(field)
    if runs(fg, "claude"):
        sender_str = "Claude"
    elif runs(fg, "agy"):
        sender_str = "AGY"
    elif runs(fg, "codex"):
        sender_str = "Codex"
    elif runs(fg, "muse"):
        sender_str = "Muse"
    else:
        sender_str = "Claude" if opposite_pane == "left" else "AGY"
    return f"Chat from {sender_str}: "


def pane_text(sid: str, profile: Profile) -> str:
    require_target(sid, profile)
    return ctl(
        "session",
        "text",
        "--pane",
        profile.pane,
        "--target",
        sid,
        "--lines",
        str(BOX_LINES),
    )


def cursor_column(sid: str, profile: Profile) -> int:
    require_target(sid, profile)
    value = ctl(
        "surface",
        "cursor",
        "--target",
        f"surface:{sid}:{profile.pane}",
    ).strip()
    try:
        return int(value)
    except ValueError as err:
        raise RuntimeError(f"surface cursor returned {value!r}") from err


def type_text(sid: str, profile: Profile, text: str) -> None:
    require_target(sid, profile)
    ctl(
        "session",
        "type",
        text,
        "--pane",
        profile.pane,
        "--target",
        sid,
    )


def codex_prompt_text(text: str) -> str | None:
    for line in reversed(text.splitlines()[-BOX_LINES:]):
        if match := CODEX_PROMPT_RE.match(line):
            return match.group(1)
    return None


def claude_prompt_text(text: str) -> str | None:
    lines = text.splitlines()[-BOX_LINES:]
    for index in range(len(lines) - 1, -1, -1):
        match = CLAUDE_PROMPT_RE.match(lines[index])
        if not match:
            continue
        # Current Claude renders queued messages immediately before the lower
        # divider, rather than immediately after the upper divider.  A divider
        # below still distinguishes its composer from ordinary transcript text.
        if any(RULE_RE.match(line) for line in lines[index + 1 :]):
            return match.group(1)
    return None


def agy_prompt_text(text: str) -> str | None:
    lines = text.splitlines()[-BOX_LINES:]
    for line in reversed(lines):
        if match := AGY_PROMPT_RE.match(line):
            return match.group(1)
    return None


def prompt_text(profile: Profile, text: str) -> str | None:
    if profile.agent == "codex":
        return codex_prompt_text(text)
    if profile.agent == "claude":
        return claude_prompt_text(text)
    if profile.agent == "agy":
        return agy_prompt_text(text)
    return agy_prompt_text(text)


def normalize(label: str, message: str) -> str:
    line = " ".join(message.split())
    prefix = label.strip()
    while line.lower().startswith(prefix.lower()):
        line = line[len(prefix) :].lstrip(": ").strip()
    if not line:
        raise ValueError("chat message is empty")
    return label + line


def composer_has_message(profile: Profile, label: str, content: str, typed: str) -> bool:
    if profile.agent in {"claude", "agy", "muse"}:
        # Match a meaningful prefix of this exact send.  Checking only the
        # label could mistake an older chat line for the newly typed composer.
        required = min(len(typed), MIN_WRAPPED_PROBE)
        return (
            typed.startswith(content) and len(content) >= required
        ) or bool(PASTED_RE.match(content))
    required = min(len(typed), MIN_WRAPPED_PROBE)
    literal = typed.startswith(content) and len(content) >= required
    return literal or bool(PASTED_RE.fullmatch(content))


def wait_for_composed(sid: str, profile: Profile, label: str, typed: str) -> str | None:
    deadline = time.monotonic() + PROBE_TIMEOUT
    while True:
        content = prompt_text(profile, pane_text(sid, profile))
        if content and composer_has_message(profile, label, content, typed):
            return content
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.1)


def wait_for_accepted(sid: str, profile: Profile, held: str) -> bool:
    deadline = time.monotonic() + PROBE_TIMEOUT
    while True:
        content = prompt_text(profile, pane_text(sid, profile))
        if content is None or content != held:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def composer_is_empty(sid: str, profile: Profile) -> bool:
    # Claude may leave its terminal cursor on a background-agent status row
    # during a redraw.  Its last prompt line followed by the lower divider is
    # stronger evidence: it distinguishes an empty composer from an occupied
    # one without depending on the transient cursor position.
    if profile.agent == "claude":
        content = claude_prompt_text(pane_text(sid, profile))
        if content is not None:
            return not content.strip()
    return cursor_column(sid, profile) == EMPTY_CURSOR_COLUMN


def send(sid: str, profile: Profile, label: str, message: str) -> int:
    typed = normalize(label, message)
    if not composer_is_empty(sid, profile):
        raise PromptBlocked(f"{profile.agent} is not ready; message was not sent")

    type_text(sid, profile, typed)
    held = wait_for_composed(sid, profile, label, typed)
    if held is None:
        raise RuntimeError(
            "message was typed but not verified in the target composer; submit withheld"
        )

    time.sleep(SUBMIT_DELAY)
    type_text(sid, profile, profile.submit)
    if not wait_for_accepted(sid, profile, held):
        raise RuntimeError("target did not accept the message; it may remain composed")
    return len(message)


def send_with_retry(sid: str, profile: Profile, label: str, message: str) -> int:
    """Quietly retry only a pre-write refusal."""
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return send(sid, profile, label, message)
        except PromptBlocked as err:
            if attempt == RETRY_ATTEMPTS:
                raise PromptBlocked(
                    f"{profile.agent} did not become ready; message was not sent"
                ) from err
            time.sleep(RETRY_DELAY)
    raise AssertionError("unreachable")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Peer chat between agents running in agterm split panes."
    )
    parser.add_argument("--to", choices=PROFILES, required=True, help="target agent (claude, codex, agy, muse)")
    parser.add_argument("--from", choices=["claude", "codex", "agy", "muse"], dest="from_agent", help="sender agent name")
    parser.add_argument("--from-label", help="custom sender label prefix (e.g. 'Chat from AGY: ')")
    parser.add_argument("--pane", choices=["left", "right"], help="override target pane side")
    parser.add_argument("--session")
    parser.add_argument(
        "--target-command",
        type=command_name,
        metavar="NAME",
        help="target agent executable or wrapper name",
    )
    parser.add_argument("--stdin", action="store_true", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        profile = target_profile(args.to, args.target_command, args.pane)
        sid = resolve_session(args.session, profile)
        label = detect_sender_label(sid, profile, args.from_agent, args.from_label)
        sent = send_with_retry(sid, profile, label, sys.stdin.read())
        print(json.dumps({"sent": sent}))
        return 0
    except KeyboardInterrupt:
        print("peer-chat: interrupted", file=sys.stderr)
        return 130
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as err:
        print(f"peer-chat: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
