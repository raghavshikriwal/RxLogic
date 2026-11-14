# Task 14 Changelog — Hosted LLM Parser Provider

Adds a pluggable LLM backend so the "Describe in words" path works on hosts
that cannot run Ollama (e.g. Render). Default behaviour is unchanged.

## Added
- `services/llm_parser.py`: `LLMBackend` protocol with `OllamaBackend` and `AnthropicBackend` (plain HTTPS via `requests`; no new dependency), `build_backend()` and `LLM_API_NAMES`.
- Provider chosen at call time via `LLM_PROVIDER` (`ollama` default | `anthropic`).
- `tests/test_llm_providers.py` (38 cases), `tests/conftest.py` (isolates LLM env vars so a local `.env` cannot change which backend a test exercises).

## Changed
- `LLMParser(backend=None)` replaces `LLMParser(base_url, model)`; schema validation is unchanged and still applies to every backend.
- `routes/api.py`: the `ExternalAPIError` handler returns `llm_api_error` for any name in `LLM_API_NAMES` (previously only `"Ollama"`). No other change.
- `.env.example` and `live_llm_smoke_test.py` are provider-aware.

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `LLM_PROVIDER` | `ollama` or `anthropic` | `ollama` |
| `ANTHROPIC_API_KEY` | Required for `anthropic`; store as a host secret | — |
| `ANTHROPIC_MODEL` | Optional model override | `claude-haiku-5-5` |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Unchanged | `http://localhost:11434` / `phi3:mini` |

Render: set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` under Environment, then redeploy.

## Behaviour
- Missing key or unknown provider -> `ValueError` -> HTTP 503 `configuration_error`.
- Network, HTTP or response-shape failure -> `ExternalAPIError("Anthropic", status)` -> HTTP 502 `llm_api_error`; the UI falls back to structured input.
- Logs record the failure class and status only, never user text, the API key or response bodies.

## Limits (read before relying on this)
- **Privacy:** with `anthropic`, user-typed text is sent to a third party. The project's "synthetic data only" rule still applies.
- Not exercised against the live Anthropic API in development; run `python live_llm_smoke_test.py` with a real key and confirm the default model name is valid for your account (override with `ANTHROPIC_MODEL`).
- One attempt per request: no retry or backoff on 429/5xx.
- The two Flask error-mapping tests need the full dependency set and were not run in the authoring sandbox; run `pytest -q` locally.
- Sends `temperature: 0`; if a future model rejects that parameter the API returns 400 and the UI shows the fallback message.

## README rows to add (Configuration table)
`LLM_PROVIDER` — `ollama` (default) or `anthropic`; `ANTHROPIC_API_KEY` — hosted-provider credential; `ANTHROPIC_MODEL` — optional model override.
