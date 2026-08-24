---
name: mcp-registry-executor
description: Design or extend an MCP server using the operation-registry + code-executor pattern — a two-tool surface (a "help"/discovery tool plus a sandboxed code "execute" tool) backed by a declarative registry of backend HTTP operations, an in-process proxy that enforces policy, and a signed bridge that routes into the app's existing HTTP API. Use when building an MCP server where you want (1) effortless exposure of existing backend routes as MCP capabilities, (2) batched/multi-step flows in a single tool call via agent-authored scripts, and (3) a discovery tool that reliably directs the agent to correct usage. Trigger on requests like "add MCP to this project", "expose my API to Claude via MCP", "I want one mcp_execute tool instead of dozens of granular tools", "design the MCP server", or porting this pattern from one project to another.
---

# MCP Registry + Executor Pattern

A blueprint for building an MCP server as **two tools instead of dozens**:

- a **discovery tool** (`mcp_help`) that returns a catalog of allowed backend operations with schemas + runnable examples, and
- a **sandboxed code-executor tool** (`mcp_execute`) that runs an agent-authored script which calls those operations through a policy-enforcing proxy.

This replaces the usual "one MCP tool per endpoint" approach. New backend capabilities become **one declarative registry entry**, not a new tool registration. Multi-step workflows happen **inside one script** (loops, joins, filters) instead of N round-trips of tool-call chatter.

## When to use this

Reach for this pattern when:
- The backend already has a coherent HTTP API and you want it reachable from an agent without writing/maintaining a hand-tool per route.
- Agents need to do **composite work** — "find all X, for each fetch Y, summarize" — which is painful and token-heavy as separate tool calls.
- You want a **single permission/audit choke point** (read vs write, call budgets, topic allowlists, feature gates) rather than scattering policy across many tools.

Don't use it (or use it *alongside* a couple of granular tools) when a capability needs bespoke natural-language inference or a uniquely shaped interface that doesn't map cleanly to "call this route with these params."

## The three design goals (and how each is met)

1. **Effortless to add any existing backend API.** Capabilities are declared as plain `Operation` records (id, topic, method, path, risk, param/body JSON Schema, description, example). Adding one = append a struct to a per-topic list + include that list in the registry factory. The bridge already knows how to route any registered operation into the existing API; no new tool, no new handler. → see `references/registry.md`.

2. **Batched/complex flow in one call.** `mcp_execute` runs a real script (Python in the reference impl). The script imports a tiny helper (`api.call(operation_id, params=…, body=…, path_params=…)` + `output(value)`), chains many calls, does local logic, and returns one structured result. One tool call, one bounded budget. → see `references/runner.md`.

3. **`mcp_help` actually directs usage.** Help is generated *from the registry*, not hand-written. Each entry carries a working example. The response also carries **agent-steering fields**: `capabilities` (per-topic read/write counts + a one-line "what you can do here" suggestion + a sample write id), `next_step`, and `next_tools` (literally telling the agent to call `mcp_execute` next). Examples are normalized so they always `import`, assign `result =`, and call `output(result)`. → see `references/help.md`.

## The five layers

```
  Agent
   │  ① mcp_help(topic?) ──────────► catalog (schemas + examples + next_step)
   │  ② mcp_execute(script, mode) ─► run script
   ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ EXECUTOR   spawn sandboxed subprocess; inject proxy URL +      │
 │            per-run token as env; enforce timeout; capture      │
 │            stdout/stderr + the single output() value           │
 └───────────────┬──────────────────────────────────────────────┘
                 │ script calls api.call("topic.res.action", …)
                 ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ HELPER LIB (in sandbox)  POST to loopback proxy w/ run-token   │
 └───────────────┬──────────────────────────────────────────────┘
                 ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ PROXY (in-process / trusted)  look up op in REGISTRY; enforce  │
 │   read_only-blocks-writes, max_api_calls, topic_allowlist,     │
 │   query-window clamps; sign body w/ HMAC; POST to bridge       │
 └───────────────┬──────────────────────────────────────────────┘
                 ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ BRIDGE (internal HTTP endpoint)  verify HMAC; resolve op in    │
 │   REGISTRY; check feature gate; substitute {path_params};      │
 │   build internal request with the FIXED server-side user;      │
 │   route into the app's existing API mux; cap + envelope resp   │
 └───────────────┬──────────────────────────────────────────────┘
                 ▼
        existing backend handlers (unchanged business logic)
```

