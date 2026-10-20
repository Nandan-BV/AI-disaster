# Local Ollama setup

RESQ-AI's default Copilot provider uses Ollama's OpenAI-compatible API. The
backend must be able to reach Ollama at `OLLAMA_BASE_URL` (default
`http://localhost:11434`); the client appends `/v1` when
`COPILOT_API_BASE_URL` is unset.

## Start Ollama

Install Ollama, then run these commands in a terminal:

```powershell
ollama serve
ollama pull qwen2.5-coder:7b
```

Keep the Ollama server running while RESQ-AI is using the model. The sample
`.env.example` selects:

```dotenv
COPILOT_PROVIDER=openai_compatible
COPILOT_MODEL_NAME=qwen2.5-coder:7b
OLLAMA_BASE_URL=http://localhost:11434
COPILOT_API_BASE_URL=http://localhost:11434/v1
```

If the backend runs in a container, `localhost` refers to that container, not
the host machine. Set the URL to a host address reachable from the backend
container. Do not expose an unauthenticated model server to an untrusted
network.

## Important tool-calling limitation

The configured model was tested with the local `/v1/chat/completions` endpoint
and produced text successfully. It did not reliably emit OpenAI-compatible
`tool_calls` when RESQ-AI supplied tools. RESQ-AI therefore refuses to present
an answer as grounded when no supporting data was fetched. A healthy model
endpoint or successful text completion does not establish that Copilot tool
use works.

Before demonstrating real Copilot workflows, select a serving model that
supports the required tool-calling format and test a query against a known
incident. Verify that the response includes the expected tool trace and
database sources. Until that is verified, `COPILOT_PROVIDER=mock` is suitable
only for an offline smoke test, not for demonstrating real incident-grounded
answers.

Event image/video analysis and event-embedding/clustering use separate models
and configuration. Starting Ollama for Copilot does not make those model
weights available.
