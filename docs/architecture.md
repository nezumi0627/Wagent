# Wagent architecture

## Dependency direction

```text
apps ───────────────┐
                    v
runtime → provider-sdk ← providers
   │                    │
   └────→ skills        └→ service/browser transports
```

`provider-sdk` is the stable seam. Runtime knows only that contract. Providers may depend on provider-sdk, but provider-sdk and runtime never depend on concrete providers.

## Event normalization

Every provider converts its native stream/result into `WagentEvent`: text, reasoning, tool calls, citations, usage, errors and done. Apps therefore do not need provider-specific parsers.

## Capabilities

Providers declare `streaming`, `tools`, `reasoning`, `vision`, `files`, `webSearch`, and `conversations`. Runtime routing uses requested capabilities and configured priorities. A capability must describe real behavior; never claim a feature merely because a model family can theoretically support it.

## Model addressing

Canonical model IDs are `provider/model`. `auto` asks the Router to choose a provider that satisfies requested capabilities. Provider-specific model strings remain opaque after the slash.

## Sessions

A Wagent session stores provider/model selection plus opaque provider state such as a web conversation URL. Runtime treats provider state as unknown JSON. Providers own its meaning.

## Skills

Skills are Markdown instruction bundles with frontmatter. The skills package loads and selects them, while runtime merely appends selected instructions to the system context. This keeps Skills portable across providers.

## Apps

`apps/server` is the network boundary. It exposes Wagent-native generation plus a compatibility layer for OpenAI clients. `apps/cli` is a thin interactive shell over the same runtime.

## Adding capabilities later

Memory, MCP/tool execution, policy hooks, retries, telemetry and multi-agent orchestration should be runtime modules operating on normalized requests/events. Do not embed those concerns into provider implementations.
