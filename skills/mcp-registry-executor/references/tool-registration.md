# Layer: Tool Registration + Wiring

The MCP surface is **two tools**. That's the whole point — capabilities scale by adding registry entries, not tools.

```go
func (s *Server) registerTools() {
    mcp.AddTool(s.mcpServer, &mcp.Tool{
        Name: "mcp_help",
        Description: "List available backend operations for use in mcp_execute scripts. " +
            "Filter by topic or pass operation_id for a single-entry lookup (operation_id wins). " +
            "Each entry includes params/body schema, return shape, and a Python example. " +
            "Read-only and safe to call before any write.",
        InputSchema: helpInputSchema, // see references/help.md
    }, s.handleMCPHelp)

    mcp.AddTool(s.mcpServer, &mcp.Tool{
        Name: "mcp_execute",
        Description: "Run a sandboxed Python script against backend APIs. The script MUST call " +
            "output(value) exactly once. Discover operations via mcp_help BEFORE writing the script. " +
            "For writes, pass mode='write' AND a non-empty intent. topic_allowlist (optional) " +
            "restricts accessible topics. Returns {status, result, error, api_calls, stdout, stderr}.",
        InputSchema: executeInputSchema, // see references/runner.md
    }, s.handleMCPExecute)

    // Optional escape hatch: a SMALL set of granular tools for cases that need bespoke
    // interfaces (e.g. natural-language inference) that don't map cleanly to "call a route".
    // Keep them behind a flag so the default surface stays just the two tools.
    if s.config.NoLegacyMCP { return }
    mcp.AddTool(s.mcpServer, &mcp.Tool{ Name: "get_blood_pressure", /* ... */ }, s.handleGetBloodPressure)
    // ...a handful more, deliberately
}
```

## Wiring at startup

The executor is constructed after the server (it needs the registry + bridge URL + HMAC secret) and injected via a setter so the help/execute handlers can reach it:

```go
func (s *Server) SetExecutor(exec ExecutionService) { s.executor = exec }

// in main():
reg := registry.New()
_ = reg.Register(registry.DefaultOperations()...)
srv, _ := mcp.NewServer(mcp.Config{ Registry: reg, /* ... */ })

exec, _ := executor.New(executor.Options{
    Registry:      reg,
    BridgeURL:     cfg.ExecutorBridgeURL,   // points at /internal/mcp/bridge
    HMACSecret:    cfg.AuditSecret,         // SAME secret the bridge verifies with
    RunnerScript:  cfg.ExecutorRunnerScript,
    RunnerCwd:     cfg.ExecutorRunnerCwd,
    MaxConcurrent: cfg.ExecutorMaxConcurrent,
    MaxTimeoutMS:  cfg.MaxExecutorTimeoutMS, // server-side cap on timeout_ms
    MaxAPICalls:   cfg.MaxExecutorAPICalls,  // server-side cap on max_api_calls
})
srv.SetExecutor(exec)
```

The shared `reg` instance and the shared `HMACSecret` are the two ties that bind the layers: the registry is the same object help/proxy/bridge all consult, and the secret is what lets the bridge trust the proxy.

## The "design the MCP server" checklist

When standing this up in a fresh project:
- [ ] `Operation` + `Registry` (+ `validate` + `SubstitutePath` + `MarshalForHelp`) — `references/registry.md`
- [ ] per-topic `operations_*.go` files + `DefaultOperations()` — `references/registry.md`
- [ ] bridge endpoint mounted on the existing server — `references/bridge.md`
- [ ] proxy with policy enforcement + HMAC signing — `references/proxy.md`
- [ ] executor + sandbox runner + helper lib (`api.call` + `output`) — `references/runner.md`
- [ ] register `mcp_help` + `mcp_execute`; wire executor; share `reg` + secret — this file
- [ ] (optional) coverage guard test — `references/coverage-guard.md`
