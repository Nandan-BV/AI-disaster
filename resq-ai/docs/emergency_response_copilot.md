# Phase 9: AI Emergency Response Copilot

The copilot answers operator questions about a live incident using data from Phases 3
through 8. It is a grounded assistant, not an autonomous agent: it can read the system and
explain what it finds, and it cannot dispatch, approve, allocate, or change anything.

## What it is for

An operator during an incident has data from eight subsystems and no single view of it. The
questions that actually come up are "how bad is this", "what is the evidence", "what is
nearby", "what is still unknown". Answering each of those means calling several services
and reconciling their output by hand, under time pressure.

The copilot does that reconciliation. It picks the right tools, reads the results, and
writes a summary an operator can act on, with the tool trace attached so the answer can be
checked rather than trusted.

## What it will not do

This is the part that matters most, so it is stated as a property of the code rather than
a rule in a prompt:

- **It cannot dispatch a resource.** No tool sends anything.
- **It cannot approve an allocation.** No tool creates an `Allocation`.
- **It cannot change a resource's status.** No tool writes to the `resources` table.
- **It cannot run SQL.** The model picks from a fixed tool list; the SQL behind each tool is
  a fixed, parameterised statement in `app/ai/tools/`.
- **It cannot invent a number.** Every factual claim must come from a tool result. When the
  data is missing, the copilot says so instead of estimating.

If someone asks it to send two ambulances, it refuses and offers to summarise what is
available for a human to decide. The response carries `refused_action: true` so the UI can
show that a refusal happened rather than rendering it as a normal answer.

`GET /copilot/tools` lists the full toolset with permission classifications. There is no
approve, dispatch, or mutation entry at any setting, which makes the boundary inspectable
instead of a matter of trust.

## Architecture

```
POST /copilot/chat
        │
        ▼
CopilotService.answer()                    app/ai/copilot.py
        │  1. Resolve incident context (explicit id, else session pin)
        │  2. Load bounded conversation history
        │  3. Bind the DB session into a contextvar
        │
        ▼
LLMClient.chat()                           app/ai/llm/  (provider chosen by name)
        │
        │  tool_calls returned
        ▼
tool_registry.invoke()                     app/ai/tool_registry.py
        │  1. Look up the tool. Unknown names are rejected, not guessed.
        │  2. Validate arguments against the tool's Pydantic model.
        │  3. Check the permission.
        │  4. Run the fixed SQL with bind parameters.
        │
        ▼
ToolResult envelope → back to the model, up to 6 iterations
        │
        ▼
Final answer + safe tool trace + uncertainty
```

The loop is capped at `MAX_TOOL_ITERATIONS = 6`. Past that the copilot is asked to answer
with what it has, which bounds latency, cost, and how much damage a confused model can do
in one turn.

## The toolset

Thirteen tools: twelve read-only, one controlled action. Each is registered with a
permission and a source, and the source is what the operator sees in the trace.

| Tool | Source |
|------|--------|
| `get_incident` | Database incident record |
| `get_incident_events` | Incident event records |
| `get_incident_evidence` | Phase 4 evidence investigation |
| `get_incident_investigation` | Phase 4 evidence investigation |
| `get_incident_location` | Incident location (PostGIS) |
| `get_incident_infrastructure` | Infrastructure inventory (PostGIS) |
| `get_incident_risk` | Phase 6 risk assessment |
| `get_incident_impact` | Phase 6 impact assessment |
| `get_nearby_resources` | Phase 7 resource inventory |
| `get_resource` | Phase 7 resource inventory |
| `get_optimization_result` | Phase 8 optimization result |
| `get_optimization_history` | Phase 8 optimization history |
| `run_resource_optimization` | Phase 8 optimization (controlled action) |

### Why the controlled action stays off

`run_resource_optimization` is registered but:

- it is **withheld from the model's tool list** while `COPILOT_ALLOW_CONTROLLED_ACTIONS` is
  false, so the model cannot even name it;
- it **refuses when called anyway**, even if the flag is later enabled.