The **registry** is the single source of truth consulted by `mcp_help` (to describe), the **proxy** (to validate the call), and the **bridge** (to route it). That shared dependency is what makes the pattern coherent: declaring an operation once lights it up in all three places.

## Why the proxy *and* the bridge (two checkpoints)

They enforce different things and trust different inputs:
- **Proxy** runs in the trusted orchestrator and enforces *per-run* policy it was handed for this execution: mode (read vs write), call budget, topic allowlist, query clamps. It never sees real user credentials.
- **Bridge** is the only thing that can mint an authenticated internal request. It verifies the HMAC (so only the proxy can reach it), re-validates the op against the registry, applies *server-owned* policy (feature flags, the fixed allowed user identity), and routes into the real API. The script never learns the bridge URL or the user identity.

This split means a compromised/buggy script can at most make allowed read calls within budget; it cannot forge identity, skip feature gates, or reach arbitrary routes.

## Applying the pattern to a project — step by step

1. **Define the `Operation` record + a `Registry`** that indexes by id and by topic, validates entries at registration (id/topic/method/path non-empty; risk ∈ {read,write}; every `{placeholder}` in the path is declared in `path_params`), and offers `Get`, `ByTopic`, `All`, `Topics`, `Suggestion`. → `references/registry.md`.
2. **Declare operations in per-topic files** (`operations_<topic>.go`), one factory each, concatenated by a `DefaultOperations()`. This is the file you edit forever after. → `references/registry.md`.
3. **Build the bridge endpoint** in the existing server: HMAC-verify → resolve op → feature-gate → substitute path → internal request as the fixed user → route into the app mux → cap + envelope the response (always 200; carry upstream status/policy-denial inside the envelope so the proxy can classify). → `references/bridge.md`.
4. **Build the proxy**: validate against registry, enforce mode/budget/allowlist/clamps, HMAC-sign, POST to bridge, normalize outcomes into stable status codes. → `references/proxy.md`.
5. **Build the executor + sandbox runner + helper lib**: spawn subprocess with proxy URL + run token in env, feed the script, enforce wall-clock timeout, require exactly one `output()`, return `{status, result, error, api_calls, stdout, stderr, warnings}`. → `references/runner.md`.
6. **Register exactly two tools** (`mcp_help`, `mcp_execute`) and wire the executor in at startup. Optionally keep a *small* set of granular tools behind a flag for cases that need bespoke interfaces. → `references/help.md` + `references/tool-registration.md`.
7. **Add a coverage guard test** (optional but recommended): every registered backend route must be either reachable via a registry operation or explicitly listed in an exemption table with a reason. This keeps the MCP surface from silently drifting behind the API. → `references/coverage-guard.md`.

## Stable status taxonomy (design it up front)

`mcp_execute` should return a small, stable set of statuses so the agent can reason about failures without parsing prose:

| status | meaning |
|---|---|
| `ok` | script ran; `result` holds the `output()` value |
| `script_error` | unhandled exception in the script |
| `timeout` | wall-clock budget exceeded |
| `sandbox_startup_failure` | couldn't spawn the runner |
| `proxy_denied` | policy rejection: write_blocked / unknown_op / topic_not_allowed / max_calls_exceeded |
| `backend_application_error` | upstream handler returned 4xx/5xx |
| `backend_transport_error` | proxy/executor couldn't reach the bridge, or bridge failed |

Mirror these as a small exception hierarchy in the helper lib so scripts can `try/except` precisely.

## Reference files

- `references/registry.md` — the `Operation` record, registry indexing/validation, per-topic file layout, how "add an API" stays one-line.
- `references/help.md` — generating help from the registry, example normalization, the `capabilities`/`next_step`/`next_tools` steering fields.
- `references/proxy.md` — policy enforcement, HMAC signing, outcome classification.
- `references/bridge.md` — HMAC verify, feature gating, path substitution, fixed-user internal routing, response envelope.
- `references/runner.md` — executor, sandbox contract, helper lib (`api.call` + `output`), example scripts, the `output()`-exactly-once rule.
- `references/tool-registration.md` — the two tool registrations + executor wiring + the optional granular-tool escape hatch.
- `references/coverage-guard.md` — the "every route registered-or-exempt" test.

The reference implementation this pattern was extracted from lives in `internal/mcp/{registry,proxy,executor}`, `internal/server/mcp_bridge.go`, and `python/` of the medicationtrackerbot project; cite those when you need a concrete, working example.
