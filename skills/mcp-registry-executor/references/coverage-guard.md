# Optional: The Coverage Guard

The failure mode of this pattern over time is **drift**: someone adds an HTTP route, ships it, and forgets to register a corresponding operation — so the capability silently never reaches MCP. A guard test makes that impossible to merge.

## The invariant

> Every backend route registered on the server MUST be either reachable via a registry operation OR explicitly listed in an exemption table with a stated reason.

## Implementation

1. Enumerate registered routes. Either introspect the mux, or (simpler) maintain the route list the server builds and iterate it in the test.
2. Build the set of `(method, path)` pairs covered by `registry.DefaultOperations()`.
3. Maintain an exemption table for routes that legitimately shouldn't be MCP-reachable — UI shell, auth, bootstrap/sync, web-push subscription, settings/feature toggles, internal MCP plumbing (the bridge itself):

```go
var mcpCoverageExempt = map[string]string{ // "METHOD /path" -> reason
    "GET /healthz":              "liveness probe, not a user capability",
    "POST /auth/login":          "authentication, not a domain operation",
    "POST /internal/mcp/bridge": "MCP plumbing — must not be self-referential",
    // ...
}
```

4. Assert every route is in exactly one of the two sets:

```go
func TestMCPCoverage_AllRoutesEitherRegisteredOrExempt(t *testing.T) {
    covered := coveredRoutes(registry.DefaultOperations())
    for _, rt := range allRegisteredRoutes() {
        key := rt.Method + " " + rt.Path
        if covered[key] { continue }
        if _, ok := mcpCoverageExempt[key]; ok { continue }
        t.Errorf("route %q is neither registered as an MCP operation nor exempt; "+
            "add an Operation in registry/operations_*.go or an entry to mcpCoverageExempt with a reason", key)
    }
}
```

## Why it's worth it

This turns "expose the API to the agent" from an ongoing discipline into a CI invariant. Adding a route forces a decision — *operation or exemption?* — at PR time, which is exactly when the author has the context to answer. It's the mechanism that keeps goal #1 ("effortless to add any existing backend API") honest: effortless to add, but impossible to forget.
