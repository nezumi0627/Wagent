# Wagent

**A lightweight, provider-agnostic AI runtime for Web providers, APIs, local models, Tools and Skills.**

Wagent started as a ChatGPT Web bridge. v0.2 rebuilds the project in TypeScript and turns the original single-provider bridge into a composable runtime: Agent/Runtime → Router → Provider → Transport.

## Included providers

- `chatgpt-web` — the original Wagent use case, rebuilt as a provider with persistent profiles, conversations, files and optional Web search
- `deepseek-web` — integrated/refactored from `deepseek-web-harness`, including conversation continuation, DeepThink/search/files where the live UI exposes them
- `openai-compatible` — OpenAI/OpenRouter/Ollama-compatible HTTP endpoints through one adapter

Every provider emits the same normalized event protocol and declares capabilities, so runtime code never needs `if provider === ...` branches.

## Why this architecture

- one event model for browser automation, APIs and local endpoints
- capability-driven routing and `provider/model` addressing
- publishable provider SDK/packages
- first-class `SKILL.md` loading and selection
- Wagent-native plus OpenAI-compatible HTTP APIs, including SSE streaming when the provider can stream
- persistent runtime sessions with opaque provider state
- root `AGENTS.md` plus AI-specific architecture/authoring docs
- Bun + strict TypeScript with a deliberately small dependency surface

## Quick start

```bash
git clone https://github.com/nezumi0627/Wagent.git
cd Wagent
bun install
bun run start
```

Server defaults to `127.0.0.1:8765`. Interactive mode:

```bash
bun run cli
```

Use a Web provider:

```json
{
  "model": "chatgpt-web/default",
  "messages": [{ "role": "user", "content": "Hello" }],
  "metadata": { "profile": "default", "webSearch": false }
}
```

The browser uses persistent data under `~/.wagent/providers/...`. If login is required, sign in in the launched Chrome/Edge profile and retry. Set `WAGENT_BROWSER` to override the browser executable.

Use an OpenAI-compatible endpoint:

```bash
export WAGENT_OPENAI_BASE_URL=https://api.openai.com/v1
export WAGENT_OPENAI_API_KEY=...
export WAGENT_DEFAULT_PROVIDER=openai-compatible
bun run start
```

## HTTP surface

```text
GET  /health
GET  /v1/status
GET  /v1/providers
GET  /v1/models
GET  /v1/skills
POST /v1/generate
POST /v1/chat                 # legacy Wagent-compatible shape
POST /v1/chat/completions     # OpenAI-compatible shape
```

Native example:

```bash
curl -X POST http://127.0.0.1:8765/v1/generate \
  -H 'content-type: application/json' \
  -d '{"model":"deepseek-web/default","messages":[{"role":"user","content":"hello"}]}'
```

Model IDs use `provider/model`. `auto` lets the Router select a provider that satisfies required capabilities.

## Repository map

```text
apps/
  cli/                  interactive client
  server/               Hono HTTP/OpenAI-compatible facade
packages/
  provider-sdk/         provider contract, events and capability model
  runtime/              routing, execution and sessions
  skills/               SKILL.md parser/loader
  providers/
    chatgpt-web/         ChatGPT Web adapter
    deepseek-web/        DeepSeek Web adapter
    openai-compatible/   OpenAI/OpenRouter/Ollama style APIs
skills/                  human/agent-readable Skills
docs/                    architecture, provider and AI-agent docs
```

For AI coding tools, start with `AGENTS.md`; it intentionally tells an agent what to read without dumping the whole repository into context. Provider authoring is documented in `docs/provider-authoring.md` and AI-agent usage in `docs/ai-agents.md`.

## Security and service terms

Web providers automate unofficial third-party web interfaces and may break when those UIs change. Users are responsible for complying with applicable service terms, laws and account policies. Never commit `.wagent/`, browser profiles, cookies, tokens or API keys.

## License

MIT. The DeepSeek Web provider incorporates/refactors MIT-licensed work from `nezumi0627/deepseek-web-harness`; attribution is retained in `THIRD_PARTY_NOTICES.md`.
