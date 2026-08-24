# Layer: The Operation Registry

The registry is the **single source of truth** consumed by all three other layers (`mcp_help` describes from it, the proxy validates against it, the bridge routes from it). Get this right and the rest falls into place.

## The `Operation` record

One declarative struct per backend route. Everything `mcp_help` shows and everything the proxy/bridge enforce comes from these fields — there is no other place to look.

```go
type Risk int
const ( RiskRead Risk = iota; RiskWrite )

type Operation struct {
    ID              string          // unique, dot-separated: "topic.resource.action" e.g. "health.bp.list"
    Topic           string          // high-level domain used for grouping + allowlists: "health", "food", ...
    Method          string          // "GET" | "POST" | "PUT" | "DELETE"
    Path            string          // backend path; may contain {placeholders}, e.g. "/api/workout/groups/{name}"
    PathParams      []string        // allowlisted placeholder names that appear in Path
    Risk            Risk            // RiskRead or RiskWrite — drives read_only-mode blocking + audit
    ParamsSchema    json.RawMessage // JSON Schema for the query string (nil if none)
    BodySchema      json.RawMessage // JSON Schema for the request body (nil if none)
    ResponseSummary string          // one line describing the response shape
    Description     string          // what it does — shown verbatim in help
    Example         string          // runnable script snippet using api.call(...) + output(...)
}
```

Design notes:
- **`ID` is the agent-facing handle.** It's what `mcp_help` lists and what `api.call("...")` takes. Keep it stable and predictable (`topic.resource.action`).
- **`Risk`** is the entire read/write security boundary. `read_only` executions block any `RiskWrite` op at the proxy before it ever reaches the bridge.
- **Schemas are raw JSON Schema**, surfaced as-is to the agent. They don't have to be enforced server-side (the underlying handler already validates) — their job is to *teach the agent the shape*.
- **`Example` is mandatory in spirit** — it's the highest-leverage field for correct usage. Help normalizes it (see `help.md`) but write it as a real snippet.

## The `Registry` type

```go
type Registry struct {
    operations  map[string]*Operation   // by ID
    byTopic     map[string][]*Operation // grouped, preserves registration order
    topicOrder  []string                // topics in first-seen order
    suggestions map[string]string       // optional goal-oriented hint per topic
}

func New() *Registry { ... }

// Register validates each op and indexes it. Returns error on the FIRST invalid op.
func (r *Registry) Register(ops ...*Operation) error

func (r *Registry) Get(id string) *Operation
func (r *Registry) ByTopic(topic string) []*Operation
func (r *Registry) All() []*Operation
func (r *Registry) Topics() []string
func (r *Registry) Suggestion(topic string) string
```

### Validation at registration (fail fast at startup)

`Register` runs `validate(op)` on each entry and refuses to start if any is malformed. Enforce:
- `ID`, `Topic`, `Method`, `Path` non-empty;
- `Method` ∈ a known set;
- `Risk` ∈ {RiskRead, RiskWrite};
- every `{placeholder}` substring in `Path` has a matching entry in `PathParams`, and vice-versa;
- each `PathParams` name matches `^[a-zA-Z_][a-zA-Z0-9_]*$` (so substitution can't be tricked);
- `ID` is unique.

This means a typo in a path or a missing path-param is a **boot-time error**, not a runtime surprise.

### Path substitution helper

Shared by the bridge. Given `Path` + a `map[string]string` of supplied path params, produce the resolved path and error if any declared placeholder is missing or any extra param is supplied:

```go
func SubstitutePath(op *Operation, pathParams map[string]string) (string, error)
```

## Per-topic file layout — the "effortless to add" property

Operations live in **per-topic files**, each exporting one factory:

```
internal/mcp/registry/
  registry.go              // Operation, Registry, validate, SubstitutePath, MarshalForHelp
  operations_health.go     // func HealthOperations() []*Operation
  operations_food.go       // func FoodOperations() []*Operation
  operations_workouts.go   // func WorkoutOperations() []*Operation
  operations_medications.go
```

```go
// operations_health.go
func HealthOperations() []*Operation {
    return []*Operation{
        {
            ID:     "health.bp.list",
            Topic:  "health",
            Method: "GET",
            Path:   "/api/bp",
            Risk:   RiskRead,
            ParamsSchema: json.RawMessage(`{
                "type":"object",
                "properties":{
                    "days":{"type":"integer","description":"Look-back window, default 30"},
                    "limit":{"type":"integer","description":"Max rows"}
                }}`),
            ResponseSummary: "JSON array of BP readings, newest first.",
            Description:     "List blood pressure readings, newest first.",
            Example: `result = api.call("health.bp.list", params={"days": 7})
output(result)`,
        },
        {
            ID:     "health.bp.create",
            Topic:  "health",
            Method: "POST",
            Path:   "/api/bp",
            Risk:   RiskWrite,
            BodySchema: json.RawMessage(`{
                "type":"object",
                "required":["systolic","diastolic"],
                "properties":{
                    "systolic":{"type":"integer"},
                    "diastolic":{"type":"integer"},
                    "pulse":{"type":"integer"}
                }}`),
            Description: "Record a blood pressure reading.",
            Example: `result = api.call("health.bp.create", body={"systolic":120,"diastolic":80})
output(result)`,
        },
    }
}
```

The registry is assembled once:

```go
func DefaultOperations() []*Operation {
    var ops []*Operation
    ops = append(ops, HealthOperations()...)
    ops = append(ops, FoodOperations()...)
    ops = append(ops, WorkoutOperations()...)
    ops = append(ops, MedicationOperations()...)
    return ops
}
```

And mounted at server construction:

```go
reg := registry.New()
if err := reg.Register(registry.DefaultOperations()...); err != nil {
    return nil, fmt.Errorf("operation registry: %w", err)
}
```

**To expose a new backend route as an MCP capability:** append one `Operation{}` literal to the relevant topic file (or add a new topic file + one line in `DefaultOperations`). No new tool, no new handler, no new schema plumbing. That single property is the payoff of the whole pattern.
