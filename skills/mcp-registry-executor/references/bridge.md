# Layer: The Bridge (the only thing that can mint an authenticated internal request)

The bridge is an HTTP endpoint mounted on the **existing server**, e.g. `POST /internal/mcp/bridge`. It is the sole component that turns a registry operation into a real, authenticated request against the app's API. The script never learns its URL or the user identity it injects.

## Responsibilities, in order

```go
func (s *Server) handleMCPBridge(w http.ResponseWriter, r *http.Request) {
    // 1. Verify HMAC — only the proxy holds the secret, so this authenticates the caller.
    raw, _ := io.ReadAll(r.Body)
    if !hmacEqual(r.Header.Get("X-Signature"), hmacSHA256Hex(raw, s.mcpAuditSecret)) {
        http.Error(w, "bad signature", http.StatusUnauthorized); return
    }

    // 2. Parse + resolve the operation against the registry (re-validate; never trust the wire).
    var req BridgeRequest
    json.Unmarshal(raw, &req)
    op := s.reg.Get(req.OperationID)
    if op == nil { writeEnvelope(w, BridgeResponse{PolicyDenial: "unknown_op"}); return }

    // 3. Feature gate — same flags the (optional) granular tools and the UI honor.
    if key := featureKeyForOperation(op); key != "" && !s.settings.FeatureEnabled(r.Context(), key) {
        writeEnvelope(w, BridgeResponse{PolicyDenial: "feature_disabled"}); return // HTTP 200 envelope!
    }

    // 4. Substitute {path_params} from the registry-declared allowlist.
    path, err := registry.SubstitutePath(op, toStringMap(req.PathParams))
    if err != nil { writeEnvelope(w, BridgeResponse{PolicyDenial: "bad_path_params"}); return }

    // 5. Build the internal request — method/path from the registry, query from req.Params,
    //    body from req.Body. Crucially: identity is the FIXED server-side allowed user,
    //    NOT anything the caller supplied.
    u, _ := url.Parse(path)
    u.RawQuery = encodeParams(req.Params)
    internal := httptest.NewRequest(op.Method, u.String(), bodyReader(req.Body))
    internal = internal.WithContext(auth.WithUser(internal.Context(), s.mcpAllowedUserID))

    // 6. Route into the app's existing mux, capturing the response under a size cap.
    cw := newCappedResponseWriter(10 << 20) // 10 MB
    s.internalMux.ServeHTTP(cw, internal)

    // 7. Envelope — ALWAYS reply 200; carry upstream status inside so the proxy can classify.
    writeEnvelope(w, BridgeResponse{
        HTTPStatus: cw.status, Body: cw.Body(), Truncated: cw.truncated,
        DurationMS: cw.elapsedMS(),
    })
}
```

## The envelope contract

```go
type BridgeRequest struct {
    OperationID string            `json:"operation_id"`
    Params      map[string]any    `json:"params,omitempty"`
    PathParams  map[string]string `json:"path_params,omitempty"`
    Body        json.RawMessage   `json:"body,omitempty"`
}

type BridgeResponse struct {
    HTTPStatus   int             `json:"http_status"`             // upstream status (may be 4xx/5xx)
    Body         json.RawMessage `json:"body,omitempty"`
    Truncated    bool            `json:"truncated,omitempty"`
    DurationMS   int64           `json:"duration_ms,omitempty"`
    PolicyDenial string          `json:"policy_denial,omitempty"` // set when the bridge itself rejects
}
```

**Why always reply HTTP 200 from the bridge:** the transport layer (proxy ↔ bridge) reaching successfully is a *different fact* from the upstream handler's status. Folding a feature-gate rejection or an upstream 404 into a non-200 bridge response would make the proxy unable to tell "couldn't reach the bridge" from "the bridge worked and the app said 404." Carrying `http_status`/`policy_denial` inside a 200 envelope keeps those orthogonal, which is what powers the clean status taxonomy.

## Auth flow summary

- **Script** knows only the loopback proxy URL + a per-run token (injected as env by the executor). It cannot reach the bridge.
- **Proxy** knows the bridge URL + HMAC secret, but not the user identity.
- **Bridge** verifies HMAC (authenticating the proxy), then injects the *fixed configured user* into the internal request context. Caller-supplied identity is ignored entirely.

Net effect: even a malicious script is boxed into "registered read/write ops, within budget, as one fixed user, behind feature gates."

## Feature gating

`featureKeyForOperation(op)` maps an operation (usually by topic or a small lookup table) to the same settings flag the rest of the app checks (e.g. `"bp"`, `"workout"`, `"food"`). Disabled features return a `PolicyDenial` envelope rather than executing — so MCP can never reach a capability the operator has switched off.