Phase 8 is not trustworthy yet: the demand, suitability, and optimizer services are
incomplete and the router calls methods that do not exist. That router is deliberately not
registered in `main.py`. Exposing it to an LLM would be the wrong way to find out.

Enabling the flag is a step toward a future, not a feature today.

## The tool result envelope

Every tool returns the same shape, so the model and the trace see a consistent contract:

```json
{
  "available": true,
  "source": "Phase 7 resource inventory",
  "data_timestamp": "2026-09-21T10:30:00",
  "retrieved_at": "2026-09-21T12:00:00",
  "notes": "Stale data: last updated 2 hours ago.",
  "data": { }
}
```

`available: false` means the query succeeded and found nothing, which is different from the
query failing. `data_timestamp` and `retrieved_at` are separate so stale data can be called
out rather than presented as current. Empty results keep the same shape as populated ones,
so the model does not see a missing key and start filling in the gap.

## Safety properties

**Grounding.** The system prompt requires every factual claim to trace to a tool result and
requires an explicit statement when the needed data is missing. Answers are checked in
`tests/test_tool_grounding.py`.

**Untrusted data.** Event text, evidence descriptions, and infrastructure names are
attacker-influenced. They are wrapped as untrusted context in the system prompt, with
instructions inside them to be reported as content rather than followed as commands.
`tests/test_prompt_injection.py` covers this, including attempts to make the copilot
approve an allocation and attempts to make it fabricate a resource count.

**Refusal.** Refusal matches intent to act, not topic vocabulary, and it has to work in both
directions. "How many ambulances can we send to MG Road?" is a capacity question an operator
needs answered; "send two ambulances to MG Road" is an order. The verbs split accordingly:
`dispatch`, `approve`, `delete`, and `bypass` always indicate a request, while `send`,
`reject`, `activate`, and `assign` are only treated as orders when the message is not
phrased as an inquiry. `is_operational_request()` in `app/ai/copilot.py` holds the logic,
and `tests/test_authorization.py` asserts both directions so a future change cannot quietly
break the answerable cases.

**Safe trace.** The response exposes tool name, status, source, and a short note. Raw
payloads, SQL, database credentials, and the system prompt never leave the backend.

**No fake answers.** If the LLM is unreachable the endpoint returns 503 and generates
nothing. There is no template fallback and no silent switch to a weaker model.

**Bounded turn.** Six tool iterations maximum.

## Configuration

```bash
# Any OpenAI-compatible server: vLLM, Ollama, llama.cpp, TGI
COPILOT_PROVIDER=openai_compatible
COPILOT_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
COPILOT_API_BASE_URL=http://localhost:8000/v1
# COPILOT_API_KEY=            # only if the server requires auth

# In-process generation. Development only: it blocks the API event loop.
COPILOT_PROVIDER=transformers
COPILOT_DEVICE=auto
COPILOT_DTYPE=auto

# Deterministic stub used by the test suite.
COPILOT_PROVIDER=mock
```

Generation is deterministic by default (`COPILOT_DO_SAMPLE=false`, temperature 0.1), which
matters for an incident summary: the same data should not produce two different numbers.

`COPILOT_ALLOW_CONTROLLED_ACTIONS` defaults to false. See the section above on why it does
not unlock anything useful yet.

## Running a model

The default provider expects an OpenAI-compatible server, which keeps the LLM out of the
API process:

```bash
# vLLM
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000
```

Ollama works too:

```bash
ollama serve
# then: COPILOT_API_BASE_URL=http://localhost:11434/v1
#       COPILOT_MODEL_NAME=qwen2.5:7b-instruct
```

For a quick look without a model server:

```bash
COPILOT_PROVIDER=mock uvicorn app.main:app --reload
```

The mock provider routes questions to tools by keyword and returns plausible text. It is
useful for wiring and UI work, and is not a substitute for evaluating real answers.

## Frontend

The Copilot tab in the React app. Components live in `frontend/src/components/copilot/`:

