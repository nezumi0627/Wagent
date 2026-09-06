---
name: wagent-contributor
description: Safely extend or refactor the Wagent AI runtime
 tags: wagent,provider,runtime,typescript,agent
---
Read `AGENTS.md` and `docs/architecture.md` before editing. First identify the owning layer. Keep runtime provider-neutral, express differences as capabilities, and normalize provider output into `WagentEvent`. Put service-specific authentication, selectors, retries and quirks inside the provider. Preserve OpenAI-compatible behavior when changing server routes. Add or update tests for pure logic and run `bun run check` before finishing.
