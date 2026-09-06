# Wagent

**A lightweight, provider-agnostic AI runtime for Web providers, APIs, local models, Tools and Skills.**

Wagent started as a ChatGPT Web bridge. v0.2 rebuilds the project in TypeScript and turns that single-provider bridge into a composable runtime: Agent/Runtime → Router → Provider → Transport.

## Why this architecture

- one normalized event protocol for Web UI automation, official APIs and OpenAI-compatible servers
- capability-driven routing instead of provider-name conditionals
- provider SDK for third-party adapters
- built-in Skills loader (`SKILL.md`)
- OpenAI-compatible server facade
- session-aware Web providers
- AI-friendly repository instructions in `AGENTS.md`
- Bun + TypeScript, with a deliberately small dependency surface

## Included providers

- `deepseek-web` — integrated from `deepseek-web-harness`; browser-profile login, conversation continuation, DeepThink/search/files where the UI exposes them
- `openai-compatible` — OpenAI/OpenRouter/Ollama-compatible HTTP endpoints through one adapter

The provider SDK is intentionally generic so ChatGPT Web, Anthropic, Gemini Web and future providers can be added without changing runtime internals.

## Quick start

```bash
bun install
bun run start
```

Server defaults to `127.0.0.1:8765`.

OpenAI-compatible provider example:

```bash
export WAGENT_OPENAI_BASE_URL=https://api.openai.com/v1
export WAGENT_OPENAI_API_KEY=...
export WAGENT_DEFAULT_PROVIDER=openai-compatible
bun run start
```

DeepSeek Web login uses a persistent local browser profile. Start the CLI and send a DeepSeek request; if login is required, sign in to the launched browser. Browser/profile data stays under `~/.wagent` (or `WAGENT_HOME`).

```bash
bun run cli
```

## Native API

```bash
curl -X POST http://127.0.0.1:8765/v1/generate \
  -H 'content-type: application/json' \
  -d '{"model":"deepseek-web/default","messages":[{"role":"user","content":"hello"}]}'
```

OpenAI-compatible clients can use:

```text
POST /v1/chat/completions
GET  /v1/models
GET  /health
GET  /v1/providers
```

Model IDs use `provider/model`, for example `deepseek-web/default` or `openai-compatible/gpt-5`.

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
    deepseek-web/        DeepSeek Web adapter
    openai-compatible/   OpenAI/OpenRouter/Ollama style APIs
skills/                  user/agent-readable skills
docs/                    architecture and extension docs
```

See `AGENTS.md` before asking an AI coding agent to modify Wagent. See `docs/architecture.md` for dependency rules and extension points.

## Security and service terms

Web providers automate third-party web interfaces and are unofficial. UI selectors can break without warning. Users are responsible for complying with applicable service terms, laws and account policies. Never commit `.wagent/`, browser profiles, cookies or API keys.

## License

MIT. The DeepSeek Web provider incorporates and refactors code from the MIT-licensed `nezumi0627/deepseek-web-harness`; attribution is retained in `THIRD_PARTY_NOTICES.md`.
