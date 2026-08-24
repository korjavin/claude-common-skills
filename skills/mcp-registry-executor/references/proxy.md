# Layer: The Proxy (per-run policy enforcement)

The proxy sits between the sandboxed script's helper lib and the bridge. It runs in the **trusted orchestrator** (the executor process), holds the per-run policy that was decided when `mcp_execute` was invoked, validates each call against the registry, and signs the request so only it can reach the bridge. It **never holds real user credentials** — that's the bridge's job.

## Shape

```go
type Proxy struct {
    reg          *registry.Registry
    bridgeURL    string        // internal bridge endpoint
    hmacSecret   string        // shared with the bridge for request signing
    httpClient   *http.Client
    maxQueryDays int           // clamp for list/range params
    callCount    atomic.Int64  // per-run counter
}

type CallOptions struct {
    Mode           string   // "read_only" | "write"
    MaxAPICalls    int
    TopicAllowlist []string // empty = all topics permitted
}
```

## Per-call validation (in order — cheapest/most-restrictive first)

```go
func (p *Proxy) Call(opID string, params, pathParams map[string]any, body any, opt CallOptions) (CallResult, error) {
    op := p.reg.Get(opID)
    if op == nil { return denied(ErrUnknownOp) }                       // unknown_op

    if opt.Mode == "read_only" && op.Risk == registry.RiskWrite {
        return denied(ErrWriteBlocked)                                 // write_blocked
    }
    if n := p.callCount.Add(1); int(n) > opt.MaxAPICalls {
        return denied(ErrMaxCallsExceeded)                             // max_calls_exceeded
    }
    if len(opt.TopicAllowlist) > 0 && !contains(opt.TopicAllowlist, op.Topic) {
        return denied(ErrTopicNotAllowed)                              // topic_not_allowed
    }
    clampQueryWindow(params, p.maxQueryDays)  // e.g. cap days/limit so a script can't
                                              // exfiltrate a wider window than granular tools allow
    return p.callBridge(op, params, pathParams, body)
}
```

The four `proxy_denied` reasons (`unknown_op`, `write_blocked`, `topic_not_allowed`, `max_calls_exceeded`) are surfaced to the agent so it can self-correct — e.g. retry with `mode="write"` after stating intent.

## Signed bridge call

```go
func (p *Proxy) callBridge(op *registry.Operation, params, pathParams map[string]any, body any) (CallResult, error) {
    reqBody, _ := json.Marshal(BridgeRequest{
        OperationID: op.ID, Params: params, PathParams: pathParams, Body: body,
    })
    sig := hmacSHA256Hex(reqBody, p.hmacSecret)

    httpReq, _ := http.NewRequest("POST", p.bridgeURL, bytes.NewReader(reqBody))
    httpReq.Header.Set("Content-Type", "application/json")
    httpReq.Header.Set("X-Signature", sig)

    resp, err := p.httpClient.Do(httpReq)
    if err != nil { return CallResult{}, backendTransportError(err) }
    defer resp.Body.Close()

    if resp.StatusCode != 200 {                 // bridge always replies 200 on success
        return CallResult{}, backendTransportError(...)  // backend_transport_error
    }
    var env BridgeResponse
    json.NewDecoder(resp.Body).Decode(&env)
    if env.PolicyDenial != "" { return denied(env.PolicyDenial) }     // feature gate, etc.
    if env.HTTPStatus >= 400 { return CallResult{}, backendAppError(env) } // backend_application_error
    return CallResult{Data: env.Body, Truncated: env.Truncated}, nil
}
```

## Outcome classification → the stable status taxonomy

The proxy maps every failure mode to one of the executor's stable statuses (see SKILL.md):
- registry/mode/budget/allowlist rejections → `proxy_denied` (+ a reason);
- `env.PolicyDenial` set (e.g. feature flag off) → `proxy_denied`;
- `env.HTTPStatus >= 400` → `backend_application_error`;
- transport failure reaching the bridge / non-200 from the bridge → `backend_transport_error`.

Keeping classification in the proxy (not the script) means the agent gets a clean, machine-readable verdict regardless of how the underlying API behaves.