- `Copilot.jsx` — chat panel, session state, request handling
- `CopilotMessage.jsx` — one message, its uncertainty list, its tool trace
- `ToolActivity.jsx` — the safe trace rendered as "Checked against the system (n)"
- `IncidentContextPanel.jsx` — session id, incident selector, suggested questions
- `ToolPermissionList.jsx` — the read-only vs controlled action split

The tool trace is shown by default rather than hidden behind a disclosure, because an
operator should be able to see which data an answer rests on without asking for it.

The permissions panel makes the boundary visible in the UI: the controlled-action group
shows its enabled state, and states outright that the copilot has no approve, dispatch, or
mutation tool at any setting.

## API

### `POST /copilot/chat`

```json
{
  "session_id": "demo-session",
  "incident_id": "optional-uuid",
  "message": "Summarise this incident and tell me what is uncertain."
}
```

`incident_id` is optional. Omit it and the copilot resolves context from the conversation:
if the session was pinned to an incident, follow-ups stay on that incident; if not, it says
it needs one. The pin is stored on the conversation, so a follow-up like "what about
resources?" lands on the right incident without the operator restating it.

### `POST /copilot/sessions/{session_id}/chat/stream`

Accepts `message` and optional `incident_id` as JSON and streams `token` events
using Server-Sent Events. A final `done` event contains the same source, tool,
uncertainty, and model metadata as the non-streaming chat response.

```json
{
  "session_id": "demo-session",
  "incident_id": "3202bfb7-00c9-405d-9736-7ceb24a592bf",
  "answer": "Flooding on MG Road ...",
  "sources": ["Database incident record", "Phase 6 risk assessment"],
  "tools_used": [
    {"tool": "get_incident", "status": "success", "source": "Database incident record"},
    {"tool": "get_incident_risk", "status": "success", "source": "Phase 6 risk assessment"}
  ],
  "uncertainty": ["Only one source has confirmed the road closure."],
  "model_name": "Qwen/Qwen2.5-7B-Instruct",
  "refused_action": false,
  "created_at": "2026-09-21T12:00:00"
}
```

### `GET /copilot/conversations/{session_id}`

Stored conversation with every message, including tool call records.

### `DELETE /copilot/conversations/{session_id}`

Deletes chat history only. No incident, resource, or optimization record is touched.

### `GET /copilot/tools`

Provider, model, the controlled-actions flag, and every tool with its permission and source.

## Tests

```bash
python -m pytest tests/test_copilot.py tests/test_copilot_tools.py \
                 tests/test_tool_grounding.py tests/test_prompt_injection.py \
                 tests/test_authorization.py -v
```

| File | Covers |
|------|--------|
| `test_copilot.py` | Operator walkthroughs, conversation context, infrastructure queries, dispatch refusal |
| `test_copilot_tools.py` | Tool registration, validation, envelopes, PostGIS queries |
| `test_tool_grounding.py` | Claims trace to tool results; missing data is stated |
| `test_prompt_injection.py` | Instructions inside event data are treated as content |
| `test_authorization.py` | The human-in-the-loop boundary, including refusal direction |

They run against a fake session and a scripted LLM client, so no model, no GPU, and no
database are needed.

## Limitations

1. **No authentication.** `session_id` is an operator-supplied handle, not an authenticated
   identity. Anyone who can reach the endpoint can read any conversation by guessing or
   reusing a session id. Add auth before this leaves a trusted network.

2. **Phase 8 is not usable.** The copilot can read optimization results if they exist, but
   the optimizer cannot currently produce them.

3. **Quality depends on the model.** The prompts constrain behaviour and the tools constrain
   access, but phrasing quality is bounded by a 7B-class model. A larger model is a
   drop-in change via `COPILOT_MODEL_NAME`.

4. **No streaming.** Answers are returned whole. Long summaries on a slow CPU-hosted model
   will feel slow.

5. **Conversation is per session, not per incident.** An operator handling two incidents
   should use two session ids, or set the incident explicitly on each question.
