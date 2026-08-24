# Layer: Executor + Sandbox Runner + Helper Library

This is what makes "batched/complex flow in one call" real: the agent writes a script, `mcp_execute` runs it in a sandboxed subprocess, and the script chains many operations + local logic into one structured result.

## `mcp_execute` input

```jsonc
{
  "type": "object",
  "required": ["script"],
  "properties": {
    "script":          { "type": "string", "description": "Must call output(value) exactly once." },
    "mode":            { "type": "string", "enum": ["read_only","write"], "description": "Default read_only." },
    "intent":          { "type": "string", "description": "Required when mode=write. One-sentence human-readable summary; goes to the audit trail." },
    "timeout_ms":      { "type": "integer", "description": "Wall-clock cap, capped by server config." },
    "max_api_calls":   { "type": "integer", "description": "Call budget, capped by server config." },
    "topic_allowlist": { "type": "array", "items": {"type":"string"}, "description": "Empty = all topics." }
  }
}
```

Two enforced rules worth calling out in the tool *description* (agents respect them when told plainly):
- **`output(value)` exactly once** — zero or multiple calls abort the run. This guarantees a single, unambiguous result.
- **Writes require `mode="write"` AND a non-empty `intent`** — a human-readable sentence ("Archive medication Lisinopril") recorded for audit. This is the consent/audit gate for mutations.

## `mcp_execute` output

```go
type ExecuteResponse struct {
    Status   string   `json:"status"`   // the stable taxonomy from SKILL.md
    Result   any      `json:"result"`   // the output() value when status == "ok"
    Error    string   `json:"error,omitempty"`
    APICalls int      `json:"api_calls"`
    Stdout   string   `json:"stdout"`   // capped (e.g. 1 MB), truncation noted in warnings
    Stderr   string   `json:"stderr"`   // capped (e.g. 256 KB)
    Warnings []string `json:"warnings,omitempty"`
}
```

## Executor responsibilities

```go
type ExecutionRequest struct {
    Script string; Mode string; Intent string
    TimeoutMS int; MaxAPICalls int; TopicAllowlist []string
}
type ExecutionService interface { Execute(ctx, ExecutionRequest) (json.RawMessage, error) }
```

On each `Execute`:
1. Mint a **per-run token**; stand up (or reuse) the loopback proxy bound to this run's `CallOptions` (mode/budget/allowlist).
2. Spawn the sandbox subprocess (`python -m runner.runner`), injecting `PROXY_URL` + `RUN_TOKEN` as env. Feed the script + config (e.g. JSON on stdin).
3. Enforce the wall-clock timeout (kill on overrun → `timeout`).
4. Capture stdout/stderr (capped) and the runner's structured envelope (the single `output()` value + status).
5. Map runner exit/envelope to the stable status, attach `api_calls` from the proxy counter, return `ExecuteResponse`.

Sandbox hardening is deployment-dependent (MVP: in-process/subprocess on the same host but the script doesn't know the bridge URL; target: a dedicated, network-isolated `runner` container that can reach *only* the proxy). The pattern doesn't mandate a specific jail — it mandates that the script's only outbound capability is `proxy → bridge → registered ops`.

## Helper library (what the script imports)

Keep it to two surfaces. In the reference impl it's a Python package `medtracker`:

```python
# medtracker/api.py
def call(operation_id: str, params: dict = None, body=None, path_params: dict = None) -> dict:
    """POST to the loopback proxy with the run token; return parsed response.
    Raises ProxyDenied / BackendError / BackendTransportError / TimeoutError / BackendResponseTruncated."""
    payload = {"operation_id": operation_id, "params": params or {},
               "path_params": path_params or {}, "body": body}
    resp = _post(os.environ["PROXY_URL"], payload,
                 headers={"X-Run-Token": os.environ["RUN_TOKEN"]})
    if resp.ok: return resp.json()
    raise _classify(resp.headers.get("X-MCP-Outcome"), resp)  # map header → typed exception
```

```python
# medtracker/output.py
_recorded = False
def output(value) -> None:
    """Record the single final result. Calling twice raises RuntimeError;
    a non-JSON-serializable value raises SerializationError."""
    global _recorded
    if _recorded: raise RuntimeError("output() called more than once")
    json.dumps(value)            # fail fast if not serializable
    _recorded = True
    _emit(value)                 # runner picks this up as the result
```

Exception hierarchy mirrors the status taxonomy so scripts can `try/except` precisely:

```
MedtrackerError
├── ProxyDenied               # unknown_op / write_blocked / topic_not_allowed / max_calls_exceeded
├── BackendError              # upstream 4xx/5xx
├── BackendTransportError     # couldn't reach the bridge
├── BackendResponseTruncated  # response exceeded the bridge cap
└── TimeoutError              # call timed out
```

## Example scripts — single-call, multi-step flow

A read-only composite ("for each group, count its variants"):

```python
from medtracker import api, output

def main():
    groups = api.call("workouts.groups.list")
    if not groups:
        return {"groups": 0, "summary": "no groups"}
    counts = {}
    for g in groups:                                   # many api.call()s in ONE mcp_execute
        variants = api.call("workouts.variants.list", params={"group_id": g["id"]})
        counts[g["name"]] = len(variants)
    return {"groups": len(groups), "variants_per_group": counts}

output(main())
```

A guarded write (note `mode="write"` + `intent` set in the `mcp_execute` call, not in the script):

```python
from medtracker import api, output
created = api.call("health.bp.create", body={"systolic": 118, "diastolic": 76})
output({"created_id": created["id"]})
```

This is the payoff of goal #2: what would be a dozen tool-call round trips becomes one script with a bounded timeout and call budget, returning a single structured `result`.
