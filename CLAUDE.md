# CLAUDE.md — Wagent guidance for Claude

Wagent is a TypeScript/Bun provider-agnostic AI runtime. Read `AGENTS.md` first; it is the canonical repository policy. This file adds Claude-specific navigation and execution guidance without duplicating the architecture rules.

## Start here

1. `AGENTS.md`
2. `docs/architecture.md`
3. `packages/provider-sdk/src/index.ts`
4. `packages/runtime/src/index.ts`
5. the package you are changing
6. `skills/claude/SKILL.md` when working through Claude-oriented agent flows

## Working style

When the request asks for an implementation, prefer making the change and validating it over only proposing code. Keep provider-specific behavior inside provider packages. Do not add provider-name branching to runtime. Preserve normalized `WagentEvent` output at package boundaries.

Use repository tools to inspect source before editing. Keep context narrow: load the owning package and direct dependencies first instead of reading the whole repository.

## Validation

Run:

```bash
bun run check
```

For browser-backed providers, also document any live UI verification that cannot be performed in CI.

## Anthropic compatibility

Wagent exposes `/v1/messages` as an Anthropic Messages-compatible facade and includes `packages/providers/anthropic`. Changes to Claude compatibility should preserve content-block streaming semantics, tool-use blocks, token usage fields, and normalized Wagent events.

Do not put API keys, browser profiles, cookies, generated sessions, or private prompts in commits.
