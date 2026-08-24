# Layer: The Discovery Tool (`mcp_help`)

The whole point of `mcp_help` is to be **a router for the agent's attention** — it should reliably move the agent from "I want to do X" to "here is the exact operation id, its schema, and a runnable example, now call `mcp_execute`." It is generated entirely from the registry so it never drifts from reality.

## Input

```jsonc
{
  "type": "object",
  "properties": {
    "topic":        { "type": "string", "description": "Domain filter, e.g. 'health'. Omit or 'all' for full catalog." },
    "operation_id": { "type": "string", "description": "Exact id for a single-entry lookup. Takes precedence over topic." }
  }
}
```

Resolution order in the handler: **exact `operation_id` → topic filter → full catalog.** Always read-only and safe to call before any write — say so in the tool description.

## Output — and the steering fields that make it *direct* usage

```go
type HelpResponse struct {
    Operations   []HelpEntry       `json:"operations"`             // compact, from MarshalForHelp
    Count        int               `json:"count"`
    Topics       []string          `json:"topics,omitempty"`
    Capabilities []TopicCapability `json:"capabilities,omitempty"` // per-topic scan
    PythonUsage  string            `json:"python_usage,omitempty"`
    Note         string            `json:"note,omitempty"`
    NextStep     string            `json:"next_step,omitempty"`   // imperative: what to do now
    NextTools    []string          `json:"next_tools,omitempty"`  // literally ["mcp_execute"]
}

type TopicCapability struct {
    Topic       string `json:"topic"`
    ReadCount   int    `json:"read_count"`
    WriteCount  int    `json:"write_count"`
    Suggestion  string `json:"suggestion"`            // one-line "what you can do here"
    SampleWrite string `json:"sample_write,omitempty"` // an example write op id
}
```

The non-obvious, high-value design choices:

- **`capabilities` lets the agent answer "can I do X here?" without reading every entry.** For each topic it reports read/write counts, a one-line action-oriented suggestion, and a sample write id. An agent hunting "can I create a BP reading?" scans capabilities, sees `health` has writes + `sample_write: "health.bp.create"`, and drills in — instead of paging the whole catalog.
- **`next_step` is imperative**, e.g. *"Pick a topic or look up an operation by id to start building a script."* On a topic hit it becomes a topic-specific suggestion (from `registry.Suggestion(topic)`).
- **`next_tools` literally names the next tool** (`["mcp_execute"]`). This removes ambiguity about what to call next — the single biggest cause of agents flailing.
- **`note`** carries cross-cutting reminders, e.g. *"Pass path_params={\"name\": \"value\"} for routes containing {placeholders}."*

Handler skeleton:

```go
func (s *Server) handleMCPHelp(ctx, req, in HelpInput) (..., HelpResponse, error) {
    topic := strings.ToLower(strings.TrimSpace(in.Topic))
    opID  := strings.ToLower(strings.TrimSpace(in.OperationID))

    if opID != "" {                                   // exact lookup wins
        op := s.reg.Get(opID)
        if op == nil { return ..., notFoundResponse(opID, s.reg.Topics()), nil }
        return ..., HelpResponse{
            Operations: registry.MarshalForHelp([]*registry.Operation{op}),
            Count: 1, NextStep: "Review the details and run it with mcp_execute.",
            NextTools: []string{"mcp_execute"},
        }, nil
    }
    if topic == "" || topic == "all" {                // full catalog
        ops := s.reg.All()
        return ..., HelpResponse{
            Operations: registry.MarshalForHelp(ops), Count: len(ops),
            Topics: s.reg.Topics(), Capabilities: s.buildCapabilities(),
            Note: defaultNote, NextStep: s.nextStepFor(""), NextTools: []string{"mcp_execute"},
        }, nil
    }
    ops := s.reg.ByTopic(topic)                        // topic filter
    if ops == nil { return ..., topicNotFound(topic, s.reg.Topics()), nil }
    return ..., HelpResponse{
        Operations: registry.MarshalForHelp(ops), Count: len(ops),
        Note: fmt.Sprintf("Showing %d op(s) for %q.", len(ops), topic),
        NextStep: s.nextStepFor(topic), NextTools: []string{"mcp_execute"},
    }, nil
}
```

## Example normalization — `MarshalForHelp`

Agents copy examples verbatim, so the examples must always be runnable. `MarshalForHelp` projects each `Operation` into a compact `HelpEntry` and **patches the `Example`** so that it invariably:

1. begins with the helper import (`from medtracker import api, output`) if absent;
2. assigns the call to a variable (`result = api.call(...)` rather than a bare `api.call(...)`);
3. ends by calling `output(result)` if the script never calls `output`.

```go
type HelpEntry struct {
    ID, Topic, Method, Path, Risk, Description, ResponseSummary string
    PathParams   []string        `json:"path_params,omitempty"`
    ParamsSchema json.RawMessage  `json:"params_schema,omitempty"`
    BodySchema   json.RawMessage  `json:"body_schema,omitempty"`
    Example      string           `json:"example"`
}

func MarshalForHelp(ops []*Operation) []HelpEntry {
    out := make([]HelpEntry, 0, len(ops))
    for _, op := range ops {
        out = append(out, HelpEntry{
            ID: op.ID, Topic: op.Topic, Method: op.Method, Path: op.Path,
            Risk: riskString(op.Risk), PathParams: op.PathParams,
            ParamsSchema: op.ParamsSchema, BodySchema: op.BodySchema,
            Description: op.Description, ResponseSummary: op.ResponseSummary,
            Example: normalizeExample(op.Example), // <- the patching above
        })
    }
    return out
}
```

This single normalization step is why an agent can lift any help example into `mcp_execute` and have it run — no "you forgot to call output()" round trips.

## `buildCapabilities`

Scan the registry once, bucket by topic, count read vs write, attach the topic's `Suggestion`, and pick the first write op id as `SampleWrite`. Cheap, and it turns the catalog into a glanceable capability map.
