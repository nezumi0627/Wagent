# AGENTS.md — Wagent contributor and AI-agent guide

Wagent is a provider-agnostic AI runtime. Treat provider-specific browser/API behavior as an adapter, never as core runtime logic.

## Read first

1. `docs/architecture.md`
2. `packages/provider-sdk/src/index.ts`
3. `packages/runtime/src/index.ts`
4. the provider package you are changing
5. relevant `skills/*/SKILL.md`

## Non-negotiable architecture rules

- Core/runtime must not import provider implementations.
- Providers emit normalized `WagentEvent` values.
- Feature differences are expressed through capabilities, not provider-name conditionals.
- Tools and Skills are provider-independent.
- Secrets, cookies, browser profiles and access tokens must never be committed or logged.
- New public behavior requires a test or a self-check path.
- Keep browser selectors and service-specific workarounds inside the owning provider.
- Prefer small typed interfaces over implicit object shapes.

## AI-agent workflow

Before editing, identify the owning layer: runtime, provider-sdk, provider, skill, app, or docs. Make the smallest cross-layer surface needed. Run `bun run check` before finishing. If an external UI cannot be exercised in CI, add pure tests around normalization, routing and request construction and document the manual verification step.

## Adding a provider

Create `packages/providers/<id>/src/index.ts`, implement `WagentProvider`, declare capabilities truthfully, normalize streaming into `WagentEvent`, and register it only in an app/bootstrap layer. Do not modify runtime to recognize the new provider by name.

## Adding a Skill

Create `skills/<name>/SKILL.md` with YAML frontmatter containing `name`, `description`, and optional `tags`. Keep instructions deterministic and provider-neutral. Skills are loaded by `@wagent/skills` and may be selected explicitly or by simple tag/description matching.

## Compatibility

`apps/server` exposes Wagent-native endpoints and an OpenAI-compatible `/v1/chat/completions` facade. Preserve response/event compatibility when changing these routes.
